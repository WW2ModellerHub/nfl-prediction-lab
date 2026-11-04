"""NFL Prediction Lab: leakage-aware, dependency-free baseline model.

Inputs: nflverse schedules/games.csv, chronologically processed. 2024+ results
are evaluated using only games known before kickoff; these are BACKTESTS,
not timestamped historical predictions. Forward picks are archived separately.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
from collections import defaultdict
from itertools import groupby
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo
from situational_validation import feature_vector, validate, predict as situational_predict
from tactical import TacticalEngine
from qb_injuries import QBEngine,DepthTimeline,injury_context
from player_validation import (FEATURES as PLAYER_FEATURES, snapshot as player_snapshot,
                               validate as validate_player, predict as predict_player)
from tactical_validation import FEATURES as TACTICAL_FEATURES, validate as validate_tactical, predict as predict_tactical
from audit import build_audit
from shadow_ensemble import vector as challenger_vector,run as run_challenger
from qb_validation import FEATURES as QB_FEATURES, snapshot as qb_snapshot, validate as validate_qb, predict as predict_qb

TEAM_NAMES = {
 'ARI':'Arizona Cardinals','ATL':'Atlanta Falcons','BAL':'Baltimore Ravens','BUF':'Buffalo Bills',
 'CAR':'Carolina Panthers','CHI':'Chicago Bears','CIN':'Cincinnati Bengals','CLE':'Cleveland Browns',
 'DAL':'Dallas Cowboys','DEN':'Denver Broncos','DET':'Detroit Lions','GB':'Green Bay Packers',
 'HOU':'Houston Texans','IND':'Indianapolis Colts','JAX':'Jacksonville Jaguars','JAC':'Jacksonville Jaguars',
 'KC':'Kansas City Chiefs','LA':'Los Angeles Rams','LAR':'Los Angeles Rams','LAC':'Los Angeles Chargers',
 'LV':'Las Vegas Raiders','MIA':'Miami Dolphins','MIN':'Minnesota Vikings','NE':'New England Patriots',
 'NO':'New Orleans Saints','NYG':'New York Giants','NYJ':'New York Jets','PHI':'Philadelphia Eagles',
 'PIT':'Pittsburgh Steelers','SEA':'Seattle Seahawks','SF':'San Francisco 49ers','TB':'Tampa Bay Buccaneers',
 'TEN':'Tennessee Titans','WAS':'Washington Commanders'
}
ALIASES={'JAC':'JAX','LAR':'LA','OAK':'LV','SD':'LAC','STL':'LA','WSH':'WAS'}

def norm(team): return ALIASES.get(team,team)

def num(s):
    try:
        if s is None or str(s).strip()=='': return None
        return float(s)
    except (ValueError, TypeError): return None

def parse_kickoff(row):
    day=(row.get('gameday') or row.get('game_date') or '').strip()
    tm=(row.get('gametime') or '13:00').strip()
    if not day: return None
    try:
        d=datetime.strptime(day+' '+(tm if tm else '13:00'),'%Y-%m-%d %H:%M')
        return d.replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)
    except ValueError:
        return None

def read_games(text):
    out=[]
    for row in csv.DictReader(io.StringIO(text)):
        if (row.get('game_type') or '').upper() not in ('REG','WC','DIV','CON','SB'): continue
        kick=parse_kickoff(row)
        if not kick: continue
        home=norm((row.get('home_team') or '').upper())
        away=norm((row.get('away_team') or '').upper())
        if home not in TEAM_NAMES or away not in TEAM_NAMES: continue
        try: season=int(row['season']); week=int(row['week'])
        except (ValueError,KeyError): continue
        hs=num(row.get('home_score')); aws=num(row.get('away_score'))
        out.append(dict(id=row.get('game_id') or f'{season}_{week}_{away}_{home}',season=season,week=week,
                        type=row.get('game_type'),kickoff=kick,home=home,away=away,
                        home_score=int(hs) if hs is not None else None,away_score=int(aws) if aws is not None else None,
                        neutral=(row.get('location') or '').strip().lower()=='neutral',
                        overtime=(None if num(row.get('overtime')) is None else bool(int(num(row.get('overtime'))))),
                        # Closing spread is used ONLY to grade historical ATS; never for pregame modelling.
                        closing_spread=num(row.get('spread_line')),
                        home_moneyline=num(row.get('home_moneyline')),
                        away_moneyline=num(row.get('away_moneyline')),
                        home_qb_name=(row.get('home_qb_name') or '').strip(),
                        away_qb_name=(row.get('away_qb_name') or '').strip(),
                        home_qb_id=(row.get('home_qb_id') or '').strip(),
                        away_qb_id=(row.get('away_qb_id') or '').strip(),
                        stadium_id=(row.get('stadium_id') or '').strip(),
                        stadium=(row.get('stadium') or '').strip(),
                        roof=(row.get('roof') or '').strip().lower().replace('"','')))
    return sorted(out,key=lambda g:(g['kickoff'],g['id']))

# Situational factors are observable matchup signals. Their historical ATS rates
# are descriptive only; until independently validated they carry ZERO probability weight.
# Six intervening non-game days means Sunday -> following Sunday (7 calendar days).
SITUATIONAL_RULES = {
 'empty_tank': {'name':'Empty Tank+', 'direction':'fade', 'description':'Previous OT; at most six full intervening off-days; opponent previously played regulation'},
 'thursday_road_ot': {'name':'Thursday Road Fatigue', 'direction':'fade', 'description':'Sunday OT followed by an away Thursday game'},
 'blowout_bounce': {'name':'Blowout Bounce', 'direction':'back', 'description':'Previous loss by 28–34 points'},
 'nuclear_bounce': {'name':'Nuclear Bounce', 'direction':'back', 'description':'Previous loss by 35+ points'},
 'rest_edge': {'name':'Rest Advantage', 'direction':'back', 'description':'At least three additional full rest days versus opponent'},
 'repeat_road': {'name':'Back-to-Back Road', 'direction':'fade', 'description':'Second consecutive away game (travel distance not modelled)'},
}

def full_rest_days(prior, current):
    """Intervening calendar off-days, not elapsed 24h periods or a provider's rest field."""
    if not prior or prior['season'] != current['season']: return None
    before=prior['kickoff'].astimezone(ZoneInfo('America/New_York')).date()
    after=current['kickoff'].astimezone(ZoneInfo('America/New_York')).date()
    if after <= before: return None
    return max(0,(after-before).days-1)

