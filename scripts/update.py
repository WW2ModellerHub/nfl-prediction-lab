"""Refresh verified NFL schedules, projections, and historical audit.

Zero-cost, resilient importer. Lightweight mode skips large optional PBP files.
No fallback to invented teams, injuries, markets, or predictions.
"""
import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from model import read_games,generate
from player_usage import load_snap_counts,UsageHistory,enrich_upcoming
from tactical import load_nflverse_pbp
from personnel_adjustment import assess as assess_personnel, qb_efficiency_preview
from qb_replacement import evaluate as assess_replacement
from forecast_revisions import revisions as save_forecast_revisions
from forecast_layers import explain as explain_forecast_layers
from model import simulate as forecast_simulate
from qb_injuries import load_historical_reports
from espn_injuries import load as load_espn_injuries
from qb_evidence import gather as gather_qb_sources, attach as attach_qb_sources
from official_reports import fetch as fetch_weekly_reports, from_existing as reuse_weekly_reports, attach as attach_weekly_reports
from pregame_verification import evaluate as verify_pregame_evidence
from weather import enrich as enrich_weather

SOURCES=(
    'https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv',
    'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv',
)


def get_schedule(local_path=None):
    errors=[]
    sources=(str(local_path),) if local_path else SOURCES
    for url in sources:
        try:
            if local_path:
                raw=Path(local_path).read_bytes()
            else:
                req=urllib.request.Request(url,headers={'User-Agent':'NFLPredictionLab/1.6 (independent personal NFL research)'})
                with urllib.request.urlopen(req,timeout=75) as response:
                    raw=response.read()
            if len(raw)>20_000_000 or len(raw)<100_000:
                raise ValueError('Unexpected games.csv size')
            text=raw.decode('utf-8-sig')
            games=read_games(text)
            if len(games)<1000 or max(g['season'] for g in games)<2025:
                raise ValueError('Incomplete schedules data')
            # Source cadence may lag behind actual NFL results. Report the latest
            # recorded final instead of implying freshness from download time.
            finals=[g for g in games if g['home_score'] is not None and g['away_score'] is not None]
            latest=max((g['kickoff'] for g in finals),default=None)
            return games,{'url':url if not local_path else 'local-file:'+str(local_path),
                'latestFinalAt':latest.isoformat() if latest else None,
                'sha256':hashlib.sha256(raw).hexdigest(), 'downloadedAt':datetime.now(timezone.utc).isoformat(),
                'parsedGames':len(games),'status':'verified','previousSourceFailures':errors}
        except (OSError,ValueError,UnicodeError) as exc:
            errors.append(url+' · '+str(exc)[:150])
    raise RuntimeError('No verified NFL schedules source available: '+'; '.join(errors))


def preserve_recent_player_context(dashboard, previous, now):
    """Keep per-fixture, verified enrichment through a lightweight refresh.

    Only the same not-yet-kicked-off fixture may reuse its earlier observations.
    Never reuse odds, predicted probabilities, game outcomes or validation gates.
    A 4-day max age and an explicit cached label avoid claiming fresh reports.
    """
    if not isinstance(previous,dict):return dashboard
    from datetime import timedelta
    try:
        previous_time=datetime.fromisoformat(previous.get('generatedAt','').replace('Z','+00:00'))
        if previous_time.tzinfo is None:previous_time=previous_time.replace(tzinfo=timezone.utc)
    except (ValueError,TypeError):return dashboard
    if previous_time>now or now-previous_time>timedelta(days=4):return dashboard
    previous_games={g['id']:g for g in previous.get('nextGames',[]) if isinstance(g,dict) and g.get('id')}
    preserved=set()
    for game in dashboard.get('nextGames',[]):
        old=previous_games.get(game.get('id'))
        if not old or old.get('kickoff')!=game.get('kickoff'):continue
        # QB data has already been primed and updated with this run's new
        # ESPN source observation; never replace it with an older snapshot.
        if (dashboard.get('qbSource',{}).get('status')!='loaded' and
            not game.get('qbSourceEvidence')):
            old_qb=old.get('qbIntelligence') or {}
            if (old_qb.get('status')=='observed' and
                any((old_qb.get(side) or {}).get('sample') or
                    (old_qb.get(side) or {}).get('basis')=='depth_chart_projection'
                    for side in ('home','away'))):
                game['qbIntelligence']={**old_qb,'cachedFrom':previous_time.isoformat()}
                preserved.add('qb')
        if dashboard.get('tacticalSource',{}).get('status') not in ('loaded','partial'):
            old_tac=old.get('tactical') or {}
            if old_tac.get('status') in ('ready','insufficient'):
                game['tactical']={**old_tac,'cachedFrom':previous_time.isoformat()}
                preserved.add('tactical')
        if dashboard.get('injurySource',{}).get('status') not in ('loaded','partial','snapshot-only'):
            old_inj=old.get('injuryIntelligence') or {}
            if old_inj.get('status') in ('reported','snapshot-only'):
                game['injuryIntelligence']={**old_inj,'status':'snapshot-cached' if old_inj.get('status')=='snapshot-only' else 'reported-cached',
                    'note':'Cached from the previous full refresh, not a current injury check. '+old_inj.get('note',''),
                    'cachedFrom':previous_time.isoformat()}
                game['injuryStatus']='Previous report cached; may be outdated'
                preserved.add('injuries')
    key_to_meta={'qb':'qbSource','tactical':'tacticalSource','injuries':'injurySource'}
    for key in preserved:
        field=key_to_meta[key]
        old_meta=previous.get(field) or {}
        dashboard[field]={**old_meta,'status':'cached','cachedFrom':previous_time.isoformat(),
            'notes':'Cached previous verified full refresh; no new feed data fetched'}
    if preserved:
        dashboard.setdefault('dataWarnings',[]).append(
            'QB/tactical/injury context cached from '+previous_time.isoformat()+
            '; player reports are not live and may have changed.')
    return dashboard



