/* Projections are optional and unofficial. Win probability is OUR normal-approximation estimate, not Sleeper's. */
(function(root){
"use strict";
function n(x){if(x===null||x===undefined||x==="")return null;var y=Number(x);return Number.isFinite(y)?y:null;}
function mapData(value){
 var result={};
 if(Array.isArray(value)){
  value.forEach(function(x){
   if(x && (x.player_id||x.id)){var id=String(x.player_id||x.id);result[id]=x.stats||x.projections||x.projected_stats||x;}
  });
 }else if(value && typeof value==="object"){
  if(value.data&&typeof value.data==="object")return mapData(value.data);
  Object.keys(value).forEach(function(id){var x=value[id];if(x && typeof x==="object")result[id]=x.stats||x.projections||x.projected_stats||x;});
 }
 return result;
}
function project(raw,scoring){
 if(!raw||typeof raw!=="object")return null;
 var stats=raw.stats||raw;
 var adjusted=0,found=0;
 Object.keys(scoring||{}).forEach(function(k){
  var val=n(stats[k]),mult=n(scoring[k]);
  if(val===null||mult===null)return;
  if(k.startsWith("pts_")||k==="bonus")return;
  adjusted+=val*mult;found++;
 });
 if(found>=2)return Math.max(0,adjusted);
 var half=n(stats.pts_half_ppr);
 if(half!==null)return Math.max(0,half);
 var ppr=n(stats.pts_ppr),std=n(stats.pts_std);
 if(ppr!==null&&std!==null)return Math.max(0,(ppr+std)/2);
 if(ppr!==null&&scoring&&Number(scoring.rec)===1)return Math.max(0,ppr);
 if(std!==null&&scoring&&Number(scoring.rec)===0)return Math.max(0,std);
 if(found)return Math.max(0,adjusted);
 return null;
}
function remainingFraction(g){
 if(!g||g.state==="pre")return 1;
 if(g.state==="post")return 0;
 if(g.state!=="in")return 1;
 var q=n(g.period)||1;if(q>4)return .05;
 var m=String(g.clock||"").match(/^(\d+):(\d{1,2})$/);
 var secs=m?(Number(m[1])*60+Number(m[2])):450;
 return Math.max(0,Math.min(1,((4-q)*900+secs)/3600));
}
function predict(row,index,games,rawMap,scoring){
 if(!row)return {final:null,remaining:null,coverage:0,total:0,variance:null};
 var starters=(row.starters||[]).map(String),map=row.players_points||row.player_points||{};
 var sum=0,rem=0,variance=0,known=0,needs=0,missing=0;
 starters.forEach(function(id,i){
  if(!id||id==="0")return;
  var p=index[id]||{},team=p.team||(/^[A-Z]{2,3}$/.test(id)?id:"");
  team=root.RedZoneCore?root.RedZoneCore.norm(team):team;
  var g=games[team],frac=remainingFraction(g),actual=n(Array.isArray(row.starters_points)?row.starters_points[i]:map[id]);
  if(actual===null)actual=n(map[id]);if(actual===null)actual=0;
  sum+=actual;
  if(g&&g.state==="post"){known++;return;}
  needs++;
  var baseline=project(rawMap[id],scoring);
  if(baseline===null){missing++;return;}
  known++;
  var expected=g&&g.state==="in"?baseline*frac:Math.max(0,baseline-actual);
  if(g&&g.state!=="pre"&&g.state!=="in")expected=0;
  rem+=expected;
  var position=p.position||"FLEX",vol=position==="QB"?.38:position==="DEF"?.58:.51;
  variance+=Math.pow(Math.max(1.5,baseline*vol),2)*Math.max(.08,frac);
 });
 var ready=missing===0&&starters.length>0;
 return {final:ready?sum+rem:null,remaining:ready?rem:null,variance:ready?variance:null,
  coverage:known,total:starters.length,missing:missing};
}
function erf(x){
 var sign=x<0?-1:1;x=Math.abs(x);var t=1/(1+.3275911*x);
 return sign*(1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-.284496736)*t+.254829592)*t*Math.exp(-x*x));
}
function winProbability(a,b){
 if(a.final===null||b.final===null)return null;
 var variance=(a.variance||0)+(b.variance||0);
 if(variance<.0001)return a.final>b.final?1:a.final<b.final?0:.5;
 var delta=(a.final-b.final)/Math.sqrt(2*variance);
 return Math.max(.005,Math.min(.995,.5*(1+erf(delta))));
}
var api={mapData:mapData,project:project,predict:predict,winProbability:winProbability,remainingFraction:remainingFraction};
root.RedZoneProjections=api;if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
