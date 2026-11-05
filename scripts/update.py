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
from qb_injuries import load_historical_reports
from espn_injuries import load as load_espn_injuries
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
        if dashboard.get('qbSource',{}).get('status')!='loaded':
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

def update(schedules_only=False,schedules_file=None):
    games,source=get_schedule(schedules_file)
    old_dashboard_path=Path('data/dashboard.json')
    try:old_dashboard=json.loads(old_dashboard_path.read_text()) if old_dashboard_path.exists() else {}
    except (OSError,ValueError):old_dashboard={}
    log_path=Path('data/predictions-log.json')
    log=json.loads(log_path.read_text()) if log_path.exists() else []
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
        pbp,loaded,errors=load_nflverse_pbp(range(max(2023,current-3),current+1),qb_sink=qb_plays)
        injuries,depth,player_meta=load_historical_reports(current)
        snap_rows,snap_meta=load_snap_counts(range(max(2025,current-1),current+1))
    supplemental, supplemental_meta = ({}, {'status':'unavailable','note':'Not fetched on lightweight runs'})
    if not schedules_only:
        supplemental,supplemental_meta=load_espn_injuries()
    # Forecast timestamp must follow all source fetches. Otherwise a new undated
    # injury snapshot appears to come from the future and is incorrectly rejected.
    now=datetime.now(timezone.utc)
    meta={'status':'loaded' if loaded and not errors else 'partial' if loaded else 'unavailable',
          'seasons':loaded,'errors':errors,'source':'nflverse play_by_play_{year}.parquet'}
    dashboard,log=generate(games,now,log,pbp,meta,qb_games=qb_plays,
                           injury_rows=injuries,depth_rows=depth,player_meta=player_meta)
    if not qb_plays:
        dashboard['qbSource']['status']='schedule-history-only'
        dashboard['qbSource']['source']='Previous recorded starting QB from completed nflverse schedule entries; no PBP statistics'
    # Additional ESPN injury-watch items are informational, and apply only to
    # future fixtures. They never become official status or training inputs.
    if not schedules_only:
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
    record_shadow_predictions(dashboard,games,now)
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