def situational_context(game, previous):
    def summary(team, side):
        prev=previous.get(team)
        days=full_rest_days(prev,game)
        if days is None: return {'team':team,'fullRestDays':None,'previous':None}
        margin=prev['margin_for'][team]
        return {'team':team,'fullRestDays':days,'previous':{
            'opponent': prev['away'] if prev['home']==team else prev['home'],
            'overtime':prev['overtime'], 'margin':margin,
            'away':prev['away']==team, 'date':prev['kickoff'].date().isoformat(),
            'score':f"{prev['home_score']}–{prev['away_score']}"}}
    home=summary(game['home'],'home');away=summary(game['away'],'away')
    by_side={'home':home,'away':away}
    signals=[]
    def signal(key,side,reason):
        rule=SITUATIONAL_RULES[key]
        signals.append({'id':key,'name':rule['name'],'direction':rule['direction'],
                        'team':game[side], 'side':side,'reason':reason})
    for side,opp_side in [('home','away'),('away','home')]:
        team=by_side[side];other=by_side[opp_side]
        prev=team['previous'];op=other['previous'];rest=team['fullRestDays']
        if prev is None or rest is None:continue
        if prev['overtime'] is True and rest<=6 and op is not None and op['overtime'] is False:
            signal('empty_tank',side,f"{team['team']} played OT last game; {rest} full off-days. {other['team']} finished in regulation.")
        if (prev['overtime'] is True and prev['date'] and
            datetime.fromisoformat(prev['date']).weekday()==6 and
            game['kickoff'].astimezone(ZoneInfo('America/New_York')).weekday()==3 and
            side=='away' and rest<=4):
            signal('thursday_road_ot',side,f"{team['team']} played Sunday OT and is away on Thursday after {rest} full off-days.")
        if -34<=prev['margin']<=-28:
            signal('blowout_bounce',side,f"{team['team']} lost its previous game by {-prev['margin']} points.")
        elif prev['margin']<=-35:
            signal('nuclear_bounce',side,f"{team['team']} lost its previous game by {-prev['margin']} points.")
        if other['fullRestDays'] is not None and rest-other['fullRestDays']>=3:
            signal('rest_edge',side,f"{team['team']} has {rest} full days off versus {other['fullRestDays']} for {other['team']}.")
        if prev['away'] and side=='away':
            signal('repeat_road',side,f"{team['team']} is away for a second consecutive game; actual travel miles not computed.")
    return {'home':home,'away':away,'signals':signals,'status':'Observed context; not yet probability-weighted'}