def record_shadow_predictions(dashboard,games,now,path=Path('data/shadow-predictions-log.json')):
    """Archive each challenger probability before kickoff, never overwrite/backfill."""
    try:
        entries=json.loads(path.read_text()) if path.exists() else []
        if not isinstance(entries,list):entries=[]
    except (OSError,ValueError):entries=[]
    seen={r.get('gameId') for r in entries if isinstance(r,dict)}
    for item in dashboard.get('nextGames',[]):
        shadow=item.get('shadowEnsemble') or {}
        p=shadow.get('homeProbability')
        if not shadow.get('researchOnly') or not isinstance(p,(float,int)):continue
        try:kickoff=datetime.fromisoformat(item['kickoff'].replace('Z','+00:00'))
        except (ValueError,KeyError,TypeError):continue
        if kickoff.tzinfo is None or now>=kickoff or item.get('id') in seen or not 0<p<1:continue
        entries.append({'gameId':item['id'],'kickoff':kickoff.isoformat(),
            'recordedAt':now.isoformat(),'homeProbability':float(p),
            'baselineHomeProbability':item.get('baselineHomeProbability',item.get('homeProbability')),
            'model':'xgboost-shadow-research-v1','researchOnly':True})
        seen.add(item['id'])
    results={g['id']:g for g in games if g.get('home_score') is not None and
             g.get('away_score') is not None and g['kickoff']<now}
    scored=[]
    for e in entries:
        g=results.get(e.get('gameId'))
        if not g or g['home_score']==g['away_score']:continue
        try:
            recorded=datetime.fromisoformat(e['recordedAt'].replace('Z','+00:00'))
            kickoff=datetime.fromisoformat(e['kickoff'].replace('Z','+00:00'))
        except (ValueError,TypeError,KeyError):continue
        p=e.get('homeProbability')
        if recorded.tzinfo is None or kickoff.tzinfo is None or not recorded<kickoff:continue
        if not isinstance(p,(int,float)) or not 0<p<1:continue
        scored.append((p,int(g['home_score']>g['away_score'])))
    dashboard['shadowForwardPerformance']={
        'recordedPicks':len(entries),'gradedGames':len(scored),
        'brier':round(sum((p-y)**2 for p,y in scored)/len(scored),5) if scored else None,
        'accuracy':round(sum(int((p>=.5)==bool(y)) for p,y in scored)/len(scored),4) if scored else None,
        'source':'Immutable pregame XGBoost challenger picks; ties and late/backfilled entries excluded',
        'researchOnly':True}
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n')
    return entries

PBP_BACKFILL_SEASONS=8
PBP_FIRST_SUPPORTED_SEASON=2019

def pbp_history_seasons(current_season):
    """Bound full PBP research to eight available years, never future seasons."""
    start=max(PBP_FIRST_SUPPORTED_SEASON,current_season-PBP_BACKFILL_SEASONS+1)
    return range(start,current_season+1)


