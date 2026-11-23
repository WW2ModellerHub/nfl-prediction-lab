/* Shootout Heat: this week's games ranked by expected scoring.
   Ratings come from scripts/shootout.py (pipeline); this file only renders.
   Self-contained helpers because app.js is wrapped in an IIFE. */
(function(){
 'use strict';
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const num=v=>typeof v==='number'&&Number.isFinite(v);
 const fx=(n,d=1)=>num(n)?Number(n).toFixed(d):'—';
 const signed=n=>num(n)?(n>=0?'+':'−')+Math.abs(n).toFixed(1):'—';
 const pct=n=>num(n)?Math.round(n*100)+'%':'—';
 const when=s=>s?new Date(s).toLocaleString('en-GB',{weekday:'short',hour:'2-digit',minute:'2-digit',timeZone:'Europe/London'}):'';
 const tierClass=t=>({Shootout:'sh-t4',High:'sh-t3',Average:'sh-t2',Low:'sh-t1'})[t]||'sh-t2';

 // The "weekend" is the earliest week that still has a real slate (4+ games
 // to come). When only a Thursday/Monday game is left, show the next week.
 const MIN_SLATE=4;
 function weeks(games){
  const rated=(games||[]).filter(g=>g&&g.shootout).sort((a,b)=>String(a.kickoff).localeCompare(String(b.kickoff)));
  const order=[],groups={};
  rated.forEach(g=>{const k=g.season+'-'+g.week;if(!groups[k]){groups[k]=[];order.push(k);}groups[k].push(g);});
  return order.map(k=>groups[k].sort((a,b)=>a.shootout.weekRank-b.shootout.weekRank));
 }
 function currentWeek(games){
  const all=weeks(games);
  return all.find(w=>w.length>=MIN_SLATE)||all[0]||[];
 }
 function leftover(games,week){
  const first=weeks(games)[0]||[];
  return week.length&&first.length&&first[0].week!==week[0].week?first:[];
 }
 function chip(g){
  const s=g&&g.shootout;if(!s)return null;
  return {text:`🔥 ${s.rating} ${s.tier}`,warn:s.tier==='Shootout'};
 }
 function factor(g){
  const s=g&&g.shootout;if(!s)return null;
  const c=s.components||{};
  const parts=[`projected ${fx(c.projectedTotal)} pts`,`passing ${signed(c.passingMatchup)}`,`explosive ${signed(c.explosivePlays)}`,`weather ${signed(c.weather)}`];
  return {span:`Heat ${s.rating}/100 · ${s.tier} · ${fx(s.shootoutTotal)} expected points · #${s.weekRank} of ${s.weekGames} this week`,
   note:`${parts.join(' · ')}${(s.weatherReasons||[]).length?' ('+s.weatherReasons.join(', ')+')':''}. In-house rating, graded against final totals.`};
 }
 function recordLine(rec){
  if(!rec||!rec.gradedWeeks)return `<p class="sh-record">Track record starts once this week's games are final${rec&&rec.pendingGames?` · ${rec.pendingGames} ratings saved before kickoff`:''}.</p>`;
  const better=num(rec.meanRankCorrelation)&&num(rec.meanProjectedTotalRankCorrelation)?(rec.meanRankCorrelation>rec.meanProjectedTotalRankCorrelation?'beats':'does not beat'):null;
  return `<p class="sh-record"><b>Track record:</b> ${pct(rec.top3HitRate)} of our top-3 picks finished top-3 for scoring · rank correlation ${fx(rec.meanRankCorrelation,2)} over ${rec.gradedWeeks} week${rec.gradedWeeks===1?'':'s'} (${rec.gradedGames} games)${better?` · ${better} the plain projected total (${fx(rec.meanProjectedTotalRankCorrelation,2)})`:''}.${rec.gradedWeeks<4?' Small sample — treat with caution.':''}</p>`;
 }
 function panel(data,opts={}){
  const week=currentWeek(data&&data.nextGames);
  const rest=leftover(data&&data.nextGames,week);
  const rec=data&&data.shootoutRecord;
  const head=`<div class="panel-head"><div><div class="panel-title">🔥 Highest-scoring games${week.length?' · Week '+esc(week[0].week):' this week'}</div><div class="panel-sub">Shootout Heat · our expected-points rating, not a betting total</div></div></div>`;
  if(!week.length)return `<article class="panel sh-panel">${head}<div class="panel-body"><p class="instruction">Shootout ratings appear after the next data refresh.</p></div></article>`;
  const rows=week.slice(0,opts.limit||week.length).map(g=>{
   const s=g.shootout,c=s.components||{};
   return `<div class="sh-row" role="button" tabindex="0" data-open="${esc(g.id)}">
    <span class="sh-rank">${s.weekRank}</span>
    <div class="sh-game"><b>${esc(g.away)} @ ${esc(g.home)}</b><small>${esc(when(g.kickoff))} · ${fx(s.shootoutTotal)} pts expected${(s.weatherReasons||[]).length?' · '+esc(s.weatherReasons.join(', ')):''}</small></div>
    <div class="sh-meter" aria-hidden="true"><span class="${tierClass(s.tier)}" style="width:${Math.max(3,s.rating)}%"></span></div>
    <div class="sh-score"><strong>${s.rating}</strong><small class="${tierClass(s.tier)}">${esc(s.tier.toUpperCase())}</small></div>
    <p class="sh-why">Projected ${fx(c.projectedTotal)} · passing ${signed(c.passingMatchup)} · explosive ${signed(c.explosivePlays)} · weather ${signed(c.weather)}</p>
   </div>`;}).join('');
  const more=opts.limit&&week.length>opts.limit?`<button class="btn btn-sm btn-ghost sh-more" data-nav="matchups">All ${week.length} games →</button>`:'';
  const tail=rest.length?`<p class="sh-record">Still to play in week ${esc(rest[0].week)}: ${rest.map(g=>`${esc(g.away)} @ ${esc(g.home)} (${g.shootout.rating} ${esc(g.shootout.tier)})`).join(' · ')}.</p>`:'';
  return `<article class="panel sh-panel">${head}<div class="sh-list">${rows}</div><div class="panel-body sh-foot">${more}${tail}${recordLine(rec)}
  <p class="source-meta">Heat 0–100 maps 36–56 expected combined points. Starts from the model's projected total, then adjusts for each offence's passing efficiency and explosive plays against the opposing defence (relative to this slate) and for wind, rain, snow and severe cold outdoors. Weights are heuristic, which is why every rating is saved before kickoff and graded.</p></div></article>`;
 }
 window.NFLShootout={panel,chip,factor,currentWeek};
})();