def grade_ats(game, side_to_back):
    """Uses final score and closing spread ONLY AFTER a game finished."""
    spread=game.get('closing_spread')
    if spread is None or game['home_score'] is None or game['away_score'] is None:return None
    # nflverse spread_line is positive when HOME is favoured.
    home_ats=(game['home_score']-game['away_score'])-spread
    signed=home_ats if side_to_back=='home' else -home_ats
    return 1 if signed>0 else 0 if signed<0 else 'push'

def summarize_signals(rows):
    results=[]
    for key,rule in SITUATIONAL_RULES.items():
        observations=[(g,sig) for g,p in rows for sig in p['situation']['signals'] if sig['id']==key]
        grades=[]
        holdout=[]
        for g,sig in observations:
            target_side=sig['side'] if rule['direction']=='back' else ('away' if sig['side']=='home' else 'home')
            outcome=grade_ats(g,target_side)
            if outcome is not None:
                grades.append(outcome)
                if g['season']>=2024:holdout.append(outcome)
        wins=grades.count(1);losses=grades.count(0);pushes=grades.count('push')
        hw=holdout.count(1);hl=holdout.count(0)
        results.append({'id':key,'name':rule['name'],'direction':rule['direction'],
            'definition':rule['description'],'observed':len(observations),
            'atsWins':wins,'atsLosses':losses,'atsPushes':pushes,
            'atsRate':round(wins/(wins+losses),4) if wins+losses else None,
            'holdoutWins':hw,'holdoutLosses':hl,
            'holdoutRate':round(hw/(hw+hl),4) if hw+hl else None,
            'validated':False})
    return results

class RatingModel:
    def __init__(self):
        self.ratings=defaultdict(lambda:1500.0)
        self.offense=defaultdict(list)
        self.defense=defaultdict(list)
        self.last_season=None
        self.results=0
        self.previous={}

    def transition(self,season):
        if season!=self.last_season:
            if self.last_season is not None:
                for t in list(self.ratings): self.ratings[t]=1500+(self.ratings[t]-1500)*0.73
            self.last_season=season

    def _form(self,records,default=22.0):
        recent=records[-12:]
        weights=[0.84**(len(recent)-1-i) for i in range(len(recent))]
        return (default*4+sum(x*w for x,w in zip(recent,weights)))/(4+sum(weights))

    def predict(self,g):
        self.transition(g['season'])
        home,away=g['home'],g['away']
        ha=0 if g['neutral'] else 55
        rating_gap=self.ratings[home]-self.ratings[away]+ha
        elo_prob=1/(1+10**(-rating_gap/400))
        home_mean=22+(self._form(self.offense[home])-22)*0.65+(self._form(self.defense[away])-22)*0.65 + (1.25 if ha else 0)
        away_mean=22+(self._form(self.offense[away])-22)*0.65+(self._form(self.defense[home])-22)*0.65 - (1.25 if ha else 0)
        base_total=max(22,min(72,home_mean+away_mean))
        score_margin=home_mean-away_mean
        margin=0.55*score_margin+0.45*(rating_gap/28)
        home_mean=(base_total+margin)/2
        away_mean=(base_total-margin)/2
        normal_prob=0.5*(1+math.erf(margin/(13.8*math.sqrt(2))))
        probability=max(0.05,min(0.95,0.6*elo_prob+0.4*normal_prob))
        context=situational_context(g,self.previous)
        # Situational factors are visible and backtested, but NOT assigned unvalidated weights.
        # Derived distribution is a model assumption, not sportsbook-implied odds.
        uncertainty=13.8
        return {'home_probability':probability,'elo_probability':elo_prob,'normal_probability':normal_prob,
                'home_points':home_mean,'away_points':away_mean,'margin':margin,'total':base_total,
                'sigma_margin':uncertainty,'elo_home':self.ratings[home], 'elo_away':self.ratings[away],
                'home_form':self._form(self.offense[home]),'away_form':self._form(self.offense[away]),
                'home_allowed':self._form(self.defense[home]),'away_allowed':self._form(self.defense[away]),
                'home_advantage':ha,'situation':context}

    def update(self,g,p):
        hs=g['home_score']; aws=g['away_score']
        if hs is None or aws is None: return
        home,away=g['home'],g['away']
        outcome=1 if hs>aws else 0 if hs<aws else 0.5
        mov_factor=min(1.65,0.85+math.log1p(abs(hs-aws))/4)
        change=22*(outcome-p['elo_probability'])*mov_factor
        self.ratings[home]+=change
        self.ratings[away]-=change
        self.offense[home].append(hs); self.offense[away].append(aws)
        self.defense[home].append(aws);self.defense[away].append(hs)
        self.results+=1
        stored={**g,'margin_for':{home:hs-aws,away:aws-hs}}
        self.previous[home]=stored
        self.previous[away]=stored

