/* The game-by-game explainability layer is data-driven and MUST NOT alter picks. */
const assert=require('node:assert/strict');
const intelligence=require('../assets/matchup-intelligence.js');
const raw={
 id:'game1',home:'BAL',away:'JAX',homeProbability:.68,awayProbability:.32,
 formHome:27,formAway:18,allowedHome:18,allowedAway:27,
 tactical:{status:'ready',
  home:{games:6,passEPA:.20,allowedPassEPA:-.12,rushEPA:.12,allowedRushEPA:-.08,explosivePass:.12,explosiveAllowed:.06,hitAllowed:.04,hitForced:.15},
  away:{games:6,passEPA:.03,allowedPassEPA:.19,rushEPA:.03,allowedRushEPA:.12,explosivePass:.05,explosiveAllowed:.13,hitAllowed:.14,hitForced:.04},
  advantages:[
   {name:'Passing efficiency',edge:.30,unit:'EPA/play',strong:true,favors:'BAL'},
   {name:'Rushing efficiency',edge:.06,unit:'EPA/play',strong:false,favors:'Even'},
   {name:'QB-hit/sack matchup',edge:.17,unit:'rate differential',strong:true,favors:'BAL'},
   {name:'Explosive pass opportunity',edge:.15,unit:'rate differential',strong:true,favors:'BAL'}
  ]},
 situation:{home:{fullRestDays:6},away:{fullRestDays:4},
  signals:[{team:'JAX',direction:'back',id:'rest_edge',name:'Rest advantage',
   reason:'JAX has three additional off days'}]},
 injuryIntelligence:{status:'reported',reportAsOf:'2026-11-05T13:00:00Z',
  home:[{name:'Projected QB',position:'QB',status:'QUESTIONABLE',starterOnDepthChart:true}],
  away:[{name:'Cornerback 1',position:'CB',status:'OUT',starterOnDepthChart:true}]},
 supplementalInjuryWatch:{status:'cached',retrievedAt:'2026-11-04T18:00:00Z',
  home:[{name:'WR1',position:'WR',status:'QUESTIONABLE',recentUsage:{offensePct:.82}}],
  away:[{name:'Cornerback 1',position:'CB',status:'OUT'}]}
};
const snapshot=JSON.stringify(raw);
const report=intelligence.analyze(raw);
assert.equal(report.favourite,'BAL');
assert.equal(report.underdog,'JAX');
assert.equal(report.underdogProbability,.32);
assert.equal(report.upsetContextCount,1);
assert.equal(report.forUnderdog[0].title,'Rest advantage');
assert.equal(report.forFavourite.some(x=>x.title==='Passing offence against pass defence'),true);
assert.equal(report.injury.away.outCount,1,'duplicate ESPN and game-week player must not double count');
assert.equal(report.injury.away.projectedStarterFlagCount,1);
assert.equal(report.injury.home.questionableCount,2);
assert.equal(report.injury.home.cached,true);
assert.equal(report.injury.home.notConfirmed,true);
assert.equal(report.matchup.filter(x=>x.status==='notable').length>=2,true);
assert.match(report.matchup.find(x=>x.type==='explosive').details,/12\.0%/);
assert.match(report.matchup.find(x=>x.type==='pressure').source,/NOT charted pressure/);
assert.equal(JSON.stringify(raw),snapshot,'The explainer may not mutate model inputs or forecast');
const missing=intelligence.analyze({home:'BAL',away:'JAX',homeProbability:.55,
 tactical:{status:'insufficient',home:{games:1},away:null},
 injuryIntelligence:{status:'unavailable'},supplementalInjuryWatch:{status:'cached',away:[],home:[]},
 situation:{signals:[]}});
assert.equal(missing.matchup.find(x=>x.type==='passing').status,'unavailable');
assert.equal(missing.injury.home.outCount,0);
assert.equal(missing.injury.home.coverage,'ESPN media observations only');
assert.equal(missing.modelOverlayActive,false);
assert.equal(missing.forUnderdog.length,0);
assert.match(missing.upsetSummary,/No material observed/);
const nullScore=intelligence.analyze({home:'BAL',away:'JAX',homeProbability:.55,formHome:null,formAway:null,allowedHome:null,allowedAway:null});
assert.equal(nullScore.matchup[0].status,'unavailable','null is missing, not zero');
const noProb=intelligence.analyze({home:'BAL',away:'JAX'});
assert.equal(noProb.underdog,null);
assert.equal(noProb.modelPredictionAvailable,false);
console.log('PASS: truthful upset routes, tactical sources, missing data, injury deduplication, immutable forecasts');
