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

// Verified ESPN position text: away at home 15 means marker 85% from away goal.
const field=R.listGames([{id:"1000",date:"2026-11-08T18:00:00Z",
 status:{type:{state:"in"},period:2,displayClock:"06:30"},
 competitions:[{competitors:[
 {id:"away",homeAway:"away",team:{abbreviation:"BAL"},score:"14"},
 {id:"home",homeAway:"home",team:{abbreviation:"WSH"},score:"10"}],
 situation:{possession:"away",downDistanceText:"2nd & 4 at WSH 15",isRedZone:true}}]}]);
assert.equal(field.length,1);
assert.equal(field[0].away,"BAL");assert.equal(field[0].home,"WAS");
assert.equal(field[0].possession,"BAL");assert.equal(field[0].position,85);
assert.equal(field[0].isRedZone,true);
assert.equal(R.listGames([{id:"x",status:{type:{state:"in"}},competitions:[{competitors:[
 {id:"away",homeAway:"away",team:{abbreviation:"BAL"}},
 {id:"home",homeAway:"home",team:{abbreviation:"WSH"}}],situation:{possession:"away"}}]}])[0].position,null);
assert.equal(R.winChanceFromProjected(110,100,24)>0.5,true);
assert.equal(R.winChanceFromProjected(100,110,24)<0.5,true);
assert.equal(R.winChanceFromProjected(100,100,24),0.5);
assert.equal(R.winChanceFromProjected(null,100,24),null);
const forecastPair={
 mine:{roster_id:9,points:10,starters:["one"],starters_points:[5]},
 theirs:{roster_id:2,points:12,starters:["two"],starters_points:[8]}
};
const projection={"one":{rec:5,rec_yd:90,team:"BAL"},
                  "two":{rec:4,rec_yd:40,team:"WAS"}};
const settings={rec:0.5,rec_yd:0.1}; // 11.5 v 6.0 for remaining games
const pre={BAL:{state:"pre"},WAS:{state:"pre"}};
const result=R.estimateMatchup(forecastPair,projection,settings,pre);
assert.equal(result.mine.final,21.5);
assert.equal(result.theirs.final,18);
assert.ok(result.win>0.5);
assert.equal(result.approximate,false);
const withoutClock=R.estimateMatchup(forecastPair,projection,settings,{});
assert.ok(withoutClock.win!==null);
assert.equal(withoutClock.approximate,true);
assert.equal(withoutClock.mine.final,16.5);
const final=R.estimateMatchup({mine:{...forecastPair.mine,points:30},
 theirs:{...forecastPair.theirs,points:27}},projection,settings,
 {BAL:{state:"post"},WAS:{state:"post"}});
assert.equal(final.win,1);
assert.equal(final.mine.final,30);


const dakVsAubrey={
  mine:{starters:["dak"],starters_points:[1.16]},
  theirs:{starters:["aubrey"],starters_points:[0]}
};
const watch=R.zoneParticipants({team:"DAL",opponent:"IND"},dakVsAubrey,{
  dak:{full_name:"Dak Prescott",position:"QB",team:"DAL"},
  aubrey:{full_name:"Brandon Aubrey",position:"K",team:"DAL"}
});
assert.equal(watch.mine.offense.length,1);
assert.equal(watch.mine.offense[0].name,"Dak Prescott");
assert.equal(watch.theirs.offense.length,0);
assert.equal(watch.theirs.kickers.length,1);
assert.equal(watch.theirs.kickers[0].name,"Brandon Aubrey");
assert.equal(R.fieldSpot("Official Timeout at 11:45","DAL","IND"),null);
assert.equal(R.fieldSpot("Official Timeout at IND 11:45","DAL","IND"),null);
assert.equal(R.fieldSpot("2nd & 4 at IND 18","DAL","IND"),82);
assert.equal(R.fieldSpot("at midfield","DAL","IND"),50);
const timeoutGame={id:"401",state:"in",away:"DAL",home:"IND",possession:"DAL",position:null};
const spot=R.summaryFieldSpot(timeoutGame,{drives:{current:{
 team:{abbreviation:"DAL"},plays:[
 {end:{text:"IND 18"}},
 {text:"Official Timeout at 11:45",end:{}}
 ]}}});
assert.equal(spot.position,82);
assert.equal(R.summaryFieldSpot(timeoutGame,{drives:{current:{team:{abbreviation:"IND"},plays:[{end:{text:"IND 5"}}]}}}),null);
assert.equal(R.summaryFieldSpot(timeoutGame,{drives:{previous:[{plays:[{end:{text:"IND 9"}}]}]}}),null);

console.log("Fantasy Red Zone matchup, scoring delta and possession tests passed.");
