"""Optional current ESPN injury watch; never used as official NFL game status.

Use only recent dated observations, and never fit historical player models from
a current public-media feed. A missing entry does not imply a healthy player.
"""
from __future__ import annotations
import json
import urllib.request
from datetime import datetime,timedelta,timezone
from qb_injuries import dt_value,normalized_team
from model import TEAM_NAMES

TEAM_NAME_TO_CODE={name.casefold():normalized_team(code) for code,name in TEAM_NAMES.items()}

URL='https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries'
MAX_AGE_DAYS=35
RELEVANT={'OUT','QUESTIONABLE','DOUBTFUL','DAY-TO-DAY','INJURED RESERVE','IR','OUT FOR SEASON','INACTIVE','WEEK-TO-WEEK','DOUBTFUL FOR GAME'}

def val(v):
    if isinstance(v,dict):
        return str(v.get('description') or v.get('name') or v.get('displayName') or v.get('abbreviation') or '').strip()
    return str(v or '').strip()

def parse(payload,now=None):
    now=now or datetime.now(timezone.utc)
    if not isinstance(payload,dict) or not isinstance(payload.get('injuries'),list):
        raise ValueError('ESPN injury response has unexpected shape')
    latest={}
    for group in payload['injuries']:
        if not isinstance(group,dict):continue
        teaminfo=group.get('team') or {}
        if not isinstance(teaminfo,dict):teaminfo={}
        team=normalized_team(val(teaminfo.get('abbreviation') or group.get('abbreviation')))
        if not team:
            fullname=val(group.get('displayName') or teaminfo.get('displayName'))
            team=TEAM_NAME_TO_CODE.get(fullname.casefold(),'')
        if not team:continue
        for item in group.get('injuries',[]):
            if not isinstance(item,dict):continue
            athlete=item.get('athlete') or {}
            if not isinstance(athlete,dict):continue
            name=val(athlete.get('fullName') or athlete.get('displayName'))
            if not name:continue
            stamp=dt_value(item.get('date') or item.get('lastUpdated'))
            if not stamp or stamp>now+timedelta(minutes=5) or now-stamp>timedelta(days=MAX_AGE_DAYS):continue
            status=val(item.get('status'))
            if status.upper() not in RELEVANT:continue
            entry={'name':name,'position':val(athlete.get('position')).upper(),
                   'status':status,'injury':val(item.get('type') or item.get('details')),
                   'reportDate':stamp.isoformat(),'source':'ESPN media injury list',
                   'officialGameStatus':False,'starterConfirmed':False}
            key=(team,val(athlete.get('id')) or name.casefold())
            if key not in latest or entry['reportDate']>latest[key]['reportDate']:
                latest[key]=entry
    result={}
    for (team,_),entry in latest.items():
        result.setdefault(team,[]).append(entry)
    priority={'OUT':0,'IR':0,'INJURED RESERVE':0,'OUT FOR SEASON':0,'INACTIVE':0,
              'DOUBTFUL':1,'DOUBTFUL FOR GAME':1,'QUESTIONABLE':2,'WEEK-TO-WEEK':3,'DAY-TO-DAY':4}
    for entries in result.values():
        entries.sort(key=lambda r:(priority.get(r['status'].upper(),5),-datetime.fromisoformat(r['reportDate']).timestamp(),r['name']))
    return result

def load(now=None):
    now=now or datetime.now(timezone.utc)
    meta={'status':'unavailable','source':URL,'retrievedAt':None,'reportCount':0,'teamsCovered':0,
          'note':'Additional ESPN media injury watch; not an official NFL weekly practice report or gameday inactive list.'}
    try:
        req=urllib.request.Request(URL,headers={'User-Agent':'NFLPredictionLab/1.8 (personal research)','Accept':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as response:
            raw=response.read(16_000_001)
        if len(raw)>16_000_000:raise ValueError('ESPN response exceeds maximum permitted size')
        fetched=datetime.now(timezone.utc)
        payload=json.loads(raw.decode('utf-8-sig'))
        # Safe shape diagnostics for an unofficial, occasionally changing feed.
        groups=payload.get('injuries',[]) if isinstance(payload,dict) else []
        groups=groups if isinstance(groups,list) else []
        items=[x for g in groups if isinstance(g,dict) for x in (g.get('injuries') or []) if isinstance(x,dict)]
        dated=[dt_value(x.get('date') or x.get('lastUpdated')) for x in items]
        dated=[x for x in dated if x]
        meta['inspection']={
            'groups':len(groups),'items':len(items),'dated':len(dated),
            'latestDate':max(dated).isoformat() if dated else None,
            'statusSamples':sorted({val(x.get('status')) for x in items if x.get('status')})[:20],
            'topKeys':sorted(payload)[:20] if isinstance(payload,dict) else [],
            'firstGroupKeys':sorted(groups[0])[:20] if groups and isinstance(groups[0],dict) else [],
            'firstItemKeys':sorted(items[0])[:20] if items else []}
        teams=parse(payload,fetched)
        n=sum(len(v) for v in teams.values())
        meta.update(status='loaded' if n else 'empty',retrievedAt=fetched.isoformat(),reportCount=n,teamsCovered=len(teams))
        if not n:meta['note']='No recent, dated injury observations passed validation; this does not mean all teams are healthy.'
        return teams,meta
    except (ValueError,UnicodeError,OSError,TimeoutError,KeyError,TypeError) as exc:
        meta['error']=f'{type(exc).__name__}: {str(exc)[:180]}'
        return {},meta
