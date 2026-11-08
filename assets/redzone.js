(function(){
"use strict";
var Core=window.RedZoneCore;
var DEF={leagueId:"1388984626868912128",rosterId:"9"};
var KCFG="nfl-lab-redzone-config-v1", KCACHE="nfl-lab-redzone-players-v1";
var cfg=read(KCFG)||DEF;
cfg.leagueId=String(cfg.leagueId||DEF.leagueId).trim();cfg.rosterId=String(cfg.rosterId||DEF.rosterId).trim();
var state={week:null,nflWeek:null,rows:[],rosters:[],users:[],league:null,players:{},games:{},zones:[],zoneKeys:null,
  pair:{mine:null,theirs:null},feed:[],before:null,loading:false,interval:null,errors:{},lastUpdated:0,
  bench:false,sound:false,notify:false,flashes:{},lastEspnTime:0,fullGames:[],selectedGame:null,projections:null,projectionAt:0,projectionWeek:null,projectionError:null,projectionBusy:false};
var $=function(id){return document.getElementById(id);};
function read(key){try{return JSON.parse(localStorage.getItem(key));}catch(e){return null;}}
function store(key,val){try{localStorage.setItem(key,JSON.stringify(val));}catch(e){}}
function esc(x){return String(x===null||x===undefined?"":x).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
function fmt(x){return typeof x==="number"&&Number.isFinite(x)?x.toFixed(2):"—";}
function stamp(t){return new Date(t).toLocaleTimeString("en-GB",{hour:"2-digit",minute:"2-digit",second:"2-digit",timeZone:"Europe/London"});}
function key(){return "nfl-lab-redzone-"+cfg.leagueId+"-"+cfg.rosterId+"-week-"+state.week;}
function fetchJson(url,timeout){
  var ctl=new AbortController();var timer=setTimeout(function(){ctl.abort();},timeout||12000);
  return fetch(url,{signal:ctl.signal,cache:"no-store"}).then(function(r){if(!r.ok)throw Error("HTTP "+r.status);return r.json();}).finally(function(){clearTimeout(timer);});
}
function url(path){return "https://api.sleeper.app/v1/"+path;}
function updateStatus(){
  var ok=Boolean(state.lastUpdated) && Date.now()-state.lastUpdated<90000;
  $("connection").className="status "+(ok?"live":state.errors.sleeper?"error":"");
  $("connection").innerHTML="<i></i>"+(ok?"SLEEPER LIVE":state.errors.sleeper?"DATA STALE":"CONNECTING");
  $("lastUpdate").textContent=state.lastUpdated?"Updated "+stamp(state.lastUpdated)+" UK":"Not connected";
  $("gameFeedStatus").textContent=state.errors.espn?"NFL drive feed unavailable":state.lastEspnTime?"NFL play feed: "+stamp(state.lastEspnTime)+" UK":"NFL play feed: waiting";
  var errors=Object.keys(state.errors).filter(function(x){return state.errors[x];});
  $("error").hidden=!errors.includes("sleeper");
  $("error").textContent=state.errors.sleeper?"Unable to refresh Sleeper: "+state.errors.sleeper+". Showing the latest successful data, if any.":"";
}
function teamName(id){
  var roster=state.rosters.find(function(x){return String(x.roster_id)===String(id);});
  var user=roster&&state.users.find(function(u){return String(u.user_id)===String(roster.owner_id);});
  return user && ((user.metadata && user.metadata.team_name)||user.display_name) || "Roster "+id;
}

function compactInitials(name){
  var tokens=String(name||"").replace(/[^a-zA-Z0-9 ]/g," ").trim().split(/\s+/).filter(Boolean);
  return tokens.length>1?(tokens[0][0]+tokens[1][0]).toUpperCase():String(name||"??").slice(0,2).toUpperCase();
}
function safeTeam(team){var t=Core.norm(team);return /^[A-Z]{2,3}$/.test(t)?t:"";}
function teamMark(team,cls){
  var t=safeTeam(team);
  return '<span class="team-mark '+(cls||"")+'" aria-label="'+esc(t||"NFL")+'">'+(t?
    '<span class="team-code">'+esc(t)+'</span><img alt="" loading="lazy" decoding="async" src="https://a.espncdn.com/i/teamlogos/nfl/500/'+t.toLowerCase()+'.png" onerror="this.remove()">':
    '<span class="team-code">NFL</span>')+'</span>';
}
function playerPhoto(player){
  var id=String(player.id||"");
  var type=/^[0-9]+$/.test(id) && player.position!=="DEF";
  return '<span class="player-photo"><span class="photo-fallback">'+esc((player.name||"?").slice(0,1))+'</span>'+
    (type?'<img src="https://sleepercdn.com/content/nfl/players/thumb/'+id+'.jpg" alt="" loading="lazy" decoding="async" onerror="this.remove()">':'')+'</span>';
}

function gameStatus(team){
  var g=state.games[Core.norm(team)];
  if(!g)return {main:"—",sub:"No feed",className:""};
  if(g.state==="in")return {main:"LIVE "+(g.period?"Q"+g.period:""),sub:(g.clock||"")+" vs "+g.opponent,className:"live"};
  if(g.state==="post")return {main:"FINAL",sub:"vs "+g.opponent,className:"final"};
  var when=g.start?new Date(g.start).toLocaleString("en-GB",{weekday:"short",hour:"2-digit",minute:"2-digit",timeZone:"Europe/London"}):"Upcoming";
  return {main:"vs "+g.opponent,sub:when,className:""};
}
function activeZonesFor(side,player){
  return state.zones.some(function(z){return z.team===Core.norm(player.team) && (side==="mine"||side==="theirs") && !["DEF","K","—"].includes(player.position);});
}
function renderLineup(side,target){
  var row=state.pair[side];
  var starters=Core.lineup(row,state.players,false);
  var bench=state.bench?Core.lineup(row,state.players,true):[];
  $(side==="mine"?"myCount":"theirCount").textContent=row?starters.length+" STARTERS":"";
  if(!row){$(target).innerHTML='<div class="empty">No matchup lineup available this week.</div>';return;}
  $(target).innerHTML=starters.concat(bench).map(function(p){
    var g=gameStatus(p.team),danger=activeZonesFor(side,p),projection=projLookup(p.id);
    var deltaKey=side+":"+(p.bench?"bench:":"")+p.id;
    var changed=state.flashes[deltaKey] && Date.now()-state.flashes[deltaKey]<6000;
    return '<div class="player '+(p.bench?"bench ":"")+(danger?"redzone "+(side==="theirs"?"enemy ":""):"")+(changed?"changed":"")+'">'+
      '<div class="who">'+playerPhoto(p)+'<span class="who-text"><strong title="'+esc(p.name)+'">'+esc(p.name)+'</strong><small>'+
      '<span class="position">'+esc(p.position)+'</span>'+teamMark(p.team,"tiny")+
      (p.bench?'<span class="bench-label">BENCH</span>':'')+
      (danger?'<span class="threat-indicator">● RZ</span>':'')+
      '</small></span></div>'+
      '<div class="game '+g.className+'">'+esc(g.main)+'<small>'+esc(g.sub)+'</small></div>'+
      '<div class="playerpoints '+(p.points===null?"unknown":"")+'">'+fmt(p.points)+(projection===null?'':'<small>PRJ '+projection.toFixed(1)+'</small>')+'</div></div>';
  }).join("");
}
function renderZones(){
  var cards=[];
  state.zones.forEach(function(z){
    ["mine","theirs"].forEach(function(side){
      var starters=Core.lineup(state.pair[side],state.players,false);
      var relevant=starters.filter(function(p){return Core.norm(p.team)===z.team && !["K","DEF","—"].includes(p.position);});
      var kickers=starters.filter(function(p){return Core.norm(p.team)===z.team && p.position==="K";});
      var defenders=starters.filter(function(p){return Core.norm(p.team)===z.opponent && p.position==="DEF";});
      if(!relevant.length && !kickers.length && !defenders.length)return;
      var mine=side==="mine";
      var names=relevant.map(function(p){return p.name;}).join(" · ");
      var other=(kickers.length?'<span class="rz-secondary">FG watch: '+esc(kickers.map(function(p){return p.name;}).join(", "))+'</span>':"")+
        (defenders.length?'<span class="rz-secondary">DEF defending: '+esc(defenders.map(function(p){return p.name;}).join(", "))+'</span>':"");
      cards.push('<article class="redzone-card '+(mine?"friendly":"opponent")+'">'+
        '<div class="rz-top"><span class="rz-pill">'+(mine?"▲ YOUR ATTACK":"▼ OPPONENT THREAT")+'</span>'+
        '<span class="rz-clock">Q'+esc(z.period||"–")+' · '+esc(z.clock||"Live")+'</span></div>'+
        '<div class="rz-main"><div class="rz-team">'+teamMark(z.team,"large")+'<div><b>'+esc(z.team)+'</b><small>vs '+esc(z.opponent)+'</small></div></div>'+
        '<span class="rz-chip">IN THE 20</span></div>'+
        '<div class="mini-field" role="img" aria-label="Schematic red zone field: offence inside opponent 20, not precise ball location"><div class="field-stripes"></div><span class="field-twenty">20</span><span class="field-ten">10</span><span class="field-goal">GOAL</span><span class="field-ball">◆</span></div>'+
        '<div class="rz-players">'+(names?esc(names):"No starting skill player")+'</div>'+other+
        '<div class="rz-foot">'+esc(z.downDistance||"Scoring chance")+'</div></article>');
    });
  });
  $("rzCount").textContent=String(cards.length);
  $("redzones").classList.toggle("has-zones",cards.length>0);
  $("redzones").innerHTML=cards.join("") ||
    '<div class="empty idle-zone"><span class="idle-icon">◎</span><div><b>No active scoring threats</b><small>'+
    (state.errors.espn?"NFL drive feed unavailable; fantasy points still refresh.":"Watching both lineups for possessions inside the 20.")+
    '</small></div></div>';
}
function renderScore(){
  var own=state.pair.mine,opp=state.pair.theirs;
  var nameMine=teamName(cfg.rosterId),nameOpp=opp?teamName(opp.roster_id):"No paired opponent";
  $("myName").textContent=nameMine;$("theirName").textContent=nameOpp;
  $("myBadge").textContent=compactInitials(nameMine);$("theirBadge").textContent=compactInitials(nameOpp);
  var my=own?Core.num(own.points):null,them=opp?Core.num(opp.points):null;
  $("myScore").textContent=fmt(my);$("theirScore").textContent=fmt(them);
  $("margin").className="margin";
  if(my!==null && them!==null){
    var d=Math.round((my-them)*100)/100;
    $("margin").textContent=Math.abs(d)<0.005?"TIED":(d>0?"▲ +":"▼ −")+Math.abs(d).toFixed(2);
    $("margin").classList.add(d>0?"leading":d<0?"trailing":"tied");
    var sum=Math.max(0,my)+Math.max(0,them);
    var pct=sum>0?Math.max(0,Math.min(100,Math.max(0,my)/sum*100)):50;
    $("myShareBar").style.width=pct.toFixed(2)+"%";
    $("theirShareBar").style.width=(100-pct).toFixed(2)+"%";
    $("mySharePct").textContent=pct.toFixed(0)+"%";
    $("theirSharePct").textContent=(100-pct).toFixed(0)+"%";
  } else {
    $("margin").textContent="VS";
    $("myShareBar").style.width="50%";$("theirShareBar").style.width="50%";
    $("mySharePct").textContent="—";$("theirSharePct").textContent="—";
  }
  $("myDetails").textContent=own?"SLEEPER SCORE":"ROSTER NOT FOUND";
  $("theirDetails").textContent=opp?"SLEEPER SCORE":"H2H NOT AVAILABLE";
}
function renderActivity(){
  $("activity").innerHTML=state.feed.length?state.feed.slice(0,65).map(function(e){
    var own=e.side==="mine",threat=e.delta===null;
    return '<div class="activity-row '+(own?"event-own":"event-rival")+'">'+
      '<span class="event-symbol">'+(threat?"◎":e.delta>=0?"↗":"↘")+'</span>'+
      '<div class="event-description"><span class="event-label">'+(own?"YOU":"OPP")+' · '+esc(stamp(e.at))+'</span>'+
      '<strong>'+esc(e.title)+'</strong><small>'+esc(e.detail)+'</small></div>'+
      '<span class="event-delta '+(e.delta<0?"neg":"")+'">'+(threat?"RZ":(e.delta>0?"+":"")+fmt(e.delta))+'</span></div>';
  }).join(""):'<div class="empty empty-events"><span class="idle-icon">↗</span><span>Waiting for the next scoring change</span></div>';
}

function participantCounts(game){
  var count={mine:0,theirs:0},players=[];
  ["mine","theirs"].forEach(function(side){
    var on=Core.lineup(state.pair[side],state.players,false).filter(function(p){return p.team===game.away||p.team===game.home;});
    count[side]=on.length;
    on.forEach(function(p){players.push({side:side,name:p.name,team:p.team});});
  });
  return {count:count,players:players};
}
function listedGames(){
  return state.fullGames.slice().sort(function(a,b){
    var rank=function(g){return (g.state==="in"?30:g.state==="pre"?20:10)+(participantCounts(g).count.mine+participantCounts(g).count.theirs?5:0);};
    return rank(b)-rank(a)||String(a.start).localeCompare(String(b.start));
  });
}
function gameStart(g){
  if(!g.start)return "SCHEDULE TBC";
  return new Date(g.start).toLocaleString("en-GB",{timeZone:"Europe/London",weekday:"short",hour:"2-digit",minute:"2-digit"});
}
function gameState(g){
  if(g.state==="in")return "Q"+g.period+" "+(g.clock||"");
  if(g.state==="post")return "FINAL";
  return gameStart(g);
}
function renderGames(){
  var games=listedGames(),live=games.filter(function(g){return g.state==="in";});
  $("gamesLiveCount").textContent=live.length+" LIVE";
  $("gamesStatus").textContent=state.errors.espn?"Drive data unavailable":games.length+" NFL GAMES";
  if(!games.length){
    $("gameStrip").innerHTML='<div class="empty">No games available from the NFL scoreboard for this week.</div>';
    $("gameDetails").innerHTML='<div class="empty">Game field view requires NFL scoreboard data.</div>';
    return;
  }
  if(!games.some(function(g){return g.id===state.selectedGame;})){
    var relevant=games.find(function(g){return g.state==="in"&&participantCounts(g).count.mine>0;})||
       games.find(function(g){return g.state==="in" && (participantCounts(g).count.mine+participantCounts(g).count.theirs)>0;})||
       games.find(function(g){return g.state==="in";})||
       games.find(function(g){return participantCounts(g).count.mine>0;})||games[0];
    state.selectedGame=relevant.id;
  }
  var preservedScroll=$("gameStrip").scrollLeft;
  $("gameStrip").innerHTML=games.map(function(g){
    var active=state.selectedGame===g.id,counts=participantCounts(g).count;
    return '<button type="button" class="game-tab '+(active?"selected ":"")+(g.state==="in"?"playing":"")+
      '" data-game="'+esc(g.id)+'" role="tab" aria-selected="'+String(active)+'">'+
      '<div class="game-tab-top"><span class="game-tab-status">'+(g.state==="in"?"● LIVE":g.state==="post"?"FINAL":gameStart(g))+'</span>'+
      ((counts.mine+counts.theirs)?'<span class="fantasy-watch-count">◉ '+(counts.mine+counts.theirs)+'</span>':"")+'</div>'+
      '<div class="game-tab-score"><span>'+teamMark(g.away,"tiny")+' '+esc(g.away)+'</span><b>'+fmtNFL(g.awayScore)+'</b></div>'+
      '<div class="game-tab-score"><span>'+teamMark(g.home,"tiny")+' '+esc(g.home)+'</span><b>'+fmtNFL(g.homeScore)+'</b></div></button>';
  }).join("");
  $("gameStrip").scrollLeft=preservedScroll;
  var chosen=games.find(function(g){return g.id===state.selectedGame;});
  var watchers=participantCounts(chosen).players;
  var hasBall=chosen.state==="in"&&chosen.position!==null;
  var spots=Array.from({length:11},function(_,i){return '<span class="yard-grid-mark" style="left:'+i*10+'%">'+(i===0||i===10?"G":i<=5?i*10:(10-i)*10)+'</span>';}).join("");
  var field= '<div class="field-wrap"><div class="field-stadium"><div class="field-surface">'+
     '<div class="endzone endzone-away">'+teamMark(chosen.away,"large")+'<b>'+esc(chosen.away)+'</b></div>'+
     '<div class="playing-field">'+spots+(hasBall?'<div class="ball-marker" style="left:'+chosen.position+'%" title="'+esc(chosen.downDistance||"Reported field position")+'"><span>🏈</span></div>':'<div class="no-ball">'+(chosen.state==="pre"?"AWAITING KICKOFF":chosen.state==="post"?"FINAL":"BALL POSITION NOT REPORTED")+'</div>')+'</div>'+
     '<div class="endzone endzone-home">'+teamMark(chosen.home,"large")+'<b>'+esc(chosen.home)+'</b></div>'+
   '</div></div></div>';
  $("gameDetails").innerHTML='<div class="field-details-head"><div class="field-matchup">'+
     teamMark(chosen.away,"large")+' <b>'+esc(chosen.away)+'</b> <span>'+fmtNFL(chosen.awayScore)+'</span>'+
     '<span class="field-vs">—</span>'+
     '<span>'+fmtNFL(chosen.homeScore)+'</span> <b>'+esc(chosen.home)+'</b> '+teamMark(chosen.home,"large")+'</div>'+
     '<div class="field-state">'+(chosen.state==="in"?'<span class="live-ring">● LIVE</span>':"")+esc(gameState(chosen))+'</div></div>'+
     field+
     '<div class="field-meta"><span>'+esc(chosen.state==="in"?(chosen.downDistance||"Down and distance unavailable"):"Game not currently in play")+'</span>'+
     '<span>'+(chosen.state==="in"&&chosen.possession?"POSSESSION · "+esc(chosen.possession):"NO LIVE POSSESSION")+'</span></div>'+
     '<div class="field-watch"><b>FANTASY WATCH</b> '+(watchers.length?watchers.map(function(p){return '<span class="watch-chip '+(p.side==="mine"?"own":"rival")+'">'+esc(p.name)+'</span>';}).join(""):'<span class="watch-none">Neither lineup has a starter in this game</span>')+'</div>'+
     (chosen.state==="in"&&chosen.lastPlay?'<div class="last-play">LAST PLAY · '+esc(chosen.lastPlay)+'</div>':'')+
     '<p class="field-source">'+(hasBall?"Ball placement from "+esc(chosen.positionSource)+" (reported, not a live animation).":"No precise ball location has been reported for this game.")+'</p>';
}
function fmtNFL(n){return n===null||n===undefined?"–":String(n);}
function projLookup(id){
  var st=state.projections&&state.projections[id];
  return Core.projectionFor(st,state.league&&state.league.scoring_settings||{});
}
function renderProjections(){
  var status=$("projectionStatus"),at=$("projectionStamp");
  var unavailable=function(message){
    $("winPct").textContent="—";$("myProjected").textContent="—";$("theirProjected").textContent="—";
    $("winGauge").style.setProperty("--win","50");
    $("myForecastBar").style.width="50%";$("theirForecastBar").style.width="50%";
    status.textContent=message;
  };
  if(!state.projections){
    at.textContent=state.projectionError?"Projection feed unavailable":"Connecting to Sleeper";
    unavailable(state.projectionError?
      "Sleeper player projections could not be retrieved. Current fantasy scores remain live; no win probability is fabricated.":
      "Loading Sleeper's projected player points…");
    return;
  }
  at.textContent="Sleeper forecasts "+stamp(state.projectionAt)+" UK";
  if(!state.pair.mine || !state.pair.theirs){
    unavailable("Waiting for both teams' matchup scores.");
    return;
  }
  var converted={};
  Object.keys(state.projections).forEach(function(id){
    var item=state.projections[id],info=state.players[id]||{};
    converted[id]=Object.assign({},item,{team:Core.norm(info.team||
      (item.player&&item.player.team)||item.team||(/^[A-Z]{2,3}$/.test(id)?id:""))});
  });
  var forecast=Core.estimateMatchup(state.pair,converted,
    state.league&&state.league.scoring_settings||{},state.games,state.players);
  if(!forecast.mine||!forecast.theirs||forecast.win===null){
    unavailable(forecast.reason||"Sleeper has not provided enough projected points to estimate this matchup.");
    return;
  }
  var a=forecast.mine.final,b=forecast.theirs.final;
  var pct=forecast.win*100;
  $("myProjected").textContent=a.toFixed(1);
  $("theirProjected").textContent=b.toFixed(1);
  $("winPct").textContent=(pct<1?pct.toFixed(1):pct>99?pct.toFixed(1):Math.round(pct))+"%";
  $("winGauge").style.setProperty("--win",pct.toFixed(2));
  var share=Math.max(0,a)/(Math.max(0,a)+Math.max(0,b)||1)*100;
  $("myForecastBar").style.width=share.toFixed(2)+"%";
  $("theirForecastBar").style.width=(100-share).toFixed(2)+"%";
  var gap=Math.abs(a-b).toFixed(1);
  status.textContent=(forecast.approximate?"PROVISIONAL · ":"MODEL ESTIMATE · ")+
    (a>b?"You projected ahead":a<b?"Opponent projected ahead":"Teams projected level")+
    " by "+gap+" points · based on "+
    forecast.mine.covered+"/"+forecast.mine.required+" and "+
    forecast.theirs.covered+"/"+forecast.theirs.required+" starters"+
    (forecast.approximate?" · some projections/game times incomplete":"");
}
function getProjections(){
  if(!state.week||state.projectionBusy)return Promise.resolve();
  var w=state.week,season=state.league&&state.league.season||new Date().getUTCFullYear();
  if(state.projectionWeek===w&&state.projections&&Date.now()-state.projectionAt<30*60*1000)return Promise.resolve();
  state.projectionBusy=true;state.projectionError=null;
  var first="https://api.sleeper.app/v1/projections/nfl/regular/"+encodeURIComponent(season)+"/"+w;
  var alternate="https://api.sleeper.com/projections/nfl/"+encodeURIComponent(season)+"/"+w+"?season_type=regular";
  function normalize(v){
    if(Array.isArray(v)){var out={};v.forEach(function(x){if(x && (x.player_id||x.player&&x.player.player_id))out[String(x.player_id||x.player.player_id)]=x.stats||x;});return out;}
    return v&&typeof v==="object"?v:{};
  }
  return fetchJson(first,15000).catch(function(){return fetchJson(alternate,15000);}).then(function(data){
    if(state.week!==w)return;
    var raw=normalize(data);
    if(!Object.keys(raw).length)throw Error("Sleeper returned no weekly projections");
    var used=new Set();
    state.rosters.forEach(function(r){(r.players||[]).forEach(function(id){used.add(String(id));});});
    var sparse={};used.forEach(function(id){if(raw[id])sparse[id]=raw[id];});
    state.projections=sparse;state.projectionAt=Date.now();state.projectionWeek=w;state.projectionError=null;renderProjections();
  }).catch(function(e){
    if(state.week===w){state.projections=null;state.projectionError=e.message||"Unable to load";renderProjections();}
  }).finally(function(){state.projectionBusy=false;});
}

function render(){
  $("weekLabel").textContent="WEEK "+(state.week||"—");
  renderScore();renderLineup("mine","myPlayers");renderLineup("theirs","theirPlayers");
  renderZones();renderGames();renderProjections();renderActivity();updateStatus();
}
function pointEvents(pair){
  var current=Core.snapshot(pair), past=state.before;
  var deltas=Core.changes(past,current);
  var playerDeltas=deltas.filter(function(d){return !d.key.endsWith(":total");});
  var events=[];
  playerDeltas.forEach(function(d){
    var sections=d.key.split(":"),side=sections[0],bench=sections.includes("bench"),id=sections[sections.length-1];
    var p=Core.lineup(pair[side],state.players,bench).find(function(x){return x.id===id;});
    var name=p?p.name:"#"+id;
    events.push({at:Date.now(),side:side,title:name,detail:(bench?"Bench · ":"")+"Fantasy points "+(d.delta>0?"increased":"decreased")+" · now "+fmt(d.points),delta:d.delta});
    state.flashes[d.key]=Date.now();
  });
  // Team-only adjustments may not be attributable to any one player (e.g., manual scoring).
  deltas.filter(function(d){return d.key.endsWith(":total");}).forEach(function(d){
    var side=d.key.split(":")[0];
    var covered=playerDeltas.some(function(p){return p.key.startsWith(side+":") && !p.key.includes(":bench:");});
    if(!covered)events.push({at:Date.now(),side:side,title:"Team total updated",detail:"Sleeper team-score movement, player detail unavailable",delta:d.delta});
  });
  state.before=current;
  store(key()+"-snapshot",current);
  if(events.length){
    state.feed=events.concat(state.feed).slice(0,100);
    store(key()+"-feed",state.feed);
    if(state.sound)beep();
    if(state.notify && typeof Notification!=="undefined" && Notification.permission==="granted"){
      var x=events[0];try{new Notification((x.side==="mine"?"Your":"Opponent")+" fantasy score changed",{body:x.title+" "+(x.delta>0?"+":"")+fmt(x.delta),tag:"nfl-rz-score"});}catch(e){}
    }
  }
}
var context=null;
function beep(){
  try{var Ctx=window.AudioContext||window.webkitAudioContext;if(!Ctx)return;if(!context)context=new Ctx();
    if(context.state==="suspended")context.resume();
    var osc=context.createOscillator(),gain=context.createGain();
    osc.type="sine";osc.frequency.value=880;osc.connect(gain);gain.connect(context.destination);
    gain.gain.setValueAtTime(.001,context.currentTime);gain.gain.exponentialRampToValueAtTime(.06,context.currentTime+.02);
    gain.gain.exponentialRampToValueAtTime(.001,context.currentTime+.18);
    osc.start();osc.stop(context.currentTime+.19);
  }catch(e){}
}
function loadPlayerIndex(){
  var used=new Set();state.rosters.forEach(function(r){(r.players||[]).forEach(function(id){used.add(String(id));});});
  var cached=read(KCACHE);
  if(cached && cached.data && Date.now()-cached.at<86400000 && Array.from(used).every(function(id){return cached.data[id] || /^[A-Z]+$/.test(id);})){
    state.players=cached.data;render();return Promise.resolve();
  }
  return fetchJson(url("players/nfl"),30000).then(function(all){
    var compact={};
    used.forEach(function(id){
      var p=all[id];if(p)compact[id]={full_name:p.full_name,first_name:p.first_name,last_name:p.last_name,position:p.position,team:p.team};
    });
    state.players=compact;store(KCACHE,{at:Date.now(),data:compact});render();
  }).catch(function(){if(cached && cached.data)state.players=cached.data;render();});
}
function getESPN(){
  if(!state.week)return Promise.resolve();
  var season=state.league && state.league.season || new Date().getUTCFullYear();
  var params="?week="+encodeURIComponent(state.week)+"&seasontype=2&dates="+encodeURIComponent(season)+"&limit=100";
  return fetchJson("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"+params,12000).then(function(data){
    var result=Core.gameData(data.events||[]);
    var newKeys=new Set(result.zones.map(function(z){return z.id;}));
    if(state.zoneKeys!==null){
      var added=result.zones.filter(function(z){return !state.zoneKeys.has(z.id);});
      added.forEach(function(z){
        var hasRelevant=["mine","theirs"].some(function(side){
          return Core.lineup(state.pair[side],state.players,false).some(function(p){return Core.norm(p.team)===z.team && !["DEF","K","—"].includes(p.position);});
        });
        if(hasRelevant){
          var yourPlayer=Core.lineup(state.pair.mine,state.players,false).some(function(p){return Core.norm(p.team)===z.team && !["DEF","K","—"].includes(p.position);});
          state.feed.unshift({at:Date.now(),side:yourPlayer?"mine":"theirs",title:z.team+" inside the 20",detail:"NFL team opportunity · not a confirmed player touch",delta:null});
          if(state.sound)beep();
        }
      });
      if(added.length)store(key()+"-feed",state.feed.slice(0,100));
    }
    state.zoneKeys=newKeys;state.games=result.games;state.zones=result.zones;
    state.fullGames=Core.listGames(data.events||[]);state.lastEspnTime=Date.now();state.errors.espn=null;render();
  }).catch(function(e){state.errors.espn=e.message||"Feed error";render();});
}
function getSleeper(){
  if(!state.week)return Promise.resolve();
  return fetchJson(url("league/"+encodeURIComponent(cfg.leagueId)+"/matchups/"+state.week)).then(function(rows){
    if(!Array.isArray(rows))throw Error("Invalid matchup response");
    var pair=Core.findMatchup(rows,cfg.rosterId);
    if(!pair.mine)throw Error("Your roster was not found in Week "+state.week);
    state.rows=rows;state.pair=pair;pointEvents(pair);
    state.lastUpdated=Date.now();state.errors.sleeper=null;render();
  }).catch(function(e){state.errors.sleeper=e.message||"Could not load";render();});
}
function tick(){
  if(state.loading||!state.week)return;
  state.loading=true;
  Promise.allSettled([getSleeper(),getESPN()]).finally(function(){state.loading=false;updateStatus();});
}
function resetWeek(week,override){
  if(!Number.isInteger(week) || week<1 || week>18)return;
  state.week=week;state.pair={mine:null,theirs:null};state.rows=[];state.before=read(key()+"-snapshot");
  state.feed=read(key()+"-feed")||[];state.flashes={};state.games={};state.zones=[];state.fullGames=[];state.selectedGame=null;state.zoneKeys=null;
  state.projections=null;state.projectionAt=0;state.projectionWeek=null;state.projectionError=null;
  cfg.weekOverride=override?week:null;store(KCFG,cfg);render();getProjections();tick();
}
function startTimer(){
  if(state.interval)clearInterval(state.interval);
  state.interval=setInterval(function(){tick();},18000);
}
function init(){
  $("leagueInput").value=cfg.leagueId;$("rosterInput").value=cfg.rosterId;
  Array.from(document.querySelectorAll(".view-switch button")).forEach(function(btn){
    btn.addEventListener("click",function(){
      var v=btn.getAttribute("data-view");
      $("lineups").setAttribute("data-view",v);
      Array.from(document.querySelectorAll(".view-switch button")).forEach(function(b){
        var yes=b===btn;b.classList.toggle("active",yes);b.setAttribute("aria-pressed",String(yes));
      });
    });
  });
  $("benchToggle").checked=false;$("benchToggle").addEventListener("change",function(e){state.bench=e.target.checked;render();});
  $("sound").addEventListener("click",function(){state.sound=!state.sound;$("sound").textContent=state.sound?"🔔 Sound on":"🔕 Sound off";if(state.sound)beep();});
  $("notifications").addEventListener("click",function(){
    if(typeof Notification==="undefined"){$("notifications").textContent="Not supported";return;}
    if(Notification.permission==="granted"){state.notify=!state.notify;$("notifications").textContent=state.notify?"Alerts on":"Alerts off";return;}
    Notification.requestPermission().then(function(p){state.notify=p==="granted";$("notifications").textContent=state.notify?"Alerts on":"Alerts unavailable";}).catch(function(){$("notifications").textContent="Alerts unavailable";});
  });
  $("refresh").addEventListener("click",function(){state.projectionAt=0;getProjections();tick();});
  $("gameStrip").addEventListener("click",function(e){
    var t=e.target.closest("[data-game]");
    if(!t)return;
    state.selectedGame=t.getAttribute("data-game");renderGames();
    t=document.querySelector('.game-tab.selected');if(t)t.scrollIntoView({behavior:"smooth",inline:"center",block:"nearest"});
  });
  function moveGame(delta){
    var games=listedGames(),at=games.findIndex(function(g){return g.id===state.selectedGame;});
    if(!games.length)return;
    state.selectedGame=games[(at+delta+games.length)%games.length].id;renderGames();
    var t=document.querySelector('.game-tab.selected');if(t)t.scrollIntoView({behavior:"smooth",inline:"center",block:"nearest"});
  }
  // Flick left/right over the field to move between games (vertical scrolling remains native).
  var swipeStartX=null,swipeStartY=null;
  $("gameDetails").addEventListener("touchstart",function(e){
    if(!e.touches||e.touches.length!==1)return;
    swipeStartX=e.touches[0].clientX;swipeStartY=e.touches[0].clientY;
  },{passive:true});
  $("gameDetails").addEventListener("touchend",function(e){
    if(swipeStartX===null||!e.changedTouches||!e.changedTouches.length)return;
    var dx=e.changedTouches[0].clientX-swipeStartX;
    var dy=e.changedTouches[0].clientY-swipeStartY;
    swipeStartX=null;swipeStartY=null;
    if(Math.abs(dx)>48 && Math.abs(dx)>Math.abs(dy)*1.4)moveGame(dx<0?1:-1);
  },{passive:true});
  $("gamePrev").addEventListener("click",function(){moveGame(-1);});
  $("gameNext").addEventListener("click",function(){moveGame(1);});
  $("gameStrip").addEventListener("keydown",function(e){if(e.key==="ArrowRight"||e.key==="ArrowLeft"){e.preventDefault();moveGame(e.key==="ArrowRight"?1:-1);}});

  $("weekPrev").addEventListener("click",function(){resetWeek((state.week||state.nflWeek||9)-1,true);});
  $("weekNext").addEventListener("click",function(){resetWeek((state.week||state.nflWeek||9)+1,true);});
  $("currentWeek").addEventListener("click",function(){if(state.nflWeek)resetWeek(state.nflWeek,false);});
  $("saveSettings").addEventListener("click",function(){
    var league=$("leagueInput").value.trim(),roster=$("rosterInput").value.trim();
    if(!/^[0-9]{5,22}$/.test(league)||!/^[0-9]{1,2}$/.test(roster)){alert("Enter a valid numeric Sleeper league ID and roster number.");return;}
    cfg={leagueId:league,rosterId:roster};store(KCFG,cfg);state.before=null;state.feed=[];bootstrap();
  });
  $("clearActivity").addEventListener("click",function(){state.feed=[];store(key()+"-feed",[]);renderActivity();});
  document.addEventListener("visibilitychange",function(){if(!document.hidden)tick();});
  bootstrap();startTimer();
}
function bootstrap(){
  state.lastUpdated=0;state.errors={};state.pair={mine:null,theirs:null};state.players={};state.games={};state.zones=[];state.fullGames=[];state.selectedGame=null;state.projections=null;state.projectionAt=0;state.projectionWeek=null;state.projectionError=null;
  state.week=null;render();
  Promise.all([
    fetchJson(url("league/"+encodeURIComponent(cfg.leagueId))),
    fetchJson(url("league/"+encodeURIComponent(cfg.leagueId)+"/rosters")),
    fetchJson(url("league/"+encodeURIComponent(cfg.leagueId)+"/users")),
    fetchJson(url("state/nfl"))
  ]).then(function(v){
    state.league=v[0];state.rosters=v[1];state.users=v[2];state.nflWeek=Number(v[3].week)||9;
    if(!Array.isArray(state.rosters)||!Array.isArray(state.users))throw Error("Invalid league roster data");
    var week=Number(cfg.weekOverride)||state.nflWeek;
    state.week=week;state.before=read(key()+"-snapshot");state.feed=read(key()+"-feed")||[];render();
    loadPlayerIndex();getProjections();tick();
  }).catch(function(e){state.errors.sleeper=e.message||"Cannot connect to league";render();});
}
init();
})();
