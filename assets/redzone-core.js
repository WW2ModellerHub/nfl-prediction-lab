/* Pure matchup and Red Zone utilities. Kept dependency-free for browser + Node tests. */
(function (root) {
  "use strict";
  function num(value) { return value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)) ? Number(value) : null; }
  function norm(team) {
    var code=String(team||"").trim().toUpperCase();
    return ({WSH:"WAS",JAC:"JAX",LA:"LAR",SD:"LAC",STL:"LAR",OAK:"LV"})[code] || code;
  }
  function starterScore(row, id, index) {
    var arr=row && row.starters_points;
    if (Array.isArray(arr) && num(arr[index])!==null) return num(arr[index]);
    if (arr && typeof arr==="object" && Object.prototype.hasOwnProperty.call(arr,id)) return num(arr[id]);
    var byId=row && (row.players_points || row.player_points);
    if (byId && Object.prototype.hasOwnProperty.call(byId,id)) return num(byId[id]);
    return null;
  }
  function benchScore(row, id) {
    var map=row && (row.players_points || row.player_points);
    return map && Object.prototype.hasOwnProperty.call(map,id) ? num(map[id]) : null;
  }
  function lineup(row, playerIndex, bench) {
    if (!row) return [];
    var starters=(row.starters || []).map(String).filter(function(x){return x && x!=="0";});
    var ids=bench ? (row.players||[]).map(String).filter(function(x){return x && x!=="0" && !starters.includes(x);}) : starters;
    return ids.map(function(id,index){
      var info=playerIndex[id] || {};
      var knownName=info.full_name || [info.first_name,info.last_name].filter(Boolean).join(" ");
      return {id:id,name:knownName || (id.length<=4 && /^[A-Z]+$/.test(id) ? id+" Defence" : "#"+id),
        position:info.position || (/^[A-Z]+$/.test(id)?"DEF":"—"),team:norm(info.team || (/^[A-Z]+$/.test(id)?id:"")),
        points:bench?benchScore(row,id):starterScore(row,id,index),bench:Boolean(bench)};
    });
  }
  function findMatchup(rows, myRoster) {
    var own=(rows||[]).find(function(r){return String(r.roster_id)===String(myRoster);});
    if (!own) return {mine:null,theirs:null};
    var other=own.matchup_id===null || own.matchup_id===undefined ? null:
      rows.find(function(r){return r!==own && r.matchup_id!==null && r.matchup_id!==undefined && String(r.matchup_id)===String(own.matchup_id);}) || null;
    return {mine:own,theirs:other};
  }
  function snapshot(pair) {
    var out={};
    ["mine","theirs"].forEach(function(side){
      var row=pair && pair[side];
      if (!row) return;
      out[side+":total"]=num(row.points);
      var starterIds=(row.starters||[]).map(String);
      starterIds.forEach(function(id,i){if(id && id!=="0") out[side+":"+id]=starterScore(row,id,i);});
      var p=row.players||[]; p.forEach(function(id){id=String(id); if(!starterIds.includes(id)) out[side+":bench:"+id]=benchScore(row,id);});
    });
    return out;
  }
  function changes(previous, current) {
    if (!previous) return [];
    return Object.keys(current||{}).filter(function(k){
      return num(previous[k])!==null && num(current[k])!==null && Math.abs(current[k]-previous[k])>=0.005;
    }).map(function(k){return {key:k,delta:Math.round((current[k]-previous[k])*100)/100,points:current[k]};});
  }
  function gameData(events) {
    var gameMap={}; var zones=[];
    (events||[]).forEach(function(event){
      var comp=event.competitions && event.competitions[0];
      if(!comp) return;
      var state=(event.status && event.status.type && event.status.type.state)||"pre";
      var situation=comp.situation || event.situation || {};
      var opponents=(comp.competitors||[]);
      var possession=opponents.find(function(c){return String(c.id)===String(situation.possession);}) ||
        opponents.find(function(c){return c.possession===true;});
      var offensive=possession && possession.team ? norm(possession.team.abbreviation) : "";
      var teams=opponents.map(function(c){return norm(c.team && c.team.abbreviation);}).filter(Boolean);
      opponents.forEach(function(c){
        var abbr=norm(c.team && c.team.abbreviation);
        var against=opponents.find(function(x){return x!==c;});
        gameMap[abbr]={state:state,clock:event.status && event.status.displayClock || "",period:event.status && event.status.period || 0,
          opponent:norm(against && against.team && against.team.abbreviation),
          start:event.date||"",inRedZone:state==="in" && situation.isRedZone===true && offensive===abbr,
          situation:situation.downDistanceText||"",offense:offensive};
      });
      if(state==="in" && situation.isRedZone===true && offensive) {
        zones.push({id:String(event.id||comp.id)+":"+offensive,gameId:String(event.id||comp.id),team:offensive,
          opponent:teams.find(function(x){return x!==offensive;})||"",clock:event.status && event.status.displayClock || "",
          period:event.status && event.status.period || 0,downDistance:situation.downDistanceText||"",
          lastPlay:situation.lastPlay && situation.lastPlay.text || ""});
      }
    });
    return {games:gameMap,zones:zones};
  }

  /** Field is drawn away (left) to home (right). Never guess position from a down alone. */
  function listGames(events){
    return (events||[]).map(function(e){
      var c=e.competitions && e.competitions[0];if(!c)return null;
      var competitors=c.competitors||[];
      var home=competitors.find(function(t){return t.homeAway==="home";})||competitors[0];
      var away=competitors.find(function(t){return t.homeAway==="away";})||competitors.find(function(t){return t!==home;});
      if(!home || !away || !home.team || !away.team)return null;
      var h=norm(home.team.abbreviation),a=norm(away.team.abbreviation);
      var sit=c.situation||e.situation||{},s=e.status||{},state=s.type&&s.type.state||"pre";
      var holder=competitors.find(function(t){return String(t.id)===String(sit.possession);})||
        competitors.find(function(t){return t.possession===true;});
      var offense=holder&&holder.team?norm(holder.team.abbreviation):"";
      var downText=String(sit.downDistanceText||"");
      var at=downText.match(/\bat\s+([A-Z]{2,3})\s+([0-9]{1,2})\b/i);
      var midfield=/\bat\s+(?:midfield|50)\b/i.test(downText);
      var yr=num(sit.yardsToEndzone),position=null,from="";
      if(state==="in" && offense && (offense===a||offense===h)){
        if(yr!==null && yr>=0 && yr<=100){
          position=offense===a?100-yr:yr;from="ESPN yards to end zone";
        } else if(midfield){position=50;from="ESPN midfield";
        }else if(at){
          var side=norm(at[1]),yard=Number(at[2]);
          if(yard>=0&&yard<=50 && side===a){position=yard;from="ESPN down and distance";}
          else if(yard>=0&&yard<=50 && side===h){position=100-yard;from="ESPN down and distance";}
        }
      }
      var homeScore=num(home.score),awayScore=num(away.score);
      return {id:String(e.id||c.id),home:h,away:a,homeScore:homeScore,awayScore:awayScore,
        state:state,clock:s.displayClock||"",period:s.period||0,start:e.date||"",
        possession:offense,position:position,positionSource:from,downDistance:downText,
        isRedZone:state==="in"&&sit.isRedZone===true,lastPlay:sit.lastPlay&&sit.lastPlay.text||""};
    }).filter(Boolean);
  }

  /** Fantasy players in one offensive red-zone possession, grouped by side and exposure. */
  function zoneParticipants(zone,pair,players){
    var out={mine:{offense:[],kickers:[],defense:[]},theirs:{offense:[],kickers:[],defense:[]}};
    ["mine","theirs"].forEach(function(side){
      lineup(pair&&pair[side],players||{},false).forEach(function(p){
        if(norm(p.team)===norm(zone.team)){
          if(p.position==="K")out[side].kickers.push(p);
          else if(p.position!=="DEF"&&p.position!=="—")out[side].offense.push(p);
        }else if(norm(p.team)===norm(zone.opponent)&&p.position==="DEF"){
          out[side].defense.push(p);
        }
      });
    });
    return out;
  }

  /** Convert confirmed ESPN yard-line text into a left-to-right football-field coordinate. */
  function fieldSpot(text,away,home){
    var raw=String(text||"");
    if(/\bmidfield\b/i.test(raw))return 50;
    var matches=raw.match(/(?:^|\bat\s+)([A-Z]{2,3})\s+([0-9]{1,2})(?![:0-9])/i);
    if(!matches)return null;
    var side=norm(matches[1]),yard=Number(matches[2]);
    if(!Number.isFinite(yard)||yard<0||yard>50)return null;
    return side===norm(away)?yard:side===norm(home)?100-yard:null;
  }

  /** Read ESPN current-drive play end location, never using the previous drive. */
  function summaryFieldSpot(game,summary){
    if(!game||game.state!=="in"||!game.possession||!summary)return null;
    var comp=summary.header&&summary.header.competitions&&summary.header.competitions[0]||{};
    var situation=comp.situation||summary.situation||{};
    var pos=fieldSpot(situation.downDistanceText,game.away,game.home);
    if(pos!==null)return {position:pos,source:"ESPN game situation"};
    var remaining=num(situation.yardsToEndzone);
    if(remaining!==null&&remaining>=0&&remaining<=100){
      return {position:game.possession===game.away?100-remaining:remaining,source:"ESPN game situation"};
    }
    var current=summary.drives&&summary.drives.current;
    if(!current)return null;
    var currentTeam=norm(current.team&&(current.team.abbreviation||current.team.team&&current.team.team.abbreviation)||"");
    if(currentTeam&&currentTeam!==game.possession)return null;
    var plays=Array.isArray(current.plays)?current.plays:[];
    for(var i=plays.length-1;i>=0;i--){
      var p=plays[i]||{};
      var end=p.end||{};
      pos=fieldSpot(end.text||end.displayValue||"",game.away,game.home);
      if(pos!==null)return {position:pos,source:"ESPN current-drive last confirmed spot"};
    }
    return null;
  }

  /** Sleeper's undocumented weekly projections are player-id -> projected raw stats. */
  function projectionFor(stat,settings){
    if(!stat || typeof stat!=="object")return null;
    if(stat.stats && typeof stat.stats==="object")stat=stat.stats;
    var total=0,hits=0;
    Object.keys(settings||{}).forEach(function(k){
      var v=num(stat[k]),weight=num(settings[k]);
      if(v!==null&&weight!==null&&k!=="bonus_rec_yd_100"&&k!=="bonus_rush_yd_100"&&k!=="bonus_pass_yd_300"){total+=v*weight;hits++;}
    });
    if(hits)return Math.max(-20,total);
    var fallback=(num(settings&&settings.rec)===0.5?num(stat.pts_half_ppr):
      num(settings&&settings.rec)===1?num(stat.pts_ppr):num(stat.pts_std));
    return fallback;
  }
  function gameRemaining(game){
    if(!game)return null;
    if(game.state==="post")return 0;
    if(game.state==="pre")return 1;
    if(game.state!=="in")return null;
    var period=Number(game.period),clock=String(game.clock||"");
    if(!period||period>=5)return 0;
    var parts=clock.match(/^(\d{1,2}):(\d{2})$/),sec=parts?Number(parts[1])*60+Number(parts[2]):450;
    return Math.max(0,Math.min(1,(4-period+Math.min(900,sec)/900)/4));
  }
  /**
   * A score share is not a win probability. Compare projected-final points
   * against a transparent remaining-score uncertainty assumption instead.
   */
  function winChanceFromProjected(myFinal,theirFinal,spread){
    var a=num(myFinal),b=num(theirFinal),sd=num(spread);
    if(a===null||b===null)return null;
    var d=a-b;
    if(sd!==null && sd<0.05)return d>0?1:d<0?0:0.5;
    sd=Math.max(6,sd===null?Math.sqrt(Math.max(0,a)+Math.max(0,b))*0.92:sd);
    return Math.max(0.005,Math.min(0.995,1/(1+Math.exp(-1.702*d/sd))));
  }
  /**
   * Current Sleeper scores are authoritative. Projection data is a forecast,
   * not a live tally. When a game status is missing, use player's projected
   * points minus points scored rather than inventing an NFL clock.
   */
  function estimateMatchup(pair,projections,scoring,games,players){
    var sides={};
    ["mine","theirs"].forEach(function(side){
      var row=pair && pair[side];
      if(!row){sides[side]=null;return;}
      var total=num(row.points);
      if(total===null){sides[side]=null;return;}
      var ids=(row.starters||[]).map(String).filter(function(x){return x && x!=="0";});
      var remaining=0,variance=0,covered=0,missing=0,uncertain=0,baseline=0;
      ids.forEach(function(id,i){
        var st=projections && projections[id];
        var value=projectionFor(st,scoring);
        if(value===null){missing++;return;}
        covered++;baseline+=value;
        var team=norm((players&&players[id]&&players[id].team) ||
          (st&&st.player&&st.player.team)||(st&&st.team)||(/^[A-Z]{2,3}$/.test(id)?id:""));
        var game=games&&games[team],left=gameRemaining(game);
        var already=starterScore(row,id,i);
        var unfinished;
        if(left===null){
          // Degraded mode: projections still support a score-based estimate,
          // but it is explicitly labelled approximate and has wider variance.
          unfinished=Math.max(0,value-Math.max(0,already||0));
          uncertain++;
        }else{
          unfinished=Math.max(0,value)*left;
          // Protect against an empty points feed double counting a completed game.
          if(left===0)unfinished=0;
        }
        remaining+=unfinished;
        var individualSD=Math.max(3.5,Math.abs(value)*0.62);
        variance+=individualSD*individualSD*(left===null?1.25:left);
      });
      sides[side]={current:total,final:total+remaining,remaining:remaining,
        variance:variance,covered:covered,required:ids.length,missing:missing,
        uncertain:uncertain,baseline:baseline};
    });
    var a=sides.mine,b=sides.theirs;
    if(!a||!b)return {mine:a,theirs:b,win:null,reason:"Waiting for both teams' scores"};
    // Do not show artificial certainty from a single forecasted player.
    if(a.covered===0||b.covered===0)return {mine:a,theirs:b,win:null,reason:"Sleeper projected scores unavailable"};
    var residual=a.missing+b.missing;
    var sd=Math.sqrt(a.variance+b.variance+residual*100);
    var alreadyFinal=(a.remaining<0.005 && b.remaining<0.005 && !residual && !a.uncertain && !b.uncertain);
    var chance=winChanceFromProjected(a.final,b.final,alreadyFinal?0:Math.max(6,sd));
    var approximate=Boolean(residual||a.uncertain||b.uncertain);
    return {mine:a,theirs:b,win:chance,approximate:approximate,
      reason:approximate?"Partial player projections or NFL game states — lower confidence":null};
  }

  var api={num:num,norm:norm,starterScore:starterScore,benchScore:benchScore,lineup:lineup,findMatchup:findMatchup,snapshot:snapshot,changes:changes,gameData:gameData,listGames:listGames,projectionFor:projectionFor,gameRemaining:gameRemaining,estimateMatchup:estimateMatchup,winChanceFromProjected:winChanceFromProjected,zoneParticipants:zoneParticipants,fieldSpot:fieldSpot,summaryFieldSpot:summaryFieldSpot};
  root.RedZoneCore=api;
  if(typeof module!=="undefined" && module.exports) module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
