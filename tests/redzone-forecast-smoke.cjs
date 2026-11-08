const assert=require("node:assert/strict");
const Core=require("../assets/redzone-core.js");
const match={mine:{roster_id:9,points:65,starters:["1","2"],starters_points:[40,25]},
theirs:{roster_id:2,points:60,starters:["3","4"],starters_points:[30,30]}};
const proj={
"1":{pts_half_ppr:25,team:"BAL"},"2":{pts_half_ppr:22,team:"WAS"},
"3":{pts_half_ppr:23,team:"CIN"},"4":{pts_half_ppr:24,team:"SF"}};
const players=Object.fromEntries(Object.entries(proj).map(([id,p])=>[id,{team:p.team}]));
const scoring={rec:.5};
const pre=Object.fromEntries(Object.values(players).map(p=>[p.team,{state:"pre"}]));
const before=Core.estimateMatchup(match,proj,scoring,pre,players);
assert(before.win!==null);
assert(before.mine.final>match.mine.points);
assert(before.theirs.final>match.theirs.points);
const higher=JSON.parse(JSON.stringify(match));higher.mine.points+=20;
const after=Core.estimateMatchup(higher,proj,scoring,pre,players);
assert(after.win>before.win,"A bigger lead with same uncertainty should increase win chance");
const gamesDone=Object.fromEntries(Object.values(players).map(p=>[p.team,{state:"post"}]));
const done=Core.estimateMatchup(match,proj,scoring,gamesDone,players);
assert.equal(done.mine.final,65);
assert.equal(done.theirs.final,60);
assert.equal(done.win,1);
const tied=JSON.parse(JSON.stringify(match));tied.theirs.points=65;
assert.equal(Core.estimateMatchup(tied,proj,scoring,gamesDone,players).win,.5);
const missing={"1":proj["1"],"2":proj["2"],"3":proj["3"]};
const incomplete=Core.estimateMatchup(match,missing,scoring,pre,players);
assert.equal(incomplete.approximate,true);
assert(incomplete.win!==null);
const noProjections=Core.estimateMatchup(match,{},scoring,pre,players);
assert.equal(noProjections.win,null);
const noClock=Core.estimateMatchup(match,proj,scoring,{},players);
assert.equal(noClock.approximate,true);
const e={id:"g",date:"2026-11-08T18:00:00Z",status:{type:{state:"in"},period:2,displayClock:"8:42"},competitions:[{competitors:[{id:"a",homeAway:"away",team:{abbreviation:"BAL"},score:"13"},{id:"h",homeAway:"home",team:{abbreviation:"CIN"},score:"10"}],situation:{possession:"a",downDistanceText:"2nd & 4 at CIN 18",isRedZone:true}}]};
const g=Core.listGames([e])[0];
assert.equal(g.position,82);assert.equal(g.possession,"BAL");
assert.equal(g.away,"BAL");assert.equal(g.home,"CIN");
const missingSpot={...e,competitions:[{...e.competitions[0],situation:{possession:"a",downDistanceText:"2nd & 4"}}]};
assert.equal(Core.listGames([missingSpot])[0].position,null,"Do not invent a ball position");
console.log("Live projected finals, matchup probability, and NFL game-centre tests passed");
