/* NFL Prediction Lab v1 live forecast: score + clock + possession vs archived pregame prior.
   EXPERIMENTAL model, not fitted/calibrated on hold-out live game data.
   ESPN scoreboard is a separate live state provider; ESPN win probability
   (if displayed) is external and never mixed into the Lab estimate. */
(function(root){
"use strict";
function number(v){return v===null||v===undefined||v===""||typeof v==="boolean"||!Number.isFinite(Number(v))?null:Number(v);}
function clamp(v,lo,hi){return Math.max(lo,Math.min(hi,v));}
function norm(c){return ({WSH:"WAS",JAC:"JAX",LA:"LAR",STL:"LAR",SD:"LAC",OAK:"LV"})[String(c||"").toUpperCase()]||String(c||"").toUpperCase();}
function sigmoid(x){return x>=0?1/(1+Math.exp(-x)):Math.exp(x)/(1+Math.exp(x));}
function logit(p){return Math.log(p/(1-p));}
function seconds(clock){
 var m=String(clock||"").match(/^(\d{1,2}):(\d{2})$/);
 if(!m||Number(m[1])>15||Number(m[2])>=60)return null;
 return Number(m[1])*60+Number(m[2]);
}
function location(text,away,home){
 var m=String(text||"").match(/\bat\s+([A-Z]{2,3})\s+(\d{1,2})(?![\d:])/i);
 if(/\bat\s+midfield\b/i.test(String(text||"")))return 50;
 if(!m)return null;
 var y=Number(m[2]),team=norm(m[1]);
 if(y<0||y>50)return null;
 return team===norm(away)?y:team===norm(home)?100-y:null;
}
function espnState(event,at){
 var comp=event&&event.competitions&&event.competitions[0],teams=comp&&comp.competitors||[];
 var home=teams.find(x=>x.homeAway==="home"),away=teams.find(x=>x.homeAway==="away");
 if(!home||!away||!home.team||!away.team)return null;
 var sit=comp.situation||event.situation||{},status=event.status||{}, poss=teams.find(x=>sit.possession!=null&&String(x.id)===String(sit.possession))||teams.find(x=>x.possession===true);
 var team=poss&&poss.team?norm(poss.team.abbreviation):null;
 var homeTeam=norm(home.team.abbreviation),awayTeam=norm(away.team.abbreviation);
 var downText=String(sit.downDistanceText||"");
 return {id:String(event.id||comp.id||""),home:homeTeam,away:awayTeam,
   homeScore:number(home.score),awayScore:number(away.score),
   state:status.type&&status.type.state||"pre",period:number(status.period),
   clock:status.displayClock||"",possession:team,position:location(downText,awayTeam,homeTeam),
   downDistance:downText,isRedZone:sit.isRedZone===true,
   fetchedAt:at||Date.now(),eventDate:event.date||null};
}
function estimate(g,prior,now){
 var p=number(prior),h=number(g&&g.homeScore),a=number(g&&g.awayScore);
 if(p===null||p<=0||p>=1)return {status:"unavailable",reason:"No saved pre-kickoff prediction"};
 if(!g||g.state==="pre")return {status:"pregame",homeProbability:p};
 if(g.state==="post")return {status:"final",winner:h!==null&&a!==null?(h>a?g.home:a>h?g.away:"TIE"):null};
 if(g.state!=="in")return {status:"unavailable",reason:"Live game status unavailable"};
 var n=number(now);if(n===null)n=Date.now();
 var received=number(g.fetchedAt);
 if(received!==null && (received>n+30000||n-received>120000))return {status:"stale",reason:"Scoreboard more than two minutes old"};
 var period=number(g.period),elapsed=seconds(g.clock);
 if(h===null||a===null||h<0||a<0||!Number.isInteger(h)||!Number.isInteger(a))
   return {status:"unavailable",reason:"NFL scores unavailable"};
 if(period===null||!Number.isInteger(period)||period<1||elapsed===null)
   return {status:"unavailable",reason:"Quarter or clock unavailable"};
 if(period>=5)return {status:"overtime",reason:"Overtime state requires a separately validated model"};
 if(period>4)return {status:"unavailable",reason:"Unsupported quarter"};
 // A transparent heuristic: archived pregame strength survives in proportion
 // to remaining game time. Remaining point-differential noise decreases with
 // the square root of time remaining. The scale 9.0 points is an explicit
 // *assumption*, not an estimated or calibrated in-play coefficient.
 var fraction=clamp((4-period+elapsed/900)/4,.003,1),sigma=9*Math.sqrt(fraction);
 var priorMargin=clamp(9*logit(p),-20,20),expected=priorMargin*fraction;
 var pClock=sigmoid(expected/sigma);
 var scoreDelta=h-a,pScore=sigmoid((expected+scoreDelta)/sigma);
 var possession=norm(g.possession),spot=number(g.position),ep=0,epBasis="not reported",withBall=false;
 if(possession===norm(g.home)||possession===norm(g.away)){
   withBall=true;
   var homePoss=possession===norm(g.home),distance=spot===null?null:homePoss?spot:100-spot;
   if(distance!==null&&distance>=0&&distance<=100){
     ep=clamp(.35+3.6*Math.pow((100-distance)/100,1.45),.3,4);
     epBasis="reported field position";
   }else if(g.isRedZone===true){
     ep=3.2;epBasis="reported red-zone possession (yard line unknown)";
   }else{ep=1.4;epBasis="possession known; field position unknown";}
   var down=String(g.downDistance||"").match(/\b([1-4])(?:st|nd|rd|th)\b/i);
   if(down)ep*=({"1":1,"2":.91,"3":.72,"4":.40})[down[1]];
   ep=clamp(ep,0,4);
   if(!homePoss)ep=-ep;
 }
 // Current possession has less scoring runway in the last minute.
 var remainingSeconds=(4-period)*900+elapsed,runway=clamp(Math.sqrt(remainingSeconds/75),.15,1);
 ep*=runway;
 var win=sigmoid((expected+scoreDelta+ep)/sigma);
 // Do not suggest certainty from heuristic assumptions.
 win=clamp(win,.005,.995);
 var modelClock=clamp(pClock,.005,.995),modelScore=clamp(pScore,.005,.995);
 return {status:"experimental",homeProbability:win,awayProbability:1-win,
   favorite:win>=.5?g.home:g.away,winProbability:Math.max(win,1-win),
   remainingFraction:fraction,scoreDifference:scoreDelta,priorMargin:priorMargin,
   possessionPoints:ep,possessionBasis:epBasis,source:"Archived pregame Lab pick + ESPN live score/clock/possession",
   validated:false,bettingEligible:false,
   layers:[
     {name:"Pregame pick",value:p,delta:0},
     {name:"Clock / unplayed time",value:modelClock,delta:modelClock-p},
     {name:"Score difference",value:modelScore,delta:modelScore-modelClock},
     {name:"Possession & field",value:win,delta:win-modelScore}
   ]};
}
/* ESPN publishes optional own per-play win probabilities. Never rewrite
   the Lab model or imply a last-play reference is the current state. */
function espnReference(summary){
 var rows=summary&&(summary.winprobability||summary.winProbability),value=null,at=null,play=null;
 if(!Array.isArray(rows))return null;
 for(var i=rows.length-1;i>=0;i--){
   var row=rows[i],p=number(row&&row.homeWinPercentage);
   if(p!==null&&p>=0&&p<=1){value=p;at=row.lastModified||row.timestamp||null;
       play=row.playId||row.play&&row.play.id||null;break;}
 }
 return value===null?null:{homeProbability:value,source:"ESPN win probability (last published play)",asOf:at,playId:play};
}
var api={estimate:estimate,espnState:espnState,espnReference:espnReference,location:location};
root.NFLGameLiveModel=api;
if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
