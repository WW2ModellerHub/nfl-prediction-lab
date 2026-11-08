/* Shared safe live NFL win probability renderer.  No bookmaker claims. */
(function(root){
"use strict";
function h(x){return String(x==null?"":x).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]});}
function pct(p){return p==null?"—":(100*p).toFixed(1)+"%";}
function delta(p){return (p>=0?"+":"−")+(Math.abs(p)*100).toFixed(1)+" pp";}
function result(g,live){return root.NFLGameLiveModel.estimate(live, g&&g.homeProbability);}
function render(g,live,reference,expanded){
 if(!g)return '<div class="livewin-empty">No saved pregame forecast for this fixture.</div>';
 var r=result(g,live),home=h(g.home),away=h(g.away),prior=pct(g.homeProbability);
 if(r.status!=="experimental"){
   var desc=r.status==="final"?"Game finished. Final result is not a prediction.":
     r.status==="overtime"?"Overtime — no calibrated live forecast available.":
     r.reason||"Waiting for an in-play score and game clock from ESPN.";
   return '<div class="livewin-unavailable"><span>◉ NFL IN-PLAY FORECAST</span><b>'+h(desc)+'</b>'+
     '<small>Archived pregame '+home+' win: '+prior+'. We do not invent a live percentage when the data is unavailable.</small></div>';
 }
 var favorite=r.favorite, winning=r.winProbability, other= favorite===g.home?g.away:g.home;
 var display='<div class="livewin-top"><span class="livewin-live">● LIVE MODEL · EXPERIMENTAL</span><small>Not validated for betting</small></div>'+
  '<div class="livewin-main"><div><strong>'+pct(winning)+'</strong><span>'+h(favorite)+' to win</span></div>'+
  '<div class="livewin-versus">'+h(other)+' '+pct(1-winning)+'<small>Updated from current score & clock</small></div></div>'+
  '<div class="livewin-prob"><span style="width:'+(r.homeProbability*100).toFixed(2)+'%"></span></div>'+
  '<div class="livewin-labels"><small>'+home+' '+pct(r.homeProbability)+'</small><small>'+away+' '+pct(r.awayProbability)+'</small></div>';
 if(expanded){
  display+='<div class="livewin-attribution"><div class="livewin-subtitle">HOW THE HOME WIN CHANCE MOVED</div>'+
    '<div class="livewin-factor"><span>Saved pregame</span><b>'+prior+'</b></div>'+
    r.layers.slice(1).map(function(row){return '<div class="livewin-factor"><span>'+h(row.name)+'</span><b class="'+(row.delta>=0?"up":"down")+'">'+delta(row.delta)+'</b></div>'}).join('')+
    '<div class="livewin-factor final"><span>Live '+home+' win probability</span><b>'+pct(r.homeProbability)+'</b></div></div>'+
    '<div class="livewin-inputs"><span>Clock: Q'+h(live.period)+' '+h(live.clock)+'</span>'+
    '<span>Score: '+away+' '+h(live.awayScore)+' – '+home+' '+h(live.homeScore)+'</span>'+
    '<span>Ball: '+h(live.possession||"not verified")+'</span>'+
    '<span>Position: '+h(r.possessionBasis)+'</span></div>';
  if(reference&&Number.isFinite(reference.homeProbability)&&reference.homeProbability>=0&&reference.homeProbability<=1)
    display+='<div class="livewin-reference">ESPN reference (last published play): <b>'+pct(reference.homeProbability)+' '+home+'</b>'+
    '<small>External model, not used in the Lab estimate; could lag the scoreboard.</small></div>';
  display+='<p class="livewin-disclaimer">Our provisional NFL in-play model uses the archived pregame prediction, scoreboard difference, game clock and approximate possession/field-position values. Assumed scoring-volatility and field-value coefficients have not passed independent historical validation. This is a research forecast, not a betting recommendation.</p>';
 }else{
   display+='<small class="livewin-mini">Before kickoff: '+prior+' '+home+' · '+(live.period?"Q"+h(live.period)+" "+h(live.clock):"game running")+'</small>';
 }
 return '<div class="livewin-panel '+(expanded?"livewin-expanded":"livewin-compact")+'">'+display+'</div>';
}
root.NFLGameLiveUI={render:render,result:result,pct:pct,delta:delta};
if(typeof module!=="undefined"&&module.exports)module.exports=root.NFLGameLiveUI;
})(typeof globalThis!=="undefined"?globalThis:this);