def apply_personnel_forecasts(dashboard,old_dashboard,now,source_mode,games):
    """Publish source-labelled, conditional QB and injury-aware forecasts.

    Only fresh, dated prior-QB OUT/DOUBTFUL status can activate a sizeable
    replacement model adjustment. A depth-chart projection alone shows a
    scenario but never assumes the projected QB actually starts. The old
    fixed QB absence rule is disabled to avoid duplicating the new model.
    """
    old_map={r.get('id'):r for r in old_dashboard.get('nextGames',[])
             if isinstance(r,dict)} if isinstance(old_dashboard,dict) else {}
    lookup={r['id']:r for r in games}
    active_counts={'statisticalQB':0,'replacementQB':0,'otherInjuries':0,
                   'conditionalQBScenarios':0,'suppressedOverlappingQB':0}
    for row in dashboard.get('nextGames',[]):
        baseline=float(row['homeProbability'])
        row['qbReplacement']={'status':'unavailable','affectsPrediction':False,'scenarios':[],
                              'reason':'No refreshed play-by-play / injury information'}
        if source_mode in ('full','evidence'):
            quality=row.get('forecastQuality') or {}
            candidate=qb_efficiency_preview(row,dashboard.get('qbValidation'))
            if quality and not quality.get('qbAutomationAllowed',False) and candidate.get('affectsPrediction'):
                candidate={**candidate,'status':'withheld-by-pregame-evidence-gate',
                    'candidateHomeDelta':candidate.get('homeDelta'),
                    'affectsPrediction':False,'homeProbability':baseline,
                    'homeDelta':0.,'marginDelta':0.,'factors':[],
                    'reason':'Material QB evidence missing or contradictory: hold numerical QB research overlay'}
            # The statistical QB overlay and the replacement model both
            # estimate QB performance. A documented NEW replacement takes
            # precedence: never stack two overlapping QB coefficients.
            observed_replacement=assess_replacement(row,now)
            if quality and not quality.get('qbAutomationAllowed',False) and observed_replacement.get('affectsPrediction'):
                observed_replacement={**observed_replacement,
                    'status':'withheld-by-pregame-evidence-gate',
                    'candidateHomeDelta':observed_replacement.get('homeDelta'),
                    'affectsPrediction':False,'homeProbability':baseline,
                    'homeDelta':0.,'marginDelta':0.,'factors':[],
                    'reason':'Official QB source disagreement or missing replacement evidence requires review'}
            if observed_replacement.get('affectsPrediction') and candidate.get('affectsPrediction'):
                q={**candidate,'status':'withheld-overlapping-replacement-impact',
                   'affectsPrediction':False,'homeProbability':baseline,'homeDelta':0.,
                   'marginDelta':0.,'factors':[],
                   'candidateHomeDelta':candidate.get('homeDelta'),
                   'reason':'Statistical QB coefficient suppressed because a reported QB replacement already changes the same matchup'}
                active_counts['suppressedOverlappingQB']+=1
            else:
                q=candidate
            qb_p=q['homeProbability'] if q.get('affectsPrediction') else baseline
            replacement=(observed_replacement if observed_replacement.get('affectsPrediction') or
                         not q.get('affectsPrediction') else
                         assess_replacement({**row,'homeProbability':qb_p},now))
            row['qbReplacement']=replacement
            repl_p=replacement['homeProbability'] if replacement.get('affectsPrediction') else qb_p
            # Never double charge the OUT QB through the older fixed-point rule:
            # the new replacement module handles QB status or leaves it unknown.
            injury=assess_personnel({**row,'homeProbability':repl_p},now,exclude_qb=True)
            final=injury['homeProbability'] if injury.get('affectsPrediction') else repl_p
            qactive=bool(q.get('affectsPrediction'))
            ractive=bool(replacement.get('affectsPrediction'))
            iactive=bool(injury.get('affectsPrediction'))
            if qactive:active_counts['statisticalQB']+=1
            if ractive:active_counts['replacementQB']+=1
            if iactive:active_counts['otherInjuries']+=1
            if replacement.get('scenarios'):active_counts['conditionalQBScenarios']+=1
            active=qactive or ractive or iactive
            flags=([name for on,name in ((qactive,'statistical QB'),
                     (ractive,'reported QB replacement'),(iactive,'other reported absences')) if on])
            s={**injury,'status':'+'.join(flags)+' — PROVISIONAL' if flags else
                       ('QB replacement scenario only' if replacement.get('scenarios')
                        else injury.get('status','no-qualifying-evidence')),
               'affectsPrediction':active,'validated':False,
               'homeProbability':round(final,5),
               'homeDelta':round(final-baseline,5),
               'qbStatisticalHomeDelta':round(qb_p-baseline,5),
               'qbReplacementHomeDelta':round(repl_p-qb_p,5),
               'injuryHomeDelta':round(final-repl_p,5),
               'marginDelta':round((q.get('marginDelta',0) if qactive else 0)+
                                   (replacement.get('marginDelta',0) if ractive else 0)+
                                   (injury.get('marginDelta',0) if iactive else 0),3),
               'factors':list(q.get('factors',[]) if qactive else [])+
                         list(replacement.get('factors',[]) if ractive else [])+
                         list(injury.get('factors',[]) if iactive else []),
               'statisticalQB':q,
               'qbReplacement':replacement,
               'sourceObservedAt':now.isoformat(),
               'sourceDetails':'Computed at refresh. ESPN media and depth-chart observations may be older.',
               'reason':(' + '.join(flags) if flags else replacement.get('reason') or
                         injury.get('reason') or 'No qualifying pregame evidence'),
               'uncertainty':'Provisional, no independent replacement injury calibration; official starter not confirmed.'}
        else:
            prior=old_map.get(row['id']) or {}
            s0=prior.get('personnelScenario') or {}
            stamp=s0.get('sourceObservedAt')
            try:observed=datetime.fromisoformat(str(stamp).replace('Z','+00:00'))
            except (ValueError,TypeError):observed=None
            if (prior.get('kickoff')==row.get('kickoff') and observed is not None
                and observed.tzinfo and now>=observed and
                (now-observed).total_seconds()<=24*3600):
                old_repl=prior.get('qbReplacement') or {}
                row['qbReplacement']={**old_repl,'status':
                    'cached '+old_repl.get('status','unavailable'),
                    'cachedFrom':stamp}
                delta=s0.get('homeDelta',0) if s0.get('affectsPrediction') else 0.
                final=round(max(.005,min(.995,baseline+delta)),5)
                s={**s0,'status':'cached provisional, not fresh',
                    'homeProbability':final,'homeDelta':round(final-baseline,5),
                    'sourceObservedAt':stamp,
                    'reason':'Previous published player/QB research retained for up to 24h. Not a new injury report.'}
                active=bool(s.get('affectsPrediction')) and abs(final-baseline)>.000001
            else:
                s={'status':'source-unavailable','validated':False,
                   'affectsPrediction':False,'homeProbability':baseline,
                   'homeDelta':0.,'marginDelta':0.,'factors':[],
                   'reason':'Schedule-only refresh cannot verify a QB replacement or new injury'}
                active=False
        row['personnelScenario']=s
        if not active:continue
        row['prePersonnelProbability']=baseline
        row['homeProbability']=round(s['homeProbability'],5)
        row['awayProbability']=round(1-row['homeProbability'],5)
        margin=s.get('marginDelta',0.)
        row['predMargin']=round(row.get('predMargin',0)+margin,2)
        row['predHome']=round(row.get('predHome',0)+margin/2,1)
        row['predAway']=round(row.get('predAway',0)-margin/2,1)
        row['favourite']=row['home'] if row['homeProbability']>=.5 else row['away']
        confidence=max(row['homeProbability'],row['awayProbability'])
        row['confidence']='High' if confidence>=.7 else 'Medium' if confidence>=.6 else 'Low'
        row['model']=(row.get('model') or 'Elo/form')+' + provisional QB/replacement and injury context'
        row['personnelEstimateValidated']=False
        if row['id'] in lookup:
            row['simulation']=forecast_simulate(lookup[row['id']],
                                  {'margin':row['predMargin'],'total':row['predTotal']})
        if row.get('scenarios'):
            row['scenarios'][0]['text']=(
                f"Provisional QB-aware estimate: {row['home']} {row['predHome']:.1f}, "
                f"{row['away']} {row['predAway']:.1f}. "
                "Estimated QB replacement and injury effects are research assumptions, "
                "not certified player availability or calibrated prediction improvement.")
    # Separate probability from verification. A numerical 75% does NOT become
    # an endorsed high-confidence pick when QB reports are disputed or absent.
    for row in dashboard.get('nextGames',[]):
        row['modelConfidence']=row.get('confidence')
        quality=row.get('forecastQuality') or {}
        if not quality.get('highConfidenceEligible',False):
            row['confidence']='Unverified'
    # One published probability, with additive, explicit contributions
    # for every weighted layer and truthful no-weight context layers.
    for row in dashboard.get('nextGames',[]):
        row['forecastExplanation']=explain_forecast_layers(row)
    dashboard['qbReplacementSource']={
        'status':'fresh-secondary-source-review' if source_mode=='evidence' else
                 'full-source-review' if source_mode=='full' else 'cached-or-unavailable',
        'counts':active_counts,
        'notes':'Projected QB change alone never confirms an absence or triggers the full replacement-point adjustment. Conditional scenarios are unvalidated; dated media reporting required for activation.'}
    return dashboard

