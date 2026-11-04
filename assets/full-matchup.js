function fullMatchupCoverage(g){
 const q=qbFor(g),t=tacticalFor(g),inj=injuriesFor(g),s=situationFor(g),w=g.supplementalInjuryWatch||{};
 const qbReady=Boolean(q.home?.qb&&q.away?.qb&&q.home?.sample&&q.away?.sample);
 const injuryReady=['reported','snapshot-only','snapshot-cached','reported-cached'].includes(inj.status)||w.status==='loaded'||w.status==='cached';
 const restReady=s.home?.fullRestDays!=null&&s.away?.fullRestDays!=null;
 const tacticalReady=t.status==='ready';
 const counts=[true,qbReady,injuryReady,tacticalReady,restReady,Boolean(g.weather?.status==='loaded')];
 return {q,t,inj,s,w,qbReady,injuryReady,restReady,tacticalReady,counts,complete:counts.filter(Boolean).length,total:counts.length};
}
function fullMatchupReport(g){
 const c=fullMatchupCoverage(g),{q,t,inj,s,w}=c;
 const media=side=>(w[side]||[]).filter(x=>['OUT','DOUBTFUL','QUESTIONABLE','IR','INJURED RESERVE','OUT FOR SEASON','WEEK-TO-WEEK','DAY-TO-DAY'].includes(String(x.status||'').toUpperCase()));
 const watchText=side=>{
   const official=inj[side]||[],other=media(side);
   if(official.length)return `${official.length} flagged in game-week report${other.length?` · ${other.length} ESPN media watch`:''}`;
   return other.length?`${other.length} ESPN media watch${w.status==='cached'?' (cached)':''}`:'No current player flags available';
 };
 const playerText=side=>{
   const p=q[side];if(!p?.qb)return 'No reliable QB name';
   const sample=p.sample;
   return `${p.qb}${sample?` · EPA/dropback ${statEPA(sample.epaPerDropback)} · ${sample.games} recent games`:' · no prior-play sample'}${p.starterChangeWatch?' · CHANGE WATCH':''}`;
 };
 const h=s.home?.fullRestDays,a=s.away?.fullRestDays;
 const restText=n=>n==null?'Unknown':`${n} full days`;
 const tacticalText=name=>{const signal=(t.advantages||[]).find(v=>v.name===name);return signal?{favors:signal.favors,edge:signal.edge,unit:signal.unit}:null;};
 const comparisons=[
   {label:'Passing matchup',v:tacticalText('Passing efficiency')},
   {label:'Rushing matchup',v:tacticalText('Rushing efficiency')},
   {label:'QB-hit/sack matchup',v:tacticalText('QB-hit/sack matchup')},
   {label:'Explosive passing',v:tacticalText('Explosive pass opportunity')}
 ];
 const statusRows=[['Team strength / scoring',true,'IN FORECAST'],['QB identity & efficiency',c.qbReady,g.overlayType==='player'?'ADJUSTMENT ACTIVE':'CONTEXT ONLY'],['Player availability',c.injuryReady,g.overlayType==='player'?'ADJUSTMENT ACTIVE':'CONTEXT ONLY'],['Tactical EPA matchups',c.tacticalReady,g.overlayType==='tactical'?'ADJUSTMENT ACTIVE':'CONTEXT ONLY'],['Rest / overtime',c.restReady,g.overlayType==='situational'?'ADJUSTMENT ACTIVE':'CONTEXT ONLY'],['Stadium weather',false,'NOT CONNECTED']];
 const qbAlerts=playerFlags(g);
 const tacticalEdges=(t.advantages||[]).filter(x=>x.strong);
 const reliability=c.complete===c.total?'Broad feed coverage':c.complete>=4?'Partial feed coverage':'Limited feed coverage';
 const verdict=`${g.homeProbability>=0.5?g.homeName:g.awayName} is the ${pct(Math.max(g.homeProbability,g.awayProbability))} baseline favourite. ${tacticalEdges.length?`${tacticalEdges.length} material tactical differential${tacticalEdges.length===1?' is':'s are'} flagged.`:'No large tactical differential is confirmed.'} ${qbAlerts.length?`${qbAlerts.length} player availability or QB watch alert${qbAlerts.length===1?' requires':'s require'} review.`:'Player availability is not independently verified.'}`;
 const row=(label,aValue,hValue)=>`<div class="fm-compare-row"><span class="fm-row-label">${escapeHTML(label)}</span><span>${escapeHTML(aValue)}</span><span>${escapeHTML(hValue)}</span></div>`;
 const status=statusRows.map(([name,available,impact])=>`<div class="fm-data-line"><span>${escapeHTML(name)}</span><span>${tag(available?impact:'MISSING',!available?'warn':impact==='IN FORECAST'?'lime':'')}</span></div>`).join('');
 return `<section class="fm-report" aria-label="Complete matchup breakdown">
 <div class="fm-header"><div><div class="eyebrow">FULL MATCHUP DOSSIER · ${escapeHTML(reliability.toUpperCase())}</div><h3>What could decide this game?</h3></div>${tag(`${c.complete}/${c.total} data layers`,c.complete>=5?'lime':'warn')}</div>
 <p class="fm-verdict">${escapeHTML(verdict)}</p>
 <div class="fm-callout"><strong>What the ${pct(g.homeProbability)} home-win probability includes</strong><p>${g.adjustmentActive?`Elo, scoring form and the validated ${escapeHTML(g.overlayType)} overlay. Other indicators below remain informational.`:'Only Elo team strength and scoring form. QB, injuries, tactical signals, overtime and rest are shown below but do NOT currently change this percentage.'} This is not an all-factor calibrated forecast.</p></div>
 <div class="fm-side-grid"><div><small>${escapeHTML(g.away)} · AWAY</small><strong>${escapeHTML(playerText('away'))}</strong><p>${escapeHTML(watchText('away'))}</p></div><div><small>${escapeHTML(g.home)} · HOME</small><strong>${escapeHTML(playerText('home'))}</strong><p>${escapeHTML(watchText('home'))}</p></div></div>
 <div class="fm-compare"><div class="fm-compare-row fm-compare-head"><span>MATCHUP FACTOR</span><span>${escapeHTML(g.away)}</span><span>${escapeHTML(g.home)}</span></div>
 ${row('Offence · recent points/game',number(g.formAway,1),number(g.formHome,1))}
 ${row('Opponent defence · points allowed/game',number(g.allowedHome,1),number(g.allowedAway,1))}
 ${row('Quarterback · EPA/dropback',q.away?.sample?statEPA(q.away.sample.epaPerDropback):'Unavailable',q.home?.sample?statEPA(q.home.sample.epaPerDropback):'Unavailable')}
 ${row('Recovery days',restText(a),restText(h))}
 ${row('Previous game OT',s.away?.previous?.overtime==null?'Unknown':s.away.previous.overtime?'Yes':'No',s.home?.previous?.overtime==null?'Unknown':s.home.previous.overtime?'Yes':'No')}
 </div>
 <div class="fm-factors">${comparisons.map(({label,v})=>`<div><b>${escapeHTML(label)}</b><strong>${v?escapeHTML(v.favors==='Even'?'No clear edge':v.favors+' advantage'):'Data unavailable'}</strong><small>${v?`${v.edge>=0?'+':''}${number(v.edge,3)} ${escapeHTML(v.unit)} towards home · research only`:'Historic PBP sample insufficient'}</small></div>`).join('')}</div>
 <div class="fm-two"><div><h4>Situational and player warnings</h4>${(s.signals||[]).length?`<p>${(s.signals||[]).map(v=>escapeHTML(v.name+' · '+v.team)).join(' · ')}</p>`:'<p>No named situational trigger for this matchup.</p>'}${qbAlerts.length?`<ul>${qbAlerts.slice(0,5).map(v=>`<li>${escapeHTML(v)}</li>`).join('')}</ul>`:'<p>QB/injury status can change before kickoff; no full-health claim.</p>'}</div><div><h4>Model input audit</h4>${status}</div></div>
 <p class="fm-footnote">Injury summaries distinguish dated media watch from official game-week reports. Depth charts are unconfirmed starters. No historical accuracy is claimed for individual flags. For details see the QB, tactical and situational sections below.</p></section>`;
}
