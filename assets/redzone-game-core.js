/* NFL game selector + field positioning. No guessed ball markers. */
(function(root){
"use strict";
function norm(v){return root.RedZoneCore?root.RedZoneCore.norm(v):String(v||"").toUpperCase();}
function possessionTeam(comp){
  var s=comp && comp.situation||{},c=comp&&comp.competitors||[];
  var poss=c.find(function(x){return String(x.id)===String(s.possession) && s.possession!==undefined && s.possession!==null;})||c.find(function(x){return x.possession===true;});
  return poss&&poss.team?norm(poss.team.abbreviation):null;
}
function extractSpot(situation, away, home){
  var text=String(situation && (situation.downDistanceText||situation.shortDownDistanceText)||"");
  if(/\b(?:at )?(?:midfield|mid-field|50 yard line)\b/i.test(text))return {x:50,label:"MIDFIELD",source:"ESPN play situation"};
  var m=text.match(/\bat\s+([A-Z]{2,3})\s+(\d{1,2})\b/i);
  if(!m)return {x:null,label:"POSITION UNAVAILABLE",source:""};
  var abbr=norm(m[1]),yd=Number(m[2]);
  if(!Number.isFinite(yd)||yd<0||yd>50)return {x:null,label:"POSITION UNAVAILABLE",source:""};
  var x=abbr===away?yd:abbr===home?100-yd:null;
  if(x===null)return {x:null,label:"POSITION UNAVAILABLE",source:""};
  return {x:x,label:abbr+" "+yd,source:"ESPN play situation"};
}
function parseEvents(events){
  return (events||[]).map(function(event){
    var comp=event.competitions&&event.competitions[0]; if(!comp)return null;
    var sides=comp.competitors||[];
    var home=sides.find(function(c){return c.homeAway==="home";})||sides[0];
    var away=sides.find(function(c){return c.homeAway==="away";})||sides.find(function(c){return c!==home;});
    if(!home||!away||!home.team||!away.team)return null;
    var h=norm(home.team.abbreviation),a=norm(away.team.abbreviation);
    var situation=comp.situation||event.situation||{};
    var state=event.status&&event.status.type&&event.status.type.state||"pre";
    var possession=possessionTeam({situation:situation,competitors:sides});
    var spot=state==="in"?extractSpot(situation,a,h):{x:null,label:state==="post"?"FINAL": "NOT STARTED",source:""};
    var last=situation.lastPlay&&(situation.lastPlay.text||situation.lastPlay.shortText)||"";
    return {id:String(event.id||comp.id),away:a,home:h,
      awayScore:away.score===undefined?null:String(away.score),homeScore:home.score===undefined?null:String(home.score),
      awayName:away.team.displayName||away.team.name||a,homeName:home.team.displayName||home.team.name||h,
      state:state,status:event.status&&event.status.type&&event.status.type.shortDetail||"",
      period:event.status&&Number(event.status.period)||0,clock:event.status&&event.status.displayClock||"",
      kickoff:event.date||"",possession:possession,spot:spot,
      down:situation.downDistanceText||"",lastPlay:last,isRedZone:Boolean(situation.isRedZone),
      arrow:possession?(possession===a?"right":possession===h?"left":null):null};
  }).filter(Boolean);
}
function matchPlayers(game,playerLists){
  var p=(playerLists||[]).flat();
  return p.filter(function(x){return x.team===game.home||x.team===game.away;});
}
function sortGames(games,playerLists){
  return (games||[]).slice().sort(function(a,b){
    function rank(g){
      var players=matchPlayers(g,playerLists).length>0?100:0;
      return players+(g.state==="in"?300:g.state==="pre"?200:0);
    }
    return rank(b)-rank(a)||Number(new Date(a.kickoff))-Number(new Date(b.kickoff));
  });
}
var api={extractSpot:extractSpot,parseEvents:parseEvents,matchPlayers:matchPlayers,sortGames:sortGames};
root.RedZoneGames=api;if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
