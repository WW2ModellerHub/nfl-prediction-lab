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
from tactical import load_nflverse_pbp
from qb_injuries import load_historical_reports

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


def update(schedules_only=False,schedules_file=None):
    games,source=get_schedule(schedules_file)
    log_path=Path('data/predictions-log.json')
    log=json.loads(log_path.read_text()) if log_path.exists() else []
    now=datetime.now(timezone.utc)
    current=now.year if now.month>=3 else now.year-1
    qb_plays={}
    if schedules_only:
        pbp={};loaded=[];errors=['Skipped optional play-by-play files in schedules-only mode']
        injuries=[];depth=[]
        player_meta={'injuries':{'status':'unavailable','loadedSeasons':[]},
                     'depth':{'status':'unavailable','loadedSeasons':[]}}
    else:
        pbp,loaded,errors=load_nflverse_pbp(range(max(2021,current-5),current+1),qb_sink=qb_plays)
        injuries,depth,player_meta=load_historical_reports(current)
    meta={'status':'loaded' if loaded and not errors else 'partial' if loaded else 'unavailable',
          'seasons':loaded,'errors':errors,'source':'nflverse play_by_play_{year}.parquet'}
    dashboard,log=generate(games,now,log,pbp,meta,qb_games=qb_plays,
                           injury_rows=injuries,depth_rows=depth,player_meta=player_meta)
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
        dashboard['dataWarnings'].append('Lightweight refresh: tactical, QB and injury feeds were deliberately not loaded')
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
        'playerValidation':dashboard.get('playerValidation'),
        'chosenOverlay':dashboard.get('overlaySelection','none'),
        'tacticalSource':dashboard.get('tacticalSource'),
        'qbSource':dashboard.get('qbSource'),
        'injurySource':dashboard.get('injurySource'),
        'depthSource':dashboard.get('depthSource'),
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
