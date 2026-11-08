/* Shared NFL in-play model: explicit experimental attribution and fail-closed cases. */
const assert=require('node:assert/strict');
const L=require('../assets/live-win-model.js');
const now=Date.parse('2026-11-08T21:25:00Z');
const base={home:'DAL',away:'NYG',state:'in',homeScore:14,awayScore:10,period:3,clock:'09:00',
  possession:'DAL',position:21,downDistance:'1st & 10 at DAL 21',fetchedAt:now};
const forecast=L.estimate(base,.58,now);
assert.equal(forecast.status,'experimental');
assert.equal(forecast.validated,false);assert.equal(forecast.bettingEligible,false);
assert(forecast.homeProbability>.58);
const total=forecast.layers.slice(1).reduce((sum,x)=>sum+x.delta,.58);
assert(Math.abs(total-forecast.homeProbability)<1e-9);
const backward=L.estimate({...base,homeScore:6,awayScore:24,period:4,clock:'03:30'},.7,now);
assert(backward.homeProbability<.15);
assert.equal(L.estimate({...base,fetchedAt:now-180000},.58,now).status,'stale');
assert.equal(L.estimate({...base,state:'post'},.58,now).status,'final');
assert.equal(L.estimate({...base,period:5},.58,now).status,'overtime');
assert.equal(L.estimate({...base,clock:'halt'},.58,now).status,'unavailable');
assert.equal(L.estimate(base,null,now).status,'unavailable');
assert.equal(L.estimate({...base,possession:null,position:null},.58,now).possessionPoints,0);
const awayHasBall=L.estimate({...base,possession:'NYG',position:75,downDistance:'3rd & 2 at DAL 25'},.58,now);
assert(awayHasBall.homeProbability<forecast.homeProbability);
assert.equal(L.location('2nd & 4 at NYG 15','NYG','DAL'),15);
assert.equal(L.location('3rd & goal at DAL 3','NYG','DAL'),97);
assert.equal(L.location('Official Timeout at 12:22','NYG','DAL'),null);
const espn=L.espnState({id:'401',date:'2026-11-08T18:00:00Z',status:{type:{state:'in'},period:3,displayClock:'09:00'},
 competitions:[{competitors:[{homeAway:'home',id:'1',team:{abbreviation:'DAL'},score:'14'},
 {homeAway:'away',id:'2',team:{abbreviation:'NYG'},score:'10'}],
 situation:{possession:'1',isRedZone:false,downDistanceText:'1st & 10 at DAL 21'}}]},now);
assert.equal(espn.position,79);
assert.equal(espn.possession,'DAL');
assert.equal(espn.homeScore,14);
assert.equal(L.espnReference({winprobability:[{homeWinPercentage:.32},{homeWinPercentage:.74,playId:'abc'}]}).homeProbability,.74);
assert.equal(L.espnReference({winprobability:[{homeWinPercentage:102}]}),null);
console.log('NFL in-play model clocks, scoring, possession, attribution, freshness and ESPN reference passed.');

/* HTML shows independent research and external model separately, never fabricated live data. */
global.NFLGameLiveModel=L;
const UI=require('../assets/live-win-ui.js');
const fixture={id:'lab-test',home:'DAL',away:'NYG',homeProbability:.58};
const freshBase={...base,fetchedAt:Date.now()};
const full=UI.render(fixture,freshBase,{homeProbability:.03,fetchedAt:Date.now()},true);
assert(full.includes('LIVE MODEL · EXPERIMENTAL'));
assert(full.includes('Clock / unplayed time'));
assert(full.includes('Score difference'));
assert(full.includes('Possession & field'));
assert(full.includes('Model disagreement'));
assert(full.includes('not a betting recommendation'));
const missing=UI.render(fixture,null,null,true);
assert(missing.includes('Awaiting') || missing.includes('unavailable'));
assert(!missing.includes('livewin-main'));
const completed=UI.render(fixture,{...freshBase,state:'post'},null,true);
assert(completed.includes('Game finished'));
const fs=require('node:fs');
assert(fs.readFileSync('assets/app.js','utf8').includes('data-live-full='));
assert(fs.readFileSync('assets/redzone.js','utf8').includes('liveNFLWinPanel(chosen)'));
assert(fs.readFileSync('redzone.html','utf8').includes('live-win-model.js'));
console.log('Live game winner UI and no-fabrication safeguards passed.');