def prime_cached_qb_history(dashboard,previous,now):
    """Reuse up-to-36h PBP QB history for lighter ESPN source-only refreshes.

    Unlike injuries, QB history is immutable until games finish. A fetched
    ESPN depthchart or injury list is then attached separately; a prior
    provisional probability is NEVER reused. Expiration cannot be extended
    by repeated lightweight refreshes.
    """
    from datetime import timedelta
    if not isinstance(previous,dict):return 0
    old_games={g.get("id"):g for g in previous.get("nextGames",[])
               if isinstance(g,dict)}
    copied=0
    for game in dashboard.get("nextGames",[]):
        prior=old_games.get(game.get("id"))
        if not prior or game.get("kickoff")!=prior.get("kickoff"):continue
        at=prior.get("qbHistoryAsOf")
        try:stamp=datetime.fromisoformat(str(at).replace("Z","+00:00"))
        except (ValueError,TypeError):continue
        if not stamp.tzinfo or stamp>now or now-stamp>timedelta(hours=36):continue
        qb=prior.get("qbIntelligence") or {}
        if qb.get("status")!="observed":continue
        # Only prior completed games and point-in-time model features are used.
        game["qbIntelligence"]=json.loads(json.dumps(qb))
        game["qbHistoryAsOf"]=stamp.isoformat()
        game["personnelDepthChart"]=json.loads(json.dumps(prior.get("personnelDepthChart") or {}))
        game["qbResearch"]=json.loads(json.dumps(prior.get("qbResearch") or {}))
        copied+=1
    if copied and isinstance(previous.get("qbValidation"),dict):
        dashboard["qbValidation"]=previous["qbValidation"]
    return copied


