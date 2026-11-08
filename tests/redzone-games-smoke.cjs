const assert=require("node:assert/strict");
global.RedZoneCore=require("../assets/redzone-core.js");
const G=require("../assets/redzone-game-core.js"),P=require("../assets/redzone-projections.js");
const e={id:"401",date:"2026-11-08T18:00:00Z",status:{type:{state:"in"},period:2,displayClock:"9:32"},competitions:[{competitors:[
{id:"101",homeAway:"away",team:{abbreviation:"BAL",displayName:"Baltimore Ravens"},score:"14"},
{id:"102",homeAway:"home",team:{abbreviation:"CIN",displayName:"Cincinnati Bengals"},score:"7"}],
situation:{possession:"101",downDistanceText:"2nd & 4 at CIN 18",isRedZone:true,lastPlay:{text:"Rush for 3 yards"}}}]};
const g=G.parseEvents([e])[0];
assert.equal(g.home,"CIN");assert.equal(g.away,"BAL");assert.equal(g.spot.x,82);assert.equal(g.possession,"BAL");assert.equal(g.arrow,"right");
assert.equal(G.extractSpot({downDistanceText:"1st & goal at BAL 3"},"BAL","CIN").x,3);
assert.equal(G.extractSpot({downDistanceText:"3rd & 1 at midfield"},"BAL","CIN").x,50);
assert.equal(G.extractSpot({downDistanceText:"3rd & 6"},"BAL","CIN").x,null);
assert.equal(G.parseEvents([{...e,status:{type:{state:"post"}},competitions:e.competitions}])[0].spot.x,null);
assert.equal(G.matchPlayers(g,[[{team:"BAL"},{team:"MIA"}],[{team:"CIN"}]]).length,2);
const mapped=P.mapData([{player_id:"1",stats:{pts_half_ppr:10}},{player_id:"2",stats:{pts_half_ppr:9}}]);
assert.equal(P.project(mapped["1"],{rec:.5}),10);
assert.equal(P.remainingFraction({state:"in",period:3,clock:"0:00"}),.25);
assert.equal(P.remainingFraction({state:"post"}),0);
const roster={starters:["1"],players_points:{"1":3},points:3};
const pred=P.predict(roster,{"1":{position:"RB",team:"BAL"}},{BAL:{state:"in",period:3,clock:"0:00"}},mapped,{rec:.5});
assert(Math.abs(pred.final-5.5)<.01);
assert.equal(P.predict({starters:["3"],players_points:{"3":4}},{"3":{team:"BAL"}},{},mapped,{}).final,null);
assert(P.winProbability({final:100,variance:25},{final:50,variance:25})>.99);
assert.equal(P.winProbability({final:null},{final:50}),null);
console.log("Live NFL field position, game filtering and projection-model tests passed");
