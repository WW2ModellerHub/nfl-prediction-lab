"""Pregame team-v-team matchup intelligence built from completed nflverse PBP.

Only completed games are inserted; at a shared kickoff, all forecasts are made
before inserting any results. Stats on this page are team-level proxies:
'sack or QB-hit rate' is NOT a tracked pressure rate, and pass EPA allowed
is NOT man/zone coverage charting. Neither an injury nor a player-level
matchup conclusion can be inferred from these inputs.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import timedelta

FIELDS = ('game_id','posteam','defteam','pass','rush','epa','sack','qb_hit','yards_gained')
STATS = ('pass_count','pass_epa','pass_hit','pass_explosive','rush_count','rush_epa',
         'allowed_pass_count','allowed_pass_epa','pass_hits_forced','explosive_allowed',
         'allowed_rush_count','allowed_rush_epa')

def value(item,default=0.0):
    try: return float(item) if item is not None and str(item).strip() != '' else default
    except (TypeError,ValueError): return default

def aggregate_plays(rows):
    """Compact game/team stats from any iterable of nflverse PBP row mappings."""
    by_game=defaultdict(lambda:defaultdict(lambda:defaultdict(float)))
    for r in rows:
        gid=r.get('game_id'); attack=r.get('posteam'); defend=r.get('defteam')
        if not gid or not attack or not defend or attack==defend:continue
        pa=value(r.get('pass'))==1; ru=value(r.get('rush'))==1
        epa=value(r.get('epa'),None)
        if epa is None or not (pa or ru):continue
        a=by_game[gid][attack];d=by_game[gid][defend]
        if pa:
            a['pass_count']+=1;a['pass_epa']+=epa
            d['allowed_pass_count']+=1;d['allowed_pass_epa']+=epa
            hit=max(value(r.get('sack')),value(r.get('qb_hit')))>0
            if hit:a['pass_hit']+=1;d['pass_hits_forced']+=1
            if value(r.get('yards_gained'))>=20:
                a['pass_explosive']+=1;d['explosive_allowed']+=1
        elif ru:
            a['rush_count']+=1;a['rush_epa']+=epa
            d['allowed_rush_count']+=1;d['allowed_rush_epa']+=epa
    return {gid:{team:dict(stats) for team,stats in teams.items()} for gid,teams in by_game.items()}

def load_nflverse_pbp(seasons,timeout=100,qb_sink=None):
    """Read upstream season parquet assets; requires polars only during online refresh.

    Returns records, loaded years, errors. Missing years are explicit. Never uses
    partial play files from failed requests. No access token required.
    """
    import io,urllib.request
    import polars as pl
    merged={};loaded=[];errors=[]
    for season in seasons:
        url=f'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet'
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'NFLPredictionLab/1.3 (personal research)'})
            with urllib.request.urlopen(request,timeout=timeout) as response:
                raw=response.read()
            if len(raw)<100000:raise ValueError('File unexpectedly small')
            # Read only recognised columns, and let QB stats use the SAME PBP
            # download rather than imposing another large network request.
            available=set(pl.read_parquet_schema(io.BytesIO(raw)))
            qb_columns=('passer_player_id','passer_player_name','pass_attempt',
                        'complete_pass','passing_yards','cpoe','interception')
            selected=list(FIELDS)+[c for c in qb_columns if c in available]
            frame=pl.read_parquet(io.BytesIO(raw),columns=selected)
            season_stats=aggregate_plays(frame.iter_rows(named=True))
            if len(season_stats)<30:raise ValueError(f'Only {len(season_stats)} games parsed')
            if qb_sink is not None:
                from qb_injuries import aggregate_qb_plays
                qb_season=aggregate_qb_plays(frame.iter_rows(named=True))
                qb_sink.update(qb_season)
            merged.update(season_stats);loaded.append(season)
        except (Exception) as exc:
            errors.append(f'{season}: {type(exc).__name__}: {str(exc)[:90]}')
    return merged,loaded,errors

class TacticalEngine:
    """Small chronological state machine. One insert AFTER all games at kickoff."""
    def __init__(self,by_game=None):
        self.by_game=by_game or {}
        self.previous=defaultdict(list)
    def update(self,game):
        stats=self.by_game.get(game['id'])
        if stats is None:return
        # Snapshot opponents' pregame quality BEFORE inserting this game's data.
        opponent_pre={t:self.summary(t,game) for t in (game['home'],game['away'])}
        for team,opponent in ((game['home'],game['away']),(game['away'],game['home'])):
            if team in stats:
                prior=opponent_pre[opponent]
                row={**stats[team]}
                row['_oppDefPass']=prior['allowedPassEPA'] if prior and prior['games']>=3 else None
                row['_oppOffPass']=prior['passEPA'] if prior and prior['games']>=3 else None
                self.previous[team].append((game['kickoff'],game['season'],row))
    def summary(self,team,game):
        # NFL seasons are explicit. Late-playoff records, past season form and
        # off-season decay should not be silently conflated with current form.
        all_rows=[(kick,year,r) for kick,year,r in self.previous[team]
                  if kick<game['kickoff'] and year>=game['season']-1]
        latest=all_rows[-8:]
        if not latest:return None
        weights=[]
        for i,(_,year,_) in enumerate(latest):
            weights.append((.82**(len(latest)-1-i))*(.50 if year!=game['season'] else 1.0))
        def rate(numerator,denominator):
            den=sum(w*r.get(denominator,0) for w,(_,_,r) in zip(weights,latest))
            if den<1:return None,0
            return sum(w*r.get(numerator,0) for w,(_,_,r) in zip(weights,latest))/den,den
        passing,pn=rate('pass_epa','pass_count')
        passing_allowed,dpn=rate('allowed_pass_epa','allowed_pass_count')
        rushing,rn=rate('rush_epa','rush_count')
        rushing_allowed,drn=rate('allowed_rush_epa','allowed_rush_count')
        hit,_=rate('pass_hit','pass_count')
        hit_forced,_=rate('pass_hits_forced','allowed_pass_count')
        explosive,_=rate('pass_explosive','pass_count')
        explosive_allowed,_=rate('explosive_allowed','allowed_pass_count')
        # Opponent-strength adjustments are optional and use only opponent
        # ratings known *before those earlier games*. A missing baseline does
        # not silently become a zero-strength opponent.
        def opponent_avg(field):
            chosen=[(w,r[field]) for w,(_,_,r) in zip(weights,latest)
                    if r.get(field) is not None and r.get('pass_count',0)>=10]
            return (sum(w*x for w,x in chosen)/sum(w for w,x in chosen),len(chosen)) if len(chosen)>=2 else (None,len(chosen))
        opp_def,opp_def_n=opponent_avg('_oppDefPass')
        opp_off,opp_off_n=opponent_avg('_oppOffPass')
        last=latest[-1][0]
        return {'team':team,'games':len(latest),'lastGameDate':last.date().isoformat(),
                'passPlays':round(pn),'rushPlays':round(rn),'defPassPlays':round(dpn),
                'passEPA':passing,'rushEPA':rushing,'allowedPassEPA':passing_allowed,
                'adjustedPassEPA':passing-opp_def if opp_def is not None and passing is not None else None,
                'adjustedAllowedPassEPA':passing_allowed-opp_off if opp_off is not None and passing_allowed is not None else None,
                'sosSamples':min(opp_def_n,opp_off_n),
                'allowedRushEPA':rushing_allowed,'hitAllowed':hit,'hitForced':hit_forced,
                'explosivePass':explosive,'explosiveAllowed':explosive_allowed}
    def matchup(self,game):
        h=self.summary(game['home'],game);a=self.summary(game['away'],game)
        if h is None or a is None:return {'status':'unavailable','reason':'Historical play-by-play is missing for one or both teams.','home':h,'away':a,'advantages':[],'features':None,'probabilityWeight':0}
        # Minimum sample sizes avoid presenting precise rankings from one-week noise.
        if any(x['games']<3 or x['passPlays']<50 or x['defPassPlays']<50 or x['rushPlays']<20 for x in (h,a)):
            return {'status':'insufficient','reason':'At least three prior games and adequate recorded plays per team are required.','home':h,'away':a,'advantages':[],'features':None,'probabilityWeight':0}
        # Home-positive features are relative differentials, scaled to typical
        # NFL units and capped for extreme small-sample outliers.
        sos_ready=all(x.get('adjustedPassEPA') is not None and
                      x.get('adjustedAllowedPassEPA') is not None for x in (h,a))
        hp=h['adjustedPassEPA'] if sos_ready else h['passEPA']
        hd=h['adjustedAllowedPassEPA'] if sos_ready else h['allowedPassEPA']
        ap=a['adjustedPassEPA'] if sos_ready else a['passEPA']
        ad=a['adjustedAllowedPassEPA'] if sos_ready else a['allowedPassEPA']
        pass_edge=(hp-ad)-(ap-hd)
        rush_edge=(h['rushEPA']-a['allowedRushEPA'])-(a['rushEPA']-h['allowedRushEPA'])
        home_risk=h['hitAllowed']+a['hitForced'];away_risk=a['hitAllowed']+h['hitForced']
        hit_edge=away_risk-home_risk
        exp_edge=(h['explosivePass']+a['explosiveAllowed'])-(a['explosivePass']+h['explosiveAllowed'])
        features=[max(-2,min(2,x/scale)) for x,scale in ((pass_edge,.45),(rush_edge,.35),(hit_edge,.16),(exp_edge,.15))]
        # 'advantage' is a descriptive sign, never betting value or a win chance.
        spec=[('Passing efficiency',pass_edge,'EPA/play',.12),('Rushing efficiency',rush_edge,'EPA/play',.12),
              ('QB-hit/sack matchup',hit_edge,'rate differential',.035),('Explosive pass opportunity',exp_edge,'rate differential',.035)]
        advantages=[]
        for name,edge,units,threshold in spec:
            advantages.append({'name':name,'edge':round(edge,3),'unit':units,
                               'favors':game['home'] if edge>threshold else game['away'] if edge < -threshold else 'Even',
                               'strong':abs(edge)>threshold})
        return {'status':'ready','reason':'Observed rolling, opponent-relative team metrics; not a proven win-probability edge.',
                'home':h,'away':a,'advantages':advantages,'features':features,
                'sosAdjustmentApplied':sos_ready, 'probabilityWeight':0}
