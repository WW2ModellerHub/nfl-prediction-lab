/* v1.9 — Evidence-led matchup explainer. This module never changes forecast probabilities. */
(function(root){'use strict';const api=(function makeEngine(){
  "use strict";
  const num=x=>typeof x==="number"&&Number.isFinite(x);
  const fixed=(v,d=2)=>num(v)?v.toFixed(d):"unknown";
  const signed=(v,d=2)=>num(v)?(v>0?"+":"")+v.toFixed(d):"unknown";
  const percent=v=>num(v)?(v*100).toFixed(1)+"%":"unavailable";
  const safeArray=x=>Array.isArray(x)?x:[];
  const normal=s=>String(s==null?"":s).trim().toUpperCase();
  const critical=new Set(["OUT","DOUBTFUL","IR","INJURED RESERVE","RESERVE/INJURED","OUT FOR SEASON","INACTIVE","DOUBTFUL FOR GAME"]);
  const uncertain=new Set(["QUESTIONABLE","WEEK-TO-WEEK","DAY-TO-DAY","LIMITED"]);
  function availability(game,side){
    const report=game.injuryIntelligence||{};
    const watch=game.supplementalInjuryWatch||{};
    const official=safeArray(report[side]).filter(x=>x&&typeof x==="object");
    const media=safeArray(watch[side]).filter(x=>x&&typeof x==="object");
    const known=new Set(official.map(x=>normal(x.name)));
    const entries=official.map(x=>({...x,source:"Dated game-week report"}))
      .concat(media.filter(x=>!known.has(normal(x.name))).map(x=>({...x,source:"ESPN media watch"})))
      .filter(x=>critical.has(normal(x.status))||uncertain.has(normal(x.status)));
    const out=entries.filter(x=>critical.has(normal(x.status)));
    const question=entries.filter(x=>uncertain.has(normal(x.status)));
    const key=out.filter(x=>x.starterOnDepthChart===true);
    const qb=out.filter(x=>normal(x.position)==="QB");
    const features=entries.filter(x=>{
      const usage=x.recentUsage||{};
      return (num(usage.offensePct)&&usage.offensePct>=.7)||(num(usage.defensePct)&&usage.defensePct>=.7);
    });
    const reportAvailable=["reported","snapshot-only","snapshot-cached","reported-cached"].includes(report.status);
    const mediaAvailable=["loaded","cached"].includes(watch.status);
    const cached=!!(String(report.status||"").includes("cached")||watch.status==="cached");
    const status=qb.length?"QB status needs checking":key.length?"Projected starter flags":out.length?"Reported absences":question.length?"Questionable players":!reportAvailable&&!mediaAvailable?"Coverage unavailable":"No relevant flags observed";
    return {team:String(game[side]||side),entries:entries.slice(0,16).map(x=>({
      name:String(x.name||"Unnamed player"),position:String(x.position||""),
      status:String(x.status||"Unknown"),source:x.source,starterOnDepthChart:x.starterOnDepthChart===true,
      usage:x.recentUsage||null,reportDate:String(x.reportDate||report.reportAsOf||"")
    })),outCount:out.length,questionableCount:question.length,
      projectedStarterFlagCount:key.length,qbFlagCount:qb.length,highUsageCount:features.length,
      status,coverage:reportAvailable?"Dated report available":mediaAvailable?"ESPN media observations only":"Missing dated report",
      cached,reportedAsOf:String(report.reportAsOf||watch.retrievedAt||"Unknown"),notConfirmed:true};
  }
  function analyze(game){
    const g=game||{},home=String(g.home||"HOME"),away=String(g.away||"AWAY");
    const ph=num(g.homeProbability)?g.homeProbability:null;
    const favourite=ph==null?null:ph>=.5?home:away;
    const underdog=ph==null?null:ph>=.5?away:home;
    const underdogProbability=ph==null?null:Math.min(ph,1-ph);
    const tact=g.tactical||{},h=tact.home||{},a=tact.away||{};
    const reliable=tact.status==="ready";
    const advantage=safeArray(tact.advantages).filter(x=>x&&x.strong===true&&x.favors!== "Even");
    const signal=safeArray(g.situation&&g.situation.signals).filter(x=>x&&x.team);
    const advFor=team=>advantage.filter(x=>String(x.favors)===String(team));
    const signalsFor=team=>signal.filter(x=>(x.team===team&&x.direction==="back")||(x.team!==team&&x.direction==="fade"));
    const against=team=>signal.filter(x=>(x.team===team&&x.direction==="fade")||(x.team!==team&&x.direction==="back"));
    const injury={home:availability(g,"home"),away:availability(g,"away")};
    const injuryFor=t=>injury[t===home?"home":"away"];
    const q=g.qbIntelligence||{},qs={home:q.home||{},away:q.away||{}};
    const src="Rolling pregame nflverse play-by-play; descriptive difference, not a validated independent win-probability edge";
    const matchup=[];
    const emit=(label,type,fn,key,offKey,defKey,decimals=3,unit="EPA/play")=>{
      const ad=advantage.find(x=>x.name===key) || safeArray(tact.advantages).find(x=>x.name===key);
      const values={homeAttack:h[offKey],awayDefence:a[defKey],awayAttack:a[offKey],homeDefence:h[defKey]};
      if(!reliable||!Object.values(values).every(num)){
        matchup.push({type,label,status:"unavailable",favors:"Unverified",details:"Both teams need a sufficient previous-game play-by-play sample.",source:src});
        return;
      }
      const sh=(num(h.games)?h.games:"?"),sa=(num(a.games)?a.games:"?");
      const detail=home+" offence "+signed(values.homeAttack,decimals)+" vs "+away+" defence allowing "+signed(values.awayDefence,decimals)
         +" · "+away+" offence "+signed(values.awayAttack,decimals)+" vs "+home+" defence allowing "+signed(values.homeDefence,decimals)+" "+unit+".";
      matchup.push({type,label,status:ad&&ad.strong?"notable":"observed",favors:ad?String(ad.favors):"Even",
         details:detail,source:src,sample:home+" "+sh+" prior games · "+away+" "+sa+" prior games",
         edge:num(ad&&ad.edge)?ad.edge:null,unit:ad&&ad.unit?String(ad.unit):unit});
    };
    emit("Passing offence against pass defence","passing",null,"Passing efficiency","passEPA","allowedPassEPA");
    emit("Rushing offence against run defence","rushing",null,"Rushing efficiency","rushEPA","allowedRushEPA");
    emit("Explosive passes vs explosive passes conceded","explosive",null,"Explosive pass opportunity","explosivePass","explosiveAllowed",1,"%");
    // Explosive fields are rates, not percentages, so convert both sides explicitly.
    if(reliable&&matchup[2]?.status!=="unavailable"){
      const m=matchup[2];m.details=home+" offence "+percent(h.explosivePass)+" vs "+away+" defence allowing "+percent(a.explosiveAllowed)
         +" · "+away+" offence "+percent(a.explosivePass)+" vs "+home+" defence allowing "+percent(h.explosiveAllowed)+".";
    }
    const hitAd=safeArray(tact.advantages).find(x=>x.name==="QB-hit/sack matchup");
    const hitOK=reliable&&[h.hitAllowed,a.hitForced,a.hitAllowed,h.hitForced].every(num);
    matchup.push({type:"pressure",label:"QB-hit/sack exposure",status:hitOK?(hitAd?.strong?"notable":"observed"):"unavailable",
      favors:hitOK?String(hitAd?.favors||"Even"):"Unverified",edge:hitOK&&num(hitAd?.edge)?hitAd.edge:null,
      details:hitOK?home+" allowed hit/sack proxy "+percent(h.hitAllowed)+"; "+away+" forced "+percent(a.hitForced)
        +" · "+away+" allowed "+percent(a.hitAllowed)+"; "+home+" forced "+percent(h.hitForced)+"."
        :"Reliable previous-play pressure proxies unavailable.",
      source:"Coarse pass play QB-hit/sack proxy; NOT charted pressure, blocking grades or certified pass-rush win rates",
      sample:hitOK?home+" "+h.games+" prior games · "+away+" "+a.games+" prior games":""});
    const formOK=[g.formHome,g.formAway,g.allowedHome,g.allowedAway].every(num);
    if(formOK){
      const homeOff=(g.formHome+g.allowedAway)/2,awayOff=(g.formAway+g.allowedHome)/2;
      matchup.unshift({type:"scoring",label:"Scoring form against opponent's points allowed",
        status:Math.abs(homeOff-awayOff)>=3?"notable":"observed",
        favors:Math.abs(homeOff-awayOff)<3?"Even":homeOff>awayOff?home:away,
        details:home+" scores "+fixed(g.formHome,1)+" PPG against "+away+" allowing "+fixed(g.allowedAway,1)+
          " · "+away+" scores "+fixed(g.formAway,1)+" PPG against "+home+" allowing "+fixed(g.allowedHome,1)+".",
        source:"Rating-model regressed and weighted past scoring form (up to 12 games), not a separate predicted total",
        edge:homeOff-awayOff,unit:"descriptive PPG contrast"});
    }else matchup.unshift({type:"scoring",label:"Scoring form",status:"unavailable",favors:"Unverified",details:"Past scoring form is not supplied for both teams.",source:"Rating-model history"});
    const qbRows=["home","away"].map(side=>{
      const item=qs[side],sample=item.sample||{},team=side==="home"?home:away;
      return {team,name:String(item.qb||"Unconfirmed"),starterStatus:"Not officially confirmed",
        changeWatch:!!item.starterChangeWatch,epaPerDropback:num(sample.epaPerDropback)?sample.epaPerDropback:null,
        sampleGames:num(sample.games)?sample.games:null,sampleDropbacks:num(sample.dropbacks)?sample.dropbacks:null};
    });
    function argumentsFor(team){
      const opposing=team===home?away:home;
      const features=[];
      for(const m of matchup){
        if(m.status==="notable"&&m.favors===team)features.push({category:m.type,title:m.label,detail:m.details,source:m.source});
      }
      for(const s of signalsFor(team)){
        features.push({category:"situation",title:String(s.name||"Situational watch"),detail:String(s.reason||"Pregame context"),source:"Prior game and rest evidence; historical research flag, not necessarily an approved model adjustment"});
      }
      const opponentInjury=injuryFor(opposing);
      if(opponentInjury.qbFlagCount>0||opponentInjury.projectedStarterFlagCount>0){
        features.push({category:"availability",title:opposing+" availability requires verification",
          detail:opponentInjury.qbFlagCount+" QB availability report(s); "+opponentInjury.projectedStarterFlagCount+" projected starter absence report(s). These may not describe final inactive status.",
          source:opponentInjury.coverage+(opponentInjury.cached?" · Cached observations":"")});
      }
      return features.slice(0,5);
    }
    const forUnderdog=underdog?argumentsFor(underdog):[],forFavourite=favourite?argumentsFor(favourite):[];
    const candidateReasons=forUnderdog.filter(x=>x.category!=="availability");
    const availabilityNeeds=injury.home.outCount+injury.away.outCount+injury.home.questionableCount+injury.away.questionableCount;
    const coverage=[{name:"Historical team scoring",available:formOK},
      {name:"Tactical previous plays",available:reliable},
      {name:"QB sample on both teams",available:qbRows.every(x=>num(x.epaPerDropback)&&num(x.sampleDropbacks)&&x.sampleDropbacks>=30)},
      {name:"Injury observations for both teams",available:injury.home.coverage!=="Missing dated report"&&injury.away.coverage!=="Missing dated report"},
      {name:"Rest and previous overtime",available:g.situation?.home?.fullRestDays!=null&&g.situation?.away?.fullRestDays!=null}];
    return {home,away,favourite,underdog,underdogProbability,modelPredictionAvailable:ph!=null,
      matchup,injury,qb:qbRows,forUnderdog,forFavourite,
      upsetContextCount:candidateReasons.length,upsetEvidenceAvailable:candidateReasons.length>0,
      upsetSummary:underdog?(candidateReasons.length?
        underdog+" has "+candidateReasons.length+" observed strength-versus-weakness or situational angle(s). These do not establish a betting edge.":
        "No material observed matchup or situational advantage currently supports a special "+underdog+" upset narrative. The baseline model still gives them "+percent(underdogProbability)+"."):
        "Cannot assess upset chances: forecast probability unavailable.",
      availabilityNeeds,coverage,
      modelOverlayActive:!!g.adjustmentActive,modelOverlayType:!!g.adjustmentActive?String(g.overlayType||"unidentified"):"none",
      caveat:"Only selected, historically validated overlays can change the published win percentage. These matchup arguments are descriptive, and reported injuries are not confirmed game-day inactives."};
  }
  return {analyze,availability};
})();root.NFLMatchupIntelligence=api;if(typeof module==='object'&&module.exports)module.exports=api;})(typeof window!=='undefined'?window:globalThis);
