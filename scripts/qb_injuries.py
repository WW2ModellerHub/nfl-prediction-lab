"""QB usage and injury/depth-chart intelligence for NFL Prediction Lab.

No implicit player availability or scoring adjustments: injury report statuses
are reports, depth charts are projections, and previous leading passer is not
an independently confirmed starting QB. All timestamps are filtered as-of.
"""
from __future__ import annotations

import csv
import io
import math
import urllib.request
from collections import defaultdict
from bisect import bisect_right
from datetime import datetime, timezone

INJURIES_URL = 'https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv'
DEPTH_URL = 'https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_{season}.parquet'
HIGH_IMPACT = {'QB', 'T','OT','LT','RT','G','LG','RG','C','OL','WR','RB','HB','FB','TE','DE','DT','DL','EDGE','LB','ILB','OLB','CB','S','FS','SS','DB'}
STATUSES = {'OUT','DOUBTFUL','QUESTIONABLE','INJURED RESERVE','IR','RESERVE/INJURED','INACTIVE','DNP'}
TEAM_ALIASES={'JAC':'JAX','LAR':'LA','WSH':'WAS','OAK':'LV','SD':'LAC','STL':'LA'}

def clean_str(v):
    return '' if v is None else str(v).strip()

def normalized_team(v):
    x=clean_str(v).upper()
    return TEAM_ALIASES.get(x,x)

def dt_value(value):
    """Decode timestamps without assuming an absent timezone is local time."""
    if isinstance(value, datetime):
        d=value
    else:
        s=clean_str(value)
        if not s:return None
        try:d=datetime.fromisoformat(s.replace('Z','+00:00'))
        except ValueError:
            try:d=datetime.strptime(s[:19],'%Y-%m-%d %H:%M:%S')
            except ValueError:return None
    if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

def aggregate_qb_plays(rows):
    """Group a single season's PBP by (game, team, passer ID).

    The `pass` marker includes dropbacks; `pass_attempt` excludes sacks.
    Counts use observed play fields, and CPOE is optional rather than imputed.
    """
    out=defaultdict(lambda:defaultdict(dict))
    for row in rows:
        gid=clean_str(row.get('game_id'))
        team=normalized_team(row.get('posteam'))
        pid=clean_str(row.get('passer_player_id'))
        if not gid or not team or not pid or pid.lower() in ('nan','none'):
            continue
        if row.get('pass') not in (1,1.0,'1',True):continue
        key=(team,pid)
        stats=out[gid][key]
        if not stats:
            stats.update({'team':team,'id':pid,'name':clean_str(row.get('passer_player_name')) or pid,
                          'dropbacks':0,'attempts':0,'completions':0,'epaTotal':0.,'epaPlays':0,
                          'passYards':0.,'sacks':0,'hitsOrSacks':0,'interceptions':0,'cpoeTotal':0.,'cpoePlays':0})
        stats['dropbacks']+=1
        epa=row.get('epa')
        try:
            val=float(epa)
            if math.isfinite(val):stats['epaTotal']+=val;stats['epaPlays']+=1
        except (ValueError, TypeError):pass
        is_sack=row.get('sack') in (1,1.0,'1',True)
        if is_sack:stats['sacks']+=1
        if is_sack or row.get('qb_hit') in (1,1.0,'1',True):stats['hitsOrSacks']+=1
        attempt=row.get('pass_attempt') in (1,1.0,'1',True)
        if attempt:
            stats['attempts']+=1
            if row.get('complete_pass') in (1,1.0,'1',True):stats['completions']+=1
            if row.get('interception') in (1,1.0,'1',True):stats['interceptions']+=1
            try:stats['passYards']+=float(row.get('passing_yards') or 0)
            except (ValueError, TypeError):pass
            try:
                val=float(row.get('cpoe'))
                if math.isfinite(val):stats['cpoeTotal']+=val;stats['cpoePlays']+=1
            except (TypeError, ValueError):pass
    return {gid:{team:{pid:dict(v) for (teamkey,pid),v in by_team.items() if teamkey==team}
                 for team in sorted({key[0] for key in by_team})}
            for gid,by_team in out.items()}

