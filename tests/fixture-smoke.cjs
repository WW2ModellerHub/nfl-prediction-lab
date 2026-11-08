/* Regression test: every rendered fixture opens a shareable, full matchup page. */
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'..','assets','app.js'),'utf8');
const marker="window.addEventListener('DOMContentLoaded',start);";
assert(source.includes(marker),'Dashboard startup signature changed');
const code=source.replace(marker,'window.__SMOKE__={setData:d=>{store.data=d},handleClick,openGamePage,syncRoute,render,openGame};'+marker);
const elements={};
const el=id=>elements[id]||(elements[id]={innerHTML:'',textContent:'',setAttribute(){},classList:{add(){},remove(){},toggle(){}},close(){},showModal(){this.opened=true}});
const document={getElementById:el,querySelectorAll:()=>[],querySelector:()=>el('sidebar')};
const window={location:{hash:'',href:'https://example.org/lab/'},scrollTo(){},addEventListener(){}};
const localStorage={getItem(){return null},setItem(){}};
window.NFLMatchupIntelligence=require(path.join(__dirname,'..','assets','matchup-intelligence.js'));
vm.runInNewContext(code,{window,document,localStorage,console,Date,Math,JSON,URL,Intl,navigator:{},setTimeout,clearTimeout},{filename:'app.js',timeout:5000});
const game={id:'test_fixture',week:9,kickoff:'2026-11-06T01:15:00Z',
 away:'JAX',home:'BAL',awayName:'Jacksonville Jaguars',homeName:'Baltimore Ravens',
 model:'Elo and form',confidence:'Low',homeProbability:.47,awayProbability:.53,
 predHome:22,predAway:24,predTotal:46,predMargin:-2,formHome:22,formAway:24,
 allowedHome:24,allowedAway:20,eloHome:1500,eloAway:1540,
 injuryStatus:'Unknown',weatherStatus:'Unavailable',simulation:[],scenarios:[],
 situation:{signals:[],home:{fullRestDays:4,previous:{overtime:false}},away:{fullRestDays:5,previous:{overtime:true}}},
 tactical:{status:'unavailable',reason:'Pending feed',advantages:[]},
 qbIntelligence:{status:'observed',home:{qb:'Quarterback H',label:'Unconfirmed'},away:{qb:'Quarterback A',label:'Unconfirmed'}},
 injuryIntelligence:{status:'unavailable',home:[],away:[]}};
window.__SMOKE__.setData({nextGames:[game],generatedAt:'2026-11-05T18:00:00Z'});
window.__SMOKE__.handleClick({target:{closest:()=>({dataset:{open:game.id}})}});
assert.equal(window.location.hash,'#game=test_fixture','Fixture URL not updated');

// v2.9: actual win/loss dashboard, separate from historical backtests.
window.__SMOKE__.setData({nextGames:[game],
 predictionRecord:{status:'timestamped-forward-grading',completed:{
 games:1,original:{games:1,wins:1,losses:0,accuracy:1,brier:.221097},
 latest:{games:1,wins:1,losses:0,accuracy:1,brier:.221097}},
 recent10:{games:1,latest:{wins:1,losses:0,accuracy:1}},
 smallSample:true,upcomingCount:1,awaitingFinalCount:0,
 latestResults:[{gameId:'2026_09_JAX_BAL',season:2026,week:9,
 home:'BAL',away:'JAX',kickoff:'2026-11-06T01:15:00Z',
 originalPick:'JAX',originalWinProbability:.52979,originalCorrect:true,
 latestPick:'JAX',latestWinProbability:.52979,latestCorrect:true,
 awayScore:33,homeScore:10,originalRecordedAt:'2026-11-04T20:34:50Z',
 latestRecordedAt:'2026-11-04T20:34:50Z',revisionCount:0,changed:false}],
 byWeek:[{season:2026,week:9,games:1,
 original:{wins:1,losses:0,accuracy:1},latest:{wins:1,losses:0,accuracy:1}}],
 upcoming:[{gameId:'test_fixture',home:'BAL',away:'JAX',kickoff:'2026-11-12T13:00:00Z',
 originalPick:'JAX',originalProbability:.53,latestPick:'BAL',latestProbability:.55}]},
 generatedAt:'2026-11-07T19:30:00Z'});
