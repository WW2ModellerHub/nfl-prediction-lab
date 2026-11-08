const assert=require("node:assert/strict");
const R=require("../assets/redzone-core.js");
const a={roster_id:9,matchup_id:3,points:13.7,starters:["3294","9997"],starters_points:[0,13.7],players:["3294","9997","123"],players_points:{"3294":0,"9997":13.7,"123":5}};
const b={roster_id:2,matchup_id:3,points:12.5,starters:["11560"],starters_points:[12.5],players:["11560"]};
assert.equal(R.findMatchup([a,b],9).theirs.roster_id,2);
assert.equal(R.findMatchup([a,{...b,matchup_id:4}],9).theirs,null);
const p=R.lineup(a,{"9997":{full_name:"Zay Flowers",position:"WR",team:"BAL"}},false);
assert.equal(p[1].name,"Zay Flowers");assert.equal(p[1].points,13.7);
assert.equal(R.lineup(a,{},true)[0].points,5);
const before=R.snapshot({mine:{...a,points:10.8,starters_points:[0,10.8]},theirs:b});
const after=R.snapshot({mine:a,theirs:b});
const changed=R.changes(before,after);
assert.equal(changed.find(x=>x.key==="mine:9997").delta,2.9);
assert.equal(changed.find(x=>x.key==="mine:total").delta,2.9);
assert.equal(R.changes(null,after).length,0);
const games=R.gameData([{id:"g1",status:{type:{state:"in"},period:3,displayClock:"8:12"},
 competitions:[{competitors:[{id:"11",team:{abbreviation:"WSH"}},{id:"22",team:{abbreviation:"BAL"}}],
 situation:{possession:"22",isRedZone:true,downDistanceText:"1st & 10 at WSH 15"}}]}]);
assert.equal(games.zones[0].team,"BAL");assert.equal(games.games.WAS.inRedZone,false);assert.equal(games.games.BAL.inRedZone,true);
assert.equal(R.gameData([{id:"g2",status:{type:{state:"post"}},competitions:[{competitors:[],situation:{isRedZone:true}}]}]).zones.length,0);
console.log("Fantasy Red Zone matchup, scoring delta and possession tests passed.");
