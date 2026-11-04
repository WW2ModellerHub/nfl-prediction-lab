"""Build a self-contained, pinned, clearly non-live v1.6 demo.

The reference-slate file is an independently reproduced Elo+form snapshot
of actual scheduled games as of 3 Nov 2026. It is not used for production
forecasts. Real production forecasts come only from scripts/update.py.
"""
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from model import TEAM_NAMES,simulate

ROOT=Path(__file__).resolve().parent.parent
AUDIT=json.loads((ROOT/'data/audit-reference.json').read_text())
RESEARCH=json.loads((ROOT/'data/situational-research.json').read_text())
SLATE=json.loads((ROOT/'data/reference-slate.json').read_text())


def fixture(x):
    kickoff=datetime.fromisoformat(x['day']+'T'+x['time']).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(ZoneInfo('UTC'))
    home=x['home'];away=x['away'];p=x['p'];m=x['margin'];t=x['total']
    neutral_situation={'home':{'team':home,'fullRestDays':None,'previous':None},
                       'away':{'team':away,'fullRestDays':None,'previous':None},'signals':[],
                       'status':'Unavailable in independent archived reference; full production source required'}
    return {'id':x['id'],'season':2026,'week':9,'type':'REG','home':home,'away':away,
      'homeName':TEAM_NAMES[home],'awayName':TEAM_NAMES[away], 'kickoff':kickoff.isoformat(),
      'homeProbability':p,'awayProbability':round(1-p,4),'predMargin':m,'predTotal':t,
      'predHome':round((t+m)/2,1),'predAway':round((t-m)/2,1),
      'favourite':home if p>=.5 else away,'confidence':'High' if max(p,1-p)>=.70 else 'Medium' if max(p,1-p)>=.60 else 'Low',
      'eloHome':'—','eloAway':'—','formHome':'—','formAway':'—','allowedHome':'—','allowedAway':'—',
      'baselineHomeProbability':p,'adjustmentActive':False,'overlayType':'none','model':'2026-11-03 Elo + form archived reconstruction',
      'injuryStatus':'No verified source in pinned reference','weatherStatus':'Not integrated',
      'qbIntelligence':{'status':'unavailable','home':None,'away':None,'reason':'No QB archive in reference snapshot'},
      'injuryIntelligence':{'status':'unavailable','home':[],'away':[],'note':'No archived injury data'},
      'playerImpact':{'status':'informational','eligible':False,'reason':'Missing archived player records','home':{},'away':{}},
      'playerProbabilityDelta':0,'tacticalProbabilityDelta':0,
      'tactical':{'status':'unavailable','reason':'PBP data not included in independent reference','advantages':[]},
      'situation':neutral_situation,
      'simulation':simulate({'id':x['id']},{'margin':m,'total':t}),
      'scenarios':[{'name':'Baseline','text':'Statistical score projection. Tactical and personnel adjustments are not in this pinned snapshot.'},
                   {'name':'Uncertainty','text':'Game outcome variance may be considerable; these are not validated player-level or live forecasts.'}]}


def build():
    perf=AUDIT['overall']['baseline']
    games=[fixture(x) for x in SLATE]
    data={'schemaVersion':3,'dataStatus':'ok','previewMode':True,'generatedAt':AUDIT['asOf'],
          'dataWarnings':['PINNED as-of 3 Nov 2026 — not live',
          'Fixture schedule is real; research probabilities independently reconstructed from historical scores',
          'No PBP, injuries, live scores or bookmaker prices attached'],
          'source':'nflverse/nfldata pinned historical source','nextGames':games,
          'recentResults':[],'powerRankings':[],'performance':{'count':perf['games'],'accuracy':perf['accuracy'],'brier':perf['brier'],
              'logLoss':perf['logLoss'],'baselineBrier':.25,'calibration':[]},
          'recentPerformance':{'count':0},'forwardPerformance':{'count':0},'forwardResults':[],
          'forwardPredictions':0,'historicalAudit':AUDIT,
          'tacticalSource':{'status':'unavailable','seasons':[]},'qbSource':{'status':'unavailable'},
          'injurySource':{'status':'unavailable'},'depthSource':{'status':'unavailable'},
          'overlaySelection':'none','playerValidation':None,'tacticalValidation':None,'situationalValidation':None,
          'situationalStats':[],'playerImpactSource':{'verifiedInjurySeasons':[],'historicalSnapshotsAvailable':False},
          'refreshMode':'archived-reference'}
    html=(ROOT/'index.html').read_text()
    html=html.replace('<link rel="stylesheet" href="assets/styles.css" />',
                      '<style>'+ (ROOT/'assets/styles.css').read_text()+'</style>')
    html=html.replace('<script src="assets/app.js" defer></script>',
                      '<script>window.NFL_LAB_EMBEDDED_DATA='+json.dumps(data,ensure_ascii=False).replace('</','<\\/')+';'
                      +'window.NFL_LAB_AUDIT_REFERENCE='+json.dumps(AUDIT,ensure_ascii=False).replace('</','<\\/')+';'
                      +'window.NFL_LAB_RESEARCH_EVIDENCE='+json.dumps(RESEARCH,ensure_ascii=False).replace('</','<\\/')+';</script>'
                      +'<script>'+(ROOT/'assets/app.js').read_text()+'</script>')
    html=html.replace('<link rel="icon" href="assets/favicon.svg" type="image/svg+xml" />','')
    outfile=ROOT.parent/'NFL_Prediction_Lab_v1_7_Demo.html'
    outfile.write_text(html)
    print(f'{len(games)} real archived fixtures, self-contained demo at {outfile}')
    return outfile

if __name__=='__main__':build()