window.location.hash='#tab=performance';
window.__SMOKE__.syncRoute();
const recordHtml=el('appContent').innerHTML;
assert.match(recordHtml,/Our actual prediction record/i);
assert.match(recordHtml,/1–0/);
assert.match(recordHtml,/100\.0% correct/);
assert.match(recordHtml,/too few games|too few to call|too few to judge/i);
assert.match(recordHtml,/JAX 33 – BAL 10/i);
assert.match(recordHtml,/JAX 53\.0%/i);
assert.match(recordHtml,/Complete source log/i);
assert.match(recordHtml,/Weekly win\/loss record/i);
assert.match(recordHtml,/Predictions waiting for kickoff/i);
assert.doesNotMatch(recordHtml,/15 snapshots/i);
window.location.hash='#tab=overview';
window.__SMOKE__.syncRoute();
assert.match(el('appContent').innerHTML,/Actual prediction record/i);
assert.match(el('appContent').innerHTML,/1–0/i);
window.location.hash='#game=test_fixture';
window.__SMOKE__.syncRoute();
assert.doesNotMatch(el('appContent').innerHTML,/Our actual prediction record/i,'No long record on individual matchup');

assert.match(el('appContent').innerHTML,/FULL MATCHUP DOSSIER/i,'Dossier not rendered in page');
assert.match(el('appContent').innerHTML,/Quarterbacks, practice and injuries/i);
assert.match(el('appContent').innerHTML,/Copy matchup link/i);
assert.match(el('appContent').innerHTML,/Why each team could win/i);
assert.match(el('appContent').innerHTML,/Player availability exposure/i);

// v2.8: one primary winner probability; the move of every weighted layer
// is reconciled, while unweighted research is explicitly 'Not applied'.
const explained={...game,homeProbability:.39,awayProbability:.61,
 baselineHomeProbability:.47,prePersonnelProbability:.47,
 forecastHistoryCount:15,
 originalForecast:{homeProbability:.404},
 forecastExplanation:{status:'provisional',homeProbability:.39,
 winner:'JAX',winnerProbability:.61,reconciles:true,
 layers:[
 {key:'elo',label:'Elo strength & home field',applied:true,
  deltaHome:-.03,afterHome:.47,kind:'core'},
 {key:'form',label:'Scoring form & projected margin',applied:true,
  deltaHome:0,afterHome:.47,kind:'core'},
 {key:'qb-statistical',label:'QB efficiency research',applied:true,
  deltaHome:-.08,afterHome:.39,kind:'provisional'},
 {key:'tactical',label:'Passing, rushing & pressure',applied:false,
  deltaHome:null,kind:'not-weighted',
  explanation:'Historical validation gate is off'},
 {key:'weather',label:'Weather & venue conditions',applied:false,
  deltaHome:null,kind:'not-weighted',
  explanation:'Weather has no independently validated probability weight'}],
 warnings:['Provisional research is not forward validated']}};
