/* Shared safe live NFL win probability renderer.  No bookmaker claims. */
(function(root){
"use strict";
function h(x){return String(x==null?"":x).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]});}
function pct(p){return p==null?"—":(100*p).toFixed(1)+"%";}
function delta(p){return (p>=0?"+":"−")+(Math.abs(p)*100).toFixed(1)+" pp";}
function result(g,live){return root.NFLGameLiveModel.estimate(live, g&&g.homeProbability);}
function render(g,live,reference,expanded){
 if(!g)return '<div class="livewin-empty">No archived pregame pick.</div>';
 var r=result(g,live),home=h(g.home),away=h(g.away),prior=pct(g.homeProbability);
 if(r.status==="final"){
   var hs=live&&live.homeScore,as=live&&live.awayScore;
   var aligned=live&&live.home===g.home&&live.away===g.away;
   var hasScores=aligned&&hs!==null&&hs!==undefined&&as!==null&&as!==undefined&&
     Number.isInteger(Number(hs))&&Number.isInteger(Number(as))&&Number(hs)>=0&&Number(as)>=0;
   if(!hasScores)return '<div class="livewin-result livewin-result-pending"><strong>FINAL</strong><small>Score awaiting confirmation</small></div>';
   var homeScore=Number(hs),awayScore=Number(as),tied=homeScore===awayScore;
   var favorite=Number(g.homeProbability)>=.5?g.home:g.away;
   var winner=tied?null:(homeScore>awayScore?g.home:g.away);
   var correct=!tied&&winner===favorite;
   return '<div class="livewin-result '+(tied?'livewin-result-tie':correct?'livewin-result-correct':'livewin-result-wrong')+'">'+
     '<strong>'+(tied?'— TIED GAME':correct?'✓ CORRECT PICK':'✕ WRONG PICK')+'</strong>'+
     (expanded?'<small>Final: '+away+' '+awayScore+' – '+home+' '+homeScore+'</small>':'')+
     '</div>';
 }
 if(r.status!=="experimental"){
   var desc=
     r.status==="overtime"?"Overtime · estimate unavailable.":
     r.reason||"Waiting for live score and clock.";
   return '<div class="livewin-unavailable"><span>◉ IN-PLAY</span><b>'+h(desc)+'</b>'+
     '<small>Archived pregame '+home+' win: '+prior+'. Live estimate unavailable.</small></div>';
 }
 var favorite=r.favorite, winning=r.winProbability, other= favorite===g.home?g.away:g.home;
 var display='<div class="livewin-top"><span class="livewin-live">● IN-PLAY · EXPERIMENTAL</span></div>'+
  '<div class="livewin-main"><div><strong>'+pct(winning)+'</strong><span>'+h(favorite)+' to win</span></div>'+
  '<div class="livewin-versus">'+h(other)+' '+pct(1-winning)+'</div></div>'+
  '<div class="livewin-prob"><span style="width:'+(r.homeProbability*100).toFixed(2)+'%"></span></div>'+
  '<div class="livewin-labels"><small>'+home+' '+pct(r.homeProbability)+'</small><small>'+away+' '+pct(r.awayProbability)+'</small></div>';
 if(expanded){
  display+='<div class="livewin-attribution"><div class="livewin-subtitle">WHAT CHANGED</div>'+
    '<div class="livewin-factor"><span>Saved pregame</span><b>'+prior+'</b></div>'+
    r.layers.slice(1).map(function(row){return '<div class="livewin-factor"><span>'+h(row.name)+'</span><b class="'+(row.delta>=0?"up":"down")+'">'+delta(row.delta)+'</b></div>'}).join('')+
    '<div class="livewin-factor final"><span>Live '+home+' win probability</span><b>'+pct(r.homeProbability)+'</b></div></div>'+
    '<div class="livewin-inputs"><span>Clock: Q'+h(live.period)+' '+h(live.clock)+'</span>'+
    '<span>Score: '+away+' '+h(live.awayScore)+' – '+home+' '+h(live.homeScore)+'</span>'+
    '<span>Ball: '+h(live.possession||"not verified")+'</span>'+
    '<span>Position: '+h(r.possessionBasis)+'</span>'+
    '<span>ESPN checked: '+(live.fetchedAt?new Date(live.fetchedAt).toLocaleTimeString("en-GB",{timeZone:"Europe/London",hour:"2-digit",minute:"2-digit",second:"2-digit"}):"unknown")+' UK</span></div>';
  if(reference&&(!reference.fetchedAt||Date.now()-reference.fetchedAt<120000)&&
     Number.isFinite(reference.homeProbability)&&reference.homeProbability>=0&&reference.homeProbability<=1)
    display+='<div class="livewin-reference">ESPN reference (last published play): <b>'+pct(reference.homeProbability)+' '+home+'</b>'+
    '<small>External model · may lag.'+
    (Math.abs(reference.homeProbability-r.homeProbability)>=.15?
       ' <b>Model disagreement: '+(Math.abs(reference.homeProbability-r.homeProbability)*100).toFixed(1)+' pp · not a proven edge.</b>':'')+
    '</small></div>';
  display+='<p class="livewin-disclaimer">Experimental: archived pregame pick + ESPN score, clock and possession. Not historically validated or suitable for betting.</p>';
 }else{
   display+='<small class="livewin-mini">Pregame: '+prior+' '+home+' · '+(live.period?"Q"+h(live.period)+" "+h(live.clock):"game running")+'</small>';
 }
 return '<div class="livewin-panel '+(expanded?"livewin-expanded":"livewin-compact")+'">'+display+'</div>';
}
root.NFLGameLiveUI={render:render,result:result,pct:pct,delta:delta};
if(typeof module!=="undefined"&&module.exports)module.exports=root.NFLGameLiveUI;
})(typeof globalThis!=="undefined"?globalThis:this);
