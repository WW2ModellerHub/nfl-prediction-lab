/* Prediction factor sheet: every fixture shows the same full set of matchup
   metrics — venue / home-away, team strength, scoring form, quarterbacks,
   injuries, rest & travel, tactical EPA and weather — side by side, with an
   honest label for whether each factor moved the published percentage.
   Self-contained: app.js is wrapped in an IIFE, so its helpers are mirrored here. */
(function(){
 'use strict';
 const escapeHTML=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const number=(n,d=1)=>n==null?'—':Number(n).toFixed(d);
 const date=s=>s?new Date(s).toLocaleString('en-GB',{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',timeZone:'Europe/London'}):'Unknown';
 const tag=(text,kind='')=>`<span class="tag ${kind?'tag-'+kind:''}">${escapeHTML(text)}</span>`;
 const SIDES=['away','home'];
 const OUT=new Set(['OUT','IR','INJURED RESERVE','OUT FOR SEASON','PUP','SUSPENDED','DOUBTFUL']);
 const Q=new Set(['QUESTIONABLE','DAY-TO-DAY','WEEK-TO-WEEK']);
 const FACTOR_LAYERS={venue:['elo'],strength:['elo'],form:['form'],qb:['qb','qb-statistical','qb-replacement'],
  injuries:['player','other-injuries'],rest:['situational'],tactical:['tactical'],weather:['weather']};

 const esc=v=>escapeHTML(v==null?'':String(v));
 const num=v=>typeof v==='number'&&Number.isFinite(v);
 const signed=(v,d=1)=>num(v)?(v>=0?'+':'')+number(v,d):'—';
 const lastName=n=>{const parts=String(n||'').trim().split(/\s+/).filter(x=>!/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(x));return parts.length?parts[parts.length-1]:'';};

 function source(g){
  // Started games carry their last pregame snapshot; upcoming rows are already complete.
  return g&&g.pregame?{...g.pregame,id:g.id,home:g.home,away:g.away,kickoff:g.kickoff}:g||{};
 }
 function isNeutral(s){return s.neutral===true||s.homeAdvantageElo===0;}
 function edgeBy(s,awayVal,homeVal,threshold,higherIsBetter=true){
  if(!num(awayVal)||!num(homeVal))return null;
  const diff=(homeVal-awayVal)*(higherIsBetter?1:-1);
  if(Math.abs(diff)<threshold)return 'even';
  return diff>0?'home':'away';
 }
 function layerStatus(s,key){
  const layers=(s.forecastExplanation&&s.forecastExplanation.layers)||[];
  const keys=FACTOR_LAYERS[key]||[];
  const hits=layers.filter(l=>keys.includes(l.key));
  const applied=hits.filter(l=>l.applied);
  if(key==='shootout')return {state:'context',label:'CONTEXT ONLY',delta:null};
  if(!hits.length)return {state:'unknown',label:'NOT REPORTED',delta:null};
  if(!applied.length)return {state:'context',label:'CONTEXT ONLY',delta:null};
  const delta=applied.reduce((t,l)=>t+(num(l.deltaHome)?l.deltaHome:0),0);
  return {state:'applied',label:'IN FORECAST',delta:(key==='venue'||key==='strength')?null:delta};
 }

 /* ---------- individual factors ---------- */
 function venue(s){
  const neutral=isNeutral(s),stadium=s.stadium||(s.weather&&s.weather.stadium)||'Venue unknown';
  const roof=String(s.roof||(s.weather&&s.weather.roof)||'').toLowerCase();
  const roofText=roof==='dome'||roof==='closed'?'indoor':roof==='open'?'retractable (open)':roof==='outdoors'?'outdoor':'roof unconfirmed';
  return {key:'venue',label:'Venue · home / away',
   away:neutral?'Neutral site':'Away · travelling',
   home:neutral?'Neutral site (listed home)':`Home · ${stadium}`,
   edge:neutral?'even':'home',
   note:neutral?`${stadium} · ${roofText} · no home-field points applied.`:`${stadium} · ${roofText} · home field is worth +55 Elo points inside the Elo layer.`,
   chip:neutral?'⌂ Neutral site':`⌂ ${s.home} home`};
 }
 function strength(s){
  const e=edgeBy(s,s.eloAway,s.eloHome,25);
  return {key:'strength',label:'Team strength · Elo',
   away:num(s.eloAway)?String(s.eloAway):'—',home:num(s.eloHome)?String(s.eloHome):'—',edge:e,
   note:num(s.eloAway)&&num(s.eloHome)?(s.eloHome===s.eloAway?'Ratings level before home field.':`${s.eloHome>s.eloAway?s.home:s.away} +${Math.abs(s.eloHome-s.eloAway)} Elo before home field; built from earlier results only.`):'Ratings unavailable.'};
 }
 function form(s){
  const net=(f,a)=>num(f)&&num(a)?f-a:null;
  const na=net(s.formAway,s.allowedAway),nh=net(s.formHome,s.allowedHome);
  const txt=(f,a,n)=>num(f)&&num(a)?`${number(f,1)} scored · ${number(a,1)} allowed (${signed(n)})`:'—';
  return {key:'form',label:'Scoring form · per game',away:txt(s.formAway,s.allowedAway,na),home:txt(s.formHome,s.allowedHome,nh),
   edge:edgeBy(s,na,nh,3),note:'Recent points for and against, weighted to recent games and shrunk toward the league average.'};
 }
 function qbSide(s,side){
  const q=(s.qbIntelligence||{})[side];
  if(!q||!q.qb)return {text:'QB unconfirmed',epa:null,name:''};
  const basis=q.confirmedStarter?'confirmed':q.basis==='depth_chart_projection'?'projected':q.basis?'last starter':'unverified';
  const sm=q.sample||{};
  const bits=[q.qb,basis];
  if(num(sm.epaPerDropback))bits.push(`${signed(sm.epaPerDropback,3)} EPA/dropback`);
  else bits.push('no prior sample');
  if(num(sm.sackRate))bits.push(`${number(sm.sackRate*100,1)}% sacked`);
  if(q.starterChangeWatch)bits.push('CHANGE WATCH');
  return {text:bits.join(' · '),epa:num(sm.epaPerDropback)?sm.epaPerDropback:null,name:q.qb,watch:!!q.starterChangeWatch};
 }
 function qb(s){
  const a=qbSide(s,'away'),h=qbSide(s,'home'),rep=s.qbReplacement||{};
  const notes=[];
  if(a.watch||h.watch)notes.push('Starter change watch — check final inactives.');
  if(rep.affectsPrediction)notes.push('A reported QB replacement adjustment is active.');
  notes.push('Depth-chart projections are not confirmed starters.');
  const name=x=>lastName(x.name)||'TBC';
  return {key:'qb',label:'Quarterback',away:a.text,home:h.text,edge:edgeBy(s,a.epa,h.epa,0.05),note:notes.join(' '),
   chip:`QB ${name(a)} v ${name(h)}`,warn:a.watch||h.watch||!a.name||!h.name};
 }
 function injurySide(s,side){
  const seen=new Map();
  const add=(p,official)=>{
   if(!p||!p.name)return;const st=String(p.status||'').toUpperCase().trim();
   const kind=OUT.has(st)?'out':Q.has(st)?'q':null;if(!kind)return;
   const key=p.name.toLowerCase();const prev=seen.get(key);
   const u=p.recentUsage||{};const key_player=!!p.starterOnDepthChart||(u.offensePct||0)>=.6||(u.defensePct||0)>=.6;
   if(!prev||(official&&!prev.official))seen.set(key,{name:p.name,pos:p.position||'',status:st,kind,official,key_player:key_player||(prev&&prev.key_player)});
  };
  ((s.injuryIntelligence||{})[side]||[]).forEach(p=>add(p,true));
  ((s.supplementalInjuryWatch||{})[side]||[]).forEach(p=>add(p,false));
  const all=[...seen.values()];
  const out=all.filter(x=>x.kind==='out'),q=all.filter(x=>x.kind==='q');
  const keyOut=out.filter(x=>x.key_player);
  const shortPos=p=>String(p).split(/\s+/).map(w=>w[0]).join('').toUpperCase().slice(0,3);
  const top=[...out,...q].sort((x,y)=>Number(y.key_player)-Number(x.key_player)||(x.kind==='out'?-1:1)).slice(0,3)
   .map(x=>`${lastName(x.name)} ${x.pos.length>3?shortPos(x.pos):x.pos} (${x.kind==='out'?(x.status==='DOUBTFUL'?'D':'Out'):'Q'})`);
  return {out:out.length,q:q.length,keyOut:keyOut.length,top,
   text:all.length?`${out.length} out/doubtful · ${q.length} questionable${top.length?' — '+top.join(', '):''}`:'No flagged players reported'};
 }
 function injuries(s){
  const a=injurySide(s,'away'),h=injurySide(s,'home');
  const score=x=>x.out+x.keyOut+x.q*0.25;
  const reported=!!((s.injuryIntelligence||{}).status||(s.supplementalInjuryWatch||{}).status);
  return {key:'injuries',label:'Injuries & availability',away:a.text,home:h.text,
   edge:reported?edgeBy(s,score(a),score(h),1.5,false):null,
   note:reported?'Official weekly report (mirrored) plus dated ESPN media list. A missing report never means fully healthy.':'Injury reports not loaded for this fixture.',
   chip:`Inj ${a.out}–${h.out}`,warn:a.keyOut+h.keyOut>0};
 }
 function restSide(x){
  if(!x)return {text:'Unknown',days:null};
  const p=x.previous||{};
  const res=num(p.margin)?(p.margin>0?'W':p.margin<0?'L':'T'):'';
  const prev=p.opponent?`last: ${res} ${p.away?'@':'vs'} ${p.opponent}${p.overtime?' (OT)':''}`:'no previous game';
  return {text:`${num(x.fullRestDays)?x.fullRestDays+' days rest':'Rest unknown'} · ${prev}`,days:num(x.fullRestDays)?x.fullRestDays:null};
 }
 function rest(s){
  const sit=s.situation||{},a=restSide(sit.away),h=restSide(sit.home);
  const signals=(sit.signals||[]).map(x=>`${x.name} (${x.team})`);
  return {key:'rest',label:'Rest, travel & overtime',away:a.text,home:h.text,edge:edgeBy(s,a.days,h.days,2),
   note:signals.length?'Situational flags: '+signals.join(' · '):'No situational trigger (short week, overtime hangover, back-to-back road) for this fixture.',
   chip:a.days!=null&&h.days!=null?`Rest ${a.days}–${h.days}`:null};
 }
 function tactical(s){
  const t=s.tactical||{};
  const txt=x=>x&&num(x.passEPA)?`Pass ${signed(x.passEPA,3)} · rush ${signed(x.rushEPA,3)} EPA/play`:'—';
  const strong=(t.advantages||[]).filter(x=>x.strong&&x.favors&&x.favors!=='Even');
  const ca=strong.filter(x=>x.favors===s.away).length,ch=strong.filter(x=>x.favors===s.home).length;
  return {key:'tactical',label:'Offence · EPA per play',away:txt(t.away),home:txt(t.home),
   edge:t.status==='ready'?(ca===ch?'even':ch>ca?'home':'away'):null,
   note:t.status==='ready'?(strong.length?'Material edges: '+strong.map(x=>`${x.name} → ${x.favors}`).join(' · '):'No material passing, rushing or pressure edge.'):'Play-by-play matchup data unavailable.'};
 }
 function weatherInfo(s){
  const w=s.weather||{},st=w.status;
  if(st==='indoor')return {text:`Indoors (${w.roof||s.roof||'roof'}) — weather not a factor`,chip:'◼ Indoors',flags:[]};
  if(st==='forecast'||st==='roof-unconfirmed'){
   const parts=[];
   if(num(w.temperatureC))parts.push(`${number(w.temperatureC,0)}°C / ${Math.round(w.temperatureC*9/5+32)}°F`);
   if(num(w.windMph))parts.push(`wind ${Math.round(w.windMph)} mph${num(w.gustMph)?` (gusts ${Math.round(w.gustMph)})`:''}`);
   if(num(w.precipitationChancePct))parts.push(`${Math.round(w.precipitationChancePct)}% precip`);
   if(num(w.snowfallCm)&&w.snowfallCm>0)parts.push(`${number(w.snowfallCm,1)} cm snow`);
   const flags=[];
   if(num(w.windMph)&&w.windMph>=15||num(w.gustMph)&&w.gustMph>=25)flags.push('strong wind: passing & kicking risk');
   if(num(w.temperatureC)&&w.temperatureC<=-5)flags.push('severe cold');
   if(num(w.precipitationChancePct)&&w.precipitationChancePct>=50)flags.push('likely rain/snow: ball security');
   if(st==='roof-unconfirmed')flags.push('roof status unconfirmed — may be closed');
   const chip=(num(w.temperatureC)?`${number(w.temperatureC,0)}°C`:'')+(num(w.windMph)?` ${Math.round(w.windMph)}mph`:'');
   return {text:parts.length?parts.join(' · '):'Forecast values missing',chip:`☁ ${chip.trim()||'forecast'}`,flags};
  }
  return {text:st==='venue-unmapped'?'Venue not mapped to a forecast location':st?`Forecast unavailable (${st})`:'Weather not loaded',chip:'☁ n/a',flags:[]};
 }
 function weather(s){
  const w=weatherInfo(s),src=s.weather||{};
  return {key:'weather',label:'Weather at kickoff',span:w.text,edge:null,
   note:[w.flags.length?'Watch: '+w.flags.join(' · ')+'.':'',src.retrievedAt?`Open-Meteo venue-area forecast retrieved ${date(src.retrievedAt)}.`:'','Shown for context; carries no probability weight.'].filter(Boolean).join(' '),
   chip:w.chip,warn:w.flags.length>0};
 }

 function shootout(s){
  const sh=window.NFLShootout,f=sh&&sh.factor(s),c=sh&&sh.chip(s);
  if(!f)return null;
  return {key:'shootout',label:'Scoring outlook',span:f.span,edge:null,note:f.note,chip:c.text,warn:c.warn};
 }
 function factors(g){
  const s=source(g);
  const list=[venue(s),strength(s),form(s),qb(s),injuries(s),rest(s),tactical(s),weather(s)];
  const heat=shootout(s);if(heat)list.push(heat);
  return list.map(f=>({...f,status:layerStatus(s,f.key)}));
 }

 /* ---------- rendering ---------- */
 function strip(g){
  if(!g||(g.archivedPregame&&!g.pregame))return '';
  const chips=factors(g).filter(f=>f.chip).map(f=>`<span class="pf-chip${f.warn?' pf-chip-warn':''}">${esc(f.chip)}</span>`).join('');
  return `<div class="pf-strip" aria-label="Prediction factors">${chips}</div>`;
 }
 function edgeLabel(s,f){
  if(f.edge==='home')return s.home;if(f.edge==='away')return s.away;if(f.edge==='even')return 'Even';return '—';
 }
 function statusTag(s,st){
  if(st.state==='applied'){
   const d=st.delta;
   const txt=num(d)&&Math.abs(d)>=0.0005?`IN FORECAST ${d>0?s.home:s.away} +${number(Math.abs(d)*100,1)}pp`:'IN FORECAST';
   return tag(txt,'lime');
  }
  return tag(st.label,st.state==='unknown'?'warn':'');
 }
 function panel(g,opts={}){
  if(!g||(g.archivedPregame&&!g.pregame))return '';
  const s=source(g),list=factors(g);
  const tally={home:0,away:0};list.forEach(f=>{if(f.edge==='home'||f.edge==='away')tally[f.edge]++;});
  const rows=list.map(f=>{
   const edge=edgeLabel(s,f),edgeCls=f.edge==='home'||f.edge==='away'?' pf-edge-on':'';
   const values=f.span!=null?`<div class="pf-span">${esc(f.span)}</div>`:`<div class="pf-val"><small>${esc(s.away)}</small>${esc(f.away)}</div><div class="pf-val"><small>${esc(s.home)}</small>${esc(f.home)}</div>`;
   return `<div class="pf-row${f.warn?' pf-row-warn':''}"><div class="pf-label"><b>${esc(f.label)}</b>${statusTag(s,f.status)}</div>${values}<div class="pf-edge${edgeCls}"><small>EDGE</small>${esc(edge)}</div>${f.note?`<p class="pf-note">${esc(f.note)}</p>`:''}</div>`;
  }).join('');
  const captured=g.pregame&&g.pregame.capturedAt?` · snapshot from ${esc(date(g.pregame.capturedAt))}, before kickoff`:'';
  return `<section class="pf-panel" aria-label="Prediction factors">
  <div class="pf-head"><div><div class="eyebrow">${opts.archived?'PREGAME FACTORS · FROZEN':'PREDICTION FACTORS'}</div><h3>Every metric behind this pick</h3></div>
  <div class="pf-tally"><span><b>${tally.away}</b> favour ${esc(s.away)}</span><span><b>${tally.home}</b> favour ${esc(s.home)}</span></div></div>
  <div class="pf-cols" aria-hidden="true"><span>FACTOR</span><span>${esc(s.away)} · AWAY</span><span>${esc(s.home)} · ${isNeutral(s)?'LISTED HOME':'HOME'}</span><span>EDGE</span></div>
  ${rows}
  <p class="source-meta">"In forecast" factors moved the published percentage (see the breakdown below); "context only" factors are shown for judgement but are not yet validated as predictive. Edge marks which side a factor leans to, not a betting signal${captured}.</p>
  </section>`;
 }
 window.NFLPredictionFactors={factors,strip,panel,source};
})();