class QBEngine:
    """Incremental passer summary: only games completed before a target kickoff."""
    def __init__(self, by_game=None):
        self.by_game=by_game or {}
        self.history=defaultdict(list)
        self.last_leader={}
        self.first_start_history=[]
        self.seen_verified_starters=set()

    def update(self,game):
        game_rows=self.by_game.get(game['id'],{})
        for side in ('home','away'):
            team=game[side]
            qb_rows=list(game_rows.get(team,{}).values())
            recorded_id=clean_str(game.get(side+'_qb_id'))
            starter_row=next((r for r in qb_rows if r.get('id')==recorded_id),None) if recorded_id else None
            # Realised performance is learned only AFTER previous games finished.
            # Never use this game's actual starter or EPA for its own forecast.
            if (starter_row and recorded_id not in self.seen_verified_starters and
                starter_row.get('dropbacks',0)>=10 and starter_row.get('epaPlays',0)>=10):
                prior_dbs=sum(r.get('dropbacks',0)
                              for _,_,r in self.history.get(recorded_id,[]))
                if prior_dbs<80:
                    self.first_start_history.append({
                        'gameId':game['id'],'season':game['season'],
                        'kickoff':game['kickoff'].isoformat(),'playerId':recorded_id,
                        'priorDropbacks':prior_dbs,'dropbacks':starter_row['dropbacks'],
                        'epaPerDropback':max(-1.,min(1.,
                             starter_row['epaTotal']/starter_row['epaPlays']))})
            if recorded_id:self.seen_verified_starters.add(recorded_id)
            for rec in qb_rows:
                if rec['dropbacks']>0:
                    self.history[rec['id']].append((game['kickoff'],game['season'],dict(rec)))
            # The nflverse schedule records the starting QB for completed games.
            # This is a last-game observation, not a forecast for next week.
            recorded=clean_str(game.get(side+'_qb_name'))
            recorded_id=clean_str(game.get(side+'_qb_id'))
            leader=max(qb_rows,key=lambda x:x.get('dropbacks',0)) if qb_rows else None
            if recorded:
                if not recorded_id and leader and leader['name'].casefold()==recorded.casefold():
                    recorded_id=leader['id']
                self.last_leader[team]={
                    'id':recorded_id or None,'name':recorded,'game':game['id'],
                    'season':game['season'],'date':game['kickoff'].isoformat(),
                    'dropbacks':next((v['dropbacks'] for v in qb_rows if v['id']==recorded_id),None),
                    'basis':'last_game_recorded_starter'}
            elif leader and leader['dropbacks']>=5:
                self.last_leader[team]={
                    'id':leader['id'],'name':leader['name'],'game':game['id'],
                    'season':game['season'],'date':game['kickoff'].isoformat(),
                    'dropbacks':leader['dropbacks'],'basis':'last_game_leading_passer'}
            else:
                self.last_leader.pop(team,None)

    def summary(self,player_id,game):
        # A player traded between teams may have previous history; retain it by ID.
        records=[rec for kickoff,season,rec in self.history.get(player_id,[])
                 if kickoff < game['kickoff'] and season>=game['season']-1]
        recent=records[-8:]
        if not recent:return None
        weights=[.83**(len(recent)-i-1) for i in range(len(recent))]
        def weighted_rate(a,b):
            numerator=sum(w*r.get(a,0) for w,r in zip(weights,recent))
            den=sum(w*r.get(b,0) for w,r in zip(weights,recent))
            return round(numerator/den,3) if den else None
        return {'games':len(recent),'dropbacks':sum(r['dropbacks'] for r in recent),
                'epaPerDropback':weighted_rate('epaTotal','epaPlays'),
                'completionPct':weighted_rate('completions','attempts'),
                'cpoe':weighted_rate('cpoeTotal','cpoePlays'),
                'passingYardsPerAttempt':weighted_rate('passYards','attempts'),
                'sackRate':weighted_rate('sacks','dropbacks'),
                'qbHitOrSackRate':weighted_rate('hitsOrSacks','dropbacks'),
                'interceptions':sum(r['interceptions'] for r in recent)}

    def first_start_prior(self,game):
        """Empirical prior from other completed rookie/low-experience starts.

        Game outcomes only enter the QB engine AFTER kickoff and final score.
        A future game's actual starter/realised performance is never read.
        """
        prior=[r for r in self.first_start_history
               if r['season']>=game['season']-7 and r['season']<=game['season']
               and datetime.fromisoformat(r['kickoff'])<game['kickoff']]
        if len(prior)<20:
            return {'status':'insufficient','starts':len(prior),
                    'epaPerDropback':None,'stddev':None,
                    'source':'Historical completed first starts; no imputed value'}
        xs=[r['epaPerDropback'] for r in prior]
        mu=sum(xs)/len(xs)
        sd=math.sqrt(sum((x-mu)**2 for x in xs)/len(xs))
        return {'status':'observed','starts':len(xs),
                'epaPerDropback':round(mu,4),'stddev':round(sd,4),
                'source':'Past completed verified first starts with <80 prior dropbacks',
                'lastCompletedSeason':max(r['season'] for r in prior)}

    def matchup(self,game,depth=None):
        depth=depth or {}
        result={'home':None,'away':None,'status':'unavailable','probabilityWeight':0,
                'reason':'PBP quarterback history has not been received.'}
        exists=False
        replacement_prior=self.first_start_prior(game)
        result['firstStartPrior']=replacement_prior
        for side in ('home','away'):
            team=game[side]
            observed=self.last_leader.get(team)
            # An old-season leading passer is not evidence of this week's starter.
            if observed and observed.get('season')!=game['season']:
                observed=None
            projected=depth.get(team,{}).get('qb')
            pid=(projected.get('id') if projected and projected.get('id') else
                 observed.get('id') if observed else None)
            s=self.summary(pid,game) if pid else None
            changed=bool(observed and projected and projected.get('id') and projected['id']!=observed['id'])
            basis=('depth_chart_projection' if projected else
                   observed.get('basis','last_game_leading_passer') if observed else 'unknown')
            result[side]={'team':team,'qb':projected['name'] if projected else observed['name'] if observed else None,
                          'playerId':pid,'basis':basis,
                          'confirmedStarter':False,'lastGameLeader':observed,
                          'starterChangeWatch':changed,'sample':s,
                          'previousQBsample':self.summary(observed['id'],game) if observed and observed.get('id') else None,
                          'replacementPrior':replacement_prior,
                          'projectedQBId':projected.get('id') if projected else None,
                          'label':('Depth-chart QB (not a confirmed starter)' if projected else
                                   'Last recorded game starter (not confirmed for this game)' if basis=='last_game_recorded_starter' else
                                   'Last-game leading passer (not confirmed for this game)' if observed else 'No recent QB observation')}
            if projected or observed:exists=True
        if exists:
            result['status']='observed'
            result['reason']='Latest observed game starter or depth-chart projection; not a confirmed starter. Player metrics require play-by-play coverage.'
        return result