def simulate(g,p,n=2500):
    seed=int(hashlib.sha256(g['id'].encode()).hexdigest()[:16],16)
    rng=random.Random(seed)
    samples=[]
    bins={'Away 21+':0,'Away 11–20':0,'Away 1–10':0,'Tie':0,'Home 1–10':0,'Home 11–20':0,'Home 21+':0}
    for _ in range(n):
        margin=rng.gauss(p['margin'],13.8)
        total=max(6,rng.gauss(p['total'],13.6))
        h=max(0,round((total+margin)/2)); a=max(0,round((total-margin)/2))
        diff=h-a
        label=('Home 21+' if diff>=21 else 'Home 11–20' if diff>=11 else 'Home 1–10' if diff>=1 else
               'Tie' if diff==0 else 'Away 1–10' if diff>=-10 else 'Away 11–20' if diff>=-20 else 'Away 21+')
        bins[label]+=1
        samples.append((h,a))
    return [{'bucket':k,'share':round(v/n*100,1)} for k,v in bins.items()]

def human_game(g,p,kind='upcoming'):
    prob=p['home_probability']; winner=g['home'] if prob>=0.5 else g['away']
    favored=max(prob,1-prob)
    out={'id':g['id'],'season':g['season'],'week':g['week'],'type':g['type'],'kickoff':g['kickoff'].isoformat(),
         'home':g['home'],'away':g['away'],'homeName':TEAM_NAMES[g['home']], 'awayName':TEAM_NAMES[g['away']],
         'stadium':g.get('stadium',''),'stadiumId':g.get('stadium_id',''),'roof':g.get('roof',''),
         'homeProbability':round(prob,4),'awayProbability':round(1-prob,4),
         'predHome':round(p['home_points'],1),'predAway':round(p['away_points'],1),
         'predTotal':round(p['total'],1),'predMargin':round(p['margin'],1),
         'favourite':winner,'confidence':'High' if favored>=0.7 else 'Medium' if favored>=0.60 else 'Low',
         'eloHome':round(p['elo_home']),'eloAway':round(p['elo_away']),
         'formHome':round(p['home_form'],1),'formAway':round(p['away_form'],1),
         'allowedHome':round(p['home_allowed'],1),'allowedAway':round(p['away_allowed'],1),
         'model':('Elo + form + validated '+p.get('overlay_type','research')+' overlay' if p.get('adjustment_active') else 'Elo + form (research overlays OFF)'),'odds':None,'oddsStatus':'Manual odds only',
         'injuryStatus':('Reported; no probability weight' if p.get('injuries',{}).get('status')=='reported'
                         else 'Undated weekly report (informational only)' if p.get('injuries',{}).get('status')=='snapshot-only'
                         else 'No verified current report'),
         'qbIntelligence':p.get('quarterbacks',{'status':'unavailable'}),
         'playerImpact':p.get('player_impact',{'status':'informational','eligible':False,'reason':'Missing historical data'}),
         'playerProbabilityDelta':round(p.get('player_probability_delta',0),4),
         'qbResearch':p.get('qb_research',{'eligible':False}),
         'qbProbabilityDelta':round(p.get('qb_probability_delta',0),4),
         'injuryIntelligence':p.get('injuries',{'status':'unavailable','home':[],'away':[]}),
         'weatherStatus':'Kickoff forecast not yet downloaded',
         'simulation':simulate(g,p), 'kind':kind, 'situation':p['situation'],
         'tactical':p.get('tactical',{'status':'unavailable','reason':'Play-by-play not yet loaded','advantages':[]}),
         'overlayType':p.get('overlay_type','none'),
         'tacticalProbabilityDelta':round(p.get('tactical_probability_delta',0),4),
         'baselineHomeProbability':round(p.get('baseline_home_probability',p['home_probability']),4),
         'situationalProbabilityDelta':round(p['home_probability']-p.get('baseline_home_probability',p['home_probability']),4) if p.get('overlay_type')=='situational' else 0,
         'adjustmentActive':p.get('adjustment_active',False),
         'scenarios':[
            {'name':'Base case','text':f"The model expects {TEAM_NAMES[g['home']]} to score around {p['home_points']:.0f} and {TEAM_NAMES[g['away']]} around {p['away_points']:.0f}."},
            {'name':'Faster game','text':f"If pace and possession volume rise, the total could finish above the baseline of {p['total']:.0f}. This is a scenario, not a separate calibrated forecast."},
            {'name':'Slower game','text':'Fewer possessions would reduce scoring opportunities for both teams and produce a tighter distribution.'}
         ]}
    if g['home_score'] is not None:
        out['homeScore']=g['home_score'];out['awayScore']=g['away_score'];out['kind']='final'
    return out

