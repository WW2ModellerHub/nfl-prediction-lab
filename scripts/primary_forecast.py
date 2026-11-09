"""Provisional primary NFL forecasts, with immutable versioned forward evaluation.

The combined model may be the prominently displayed RESEARCH pick, while the
historical published Elo/personnel pick remains unchanged and remains the
existing prediction-ledger benchmark. Never retroactively treat a backtest or
an older saved prediction as a forward primary pick.

No automatic betting approval or model graduation; that must follow forward
evidence and review. Each first observed version/game is permanently archived.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from shadow_ensemble import VERSION as JOINT_VERSION
import json,math

PRIMARY_VERSION='primary-provisional-v2+'+JOINT_VERSION

def _dt(v):
    try:
        d=v if isinstance(v,datetime) else datetime.fromisoformat(str(v).replace('Z','+00:00'))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (TypeError,ValueError,OverflowError):return None

def _p(v):
    return isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v) and 0<v<1

def candidate(g,report,now):
    """One auditable display pick; preserve existing production probability."""
    old=g.get('homeProbability')
    active=g.get('shadowEnsemble') or {}
    gate=g.get('forecastQuality') or {}
    kick=_dt(g.get('kickoff'))
    personnel=g.get('personnelScenario') or {}
    # The candidate models historical QB efficiency, not a fresh third-string
    # starter or a newly OUT player. A material externally observed personnel
    # repricing must not be silently overwritten by the candidate.
    news_delta=personnel.get('homeDelta')
    material_news=(personnel.get('affectsPrediction') is True and
        isinstance(news_delta,(int,float)) and not isinstance(news_delta,bool) and
        math.isfinite(news_delta) and abs(news_delta)>=.005)
    accepted=(not material_news and kick and now<kick and
        report.get('status')=='historical-research-candidate' and
        report.get('candidateQualifiedForFurtherResearch') is True and
        active.get('version')==JOINT_VERSION and
        active.get('researchOnly') is True and
        active.get('reconciles') is True and
        active.get('productionWeight')==0 and
        isinstance(active.get('layers'),list) and
        bool(active.get('layers')) and
        _p(old) and _p(active.get('homeProbability')))
    if not accepted:
        return {'status':'original-fallback','modelVersion':'elo-form-legacy',
                'homeProbability':old,'awayProbability':1-old if _p(old) else None,
                'originalHomeProbability':old,'eligibleForBetting':False,
                'reason':('Fresh QB/injury adjustment is not represented in the combined research model'
                    if material_news else 'Combined candidate not available or validation gate not met'),
                'isProvisional':False}
    pick=active['homeProbability']
    return {'status':'provisional','modelVersion':PRIMARY_VERSION,
        'homeProbability':round(pick,6),'awayProbability':round(1-pick,6),
        'originalHomeProbability':round(old,6),
        'deltaVsOriginalPP':round((pick-old)*100,3),
        'originalForecastModel':g.get('model'),
        'evidenceLevel':gate.get('level','unavailable'),
        'needsReview':gate.get('level')!='checked',
        'eligibleForBetting':False,'isProvisional':True,
        'reconciles':True,'factorAttributionBasis':'TreeSHAP vs raw Elo/form model, not vs official personnel-adjusted probability',
        'source':'Joint XGBoost v2 historical candidate; 2026 prospective performance unverified',
        'researchOnly':True}

def publish(dashboard,games,now,path=Path('data/primary-predictions-log.json')):
    """Build the current primary choice and grade immutable past primary picks."""
    now=_dt(now)
    if now is None:raise ValueError('Timezone-aware update required')
    report=dashboard.get('challengerValidation') or {}
    for g in dashboard.get('nextGames',[]):
        g['primaryForecast']=candidate(g,report,now)
    try:
        saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
        if not isinstance(saved,list) or any(not isinstance(x,dict) for x in saved):
            raise ValueError('Malformed primary forecast log; refusing to overwrite')
    except FileNotFoundError:
        saved=[]
    keys={(x.get('gameId'),x.get('modelVersion')) for x in saved}
    added=0
    for g in dashboard.get('nextGames',[]):
        primary=g['primaryForecast'];kick=_dt(g.get('kickoff'))
        if not kick or now>=kick or not primary.get('isProvisional'):continue
        key=(g.get('id'),PRIMARY_VERSION)
        if key in keys:continue
        rec={
           'gameId':g['id'],'home':g['home'],'away':g['away'],
           'kickoff':kick.isoformat(),'recordedAt':now.isoformat(),
           'modelVersion':PRIMARY_VERSION,'kind':'first-versioned-primary',
           'homeProbability':primary['homeProbability'],
           'originalHomeProbability':primary['originalHomeProbability'],
           'researchOnly':True,'eligibleForBetting':False,
           'evidenceLevel':primary['evidenceLevel'],
           'note':'First genuinely published provisional pick, not reconstructed',
        }
        saved.append(rec);keys.add(key);added+=1
    finals={g['id']:g for g in games if isinstance(g,dict) and
        _dt(g.get('kickoff')) and _dt(g['kickoff'])<=now and
        g.get('home_score') is not None and g.get('away_score') is not None and
        g.get('home_score')!=g.get('away_score')}
    scored=[]
    for rec in saved:
        if rec.get('modelVersion')!=PRIMARY_VERSION:continue
        game=finals.get(rec.get('gameId'))
        recorded=_dt(rec.get('recordedAt'));kick=_dt(rec.get('kickoff'))
        if (not game or not recorded or not kick or not recorded<kick or
            game.get('home')!=rec.get('home') or game.get('away')!=rec.get('away') or
            _dt(game['kickoff'])!=kick or
            not _p(rec.get('homeProbability')) or
            not _p(rec.get('originalHomeProbability'))):continue
        outcome=int(game['home_score']>game['away_score'])
        scored.append((rec['homeProbability'],rec['originalHomeProbability'],outcome))
    n=len(scored)
    primary_brier=sum((p-y)**2 for p,b,y in scored)/n if n else None
    old_brier=sum((b-y)**2 for p,b,y in scored)/n if n else None
    dashboard['primaryForecastSummary']={
        'status':'provisional-active' if report.get('candidateQualifiedForFurtherResearch') else 'original-model-only',
        'modelVersion':PRIMARY_VERSION,
        'upcomingProvisional':sum(g['primaryForecast']['isProvisional'] for g in dashboard.get('nextGames',[])),
        'firstRecordedPicks':sum(rec.get('modelVersion')==PRIMARY_VERSION for rec in saved),
        'legacyVersionPicks':sum(rec.get('modelVersion')!=PRIMARY_VERSION for rec in saved),
        'newRecords':added,'gradedGames':n,
        'provisionalBrier':round(primary_brier,6) if n else None,
        'matchedOriginalBrier':round(old_brier,6) if n else None,
        'pairedBrierGain':round(old_brier-primary_brier,6) if n else None,
        'provisionalAccuracy':round(sum((p>=.5)==bool(y) for p,b,y in scored)/n,4) if n else None,
        'originalAccuracy':round(sum((b>=.5)==bool(y) for p,b,y in scored)/n,4) if n else None,
        'historicalEvaluatedGames':report.get('evaluationGames',0),
        'minimumIndependentGames':100,'autopromote':False,'bettingEligible':False,
        'source':'Provisional vs original picks recorded at the same pre-kickoff time. No retrospective fitting.',
        'note':'This is a new independent cohort. Existing official 2026 predictions and their historical grading are unchanged.'}
    if added or not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return dashboard['primaryForecastSummary']