window.__SMOKE__.setData({nextGames:[explained],generatedAt:'2026-11-05T18:00:00Z'});
window.__SMOKE__.syncRoute();
const explainedHTML=el('appContent').innerHTML;
assert.match(explainedHTML,/one-forecast-number[^>]*>61\.0%/,'Single dominant winner probability must render');
assert.match(explainedHTML,/Jacksonville Jaguars to win/);
assert.match(explainedHTML,/How we got to 61\.0%/);
assert.match(explainedHTML,/Elo strength &amp; home field/);
assert.match(explainedHTML,/QB efficiency research/);
assert.match(explainedHTML,/\+3\.0 pp/,'Home negative contribution should help the AWAY winner');
assert.match(explainedHTML,/\+8\.0 pp/,'QB home negative contribution should help the AWAY winner');
assert.match(explainedHTML,/Not applied/,'Unweighted layers must not claim numerical effects');
assert.match(explainedHTML,/class="matchup-evidence"/,'All supporting evidence must remain accessible but collapsed');
assert.doesNotMatch(explainedHTML,/Saved pre-game predictions/,'Remove repetitive pregame prediction snapshots from matchup');
assert.doesNotMatch(explainedHTML,/15 snapshots/,'Never render archived revision counts in the main matchup');
assert.doesNotMatch(explainedHTML,/FIRST RECORDED HOME WIN/,'No old 3-column revision-summary panel');
assert.doesNotMatch(source,/revisions:\['Prediction History'/,'Remove redundant Prediction History main nav');
const oldForecast={...game,homeProbability:.53,awayProbability:.47};
window.__SMOKE__.setData({nextGames:[oldForecast],generatedAt:'2026-11-05T18:00:00Z'});
window.__SMOKE__.syncRoute();

const evidenceHeld={...game,forecastQuality:{
 level:'hold',status:'manual-verification-required',bettingEligible:false,
 riskSummary:'Two quarterbacks out, projected starter not officially confirmed',
 issues:['BAL: 2 QBs designated unavailable','BAL: sources disagree'],
 teamChecks:[{team:'BAL',establishedQB:'Franchise QB',
   projectedQB:'Third QB',qbProjectionStatus:'one-source-only',
   officialReportForWeek:true,twoOrMoreQBsUnavailable:true,
   officialReportQBRows:[{name:'Franchise QB',status:'OUT'},
                         {name:'Backup QB',status:'OUT'}]},
  {team:'JAX',projectedQB:'Jacksonville QB',qbProjectionStatus:'two-sources-agree',
   officialReportForWeek:true,officialReportQBRows:[]}]}};
window.__SMOKE__.setData({nextGames:[evidenceHeld],generatedAt:'2026-11-08T11:00:00Z'});
window.location.hash='#game=test_fixture';
window.__SMOKE__.syncRoute();
const heldPage=el('appContent').innerHTML;
assert.match(heldPage,/Pregame verification/);
assert.match(heldPage,/HOLD · VERIFY QB/i);
assert.match(heldPage,/2 QBs designated unavailable/i);
assert.match(heldPage,/Franchise QB/);
assert.match(heldPage,/Third QB/);
assert.match(heldPage,/NO HIGH-CONFIDENCE OR VALUE ALERT/i);
assert.match(heldPage,/53\.0%/,'Hold status must not invent a probability change');
window.location.hash='#tab=overview';
window.__SMOKE__.syncRoute();
assert.match(el('appContent').innerHTML,/EVIDENCE HOLD/);

window.location.hash='#game=test_fixture';
window.__SMOKE__.syncRoute();
assert.match(el('appContent').innerHTML,/LAYER AUDIT PENDING/,'Missing layer data cannot be invented');
assert.match(el('appContent').innerHTML,/53\.0%/,'Missing attribution does not hide the published probability');


assert.match(el('appContent').innerHTML,/QB Replacement/i);
assert.match(el('appContent').innerHTML,/No separate QB replacement percentage has been applied/i);
assert.doesNotMatch(el('appContent').innerHTML,/Published home win change from replacement alone/i);
window.__SMOKE__.setData({nextGames:[{...game,qbReplacement:{
 status:'reported-absence-unpriced',affectsPrediction:false,
 coverageStatus:'reported-absence-unpriced',
 coverageSummary:'Outgoing quarterback OUT but replacement projection is missing',
 teamChecks:[{team:'BAL',side:'home',lastRecordedQB:'Star QB',
   lastRecordedAt:'2026-11-01T00:00:00Z',projectedQB:null,
   injuryReportStatus:'OUT',depthChartAsOf:null,outgoingPriorDropbacks:300,
   missingReasons:['No dated replacement-QB projection available'],
   injuryFeedStatus:'loaded'}],scenarios:[]}}]});
window.__SMOKE__.syncRoute();
assert.match(el('appContent').innerHTML,/REPORTED OUT.*REPLACEMENT UNKNOWN/i);
assert.match(el('appContent').innerHTML,/No dated replacement-QB projection available/i);

window.__SMOKE__.setData({nextGames:[{...game,qbReplacement:{
 status:'conflicting-sources',affectsPrediction:false,coverageStatus:'conflicting-sources',
 coverageSummary:'ESPN and nflverse disagree about projected QB',
 teamChecks:[],scenarios:[]},
 qbSourceEvidence:{status:'loaded',home:{team:'BAL',nflverseProjectedQB:'Starter Q',
  espnProjectedQB:'Backup R',sourceConflict:true,espnDepthStatus:'loaded',
  espnObservedAt:'2026-11-05T14:00:00Z'},
 away:{team:'JAX',nflverseProjectedQB:'Starter J',espnProjectedQB:'Starter J',
  sourcesAgree:true,espnDepthStatus:'loaded',espnObservedAt:'2026-11-05T14:00:00Z'}}}]});
window.__SMOKE__.syncRoute();
assert.match(el('appContent').innerHTML,/SOURCES DISAGREE/i);
assert.match(el('appContent').innerHTML,/Backup R/i);
assert.match(el('appContent').innerHTML,/nflverse/i);
assert.match(el('appContent').innerHTML,/PROJECTIONS AGREE/i);
assert.match(el('appContent').innerHTML,/ESPN roster QBs \(not starters\)/i);
assert.match(el('appContent').innerHTML,/Dated QB injuries/i);

window.__SMOKE__.setData({nextGames:[{...game,qbReplacement:{
 status:'established-absence-already-reflected',affectsPrediction:false,
 coverageStatus:'established-qb-already-absent',
 coverageSummary:'Primary starter did not start last week; prior absence already in form.',
 teamChecks:[{team:'BAL',side:'home',establishedQB:'Franchise Q',
 establishedStarts:6,establishedQBStatus:'OUT',lastRecordedQB:'Backup Q',
 injuryReportStatus:null,projectedQB:'Backup Q',
 alreadyMissingFromLastGame:true,doubleAbsenceReported:false,
 missingReasons:['Do not deduct original QB twice']}],scenarios:[]}}]});
window.__SMOKE__.syncRoute();
assert.match(el('appContent').innerHTML,/ESTABLISHED QB ALREADY ABSENT/i);
assert.match(el('appContent').innerHTML,/Franchise Q/i);
assert.match(el('appContent').innerHTML,/Backup Q/i);
assert.match(el('appContent').innerHTML,/no second deduction/i);


assert.doesNotMatch(el('appContent').innerHTML,/0\.0 percentage points/i);

window.location.hash='#game=test_fixture';window.__SMOKE__.syncRoute();
assert.match(el('appContent').innerHTML,/Jacksonville Jaguars/);
window.__SMOKE__.setData({nextGames:[{...game,situation:null,tactical:null,qbIntelligence:null,injuryIntelligence:null}]});
window.__SMOKE__.syncRoute();
assert.match(el('appContent').innerHTML,/FULL MATCHUP DOSSIER/i,'Missing source inputs broke page');
window.location.hash='#game=unknown';window.__SMOKE__.syncRoute();
assert.match(el('appContent').innerHTML,/no longer on this slate/i,'Stale URL should be explained');
window.__SMOKE__.openGame(game.id);
assert.match(el('dialogContent').innerHTML,/FULL MATCHUP DOSSIER/i,'Legacy modal still available');
console.log('PASS: mobile-friendly matchup page, deep link, source fallback and optional modal');