def current_season(now): return now.year if now.month>=3 else now.year-1

def performance(rows):
    if not rows: return {'count':0,'accuracy':None,'brier':None,'logLoss':None,'calibration':[],'recent':[]}
    brier=mean((r['homeProbability']-r['outcome'])**2 for r in rows)
    acc=mean(float((r['homeProbability']>=0.5)==(r['outcome']>=0.5)) for r in rows if r['outcome']!=0.5) if any(r['outcome']!=0.5 for r in rows) else None
    loss=mean(-(r['outcome']*math.log(max(1e-6,r['homeProbability']))+(1-r['outcome'])*math.log(max(1e-6,1-r['homeProbability']))) for r in rows)
    bucket=[]
    for start in (0,0.2,0.4,0.6,0.8):
        selected=[r for r in rows if start<=r['homeProbability']<(start+0.2 if start<0.8 else 1.00001)]
        if selected:bucket.append({'label':f'{int(start*100)}–{int((start+.2)*100)}%', 'pred':round(mean(x['homeProbability'] for x in selected)*100,1),'actual':round(mean(x['outcome'] for x in selected)*100,1),'count':len(selected)})
    recent=rows[-100:]
    trend=[]
    for i in range(0,len(recent),10):
        chunk=recent[i:i+10]
        if len(chunk)>=5:trend.append({'period':f'{i+1}–{i+len(chunk)}','brier':round(mean((r['homeProbability']-r['outcome'])**2 for r in chunk),3)})
    return {'count':len(rows),'accuracy':round(acc,4) if acc is not None else None,'brier':round(brier,4),
            'logLoss':round(loss,4),'baselineBrier':round(mean((.5-r['outcome'])**2 for r in rows),4),
            'calibration':bucket,'recent':trend}

