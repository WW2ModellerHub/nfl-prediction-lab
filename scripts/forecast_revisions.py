"""Append-only pre-kickoff forecasts; no rewriting past predictions."""
import json, math
from pathlib import Path
from datetime import datetime,timezone

def dt(x):
    try:
        v=datetime.fromisoformat(str(x).replace('Z','+00:00'))
        return v.astimezone(timezone.utc) if v.tzinfo else None
    except (ValueError,TypeError):return None

def valid(p):
    return isinstance(p,(int,float)) and math.isfinite(p) and 0<p<1

def snapshot(g,stamp,kind,origin):
    personnel=g.get('personnelScenario') or {}
    return {'gameId':g['id'],'kickoff':g['kickoff'],'recordedAt':stamp.isoformat(),
       'kind':kind,'origin':origin,'home':g['home'],'away':g['away'],
       'homeProbability':round(g['homeProbability'],5),
       'baselineHomeProbability':g.get('baselineHomeProbability'),
       'predHome':g.get('predHome'),'predAway':g.get('predAway'),
       'predMargin':g.get('predMargin'),'predTotal':g.get('predTotal'),
       'model':g.get('model'),'overlayType':g.get('overlayType','none'),
       'personnelStatus':personnel.get('status'),'personnelHomeDelta':personnel.get('homeDelta',0),
       'personnelMarginDelta':personnel.get('marginDelta',0),
       'personnelEvidence':personnel.get('factors',[]),
       'personnelWarnings':personnel.get('warnings',[])[:6],
       'mediaRetrievedAt':personnel.get('sourceObservedAt'),
       'qbNames':{side:((g.get('qbIntelligence') or {}).get(side) or {}).get('qb')
                  for side in ('home','away')},
       'provisionalPlayerRules':True}

def revisions(dashboard,originals,completed_games,now,path=Path('data/forecast-revisions.json')):
    now=dt(now)
    if now is None:raise ValueError('UTC timestamp required')
    try:
        data=json.loads(path.read_text(encoding='utf8')) if path.exists() else []
        if not isinstance(data,list):raise ValueError('Invalid revision history')
    except FileNotFoundError:
        data=[]
    originals={x.get('gameId'):x for x in originals if isinstance(x,dict)
               and x.get('gameId') and valid(x.get('homeProbability'))}
    keys={(x.get('gameId'),x.get('recordedAt'),x.get('kind')) for x in data}
    for game in dashboard.get('nextGames',[]):
        kick=dt(game.get('kickoff'))
        if not kick or now>=kick or not valid(game.get('homeProbability')):continue
        gid=game['id']
        previous=any(x.get('gameId')==gid for x in data)
        first=originals.get(gid)
        if not previous and first and dt(first.get('recordedAt')) and dt(first['recordedAt'])<kick:
            item={'gameId':gid,'kickoff':first.get('kickoff',game['kickoff']),
                  'recordedAt':first['recordedAt'],'kind':'first','origin':'immutable-original-prediction',
                  'home':first.get('home',game['home']),'away':first.get('away',game['away']),
                  'homeProbability':first['homeProbability'],'baselineHomeProbability':first.get('baselineHomeProbability'),
                  'predMargin':first.get('predMargin'),'predTotal':first.get('predTotal'),
                  'model':first.get('model'),'overlayType':first.get('overlayType','none')}
            key=(gid,item['recordedAt'],'first')
            if key not in keys:data.append(item);keys.add(key)
        elif not previous:
            item=snapshot(game,now,'first','first-published-forecast')
            key=(gid,item['recordedAt'],'first')
            if key not in keys:data.append(item);keys.add(key)
        current=snapshot(game,now,'refresh','source-refresh')
        key=(gid,current['recordedAt'],'refresh')
        if key not in keys:data.append(current);keys.add(key)
    by_game={}
    for item in data:
        if not isinstance(item,dict):continue
        by_game.setdefault(item.get('gameId'),[]).append(item)
    for game in dashboard.get('nextGames',[]):
        history=sorted(by_game.get(game['id'],[]),key=lambda e:e.get('recordedAt',''))
        game['forecastHistory']=history[-12:]
        game['forecastHistoryCount']=len(history)
        if history:
            game['originalForecast']=next((r for r in history if r.get('kind')=='first'),history[0])
            game['latestRecordedForecast']=history[-1]
    finished={g['id']:g for g in completed_games
              if g.get('home_score') is not None and g.get('away_score') is not None
              and g['home_score']!=g['away_score']}
    scored=[]
    for gid,hist in by_game.items():
        game=finished.get(gid)
        if not game:continue
        kickoff=dt(game.get('kickoff'))
        eligible=[x for x in hist if valid(x.get('homeProbability')) and dt(x.get('recordedAt'))
                  and kickoff and dt(x['recordedAt'])<kickoff]
        if not eligible:continue
        eligible.sort(key=lambda x:x['recordedAt'])
        scored.append((eligible[0]['homeProbability'],eligible[-1]['homeProbability'],
                       int(game['home_score']>game['away_score'])))
    def metric(i):
        return round(sum((x[i]-x[2])**2 for x in scored)/len(scored),5) if scored else None
    dashboard['forecastRevisionSummary']={
        'savedRevisions':len(data),'gamesTracked':len(by_game),'completedCompared':len(scored),
        'originalBrier':metric(0),'latestBrier':metric(1),
        'note':'Immutable first forecast compared with last actually recorded pre-kickoff refresh.',
        'source':'data/forecast-revisions.json'}
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    return data