def read_injuries(text, observation_time=None, snapshot_mode=False):
    """Use exact report times, or prospectively observe an undated weekly snapshot.

    An archive with no record timestamps cannot be assigned to past kickoffs.
    Only the current season is allowed to use the actual retrieval time.
    """
    records=[]
    for r in csv.DictReader(io.StringIO(text)):
        ts=dt_value(r.get('date_modified'))
        undated=ts is None
        if undated:
            if not snapshot_mode or observation_time is None:continue
            ts=dt_value(observation_time)
        if ts is None:continue
        try:season=int(r.get('season') or 0);week=int(r.get('week') or 0)
        except ValueError:continue
        if season<2009 or week<1:continue
        team=normalized_team(r.get('team'))
        player=clean_str(r.get('full_name'))
        pid=clean_str(r.get('gsis_id'))
        if not team or not player:continue
        records.append({'season':season,'week':week,'team':team,'id':pid,'name':player,
                        'position':clean_str(r.get('position')).upper(),
                        'reportStatus':clean_str(r.get('report_status')),
                        'practiceStatus':clean_str(r.get('practice_status')),
                        'injury':clean_str(r.get('report_primary_injury') or r.get('practice_primary_injury')),
                        'asOf':ts,'timestampBasis':'download-observation' if undated else 'row-updated'})
    return records

def read_depth_rows(rows):
    result=[]
    for r in rows:
        dt=dt_value(r.get('dt'))
        team=normalized_team(r.get('team'))
        name=clean_str(r.get('player_name'))
        pid=clean_str(r.get('gsis_id'))
        abb=clean_str(r.get('pos_abb')).upper()
        group=clean_str(r.get('pos_grp_id')).upper()
        try:rank=int(float(r.get('pos_rank')))
        except (ValueError, TypeError):rank=999
        if dt and team and name and abb:
            result.append({'asOf':dt,'team':team,'name':name,'id':pid,
                           'position':abb,'group':group,'rank':rank})
    return result