def generate(games,now=None,previous_log=None,pbp_games=None,pbp_meta=None,
             qb_games=None,injury_rows=None,depth_rows=None,player_meta=None):
    now=now or datetime.now(timezone.utc)
    current=current_season(now)
    model=RatingModel()
    tactical_engine=TacticalEngine(pbp_games)
    qb_engine=QBEngine(qb_games)
    injury_rows=injury_rows or []
    depth_rows=depth_rows or []
    player_meta=player_meta or {'injuries':{'status':'unavailable'},'depth':{'status':'unavailable'}}
    chart_history=DepthTimeline(depth_rows or [])
    injuries_by_week=defaultdict(list)
    for r in injury_rows:
        injuries_by_week[(r["season"],r["week"])].append(r)
    # An injury archive is loaded by season, not presumed available merely
    # because one player happens to have a reported injury.
    verified_injury_seasons=(player_meta or {}).get('injuries',{}).get('loadedSeasons',[])
    tactical_rows=[]
    player_rows=[]
    qb_rows=[]
    challenger_rows=[]
    all_backtests=[]; upcoming=[]; scored=[]; strategy_history=[]; situation_rows=[]
    # Same-kickoff games must be predicted as one batch. Otherwise, a 13:00
    # final would leak into another game's 13:00 pregame probability.
    eligible=[g for g in games if 2016<=g['season']<=current+1]
    for kickoff,batch_it in groupby(eligible,key=lambda g:g['kickoff']):
        batch=list(batch_it)
        prepared=[]
        for game in batch:
            pred=model.predict(game)
            pred['tactical']=tactical_engine.matchup(game)
            # Historical observations and depth charts are filtered to the
            # exact time a prediction could have been known. These remain
            # informational pending independently validated injury effects.
            # Both historical and future player snapshots stop strictly before
            # kickoff, or the current time for forecasts that have not begun.
            cutoff=min(now,game['kickoff']-timedelta(hours=2))
            chart=chart_history.at(cutoff,(game['home'],game['away'])) if game['season']>=2025 else {}
            pred['quarterbacks']=qb_engine.matchup(game,chart)
            pred['qb_research']=qb_snapshot(game,pred['quarterbacks'],chart,cutoff)
            pred['injuries']=injury_context(game,injuries_by_week[(game['season'],game['week'])],chart,cutoff)
            pred['player_impact']=player_snapshot(game,pred['quarterbacks'],pred['injuries'],
                                                  chart,cutoff,verified_injury_seasons)
            prepared.append((game,pred))
        to_update=[]
        for game,p in prepared:
            is_finished=game['home_score'] is not None and game['away_score'] is not None and kickoff<=now
            if is_finished:
                if game['season']>=2016: strategy_history.append((game,p))
                if game['season']>=2024:
                    row=human_game(game,p,kind='final')
                    row['outcome']=1 if game['home_score']>game['away_score'] else 0 if game['home_score']<game['away_score'] else 0.5
                    # Only for RETROSPECTIVE grading; closing lines must never be model inputs.
                    row['closingHomeMoneyline']=game.get('home_moneyline')
                    row['closingAwayMoneyline']=game.get('away_moneyline')
                    all_backtests.append(row)
                scored.append(game)
                # Preserve strictly pregame feature and baseline snapshots for season-forward validation.
                if game['season']>=2016 and game['home_score']!=game['away_score']:
                    situation_rows.append({'season':game['season'],'p':p['home_probability'],
                                           'features':feature_vector(p['situation']),
                                           'y':1 if game['home_score']>game['away_score'] else 0})
                if p['tactical'].get('status')=='ready' and game['home_score']!=game['away_score']:
                    tactical_rows.append({'season':game['season'],'p':p['home_probability'],
                                         'features':p['tactical']['features'],
                                         'y':1 if game['home_score']>game['away_score'] else 0})
                if game['home_score']!=game['away_score']:
                    challenger_rows.append({'id':game['id'],'season':game['season'],
                        'p':p['home_probability'],'features':challenger_vector(game,p),
                        'y':int(game['home_score']>game['away_score'])})
                if p['qb_research']['eligible'] and game['home_score']!=game['away_score']:
                    qb_rows.append({'season':game['season'],'p':p['home_probability'],
                                    'features':p['qb_research']['features'],
                                    'y':1 if game['home_score']>game['away_score'] else 0})
                if p['player_impact']['eligible'] and game['home_score']!=game['away_score']:
                    player_rows.append({'season':game['season'],'p':p['home_probability'],
                                        'features':p['player_impact']['features'],
                                        'y':1 if game['home_score']>game['away_score'] else 0})
                to_update.append((game,p))
            elif kickoff>now and game['season']>=current:
                upcoming.append((game,p))
        for game,p in to_update:
            model.update(game,p)
            tactical_engine.update(game)
            qb_engine.update(game)
    # Validate the situational overlay using COMPLETE past seasons only.
    # Current-season scores are deliberately unavailable to the overlay trainer.
    validation=validate(situation_rows,current)
    tactical_validation=validate_tactical(tactical_rows,current)
    player_validation=validate_player(player_rows,current)
    qb_validation=validate_qb(qb_rows,current)
    # XGBoost challenger: research only, never a live overlay or bet input.
    shadow_upcoming=[{'id':g['id'],'p':p['home_probability'],
                      'features':challenger_vector(g,p)} for g,p in upcoming]
    challenger_validation,challenger_predictions=run_challenger(
        challenger_rows,shadow_upcoming,current)
    # No stacking: individual overlays were compared with the SAME baseline,
    # not tested in combination. An ineligible player snapshot cannot activate
    # player impact for that specific fixture, even if the global gate passes.
    situ_gain=validation.get('selectionBrierGain') or 0
    tact_gain=tactical_validation.get('brierGain') or 0
    player_gain=player_validation.get('brierGain') or 0
    qb_gain=qb_validation.get('brierGain') or 0
    eligible_gates=[(gain,key) for gain,key,on in ((situ_gain,'situational',validation['enabled']),
                    (tact_gain,'tactical',tactical_validation['enabled']),
                    (player_gain,'player',player_validation['enabled']),
                    (qb_gain,'qb',qb_validation['enabled'])) if on]
    chosen=max(eligible_gates,key=lambda x:x[0])[1] if eligible_gates else 'none' 
    for game,p in upcoming:
        p['baseline_home_probability']=p['home_probability']
        p['overlay_type']='none'
        p['tactical_probability_delta']=0
        p['player_probability_delta']=0
        p['qb_probability_delta']=0
        if chosen=='situational':
            coefs=[validation['coefficients'][k] for k in ('empty_tank','thursday_road_ot','blowout_bounce','nuclear_bounce','rest_edge','repeat_road')]
            p['home_probability']=situational_predict(p['home_probability'],feature_vector(p['situation']),coefs)
            p['adjustment_active']=True
            p['overlay_type']='situational'
        elif chosen=='tactical' and p['tactical'].get('features') is not None:
            coefs=[tactical_validation['coefficients'][k] for k in TACTICAL_FEATURES]
            p['home_probability']=predict_tactical(p['home_probability'],p['tactical']['features'],coefs)
            p['tactical_probability_delta']=p['home_probability']-p['baseline_home_probability']
            p['adjustment_active']=True
            p['overlay_type']='tactical'
        elif chosen=='player' and p['player_impact'].get('eligible'):
            coefs=[player_validation['coefficients'][k] for k in PLAYER_FEATURES]
            p['home_probability']=predict_player(p['home_probability'],p['player_impact']['features'],coefs)
            p['player_probability_delta']=p['home_probability']-p['baseline_home_probability']
            p['adjustment_active']=True
            p['overlay_type']='player'
        elif chosen=='qb' and p['qb_research']['eligible']:
            coefs=[qb_validation['coefficients'][k] for k in QB_FEATURES]
            p['home_probability']=predict_qb(p['home_probability'],p['qb_research']['features'],coefs)
            p['qb_probability_delta']=p['home_probability']-p['baseline_home_probability']
            p['adjustment_active']=True
            p['overlay_type']='qb'
    # Game scores in source may be late. Never infer they're live.
    upcoming.sort(key=lambda x:x[0]['kickoff'])
    candidates=[(g,p) for g,p in upcoming if g['kickoff']<=now+timedelta(days=21)]
    if not candidates: candidates=upcoming[:24]
    future=[human_game(g,p) for g,p in candidates[:40]]
    for row in future:
        if row['id'] in challenger_predictions:
            row['shadowEnsemble']={'homeProbability':challenger_predictions[row['id']],
                'researchOnly':True,'affectsForecast':False,
                'status':'SHADOW — not a validated betting forecast'}
    log=list(previous_log or [])
    logged_ids={x.get('gameId') for x in log}
    for g,p in candidates:
        if g['kickoff']>now and g['id'] not in logged_ids:
            log.append({'gameId':g['id'],'recordedAt':now.isoformat(),'kickoff':g['kickoff'].isoformat(),
                        'home':g['home'],'away':g['away'],'homeProbability':round(p['home_probability'],5),
                        'predMargin':round(p['margin'],2),'predTotal':round(p['total'],2),
                        'situationalSignals':[s['id'] for s in p['situation']['signals']],
                        'model':'elo-form-v1-overlays-validated-v1.5',
                        'overlayType':p.get('overlay_type','none'),
                        'tacticalProbabilityDelta':round(p.get('tactical_probability_delta',0),5),
                        'playerProbabilityDelta':round(p.get('player_probability_delta',0),5),
                        'qbProbabilityDelta':round(p.get('qb_probability_delta',0),5),
                        'qbResearch':p.get('qb_research'),
                        'qbObserved':{s:p.get('quarterbacks',{}).get(s,{}).get('playerId') for s in ('home','away')},
                        'injuryReportAsOf':p.get('injuries',{}).get('reportAsOf'),
                        'qbInjuryProbabilityWeight':round(p.get('player_probability_delta',0),5),
                        'playerFeatures':p.get('player_impact',{}).get('features'),
                        'playerImpactStatus':p.get('player_impact',{}).get('status'),
                        'tacticalFeatures':p.get('tactical',{}).get('features'),
                        'baselineHomeProbability':round(p.get('baseline_home_probability',p['home_probability']),5),
                        'adjustmentActive':bool(p.get('adjustment_active',False)),
                        'situationalProbabilityDelta':round(p['home_probability']-p.get('baseline_home_probability',p['home_probability']),5) if p.get('overlay_type')=='situational' else 0})
            logged_ids.add(g['id'])
    # Grade immutable forward predictions only using completed games. Never mutate original probability.
    score_by_id={g['id']:g for g in scored}
    forward=[]
    for entry in log:
        game=score_by_id.get(entry.get('gameId'))
        if game and game['home_score'] is not None:
            y=1 if game['home_score']>game['away_score'] else 0 if game['home_score']<game['away_score'] else .5
            forward.append({'gameId':entry['gameId'],'home':entry['home'],'away':entry['away'],
                            'homeProbability':entry['homeProbability'],'outcome':y,'homeScore':game['home_score'],
                            'awayScore':game['away_score'],'recordedAt':entry['recordedAt']})
    last_100=all_backtests[-100:]
    historical_perf=performance(all_backtests)
    ranks=sorted(([{'team':team,'name':TEAM_NAMES[team],'rating':round(rating),
                    'pointsFor':round(model._form(model.offense[team]),1),
                    'pointsAgainst':round(model._form(model.defense[team]),1)}
                   for team,rating in model.ratings.items() if team in TEAM_NAMES]),key=lambda r:r['rating'],reverse=True)
    latest=max((g['kickoff'] for g in scored),default=None)
    data={'schemaVersion':1,'generatedAt':now.isoformat(),'dataStatus':'ok' if games else 'unavailable',
          'source':'nflverse schedules release (games.csv)','sourceUrl':'https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv',
          'model':'Elo + scoring form; optional single research-gated situational, tactical, QB or player overlay','historicalLabel':'Sequential backtest (not actual pregame archived forecasts)',
          'latestResultAt':latest.isoformat() if latest else None,'currentSeason':current,
          'nextGames':future,'recentResults':all_backtests[-30:][::-1],
          'performance':historical_perf,'historicalAudit':build_audit(all_backtests,now.isoformat()),
          'recentPerformance':performance(last_100),
          'forwardPerformance':performance(forward),'forwardResults':forward[-50:][::-1],
          'forwardPredictions':len(log),'powerRankings':ranks,'situationalStats':summarize_signals(strategy_history),
          'situationalValidation':validation,
          'tacticalValidation':tactical_validation,
          'playerValidation':player_validation,
          'qbValidation':qb_validation,
          'challengerValidation':challenger_validation,
          'tacticalSource':pbp_meta or {'status':'unavailable','seasons':[]},
          'qbSource':{'status':'loaded' if qb_games else 'unavailable',
                      'games':len(qb_games or {}),'source':'Same nflverse PBP downloaded for tactical engine'},
          'injurySource':player_meta.get('injuries',{'status':'unavailable'}),
          'depthSource':player_meta.get('depth',{'status':'unavailable'}),
          'overlaySelection':chosen,
          'playerImpactSource':{'verifiedInjurySeasons':list(verified_injury_seasons),
                                'historicalSnapshotsAvailable':bool(depth_rows),
                                'notes':'Only pregame depth charts and timestamped injury reports used.'},
          'dataWarnings':['No verified live play-by-play feed','No automated player prop feed','QB and injury effects are informational unless the player model passes completed-season validation','No weather adjustments','Tactical PBP data: '+(pbp_meta or {}).get('status','unavailable'), 'No situational, tactical or player overlay activates without a completed-season validation gate','Pass rush proxy is QB hits/sacks, NOT independently charted pressures','No coverage scheme data (man/zone) connected','Odds require manual entry','Backtests use score histories; no historical market ROI claimed']}
    return data,log

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument('--csv',required=True);ap.add_argument('--out',default='data/dashboard.json');ap.add_argument('--log',default='data/predictions-log.json');ap.add_argument('--now')
    a=ap.parse_args()
    now=datetime.fromisoformat(a.now.replace('Z','+00:00')) if a.now else datetime.now(timezone.utc)
    path=Path(a.log)
    try:old=json.loads(path.read_text()) if path.exists() else []
    except (ValueError,OSError):old=[]
    dashboard,log=generate(read_games(Path(a.csv).read_text(encoding='utf-8-sig')),now,old)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(dashboard,indent=2,ensure_ascii=False)+'\n')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(log,indent=2)+'\n')
    print(f'Published {len(dashboard["nextGames"])} upcoming games, {dashboard["performance"]["count"]} backtests, {len(log)} immutable forward picks')
