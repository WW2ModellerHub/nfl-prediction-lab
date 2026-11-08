"""Immutable pregame prediction history, outcome scorecard, and timing audit.

Never create a new prediction for a started game. A historical first forecast
may be COPIED from a genuinely timestamped, immutable pre-kickoff legacy log,
with explicit importAt provenance; this is not a postgame reconstruction.
Compare first and latest observed snapshots on exactly the same scored games.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

from prediction_record import summarize as summarize_prediction_record
from player_effect_scorecard import summarize as summarize_player_effects

def dt(value):
    try:
        value=datetime.fromisoformat(str(value).replace("Z","+00:00")) if not isinstance(value,datetime) else value
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except (ValueError,TypeError,OverflowError):
        return None

def valid(p):
    return isinstance(p,(int,float)) and not isinstance(p,bool) and math.isfinite(p) and 0<p<1

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
       # Point-in-time paired control: never reconstruct a no-player forecast
       # after the game, and never confuse it with the Elo-only baseline.
       'prePersonnelProbability':round(g['prePersonnelProbability'],5)
           if valid(g.get('prePersonnelProbability')) else None,
       'provisionalPlayerApplied':bool(personnel.get('affectsPrediction') and
           valid(g.get('prePersonnelProbability')) and
           abs(g['homeProbability']-g['prePersonnelProbability'])>=.00001),
       'personnelSourceMode':('cached' if 'cached' in str(personnel.get('status','')).lower()
           else 'fresh' if personnel.get('sourceObservedAt') else 'unknown'),
       'personnelSourceObservedAt':personnel.get('sourceObservedAt'),
       'playerEffectDeltas':{key:round(float(personnel.get(field,0)),5)
           for key,field in (('qb-statistical','qbStatisticalHomeDelta'),
                             ('qb-replacement','qbReplacementHomeDelta'),
                             ('other-injuries','injuryHomeDelta'))
           if isinstance(personnel.get(field,0),(int,float)) and
              not isinstance(personnel.get(field,0),bool) and
              math.isfinite(personnel.get(field,0))},
       'personnelWarnings':personnel.get('warnings',[])[:6],
       'mediaRetrievedAt':personnel.get('sourceObservedAt'),
       'qbNames':{side:((g.get('qbIntelligence') or {}).get(side) or {}).get('qb')
                  for side in ('home','away')},
       'provisionalPlayerRules':True,
       'appliedLayerDeltas':{item['key']:item['deltaHome']
           for item in (g.get('forecastExplanation') or {}).get('layers',[])
           if item.get('applied')},
       'layerExplanationStatus':(g.get('forecastExplanation') or {}).get('status','unavailable'),
       'verificationLevel':(g.get('forecastQuality') or {}).get('level','not-collected'),
       'verificationAt':(g.get('forecastQuality') or {}).get('timestamp'),
       'verificationIssues':(g.get('forecastQuality') or {}).get('issues',[])[:10],
       'reportMirrorStatus':(g.get('officialInjuryEvidence') or {}).get('status'),
       'reportTimestampBasis':{side:
          ('download-observation' if any(x.get('timestampBasis')=='download-observation'
              for x in ((g.get('officialInjuryEvidence') or {}).get(side) or {}).get('rows',[]))
           else 'row-updated' if ((g.get('officialInjuryEvidence') or {}).get(side) or {}).get('rows')
           else 'unavailable') for side in ('home','away')}}

def _legacy_original(record,now):
    """Existing recorded forecast is reproduced exactly; never re-estimated."""
    return {'gameId':record['gameId'],'kickoff':record['kickoff'],
        'recordedAt':record['recordedAt'],'kind':'first',
        'origin':'recovered-from-immutable-original-log',
        'importedAt':now.isoformat(),'home':record.get('home'),
        'away':record.get('away'),'homeProbability':record['homeProbability'],
        'baselineHomeProbability':record.get('baselineHomeProbability'),
        'predMargin':record.get('predMargin'),'predTotal':record.get('predTotal'),
        'model':record.get('model'),'overlayType':record.get('overlayType','none'),
        'personnelStatus':record.get('personnelStatus') or 'not-collected-in-legacy-forecast',
        'personnelHomeDelta':record.get('personnelHomeDelta',0),
        'personnelEvidence':[], 'provisionalPlayerRules':False,
        'verificationLevel':record.get('verificationLevel','not-collected-in-original'),
        'verificationAt':record.get('recordedAt') if record.get('verificationLevel') else None,
        'verificationIssues':record.get('verificationReasons',[])[:10]}

def _evaluate(rows,field):
    if not rows:return {'games':0,'brier':None,'accuracy':None,'logLoss':None}
    n=len(rows)
    return {'games':n,
            'brier':round(sum((row[field]-row['outcomeHome'])**2 for row in rows)/n,6),
            'accuracy':round(sum(int((row[field]>=.5)==bool(row['outcomeHome'])) for row in rows)/n,4),
            'logLoss':round(sum(-row['outcomeHome']*math.log(max(.005,min(.995,row[field])))-
                       (1-row['outcomeHome'])*math.log(max(.005,min(.995,1-row[field])))
                       for row in rows)/n,6)}

def _final_games(games,now):
    out={}
    for g in games:
        kick=dt(g.get('kickoff'))
        if not kick or kick>now or g.get('home_score') is None or g.get('away_score') is None:continue
        if g['home_score']==g['away_score']:continue
        out[g['id']]=g
    return out

def revisions(dashboard,originals,completed_games,now,path=Path('data/forecast-revisions.json')):
    """Archive first picks, append next forecasts, grade only actual pregame data."""
    now=dt(now)
    if not now:raise ValueError('Timezone-aware forecast timestamp required')
    try:
        records=json.loads(path.read_text(encoding='utf8')) if path.exists() else []
        if not isinstance(records,list) or any(not isinstance(x,dict) for x in records):
            raise ValueError('Existing prediction ledger malformed; refusing to overwrite')
    except FileNotFoundError:
        records=[]
    by_game={}
    keys=set()
    for item in records:
        by_game.setdefault(item.get('gameId'),[]).append(item)
        keys.add((item.get('gameId'),item.get('recordedAt'),item.get('kind')))

    # Recover only originally archived, genuinely time-stamped pregame picks.
    # Original 2026 JAX@BAL (and other completed games) must remain auditable
    # even though they are absent from the CURRENT upcoming-fixture list.
    originals_by_id={}
    for orig in originals:
        if not isinstance(orig,dict) or not orig.get('gameId') or not valid(orig.get('homeProbability')):
            continue
        stamp=dt(orig.get('recordedAt'));kick=dt(orig.get('kickoff'))
        if not stamp or not kick or stamp>=kick or stamp>now:continue
        originals_by_id.setdefault(orig['gameId'],orig)
    for gid,orig in originals_by_id.items():
        legacy=_legacy_original(orig,now)
        existing_first=[r for r in by_game.get(gid,[]) if r.get('kind')=='first']
        if existing_first:
            if any(abs(r.get('homeProbability',-99)-orig['homeProbability'])>0.00001
                   for r in existing_first):
                raise ValueError('Immutable original changed for '+str(gid))
            continue
        key=(gid,legacy['recordedAt'],'first')
        if key not in keys:
            records.append(legacy);by_game.setdefault(gid,[]).append(legacy);keys.add(key)

    # Only create genuinely new forecasts for games still ahead.
    for game in dashboard.get('nextGames',[]):
        kick=dt(game.get('kickoff'))
        if not kick or now>=kick or not valid(game.get('homeProbability')):continue
        gid=game['id']
        if not by_game.get(gid):
            item=snapshot(game,now,'first','first-published-with-revision-ledger')
            key=(gid,item['recordedAt'],'first')
            if key not in keys:
                records.append(item);by_game.setdefault(gid,[]).append(item);keys.add(key)
        item=snapshot(game,now,'refresh','automated-verified-source-refresh')
        key=(gid,item['recordedAt'],'refresh')
        if key not in keys:
            records.append(item);by_game.setdefault(gid,[]).append(item);keys.add(key)

    for game in dashboard.get('nextGames',[]):
        history=sorted(by_game.get(game.get('id'),[]),key=lambda r:r.get('recordedAt',''))
        game['forecastHistory']=history[-12:]
        game['forecastHistoryCount']=len(history)
        if history:
            game['originalForecast']=next((r for r in history if r.get('kind')=='first'),history[0])
            game['latestRecordedForecast']=history[-1]

    finals=_final_games(completed_games,now)
    scored=[]
    for gid,hist in by_game.items():
        g=finals.get(gid)
        if not g:continue
        kick=dt(g['kickoff'])
        valid_history=sorted((r for r in hist if valid(r.get('homeProbability'))
                              and dt(r.get('recordedAt')) and dt(r['recordedAt'])<kick),
                             key=lambda r:r['recordedAt'])
        if not valid_history:continue
        first=next((r for r in valid_history if r.get('kind')=='first'),valid_history[0])
        last=valid_history[-1]
        first_time=dt(first['recordedAt']);last_time=dt(last['recordedAt'])
        hour_before=kick-timedelta(hours=24)
        near=[r for r in valid_history if dt(r['recordedAt'])>=hour_before]
        last24=near[-1] if near else None
        outcome=int(g['home_score']>g['away_score'])
        p0=first['homeProbability'];p1=last['homeProbability']
        score0=(p0-outcome)**2;score1=(p1-outcome)**2
        scored.append({
            'gameId':gid,'season':g.get('season'),'week':g.get('week'),
            'kickoff':kick.isoformat(),'home':g.get('home'),'away':g.get('away'),
            'homeScore':g['home_score'],'awayScore':g['away_score'],
            'outcomeHome':outcome,'winner':g.get('home') if outcome else g.get('away'),
            'firstProbability':p0,'lastProbability':p1,
            'firstRecordedAt':first_time.isoformat(),
            'lastRecordedAt':last_time.isoformat(),
            'firstAgeHours':round((kick-first_time).total_seconds()/3600,1),
            'lastAgeHours':round((kick-last_time).total_seconds()/3600,1),
            'revisionsAfterFirst':max(0,len(valid_history)-1),
            'changed':abs(p0-p1)>=.00001,
            'firstCorrect':int((p0>=.5)==bool(outcome)),
            'lastCorrect':int((p1>=.5)==bool(outcome)),
            'firstBrier':round(score0,6),'lastBrier':round(score1,6),
            'brierGain':round(score0-score1,6),
            'lastPersonnelStatus':last.get('personnelStatus') or 'unknown',
            'lastQBEvidence':any(x.get('kind')=='qb' or x.get('kind')=='qb-efficiency'
                                 for x in (last.get('personnelEvidence') or [])
                                 if isinstance(x,dict)),
            'within24hProbability':last24['homeProbability'] if last24 else None,
            'within24hRecordedAt':last24['recordedAt'] if last24 else None})
    scored.sort(key=lambda x:(x['kickoff'],x['gameId']),reverse=True)

    base=[{'p0':r['firstProbability'],'p1':r['lastProbability'],'y':r['outcomeHome']} for r in scored]
    firsts=_evaluate([{'first':x['p0'],'outcomeHome':x['y']} for x in base],'first')
    lasts=_evaluate([{'last':x['p1'],'outcomeHome':x['y']} for x in base],'last')
    changed=[r for r in scored if r['changed']]
    qb_games=[r for r in scored if r['lastQBEvidence']]
    late=[r for r in scored if r['within24hProbability'] is not None]
    late_first=_evaluate([{'v':r['firstProbability'],'outcomeHome':r['outcomeHome']} for r in late],'v')
    late_new=_evaluate([{'v':r['within24hProbability'],'outcomeHome':r['outcomeHome']} for r in late],'v')

    dashboard['forecastRevisionSummary']={
       'savedRevisions':len(records),'gamesTracked':len(by_game),
       'completedCompared':len(scored),
       'originalBrier':firsts['brier'],'latestBrier':lasts['brier'],
       'originalAccuracy':firsts['accuracy'],'latestAccuracy':lasts['accuracy'],
       'originalLogLoss':firsts['logLoss'],'latestLogLoss':lasts['logLoss'],
       'brierGain':round(firsts['brier']-lasts['brier'],6) if scored else None,
       'changedGames':len(changed),'improvedGames':sum(r['brierGain']>0 for r in changed),
       'worsenedGames':sum(r['brierGain']<0 for r in changed),
       'unchangedGames':len(scored)-len(changed),
       'qbEvidenceGraded':len(qb_games),
       'qbEvidenceBrierGain':round(sum(r['brierGain'] for r in qb_games)/len(qb_games),6) if qb_games else None,
       'latestWithin24hGames':len(late),'firstBrierOn24hCohort':late_first['brier'],
       'latest24hBrier':late_new['brier'],
       'recentFinals':len(scored),'source':'data/forecast-revisions.json',
       'note':'Only original timestamped picks and later forecasts saved before the actual kickoff are scored. Recovered originals retain their original observation time and import provenance. Last recorded does not necessarily mean near kickoff; a separate 24-hour cohort reports true late updates. Ties excluded. No retrospective injury estimates.'}
    dashboard['forecastRevisionResults']=scored[:80]
    dashboard['playerEffectScorecard']=summarize_player_effects(scored,by_game,dt,valid)
    record=summarize_prediction_record(scored,by_game,now,dt,valid)
    dashboard['predictionRecord']={
        key:value for key,value in record.items() if key!='allResults'
    }
    path.parent.mkdir(parents=True,exist_ok=True)
    # One row per outcome, including every source timestamp; the full
    # snapshot archive above remains the immutable historical authority.
    record_path=path.with_name('prediction-results.json')
    record_path.write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n',
                           encoding='utf8')
    path.write_text(json.dumps(records,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    return records
