"""Immutable real pre-kickoff feature observations for future independent tests.

No historical injury/weather records are manufactured. Only values observed
during a live pipeline refresh, before the fixture starts, are captured.
Two snapshots per fixture: an early-week view and the first late (<6h) view.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import math

VERSION=1
def _date(x):
    try:
        d=x if isinstance(x,datetime) else datetime.fromisoformat(str(x).replace('Z','+00:00'))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError,TypeError,OverflowError):return None

def _num(x,lo=None,hi=None):
    if x is None or isinstance(x,bool):return None
    try:
        z=float(x)
        if not math.isfinite(z) or (lo is not None and z<lo) or (hi is not None and z>hi):return None
        return z
    except (ValueError,TypeError,OverflowError):return None

def record(dashboard,now,path=Path('data/pregame-features.json')):
    stamp=_date(now)
    if stamp is None:raise ValueError('Timezone-aware capture timestamp required')
    try:
        previous=json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
        if previous and (previous.get('schemaVersion')!=VERSION or not isinstance(previous.get('observations'),list)):
            raise ValueError('Invalid pregame feature archive; refusing overwrite')
    except FileNotFoundError:
        previous={}
    entries=list(previous.get('observations') or [])
    seen={(item.get('gameId'),item.get('window')) for item in entries if isinstance(item,dict)}
    added=0
    for g in dashboard.get('nextGames',[]):
        if not isinstance(g,dict):continue
        kick=_date(g.get('kickoff'))
        gid=g.get('id')
        if not gid or not kick or not stamp<kick:continue
        hours=(kick-stamp).total_seconds()/3600
        if hours>24*8:continue
        window='late' if hours<=6 else 'early'
        key=(gid,window)
        if key in seen:continue
        weather=g.get('weather') or {}
        # Weather source is dated only if weather was actually downloaded.
        weather_stamp=_date(weather.get('retrievedAt'))
        weather_reported=weather.get('status') in ('forecast','roof-unconfirmed') and weather_stamp is not None and weather_stamp<=stamp
        fields=('temperatureC','precipitationChancePct','windMph','gustMph','snowfallCm')
        weather_values={k:_num(weather.get(k)) for k in fields}
        weather_values={k:v for k,v in weather_values.items() if v is not None} if weather_reported else {}
        qb=g.get('qbIntelligence') or {}
        injury=g.get('injuryIntelligence') or {}
        joint=g.get('shadowEnsemble') or {}
        def qb_side(side):
            item=qb.get(side) or {}
            sample=item.get('sample') or {}
            return {'id':item.get('playerId'),'status':item.get('label') or qb.get('status'),
                'priorDropbacks':_num(sample.get('dropbacks'),0),
                'priorEPA':_num(sample.get('epaPerDropback'),-3,3)}
        entries.append({
            'gameId':gid,'season':g.get('season'),'week':g.get('week'),
            'kickoff':kick.isoformat(),'recordedAt':stamp.isoformat(),'window':window,
            'home':g.get('home'),'away':g.get('away'),
            'baselineHomeProbability':_num(g.get('baselineHomeProbability'),0,1),
            'publishedHomeProbability':_num(g.get('homeProbability'),0,1),
            'jointVersion':joint.get('version') if joint.get('researchOnly') else None,
            'jointHomeProbability':_num(joint.get('homeProbability'),0,1) if joint.get('researchOnly') else None,
            'jointMissingEvidence':list(joint.get('missingEvidence') or [])[:8],
            'weather':{
                'status':weather.get('status','unavailable'),
                'roof':weather.get('roof'),'stadiumId':weather.get('stadiumId'),
                'source':weather.get('source') if weather_reported else None,
                'sourceRetrievedAt':weather_stamp.isoformat() if weather_reported else None,
                'forecastFor':weather.get('forecastFor') if weather_reported else None,
                'values':weather_values,
            },
            'quarterbacks':{'home':qb_side('home'),'away':qb_side('away')},
            'injuries':{
                'status':injury.get('status','unavailable'),
                'asOf':injury.get('reportAsOf'),
                'observedFlagCounts':{side:len(injury.get(side) or []) for side in ('home','away')}
                     if injury.get('status') in ('reported','snapshot-only','reported-cached') else None,
                'verifiedActiveRoster':False,
            },
            'trainingEligible':False, # Prospectively grade after the fact; no automatic production fitting.
            'source':'Live pre-kickoff pipeline capture, never a postgame reconstruction',
        })
        seen.add(key);added+=1
    if added or not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'schemaVersion':VERSION,'observations':entries},
            indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    return {'status':'recorded','observations':len(entries),'added':added,
            'nextExpected':'First pre-kickoff snapshot per fixture per window, earlier and within six hours',
            'historicalWeatherTrainingReady':False,'historicalInjuryTrainingReady':False}