def depth_at(depth_rows,cutoff):
    """Latest team chart snapshot <= cutoff; never mix rows from later snapshots."""
    stamp={}
    for r in depth_rows:
        if r['asOf']<=cutoff and (r['team'] not in stamp or r['asOf']>stamp[r['team']]):
            stamp[r['team']]=r['asOf']
    result={}
    for row in depth_rows:
        team=row['team']
        if stamp.get(team)!=row['asOf']:continue
        summary=result.setdefault(team,{'asOf':row['asOf'].isoformat(),'starters':set(),'qb':None})
        if row['rank']==1:
            if row.get('id'):summary['starters'].add(row['id'])
            if row['position']=='QB' and (summary['qb'] is None or row.get('id')):
                summary['qb']={'id':row['id'],'name':row['name']}
    # convert internal set to list: safe for serialization and membership checks
    for s in result.values():s['starters']=sorted(s['starters'])
    return result

class DepthTimeline:
    """Index dated chart snapshots for efficient historical as-of lookups."""
    def __init__(self, rows):
        by_key={}
        for row in rows:
            team=row['team'];ts=row['asOf']
            item=by_key.setdefault((team,ts),{'asOf':ts.isoformat(),'starters':set(),'qb':None})
            if row['rank']==1:
                if row.get('id'):item['starters'].add(row['id'])
                if row['position']=='QB' and (item['qb'] is None or row.get('id')):
                    item['qb']={'id':row['id'],'name':row['name']}
        self.snapshots=defaultdict(list)
        for (team,ts),item in by_key.items():
            item['starters']=sorted(item['starters'])
            self.snapshots[team].append((ts,item))
        self.times={}
        for team,rec in self.snapshots.items():
            rec.sort(key=lambda x:x[0]);self.times[team]=[x[0] for x in rec]
    def at(self,cutoff,teams):
        result={}
        for team in teams:
            timestamps=self.times.get(team,[])
            idx=bisect_right(timestamps,cutoff)-1
            if idx>=0:result[team]=self.snapshots[team][idx][1]
        return result

def injury_context(game,records,depth,as_of):
    cutoff=min(as_of,game['kickoff'])
    latest={}
    for r in records:
        if r['season']!=game['season'] or r['week']!=game['week'] or r['team'] not in (game['home'],game['away']):continue
        if r['asOf']>cutoff:continue
        key=(r['team'],r['id'] or r['name'].lower())
        if key not in latest or r['asOf']>latest[key]['asOf']:
            latest[key]=r
    result={'home':[],'away':[],'reportAsOf':None,'status':'unavailable',
            'probabilityWeight':0,'note':'Published injury/practice reports are not confirmed gameday inactives.'}
    if not latest:
        result['note']='No timestamp-verified injury reports available for this matchup and week.'
        return result
    for r in latest.values():
        status=r['reportStatus'].upper()
        practice=r['practiceStatus'].upper()
        if status not in STATUSES and not (practice in ('DNP','DID NOT PARTICIPATE','LIMITED PARTICIPATION','LP','LIMITED')):
            continue
        pos=r['position']
        if pos not in HIGH_IMPACT:continue
        team=r['team'];chart=depth.get(team,{})
        starter=r['id'] in chart.get('starters',[]) if r['id'] else False
        weight=3 if status in ('OUT','INJURED RESERVE','IR','RESERVE/INJURED','INACTIVE') else 2 if status=='DOUBTFUL' else 1
        item={'name':r['name'],'id':r['id'],'position':pos,'status':r['reportStatus'] or 'Not designated',
              'practice':r['practiceStatus'],'injury':r['injury'],'starterOnDepthChart':starter,
              'severity':weight,'reportAsOf':r['asOf'].isoformat()}
        result['home' if team==game['home'] else 'away'].append(item)
    for side in ('home','away'):
        result[side].sort(key=lambda x:(-x['severity'],not x['starterOnDepthChart'],x['position'],x['name']))
        result[side]=result[side][:25]
    result['reportAsOf']=max(r['asOf'] for r in latest.values()).isoformat()
    snapshot=any(r.get('timestampBasis')=='download-observation' for r in latest.values())
    result['status']='snapshot-only' if snapshot else 'reported'
    result['timestampBasis']='download-observation' if snapshot else 'row-updated'
    result['note']=('Source records lack individual modification times. Observed by this dashboard at retrieval time; reports may be stale. Never used for historical player-impact fitting or automatic probability changes.' if snapshot else 'Reports may change before kickoff. A depth-chart rank is an unconfirmed projection; no automated probability effect is applied.')
    return result

def _download(url,limit=35_000_000):
    request=urllib.request.Request(url,headers={'User-Agent':'NFLPredictionLab/1.5 (personal analytics research)'})
    with urllib.request.urlopen(request,timeout=90) as response:
        body=response.read(limit+1)
        if len(body)>limit:raise ValueError('Upstream file exceeds size cap')
    return body