def update(schedules_only=False,schedules_file=None):
    games,source=get_schedule(schedules_file)
    old_dashboard_path=Path('data/dashboard.json')
    try:old_dashboard=json.loads(old_dashboard_path.read_text()) if old_dashboard_path.exists() else {}
    except (OSError,ValueError):old_dashboard={}
    log_path=Path('data/predictions-log.json')
    log=json.loads(log_path.read_text()) if log_path.exists() else []
    previous_first_ids={x.get('gameId') for x in log if isinstance(x,dict)}
    now=datetime.now(timezone.utc)
    current=now.year if now.month>=3 else now.year-1
    qb_plays={}
    snap_rows=[]
    snap_meta={'status':'unavailable','source':'nflreadpy snap counts', 'note':'Not downloaded on lightweight refresh'}
    if schedules_only:
        pbp={};loaded=[];errors=['Skipped optional play-by-play files in schedules-only mode']
        injuries=[];depth=[]
        player_meta={'injuries':{'status':'unavailable','loadedSeasons':[]},
                     'depth':{'status':'unavailable','loadedSeasons':[]}}
    else:
        pbp,loaded,errors=load_nflverse_pbp(pbp_history_seasons(current),qb_sink=qb_plays)
        injuries,depth,player_meta=load_historical_reports(current)
        snap_rows,snap_meta=load_snap_counts(range(max(2025,current-1),current+1))
    # ESPN media reports are cheap enough to check on both full and lightweight runs.
    supplemental,supplemental_meta=load_espn_injuries()
    # Forecast timestamp must follow all source fetches. Otherwise a new undated
    # injury snapshot appears to come from the future and is incorrectly rejected.
    now=datetime.now(timezone.utc)
    meta={'status':'loaded' if loaded and not errors else 'partial' if loaded else 'unavailable',
          'seasons':loaded,'errors':errors,'requestedSeasons':list(pbp_history_seasons(current)) if not schedules_only else [],'source':'nflverse play_by_play_{year}.parquet'}
    dashboard,log=generate(games,now,log,pbp,meta,qb_games=qb_plays,
                           injury_rows=injuries,depth_rows=depth,player_meta=player_meta)
    if not qb_plays:
        dashboard['qbSource']['status']='schedule-history-only'
        dashboard['qbSource']['source']='Previous recorded starting QB from completed nflverse schedule entries; no PBP statistics'
    # Additional ESPN injury-watch items are informational, and apply only to
    # future fixtures. They never become official status or training inputs.
    if not schedules_only or supplemental_meta.get('status') in ('loaded','empty'):
        for g in dashboard.get('nextGames',[]):
            g['supplementalInjuryWatch']={
                'away':supplemental.get(g['away'],[])[:12],
                'home':supplemental.get(g['home'],[])[:12],
                'status':supplemental_meta['status'],
                'retrievedAt':supplemental_meta.get('retrievedAt'),
                'note':supplemental_meta.get('note','')}
    else:
        old_map={g['id']:g for g in old_dashboard.get('nextGames',[]) if isinstance(g,dict) and g.get('id')}
        for g in dashboard.get('nextGames',[]):
            old=old_map.get(g['id'])
            prior=(old or {}).get('supplementalInjuryWatch') or {}
            if old and old.get('kickoff')==g.get('kickoff') and prior.get('status') in ('loaded','cached'):
                try:
                    stamp=datetime.fromisoformat(prior.get('retrievedAt','').replace('Z','+00:00'))
                    if stamp.tzinfo and (now-stamp).total_seconds()<48*3600 and now>=stamp:
                        g['supplementalInjuryWatch']={**prior,'status':'cached',
                            'note':'Older ESPN media injury list retained from a full refresh. Not a current injury check.'}
                        supplemental_meta={**old_dashboard.get('additionalInjurySource',{}),'status':'cached','retrievedAt':stamp.isoformat()}
                except (ValueError,TypeError):pass
    dashboard['additionalInjurySource']=supplemental_meta

    # The secondary ESPN sources are OBSERVATIONS, not actual NFL starters.
    # They are retrieved after the main historical model run. Update the
    # publication timestamp only AFTER both media and chart feeds complete,
    # so an archived first pick cannot predate evidence used for that pick.
    if schedules_only:
        reused=prime_cached_qb_history(dashboard,old_dashboard,now)
    else:
        reused=0
        if qb_plays:
            for g in dashboard.get('nextGames',[]):g['qbHistoryAsOf']=now.isoformat()
    second,second_meta=gather_qb_sources(dashboard.get('nextGames',[]),datetime.now(timezone.utc))
    now=datetime.now(timezone.utc)
    dashboard['generatedAt']=now.isoformat()
    for g in dashboard.get('nextGames',[]):
        attach_qb_sources(g,second,second_meta,now)
    # NFL official WEEKLY game/practice status fields, mirrored by nflverse.
    # Fetch on light refreshes too; the previous full-mode source was loaded
    # during the model build and can be reused with identical date provenance.
    if schedules_only:
        weekly_rows,weekly_meta=fetch_weekly_reports(current,datetime.now(timezone.utc))
    else:
        weekly_rows,weekly_meta=reuse_weekly_reports(injuries,current,datetime.now(timezone.utc))
    now=datetime.now(timezone.utc)
    dashboard['generatedAt']=now.isoformat()
    for fixture in dashboard.get('nextGames',[]):
        attach_weekly_reports(fixture,weekly_rows,weekly_meta,now)
        # The official weekly game-status designation is the authoritative
        # *report* field; its timestamp is preserved. It is NOT a confirmed QB
        # starter or final active/inactive list. ESPN media remains visible as
        # an independent source so contradictions can be detected by the gate.
        media=fixture.setdefault('supplementalInjuryWatch',{'status':'unavailable'})
        for side in ('home','away'):
            reports=(fixture.get('officialInjuryEvidence') or {}).get(side,{}).get('rows',[])
            for rec in reports:
                if rec.get('gameStatus') and rec.get('reportDate'):
                    media.setdefault(side,[]).append({
                        'name':rec.get('name'),'position':rec.get('position'),
                        'status':rec['gameStatus'],'injury':rec.get('injury'),
                        'reportDate':rec['reportDate'],'source':rec['source'],
                        'officialGameStatus':False, # source is a dated MIRROR, not direct NFL.com
                        'officialReportDerived':True,
                        'starterConfirmed':False})
            if reports:media['status']='loaded'
        fixture['forecastQuality']=verify_pregame_evidence(fixture,now)
    quality_counts={'checked':0,'review':0,'hold':0,'closed':0}
    for fixture in dashboard.get('nextGames',[]):
        key=fixture['forecastQuality']['level']
        quality_counts[key]=quality_counts.get(key,0)+1
    dashboard['pregameVerificationSource']={
        'status':weekly_meta.get('status'),
        'sourceType':'official-report-derived-mirror',
        'officialReference':'https://www.nfl.com/injuries/',
        'weeklyReports':weekly_meta,
        'qualityCounts':quality_counts,
        'note':'Weekly official game-status fields are accessed from nflverse mirror; no direct NFL.com starting lineup or inactive-list feed is connected. Forecasts on hold cannot trigger value alerts.'}
    dashboard['qbEvidenceSource']={**second_meta,
        'historicalQBReusedOnLightweight':reused,
        'nflverseDepthSource':dashboard.get('depthSource',{}).get('source'),
        'mediaSource':supplemental_meta.get('source'),
        'notes':second_meta.get('notes','')+
            ' Already completed historical QB plays may be reused for up to 36h. ESPN feed access may fail; missing sources are not imputed.'}
    if snap_rows:
        snap_meta['watchItemsEnriched']=enrich_upcoming(
            dashboard.get('nextGames',[]),UsageHistory(snap_rows,games),now)
    elif schedules_only and any(
        item.get('recentUsage') for g in dashboard.get('nextGames',[])
        for side in ('home','away')
        for item in (g.get('supplementalInjuryWatch') or {}).get(side,[])):
        snap_meta={'status':'cached','source':'Previous snap-count observation',
            'note':'Past snap participation carried forward, not a live player availability check'}
    dashboard['playerUsageSource']=snap_meta
    # A lightweight refresh can re-evaluate NEW dated reports against earlier
    # completed QB history. The experimental adjustment is still labelled
    # provisional and a missing history prevents statistical QB repricing.
    dashboard=apply_personnel_forecasts(dashboard,old_dashboard,now,
                                       'evidence' if schedules_only else 'full',games)
    # The first published forecast is immutable; new fixture entries must
    # match the final publish-time model, not the earlier unadjusted stage.
    current_rows={row['id']:row for row in dashboard.get('nextGames',[])}
    for item in log:
        if item.get('gameId') in previous_first_ids:continue
        item['recordedAt']=now.isoformat()  # first public forecast follows evidence retrieval
        row=current_rows.get(item.get('gameId'))
        if not row:continue
        item['homeProbability']=round(row['homeProbability'],5)
        item['baselineHomeProbability']=round(row.get('baselineHomeProbability',row['homeProbability']),5)
        item['personnelStatus']=(row.get('personnelScenario') or {}).get('status')
        item['personnelHomeDelta']=(row.get('personnelScenario') or {}).get('homeDelta',0)
        item['predMargin']=row.get('predMargin')
        item['overlayType']=row.get('overlayType','none')
        item['verificationLevel']=(row.get('forecastQuality') or {}).get('level','unavailable')
        item['verificationReasons']=(row.get('forecastQuality') or {}).get('issues',[])[:8]
    record_shadow_predictions(dashboard,games,now)
    save_forecast_revisions(dashboard,log,games,now)
    dashboard=preserve_recent_player_context(dashboard,old_dashboard,now)
    # Schedules-only refresh cannot recompute historical play-by-play accuracy.
    if schedules_only:
        old_lab=old_dashboard.get('signalAccuracyLab') or {}
        if old_lab.get('evaluatedGames',0)>0 and not dashboard.get('signalAccuracyLab',{}).get('evaluatedGames'):
            dashboard['signalAccuracyLab']={**old_lab,
                'status':'cached historical research — not recalculated',
                'cachedAt':now.isoformat(),
                'notes':list(old_lab.get('notes') or [])+
                    ['This historical research was retained from a previous full PBP refresh.']}
    # Independent, public area forecast only: never changes win percentages.
    # Every fixture records the roof status, horizon and source availability.
    dashboard['weatherSource']=enrich_weather(dashboard.get('nextGames',[]),now)

    if any((r.get('personnelScenario') or {}).get('affectsPrediction') for r in dashboard.get('nextGames',[])):
        dashboard['dataWarnings'].append(
            'Published win chances may include a provisional media-injury/QB scenario. Its assumed point adjustments have NOT passed historical or forward validation.')
    if dashboard.get('injurySource',{}).get('status')=='snapshot-only':
        dashboard.setdefault('dataWarnings',[]).append('Current-season injury records have no individual report timestamps; displayed only as observed downloaded snapshots, not used for historical model fitting.')
    dashboard['source']=source['url'];dashboard['sourceUrl']=source['url'];dashboard['dataProvenance']=source
    dashboard['refreshMode']='schedules-only' if schedules_only else 'full'
    latest=source.get('latestFinalAt')
    if latest:
        days=(now-datetime.fromisoformat(latest)).total_seconds()/86400
        dashboard['sourceLagDays']=round(days,1)
        # During the main NFL calendar, a large gap between final scores and
        # refresh time is worth investigating. This is not a live-game feed.
        if (now.month>=9 or now.month<=1) and days>10:
            dashboard['dataWarnings'].append('Latest confirmed final score is over 10 days old; verify schedule-source freshness')
    if schedules_only:
        dashboard['dataWarnings'].append('Lightweight refresh: new tactical, QB statistics and injury updates were not fetched; previous observations may be cached')
    out=Path('data/dashboard.json');out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(dashboard,ensure_ascii=False,indent=2)+'\n')
    # A machine-readable publication audit, separate from the frozen historical
    # research snapshot.  An absent feed is recorded as unavailable, not zero.
    audit_report={
        'generatedAt':now.isoformat(),
        'status':'production-pipeline-snapshot',
        'source':source,
        'mode':dashboard['refreshMode'],
        'latestResultAt':dashboard.get('latestResultAt'),
        'baseline':dashboard.get('historicalAudit'),
        'situationalValidation':dashboard.get('situationalValidation'),
        'tacticalValidation':dashboard.get('tacticalValidation'),
        'signalAccuracyLab':dashboard.get('signalAccuracyLab'),
        'playerValidation':dashboard.get('playerValidation'),
        'qbValidation':dashboard.get('qbValidation'),
        'qbReplacementResearch':dashboard.get('qbReplacementResearch'),
        'qbReplacementSource':dashboard.get('qbReplacementSource'),
        'qbEvidenceSource':dashboard.get('qbEvidenceSource'),
        'pregameVerificationSource':dashboard.get('pregameVerificationSource'),
        'weatherSource':dashboard.get('weatherSource'),
        'chosenOverlay':dashboard.get('overlaySelection','none'),
        'tacticalSource':dashboard.get('tacticalSource'),
        'qbSource':dashboard.get('qbSource'),
        'injurySource':dashboard.get('injurySource'),
        'depthSource':dashboard.get('depthSource'),
        'additionalInjurySource':dashboard.get('additionalInjurySource'),
        'playerUsageSource':dashboard.get('playerUsageSource'),
        'challengerValidation':dashboard.get('challengerValidation'),
        'shadowForwardPerformance':dashboard.get('shadowForwardPerformance'),
        'forecastRevisionSummary':dashboard.get('forecastRevisionSummary'),
        'forecastRevisionResults':dashboard.get('forecastRevisionResults',[]),
        'predictionRecord':dashboard.get('predictionRecord'),
        'personnelModelStatus':'EXPERIMENTAL — reported injury/QB scenario assumptions, no validated active player coefficient',
        'forwardPredictions':dashboard.get('forwardPredictions'),
        'forwardPerformance':dashboard.get('forwardPerformance'),
        'warnings':dashboard.get('dataWarnings',[]),
        'disclaimer':'Research validation is not a prospective betting edge. Only timestamped forward picks support forward performance.'
    }
    Path('data/full-model-audit.json').write_text(json.dumps(audit_report,ensure_ascii=False,indent=2)+'\n')
    # Keep original, immutable forecasts as published; refresh cannot modify them.
    log_path.write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n')
    print(f"Verified {source['parsedGames']} games. Updated {len(dashboard['nextGames'])} upcoming fixtures, "
          f"{dashboard['performance']['count']} historical backtests; "
          f"paired closing-price audit n={dashboard['historicalAudit']['overall']['marketCoverage']}. "
          f"Mode: {dashboard['refreshMode']}")

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--schedules-only',action='store_true',help='Skip optional PBP/injuries for fast, free refresh')
    ap.add_argument('--schedules-file',help='Use a local, genuine nflverse games.csv (reproducible offline)')
    args=ap.parse_args()
    try:
        update(schedules_only=args.schedules_only,schedules_file=args.schedules_file)
    except Exception as exc:
        print(f'Unable to refresh verified NFL data: {exc}',file=sys.stderr)
        sys.exit(1)
