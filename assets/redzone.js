(function(){
"use strict";
var Core=window.RedZoneCore;
var DEF={leagueId:"1388984626868912128",rosterId:"9"};
var KCFG="nfl-lab-redzone-config-v1", KCACHE="nfl-lab-redzone-players-v1";
var cfg=read(KCFG)||DEF;
cfg.leagueId=String(cfg.leagueId||DEF.leagueId).trim();cfg.rosterId=String(cfg.rosterId||DEF.rosterId).trim();
var state={week:null,nflWeek:null,rows:[],rosters:[],users:[],league:null,players:{},games:{},zones:[],zoneKeys:null,
  pair:{mine:null,theirs:null},feed:[],before:null,loading:false,interval:null,errors:{},lastUpdated:0,
  bench:false,sound:false,notify:false,flashes:{},lastEspnTime:0};
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
    var g=gameStatus(p.team),danger=activeZonesFor(side,p);
    var deltaKey=side+":"+(p.bench?"bench:":"")+p.id;
    var changed=state.flashes[deltaKey] && Date.now()-state.flashes[deltaKey]<6000;
    return '<div class="player '+(p.bench?"bench ":"")+(danger?"redzone "+(side==="theirs"?"enemy ":""):"")+(changed?"changed":"")+'">'+
      '<div class="who">'+playerPhoto(p)+'<span class="who-text"><strong title="'+esc(p.name)+'">'+esc(p.name)+'</strong><small>'+
      '<span class="position">'+esc(p.position)+'</span>'+teamMark(p.team,"tiny")+
      (p.bench?'<span class="bench-label">BENCH</span>':'')+
      (danger?'<span class="threat-indicator">● RZ</span>':'')+
      '</small></span></div>'+
      '<div class="game '+g.className+'">'+esc(g.main)+'<small>'+esc(g.sub)+'</small></div>'+
      '<div class="playerpoints '+(p.points===null?"unknown":"")+'">'+fmt(p.points)+'</div></div>';
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
function render(){
  $("weekLabel").textContent="WEEK "+(state.week||"—");
  renderScore();renderLineup("mine","myPlayers");renderLineup("theirs","theirPlayers");
  renderZones();renderActivity();updateStatus();
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
    state.lastEspnTime=Date.now();state.errors.espn=null;render();
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
  state.feed=read(key()+"-feed")||[];state.flashes={};state.games={};state.zones=[];state.zoneKeys=null;
  cfg.weekOverride=override?week:null;store(KCFG,cfg);render();tick();
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
  $("refresh").addEventListener("click",tick);
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
  state.lastUpdated=0;state.errors={};state.pair={mine:null,theirs:null};state.players={};state.games={};state.zones=[];
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
    loadPlayerIndex();tick();
  }).catch(function(e){state.errors.sleeper=e.message||"Cannot connect to league";render();});
}
init();
})();
