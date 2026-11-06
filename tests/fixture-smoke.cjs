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
assert.match(el('appContent').innerHTML,/FULL MATCHUP DOSSIER/i,'Dossier not rendered in page');
assert.match(el('appContent').innerHTML,/Quarterbacks, practice and injuries/i);
assert.match(el('appContent').innerHTML,/Copy matchup link/i);
assert.match(el('appContent').innerHTML,/Why each team could win/i);
assert.match(el('appContent').innerHTML,/Player availability exposure/i);

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