def load_current_reports(season,snapshot_mode=False,observation_time=None):
    """Load injury CSV and new-format depth chart parquet, separately fault tolerant."""
    injuries=[];depth=[]
    meta={'injuries':{'status':'unavailable','season':season,'errors':[],'source':INJURIES_URL.format(season=season)},
          'depth':{'status':'unavailable','season':season,'errors':[],'source':DEPTH_URL.format(season=season)}}
    try:
        raw=_download(INJURIES_URL.format(season=season)).decode('utf-8-sig')
        injuries=read_injuries(raw,observation_time=observation_time,snapshot_mode=snapshot_mode)
        if not injuries:
            raise ValueError('No timestamped report rows; undated historical records are not backdated')
        undated=any(x['timestampBasis']=='download-observation' for x in injuries)
        meta['injuries'].update(
            status='snapshot-only' if undated else 'loaded', records=len(injuries),
            asOf=max(r['asOf'] for r in injuries).isoformat(),
            timestampBasis='download-observation' if undated else 'row-updated',
            note=('Undated weekly rows: downloaded now, not historically timestamped; not used in player model validation' if undated else 'Timestamped report rows'))
    except Exception as e:
        meta['injuries']['errors'].append(f'{type(e).__name__}: {str(e)[:450]}')
    try:
        import polars as pl
        data=_download(DEPTH_URL.format(season=season),limit=90_000_000)
        frame=pl.read_parquet(io.BytesIO(data))
        must={'dt','team','player_name','gsis_id','pos_abb','pos_rank'}
        if not must.issubset(frame.columns):raise ValueError('Unexpected depth chart column schema')
        depth=read_depth_rows(frame.select(list(must)).iter_rows(named=True))
        if not depth:raise ValueError('No timestamped depth chart rows')
        meta['depth'].update(status='loaded',records=len(depth),asOf=max(r['asOf'] for r in depth).isoformat())
    except Exception as e:
        meta['depth']['errors'].append(f'{type(e).__name__}: {str(e)[:120]}')
    return injuries,depth,meta


def load_historical_reports(current_season,first_season=2025):
    """Load dated injury and chart history from 2025 onward.

    Older (<=2024) depth charts are weekly snapshots without a robust as-of
    timestamp and are intentionally excluded from point-in-time player tests.
    Failure to load any season marks it unavailable rather than imputing health.
    """
    all_injuries=[];all_depth=[]
    meta={'injuries':{'status':'unavailable','loadedSeasons':[],'snapshotSeasons':[],'errors':[],
                      'source':'nflverse dated injuries_{season}.csv'},
          'depth':{'status':'unavailable','loadedSeasons':[],'errors':[],
                   'source':'nflverse 2025+ timestamped depth_charts_{season}.parquet'}}
    observed=datetime.now(timezone.utc)
    for season in range(max(2025,first_season),current_season+1):
        # For undated sources, only this year's future games may see a
        # snapshot first observed during the current refresh.
        injuries,depth,sub=load_current_reports(
            season,snapshot_mode=(season==current_season),observation_time=observed)
        if sub['injuries']['status']=='loaded':
            all_injuries.extend(injuries)
            meta['injuries']['loadedSeasons'].append(season)
        elif sub['injuries']['status']=='snapshot-only':
            all_injuries.extend(injuries)
            meta['injuries']['snapshotSeasons'].append(season)
            meta['injuries']['asOf']=sub['injuries'].get('asOf')
            meta['injuries']['timestampBasis']='download-observation'
        else:
            meta['injuries']['errors'] += [f'{season}: {x}' for x in sub['injuries']['errors']]
        if sub['depth']['status']=='loaded':
            all_depth.extend(depth)
            meta['depth']['loadedSeasons'].append(season)
        else:
            meta['depth']['errors'] += [f'{season}: {x}' for x in sub['depth']['errors']]
    for key in ('injuries','depth'):
        count=len(all_injuries if key=='injuries' else all_depth)
        meta[key]['records']=count
        ok=meta[key]['loadedSeasons']
        meta[key]['status']=('loaded' if len(ok)==max(0,current_season-max(2025,first_season)+1) and ok
                             else 'partial' if ok
                             else 'snapshot-only' if key=='injuries' and meta[key].get('snapshotSeasons')
                             else 'unavailable')
    return all_injuries,all_depth,meta
