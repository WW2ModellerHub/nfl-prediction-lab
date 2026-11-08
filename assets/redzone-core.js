/* Pure matchup and Red Zone utilities. Kept dependency-free for browser + Node tests. */
(function (root) {
  "use strict";
  function num(value) { return value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)) ? Number(value) : null; }
  function norm(team) {
    var code=String(team||"").trim().toUpperCase();
    return ({WSH:"WAS",JAC:"JAX",LA:"LAR",SD:"LAC",STL:"LAR",OAK:"LV"})[code] || code;
  }
  function starterScore(row, id, index) {
    var byId=row && (row.players_points || row.player_points);
    if (byId && Object.prototype.hasOwnProperty.call(byId,id)) return num(byId[id]);
    var arr=row && row.starters_points;
    if (Array.isArray(arr)) return num(arr[index]);
    if (arr && typeof arr==="object" && Object.prototype.hasOwnProperty.call(arr,id)) return num(arr[id]);
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
  var api={num:num,norm:norm,starterScore:starterScore,benchScore:benchScore,lineup:lineup,findMatchup:findMatchup,snapshot:snapshot,changes:changes,gameData:gameData};
  root.RedZoneCore=api;
  if(typeof module!=="undefined" && module.exports) module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
