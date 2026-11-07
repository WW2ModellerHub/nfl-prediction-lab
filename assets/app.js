/* NFL Prediction Lab — static, dependency-free dashboard.
   Odds and actual bet records are device-local. Published predictions are
   derived by scripts/model.py from nflverse, not fabricated in the browser. */
(() => {
'use strict';
const TEAM_COLORS={ARI:'#a71930',ATL:'#a71930',BAL:'#6637a6',BUF:'#185aa6',CAR:'#0085ca',CHI:'#c14720',CIN:'#e56b1e',CLE:'#d06423',DAL:'#769fc6',DEN:'#fa751e',DET:'#2476b2',GB:'#248363',HOU:'#1c426d',IND:'#4c72a6',JAX:'#008b91',KC:'#d62d3e',LA:'#2874b8',LAC:'#f0bc46',LV:'#8e98a0',MIA:'#068b92',MIN:'#7657a5',NE:'#3c6289',NO:'#b9a169',NYG:'#296ba0',NYJ:'#2c7554',PHI:'#1c7378',PIT:'#eac046',SEA:'#477ba1',SF:'#c84348',TB:'#bd4549',TEN:'#5c8fbb',WAS:'#9d752d'};
const TABS={overview:['Command Centre','Every matchup. Every probability. Every prediction accountable.'],matchups:['Full Matchup','QB, injuries, pass/rush matchups, rest, projected scores and the exact factors used in win probabilities.'],tactics:['Tactical Radar','Pass and rush EPA, QB-hit/sack proxies and explosive-play matchup intelligence.'],players:['QB & Injury Radar','Observed quarterback performance, depth-chart projections and dated injury reports.'],impact:['Player Impact Lab','QB changes, injury signals, historical eligibility and honest prediction improvements.'],radar:['Upset & Value Radar','Separate win probability from the potential value of a bookmaker price.'],performance:['Prediction Record','Every saved pregame pick, verified result and actual hit rate — with historical backtests kept separate.'],accuracy:['Signal Accuracy Lab','Does passing, rushing, pressure or explosive-play information reduce forecasting errors on later completed seasons?'],audit:['Market Reality Check','Historical probability accuracy against a no-vig closing moneyline benchmark.'],evidence:['Situational Evidence','Real NFL games: assess overtime, recovery and bounce-back effects.'],models:['Model Laboratory','Transparent statistical forecasts with explicit source limitations.'],bets:['My Bet Ledger','Your personal bookmaker entries, paper value checks and actual bet records.']};
const byId=id=>document.getElementById(id); const $=sel=>document.querySelector(sel);
const escapeHTML=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=x=>x==null?'—':(100*x).toFixed(1)+'%'; const number=(n,d=1)=>n==null?'—':Number(n).toFixed(d);
const money=n=>'£'+Number(n||0).toLocaleString('en-GB',{minimumFractionDigits:2,maximumFractionDigits:2});
const date=s=>s?new Date(s).toLocaleString('en-GB',{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',timeZone:'Europe/London'}):'Unknown';
function save(key,v){try{localStorage.setItem('nfl-lab-'+key,JSON.stringify(v));return true}catch{toast('Local storage unavailable.');return false}}
function load(key,fallback){try{return JSON.parse(localStorage.getItem('nfl-lab-'+key))??fallback}catch{return fallback}}
let store={data:null,auditReference:window.NFL_LAB_AUDIT_REFERENCE||null,researchEvidence:window.NFL_LAB_RESEARCH_EVIDENCE||null,tab:'overview',odds:load('odds',{}),bets:load('bets',[]),query:'',week:'All',busy:false,activeGameId:null};
let timer;
function toast(message){const el=byId('toast');el.textContent=message;el.classList.add('show');clearTimeout(timer);timer=setTimeout(()=>el.classList.remove('show'),2900)}
function initials(team){return `<span class="team-bubble" style="border-color:${TEAM_COLORS[team]||'#456'}88;background:${TEAM_COLORS[team]||'#203447'}30">${escapeHTML(team)}</span>`}
function tag(text,kind=''){return `<span class="tag ${kind?'tag-'+kind:''}">${escapeHTML(text)}</span>`}
function metric(label,val,sub,kind='',icon='↗'){return `<div class="metric"><div class="metric-label">${label}<span class="metric-ico">${icon}</span></div><div class="metric-number ${kind?'metric-'+kind:''}">${val}</div><div class="metric-sub">${sub}</div></div>`}
function panel(title,content,subtitle='',action=''){return `<article class="panel"><div class="panel-head"><div><div class="panel-title">${title}</div>${subtitle?`<div class="panel-sub">${subtitle}</div>`:''}</div>${action}</div>${content}</article>`}
function empty(title,body){return `<div class="empty"><div class="empty-symbol">◇</div><h3>${title}</h3><p>${body}</p></div>`}
function warnBanner(){if(store.data?.previewMode)return `<div class="data-banner"><div><strong>ARCHIVED RESEARCH PREVIEW — NOT LIVE</strong><p>Real November 2026 fixtures and a pinned independent baseline reconstruction; no tactical, injury, live or bookmaker data. Real production predictions are generated after the GitHub workflow refresh.</p></div>${tag('PINNED 3 NOV 2026','warn')}</div>`;if(store.data?.dataStatus==='ok')return `<div class="banner-plain"><strong>DATA SCOPE ·</strong> Pregame statistical model. ${escapeHTML(store.data.dataWarnings?.slice(0,4).join(' · ')||'')}.</div>`; return `<div class="data-banner"><div><strong>◉ Awaiting the first real-data refresh</strong><p>The interface is installed, but predictions are not yet published. Run <code>python scripts/update.py</code> with internet access, or trigger the GitHub Actions workflow after deployment. No simulated picks are displayed as real.</p></div>${tag('SETUP REQUIRED','warn')}</div>`}
function latest(){if(store.data?.previewMode)return 'ARCHIVED 3 NOV 2026';if(!store.data?.generatedAt)return 'AWAITING DATA';const age=(Date.now()-new Date(store.data.generatedAt).getTime())/3600000;return age<0?'DATA TIMESTAMP CHECK':age<1?'UPDATED <1H AGO':age<24?`UPDATED ${Math.floor(age)}H AGO`:`UPDATED ${Math.floor(age/24)}D AGO`}
function games(){return store.data?.nextGames||[]}
function oddsFor(g){return store.odds[g.id]||null}
function situationFor(g){return g.situation||{home:null,away:null,signals:[],status:'Awaiting updated fixture data'}}
function situationBadge(g){const flags=situationFor(g).signals||[];return flags.length?`<span class="situation-badge">⚡ ${flags.length} situation${flags.length===1?'':'s'}</span>`:''}
function situationTeam(team){if(!team)return '<div class="data-item"><b>Prior game</b><p>Awaiting updated data</p></div>';
 const p=team.previous;const rest=team.fullRestDays;
 return `<div class="data-item"><b>${escapeHTML(team.team)} · ${rest==null?'Rest unknown':rest+' full rest days'}</b><p>${p?`Previous: vs ${escapeHTML(p.opponent)} · ${p.margin>0?'Won by '+p.margin:p.margin<0?'Lost by '+(-p.margin):'Tied'} · ${p.overtime===true?'OVERTIME':p.overtime===false?'Regulation':'OT status unknown'}`:'No previous completed regular/postseason game this season'}</p></div>`;
}
function signalDetails(g){const ctx=situationFor(g);const flags=ctx.signals||[];
 return `<div class="situational-summary">${situationTeam(ctx.away)}${situationTeam(ctx.home)}</div>
 ${flags.length?`<div class="signal-list">${flags.map(x=>`<div class="signal-card"><span class="signal-label">${escapeHTML(x.name)}</span><span class="signal-side">${escapeHTML(x.team)} · ${x.direction==='fade'?'Historical angle: oppose':'Historical angle: support'}</span><p>${escapeHTML(x.reason)}</p></div>`).join('')}</div>`:`<div class="note-box">No named situational triggers found for this matchup, or previous game data is missing.</div>`}
 <p class="source-meta">Situational flags are observed pregame. They influence probabilities ONLY when the historical validation gate is active; ATS records are descriptive and not proof of betting value.</p>`;
}
function tacticalFor(g){return g.tactical||{status:'unavailable',reason:'Awaiting verified play-by-play source.',advantages:[]};}
function statPct(x){return x==null?'—':number(x*100,1)+'%';}
function statEPA(x){return x==null?'—':(x>=0?'+':'')+number(x,3);}
function tacticalDetails(g){const t=tacticalFor(g); if(t.status!=='ready')return `<div class="note-box"><b>Tactical data ${escapeHTML(t.status||'unavailable')}</b> — ${escapeHTML(t.reason||'No compatible data received')}. We do not fabricate matchup statistics.</div>`;
 const row=(side)=>{const v=t[side];return `<div class="data-item"><b>${escapeHTML(v.team)} · last ${v.games} games · ${v.passPlays} weighted dropbacks</b><p>Pass EPA/play ${statEPA(v.passEPA)} · SOS-adjusted ${statEPA(v.adjustedPassEPA)} · Rush EPA/play ${statEPA(v.rushEPA)}<br>Pass EPA allowed ${statEPA(v.allowedPassEPA)} · SOS-adjusted ${statEPA(v.adjustedAllowedPassEPA)} · Rush EPA allowed ${statEPA(v.allowedRushEPA)}<br>Hit/sack proxy allowed ${statPct(v.hitAllowed)} · forced ${statPct(v.hitForced)} · Explosive pass ${statPct(v.explosivePass)} · explosive passes allowed ${statPct(v.explosiveAllowed)}</p></div>`};
 return `<div class="tactical-summary">${row('away')}${row('home')}</div><div class="tactical-grid">${(t.advantages||[]).map(x=>`<div class="tactical-factor"><b>${escapeHTML(x.name)}</b><strong class="${x.favors==='Even'?'muted':'positive'}">${escapeHTML(x.favors)}</strong><small>${x.edge>=0?'+':''}${number(x.edge,3)} ${escapeHTML(x.unit)} towards home</small></div>`).join('')}</div><p class="source-meta">Rolling, weighted, historical team play-by-play only, filtered to previously completed games. Opponent-strength passing adjustment: ${t.sosAdjustmentApplied?'ON (past opponent pregame stats)':'NOT AVAILABLE (raw comparison)'}. A QB hit or sack is a coarse proxy, not a charted pressure. Defensive pass EPA is NOT coverage-specific man/zone data. These advantages are descriptive until validation allows a probability weight.</p>`;
}
function tacticalRadar(){const d=store.data||{}, g=games(),ready=g.filter(x=>tacticalFor(x).status==='ready'),src=d.tacticalSource||{};
 const rows=ready.map(x=>{const t=tacticalFor(x),signals=(t.advantages||[]).filter(z=>z.strong);return {g:x,t,signals,degree:signals.length}}).sort((a,b)=>b.degree-a.degree);
 return warnBanner()+`<div class="summary">${metric('Analysed games',ready.length,`${g.length} scheduled matchups`,'lime','◎')}${metric('Matchup flags',rows.reduce((sum,x)=>sum+x.signals.length,0),'Descriptive differences, not recommended bets','blue','↗')}${metric('PBP seasons',src.seasons?.length||0,'Verified downloaded seasonal files','orange','▤')}${metric('Probability overlay',d.overlaySelection==='tactical'?'TACTICAL':'NOT TACTICAL',d.overlaySelection==='tactical'?'Historical research gate passed':'Not used for win percentages','','∿')}</div>`+
 panel('Tactical matchup board',`<div>${rows.length?rows.map(({g,signals,t})=>`<div class="signal-radar-item" role="button" tabindex="0" data-open="${escapeHTML(g.id)}"><div class="signal-radar-top"><strong>${escapeHTML(g.away)} @ ${escapeHTML(g.home)}</strong>${tag(signals.length+' DIFFERENTIALS',signals.length?'warn':'')}</div><div class="signal-radar-list">${signals.length?signals.map(x=>`<span>${escapeHTML(x.name)} → ${escapeHTML(x.favors)}</span>`).join(''):'<span>Balanced within thresholds</span>'}</div><p>Pass efficiency, rush efficiency, hit/sack proxy and explosive passing. Open for exact underlying metrics.</p></div>`).join(''):empty('No verified tactical metrics available','Run the data update with access to nflverse play-by-play files. We will not invent team metrics when upstream files are missing.')}</div>`,'Historic-play statistics, not certified player-level defensive matchups')+
 panel('Data quality & limitations',`<div class="panel-body"><div class="stat-pair"><span>Source status</span><strong>${escapeHTML(src.status||'unavailable')}</strong></div><div class="stat-pair"><span>Seasons loaded</span><strong>${escapeHTML((src.seasons||[]).join(', ')||'None')}</strong></div><div class="stat-pair"><span>Matchup model</span><strong>${escapeHTML(d.tacticalValidation?.status||'Awaiting validation')}</strong></div><div class="note-box">No player-level coverage assignments, true pressure tracking, confirmed lineup effects or injury probabilities are inferred. Only completed play-by-play records are included in historical matchup snapshots. ${escapeHTML((src.errors||[]).slice(0,3).join(' · '))}</div></div>`,'Tactical features activate as a probability overlay only with sequential historical validation');
}

function qbFor(g){return g.qbIntelligence||{status:'unavailable',home:null,away:null,reason:'No historical quarterback snapshots loaded'};}
function injuriesFor(g){return g.injuryIntelligence||{status:'unavailable',home:[],away:[],note:'No verified injury reports connected'};}
function playerFlags(g){
 const qb=qbFor(g),inj=injuriesFor(g);
 const notes=[];
 for(const side of ['away','home']){
  const t=g[side],p=qb[side];
  if(p?.starterChangeWatch)notes.push(`${t}: projected QB differs from last game`);
  const expectedName=String(p?.qb||'').trim().toLowerCase();
  const media=(g.supplementalInjuryWatch?.[side]||[]);
  const questionable=media.find(x=>expectedName && String(x.name||'').trim().toLowerCase()===expectedName && ['OUT','DOUBTFUL','QUESTIONABLE','INJURED RESERVE','IR','OUT FOR SEASON'].includes(String(x.status||'').toUpperCase()));
  if(questionable)notes.push(`${t}: ESPN currently lists depth-chart QB ${questionable.name} as ${questionable.status}; this is NOT confirmed gameday status`);
  for(const z of inj[side]||[])if(z.position==='QB'&&['OUT','DOUBTFUL','QUESTIONABLE','INJURED RESERVE','IR','INACTIVE'].includes(String(z.status).toUpperCase()))notes.push(`${t}: ${z.name} (${z.status})`);
  const key=(inj[side]||[]).filter(z=>z.starterOnDepthChart && ['OUT','DOUBTFUL'].includes(String(z.status).toUpperCase())&&z.position!=='QB');
  if(key.length)notes.push(`${t}: ${key.length} projected starter(s) out/doubtful`);
 }
 return [...new Set(notes)];
}
function qbDetailBlock(g,side){
 const q=qbFor(g)[side],t=g[side];
 if(!q)return `<div class="qb-team"><h3>${escapeHTML(t)}</h3><p class="instruction">No QB history available.</p></div>`;
 const s=q.sample;
 return `<div class="qb-team"><div class="qb-team-head"><strong>${escapeHTML(t)}</strong>${q.starterChangeWatch?tag('QB CHANGE WATCH','warn'):tag('UNCONFIRMED','')}</div>
 <h3>${escapeHTML(q.qb||'Unknown quarterback')}</h3><p class="tiny">${escapeHTML(q.label||'No confirmed starter')}</p>
 ${s?`<div class="qb-stat-grid"><div><small>EPA / dropback</small><b>${statEPA(s.epaPerDropback)}</b></div><div><small>Completion</small><b>${statPct(s.completionPct)}</b></div><div><small>CPOE</small><b>${s.cpoe==null?'—':(s.cpoe>=0?'+':'')+number(s.cpoe,1)}</b></div><div><small>Sack / dropback</small><b>${statPct(s.sackRate)}</b></div><div><small>Yds / attempt</small><b>${number(s.passingYardsPerAttempt,1)}</b></div><div><small>Sample</small><b>${s.games} G / ${s.dropbacks} DB</b></div></div>`:'<p class="note-box">Player-specific stats are unavailable until the play-by-play feed loads. The listed QB, if present, is only the last recorded starter or a depth-chart projection.</p>'}
 <p class="tiny" style="margin-top:10px">${q.lastGameLeader?`Last recorded game QB: ${escapeHTML(q.lastGameLeader.name)} (${q.lastGameLeader.dropbacks == null ? 'starter record' : q.lastGameLeader.dropbacks+' dropbacks'}).`:'No previous game QB observation.'}</p></div>`;
}
function injuryTeamBlock(g,side){
 const injury=injuriesFor(g),list=injury[side]||[];
 return `<div class="injury-team"><div class="qb-team-head"><strong>${escapeHTML(g[side])} · injury watch</strong>${tag(list.length+' flag'+(list.length===1?'':'s'),'')}</div>
 ${list.length?list.map(item=>`<div class="injury-row"><div><b>${escapeHTML(item.name)} <span class="muted">${escapeHTML(item.position)}</span></b><small>${escapeHTML(item.injury||'Injury type not specified')} · ${item.starterOnDepthChart?'Depth-chart starter':'Role not confirmed'}${item.practice?' · Practice: '+escapeHTML(item.practice):''}</small></div><span class="status-pill ${String(item.status).toUpperCase()==='OUT'?'status-out':''}">${escapeHTML(item.status)}</span></div>`).join(''):'<p class="instruction">No flagged players in the available game-week report. That does not confirm a healthy roster; check the source status below.</p>'}</div>`;
}
function supplementalInjuryDetails(g){
 const watch=g.supplementalInjuryWatch||{},state=watch.status||'unavailable';
 if(state==='unavailable'||state==='empty'){
   return '<div class="note-box">Additional ESPN injury watch: '+escapeHTML(state)+'. No verified current items are available. This does not confirm a healthy roster.</div>';
 }
 let html='<h3 class="mini-title" style="margin-top:18px">ADDITIONAL INJURY WATCH · ESPN</h3><div class="qb-matchup">';
 for(const side of ['away','home']){
   const list=(watch[side]||[]).slice(0,12);
   html+='<div class="injury-team"><div class="qb-team-head"><strong>'+escapeHTML(g[side])+' · ESPN watch</strong>'+tag(list.length+' item'+(list.length===1?'':'s'),'')+'</div>';
   if(!list.length)html+='<p class="instruction">No recent ESPN items for this team. That does not establish full health.</p>';
   for(const item of list){
     html+='<div class="injury-row"><div><b>'+escapeHTML(item.name)+' <span class="muted">'+escapeHTML(item.position||'')+'</span></b><small>'+escapeHTML(item.injury||'Injury unspecified')+' · report '+escapeHTML((item.reportDate||'').slice(0,10))+(item.recentUsage?' · Prior '+item.recentUsage.games+' games: '+(item.recentUsage.offensePct!=null?Math.round(item.recentUsage.offensePct*100)+'% offensive':item.recentUsage.defensePct!=null?Math.round(item.recentUsage.defensePct*100)+'% defensive':'usage unavailable')+' snaps (not current availability)':'')+'</small></div><span class="status-pill">'+escapeHTML(item.status||'Listed')+'</span></div>';
   }
   html+='</div>';
 }
 html+='</div><p class="source-meta">'+(state==='cached'?'CACHED — NOT A CURRENT CHECK. ':'')+'ESPN media injury list retrieved '+escapeHTML(watch.retrievedAt||'unknown')+'. Dated media reports are not the official NFL weekly report or verified gameday inactive list. Any numerical effects actually applied appear in the forecast layer breakdown above.</p>';
 return html;
}

/* Full matchup dossier: source-backed comparisons, not unvalidated betting probabilities. */
function fullMatchupCoverage(g){
 const q=qbFor(g),t=tacticalFor(g),inj=injuriesFor(g),s=situationFor(g),w=g.supplementalInjuryWatch||{};
 const qbReady=Boolean(q.home?.qb&&q.away?.qb&&q.home?.sample&&q.away?.sample);
 const injuryReady=['reported','snapshot-only','snapshot-cached','reported-cached'].includes(inj.status)||w.status==='loaded'||w.status==='cached';
 const restReady=s.home?.fullRestDays!=null&&s.away?.fullRestDays!=null;
 const tacticalReady=t.status==='ready';
 const weatherReady=['forecast','indoor','roof-unconfirmed'].includes(g.weather?.status);
 const counts=[true,qbReady,injuryReady,tacticalReady,restReady,weatherReady];
 return {q,t,inj,s,w,qbReady,injuryReady,restReady,tacticalReady,weatherReady,counts,complete:counts.filter(Boolean).length,total:counts.length};
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
 const tacticalText=(name)=>{const signal=(t.advantages||[]).find(v=>v.name===name);return signal?{favors:signal.favors,edge:signal.edge,unit:signal.unit}:null;};
 const comparisons=[
   {label:'Passing matchup',v:tacticalText('Passing efficiency')},
   {label:'Rushing matchup',v:tacticalText('Rushing efficiency')},
   {label:'QB-hit/sack matchup',v:tacticalText('QB-hit/sack matchup')},
   {label:'Explosive passing',v:tacticalText('Explosive pass opportunity')}
 ];
 const statusRows=[['Team strength / scoring',true,'IN FORECAST'],
 ['QB identity & efficiency',c.qbReady,(g.forecastExplanation?.layers||[]).some(x=>x.applied&&['qb','qb-statistical','qb-replacement'].includes(x.key))?'IN FORECAST':'RESEARCH ONLY'],
 ['Player availability',c.injuryReady,(g.forecastExplanation?.layers||[]).some(x=>x.applied&&['player','other-injuries'].includes(x.key))?'IN FORECAST':'RESEARCH ONLY'],
 ['Tactical EPA matchups',c.tacticalReady,g.overlayType==='tactical'?'IN FORECAST':'RESEARCH ONLY'],
 ['Rest / overtime',c.restReady,g.overlayType==='situational'?'IN FORECAST':'RESEARCH ONLY'],
 ['Venue-area weather',c.weatherReady,'CONTEXT ONLY']];
 const qbAlerts=playerFlags(g);
 const weather=g.weather||{};
 const weatherBlurb=weather.status==='indoor'?'Enclosed stadium: outside wind/rain not expected to affect on-field play.':
 ['forecast','roof-unconfirmed'].includes(weather.status)?
 [weather.temperatureC==null?'Temperature unknown':weather.temperatureC+'°C',
 weather.windMph==null?'Wind unknown':weather.windMph+' mph wind',
 weather.gustMph==null?'Gust unknown':weather.gustMph+' mph gusts',
 weather.precipitationChancePct==null?'Precipitation chance unknown':weather.precipitationChancePct+'% precipitation chance'].join(' · '):
 'Kickoff forecast unavailable ('+(weather.status||'not loaded')+').';
 const tacticalEdges=(t.advantages||[]).filter(x=>x.strong);
 const reliability=c.complete===c.total?'Broad feed coverage':c.complete>=4?'Partial feed coverage':'Limited feed coverage';
 const verdict=`${g.homeProbability>=0.5?g.homeName:g.awayName} is the ${pct(Math.max(g.homeProbability,g.awayProbability))} published favourite. ${tacticalEdges.length?`${tacticalEdges.length} material tactical differential${tacticalEdges.length===1?' is':'s are'} flagged.`:'No large tactical differential is confirmed.'} ${qbAlerts.length?`${qbAlerts.length} player availability or QB watch alert${qbAlerts.length===1?' requires':'s require'} review.`:'Player availability is not independently verified.'}`;
 const row=(label,aValue,hValue)=>`<div class="fm-compare-row"><span class="fm-row-label">${escapeHTML(label)}</span><span>${escapeHTML(aValue)}</span><span>${escapeHTML(hValue)}</span></div>`;
 const status=statusRows.map(([name,available,impact])=>`<div class="fm-data-line"><span>${escapeHTML(name)}</span><span>${tag(available?impact:'UNAVAILABLE',!available?'warn':impact==='IN FORECAST'?'lime':'')}</span></div>`).join('');
 return `<section class="fm-report" aria-label="Complete matchup breakdown">
 <div class="fm-header"><div><div class="eyebrow">FULL MATCHUP DOSSIER · ${escapeHTML(reliability.toUpperCase())}</div><h3>What could decide this game?</h3></div>${tag(`${c.complete}/${c.total} data layers`,c.complete>=5?'lime':'warn')}</div>
 <p class="fm-verdict">${escapeHTML(verdict)}</p>
 <div class="fm-callout"><strong>What the ${pct(g.homeProbability)} home-win probability includes</strong><p>The reconciled forecast breakdown above is authoritative: it identifies exactly which statistical, QB and injury layers moved the published number. Other matchup evidence is displayed here as context only and may be unavailable or unweighted. Provisional player effects have not passed independent forward validation.</p></div>
 <div class="fm-side-grid"><div><small>${escapeHTML(g.away)} · AWAY</small><strong>${escapeHTML(playerText('away'))}</strong><p>${escapeHTML(watchText('away'))}</p></div><div><small>${escapeHTML(g.home)} · HOME</small><strong>${escapeHTML(playerText('home'))}</strong><p>${escapeHTML(watchText('home'))}</p></div></div>
 <div class="fm-compare"><div class="fm-compare-row fm-compare-head"><span>MATCHUP FACTOR</span><span>${escapeHTML(g.away)}</span><span>${escapeHTML(g.home)}</span></div>
 ${row('Offence · recent points/game',number(g.formAway,1),number(g.formHome,1))}
 ${row('Opponent defence · points allowed/game',number(g.allowedHome,1),number(g.allowedAway,1))}
 ${row('Quarterback · EPA/dropback',q.away?.sample?statEPA(q.away.sample.epaPerDropback):'Unavailable',q.home?.sample?statEPA(q.home.sample.epaPerDropback):'Unavailable')}
 ${row('Recovery days',restText(a),restText(h))}
 ${row('Previous game OT',s.away?.previous?.overtime==null?'Unknown':s.away.previous.overtime?'Yes':'No',s.home?.previous?.overtime==null?'Unknown':s.home.previous.overtime?'Yes':'No')}
 </div>
 <div class="note-box"><strong>VENUE WEATHER · ${escapeHTML(weather.stadium||g.stadium||'Unknown venue')}</strong><p>${escapeHTML(weatherBlurb)}</p><p class="source-meta">${escapeHTML(weather.note||'Near-kickoff weather remains uncertain until game day.')} · ${weather.retrievedAt?'Forecast retrieved '+escapeHTML(weather.retrievedAt):'No dated forecast'} · Approximate venue-area conditions, not on-site measurements. Never automatically changes the win percentage. <a href="https://open-meteo.com/en/docs" target="_blank" rel="noopener noreferrer">Open-Meteo source</a></p></div>
 <div class="fm-factors">${comparisons.map(({label,v})=>`<div><b>${escapeHTML(label)}</b><strong>${v?escapeHTML(v.favors==='Even'?'No clear edge':v.favors+' advantage'):'Data unavailable'}</strong><small>${v?`${v.edge>=0?'+':''}${number(v.edge,3)} ${escapeHTML(v.unit)} towards home · research only`:'Historic PBP sample insufficient'}</small></div>`).join('')}</div>
 <div class="note-box"><strong>QB-only model test · ${escapeHTML(store.data?.qbValidation?.status||'Not run')}</strong><p>${store.data?.qbValidation?.evaluationGames||0} historical evaluation games · Brier gain ${number(store.data?.qbValidation?.brierGain,5)}. ${g.overlayType==='qb'?'Validated QB adjustment selected for this fixture.':g.qbResearch?.eligible?'Previous QB data is sufficient, but the adjustment is not active unless historical testing supports it.':'Insufficient pregame QB observations for a numeric adjustment.'}</p></div>
 <div class="fm-two"><div><h4>Situational and player warnings</h4>${(s.signals||[]).length?`<p>${(s.signals||[]).map(v=>escapeHTML(v.name+' · '+v.team)).join(' · ')}</p>`:'<p>No named situational trigger for this matchup.</p>'}${qbAlerts.length?`<ul>${qbAlerts.slice(0,5).map(v=>`<li>${escapeHTML(v)}</li>`).join('')}</ul>`:'<p>QB/injury status can change before kickoff; no full-health claim.</p>'}</div><div><h4>Model input audit</h4>${status}</div></div>
 <p class="fm-footnote">Injury summaries distinguish dated media watch from official game-week reports. Depth charts are unconfirmed starters. No historical accuracy is claimed for individual flags. For details see the QB, tactical and situational sections below.</p></section>`;
}

function playerDetails(g){
 const qb=qbFor(g),inj=injuriesFor(g),flags=playerFlags(g);
 return `<div class="qb-matchup">${qbDetailBlock(g,'away')}${qbDetailBlock(g,'home')}</div>
 <div class="player-flag-list">${flags.length?flags.map(x=>`<div class="signal-card"><span class="signal-label">PLAYER AVAILABILITY WATCH</span><p>${escapeHTML(x)}</p></div>`).join(''):'<div class="note-box">No player alerts identified in the available reports, or reporting is incomplete. No absence or full health is presumed.</div>'}</div>
 <h3 class="mini-title" style="margin-top:18px">INJURY / PRACTICE REPORTS</h3><div class="qb-matchup">${injuryTeamBlock(g,'away')}${injuryTeamBlock(g,'home')}</div>${supplementalInjuryDetails(g)}
 <p class="source-meta">Report coverage: ${escapeHTML(inj.status||'unavailable')}${inj.cachedFrom?' · Cached at '+escapeHTML(inj.cachedFrom):''} · ${inj.timestampBasis==='download-observation'?'Snapshot retrieved (original report time unavailable)':'Last report timestamp'}: ${escapeHTML(inj.reportAsOf||'unknown')} · ${escapeHTML(inj.note||'')}. Depth charts are forecasts, not official inactives. Last-game passer is not a confirmed starter. <b>No unvalidated QB or injury weight has been added to win probabilities.</b> <a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener noreferrer">Official NFL injury reports</a></p>`;
}
function playerRadar(){
 const d=store.data||{},g=games(),src=d.qbSource||{},inj=d.injurySource||{},depth=d.depthSource||{};
 const cards=g.map(game=>({game,flags:playerFlags(game),qb:qbFor(game),inj:injuriesFor(game)}))
     .sort((a,b)=>b.flags.length-a.flags.length || new Date(a.game.kickoff)-new Date(b.game.kickoff));
 const flagged=cards.filter(x=>x.flags.length);
 const seenQB=g.filter(x=>qbFor(x).status==='observed').length;
 const seenInj=g.filter(x=>['reported','snapshot-only','snapshot-cached','reported-cached'].includes(injuriesFor(x).status)).length;
 return warnBanner()+`<div class="summary">${metric('QB coverage',seenQB,`${g.length} scheduled games`,'lime','♙')}${metric('Injury coverage',seenInj,'Available game-week observations','blue','✚')}${metric('Player alerts',flagged.reduce((n,x)=>n+x.flags.length,0),'Informational only','orange','⚠')}${metric('Impact weighting','OFF','Awaiting independent validation','','∿')}</div>`+
 panel('Quarterback & injury matchup board',`<div>${cards.length?cards.map(({game,flags,qb,inj})=>`<div class="signal-radar-item" data-open="${escapeHTML(game.id)}" role="button" tabindex="0"><div class="signal-radar-top"><strong>${escapeHTML(game.away)} @ ${escapeHTML(game.home)}</strong>${tag(flags.length?flags.length+' WATCH FLAGS':(['reported','snapshot-only','snapshot-cached','reported-cached'].includes(inj.status)?'NO FLAG':'REPORT UNAVAILABLE'),flags.length?'warn':(['reported','snapshot-only','snapshot-cached','reported-cached'].includes(inj.status)?'':'warn'))}</div><div class="qb-board-line"><span>${escapeHTML(game.away)}: ${escapeHTML(qb.away?.qb||'QB unknown')}</span><span>${escapeHTML(game.home)}: ${escapeHTML(qb.home?.qb||'QB unknown')}</span></div><div class="signal-radar-list">${flags.length?flags.map(x=>`<span>${escapeHTML(x)}</span>`).join(''):'<span>Open for player history and report availability</span>'}</div></div>`).join(''):empty('No fixtures available','Run the data refresh to show upcoming fixtures and player information.')}</div>`,'Projected depth charts and observed prior-game passers are not confirmed starters')+
 panel('Data quality & source health',`<div class="panel-body"><div class="stat-pair"><span>Previous-game snap-count data</span><strong>${escapeHTML(d.playerUsageSource?.status||"unavailable")}</strong></div><div class="stat-pair"><span>Additional ESPN injury watch</span><strong>${escapeHTML(d.additionalInjurySource?.status||'unavailable')}</strong></div><div class="stat-pair"><span>Recent dated ESPN observations</span><strong>${d.additionalInjurySource?.reportCount??'—'}</strong></div><div class="stat-pair"><span>QB play-by-play</span><strong>${escapeHTML(src.status||'unavailable')}</strong></div><div class="stat-pair"><span>Injury report source</span><strong>${escapeHTML(inj.status||'unavailable')}</strong></div><div class="stat-pair"><span>Depth-chart snapshots</span><strong>${escapeHTML(depth.status||'unavailable')}</strong></div><div class="stat-pair"><span>Injury snapshot retrieved</span><strong>${escapeHTML(inj.asOf||'—')}</strong></div><div class="stat-pair"><span>Depth-chart feed as of</span><strong>${escapeHTML(depth.asOf||'—')}</strong></div><div class="note-box">A missing report is NOT proof a player is healthy. A cached source is not a live injury check. Questionable and limited practice are not equivalent to ruled out. Depth charts may be late, and this dashboard does not yet fetch officially confirmed gameday inactives or assign player-specific points adjustments. ${escapeHTML([...(inj.errors||[]),...(depth.errors||[])].slice(0,3).join(' · '))}</div></div>`,'NFLverse public releases · refresh workflow must succeed before source data appears');
}

function playerImpactFor(g){return g.playerImpact||{status:'informational',eligible:false,reason:'Historical player inputs not yet loaded',features:null};}
function impactGatePanel(){const d=store.data||{},v=d.playerValidation||{},src=d.playerImpactSource||{},rows=v.seasons||[];
 const history=rows.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Evaluation season</th><th>Games</th><th>Baseline Brier</th><th>Player Brier</th><th>Change</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${x.season}</td><td>${x.games}</td><td>${number(x.baselineBrier,4)}</td><td>${number(x.adjustedBrier,4)}</td><td class="${x.brierGain>0?'positive':'negative'}">${x.brierGain>0?'+':''}${number(x.brierGain,4)}</td></tr>`).join('')}</tbody></table></div>`:empty('No eligible walk-forward seasons','At least one previous season of pregame player features is required for training, followed by later independent selection seasons.');
 const weights=v.coefficients||{};
 const dictionary={'qb_epa_edge':'Recent projected-QB EPA advantage','qb_change_edge':'Projected QB change watch','qb_sack_edge':'Recent QB sack-rate gap','key_reported_absences_edge':'Reported OUT/DOUBTFUL depth-chart players'};
 return `<div class="panel-body"><div class="validation-head"><div><strong>${escapeHTML(v.status||'OFF — awaiting data')}</strong><p>${v.sampleSize||0} eligible completed-season games · ${v.evaluationGames||0} evaluated · ${v.improvingSeasons||0} improving years</p></div>${tag(v.enabled?'RESEARCH-GATED':'NO PLAYER WEIGHT',v.enabled?'lime':'warn')}</div>
 ${history}<div class="note-box">Activation requires ≥${v.thresholds?.minEvaluationGames||350} eligible evaluation games, at least two improving seasons, and a Brier gain of ≥${number(v.thresholds?.minBrierGain??.001,3)}. Current-season results are excluded from the gate. Evaluation years are used to select the model, so they are not an untouched forward test.</div>
 <details class="effects-details"><summary>Player model coefficients and provenance</summary><div class="effects-grid">${Object.entries(dictionary).map(([key,name])=>`<div class="stat-pair"><span>${name}</span><strong>${Object.hasOwn(weights,key)?number(weights[key],4):'Not estimated'}</strong></div>`).join('')}</div><p class="source-meta">Coefficients describe correlational changes in win log-odds conditional on the baseline. They are not causal player point values.</p></details>
 <div class="source-meta">Verified historical injury seasons: ${escapeHTML((src.verifiedInjurySeasons||[]).join(', ')||'none')} · Historical depth charts: ${src.historicalSnapshotsAvailable?'at least one archive loaded':'unavailable'} · Source: timestamped nflverse observations</div></div>`;
}
function impactDetail(g){const x=playerImpactFor(g);const delta=g.playerProbabilityDelta||0;const ff=x.features;
 return `<div class="model-adjustment"><strong>PLAYER IMPACT: ${g.overlayType==='player'?'RESEARCH-GATED ADJUSTMENT ACTIVE':'INFORMATION ONLY · NO PROBABILITY WEIGHT'}</strong><p>Eligibility: ${x.eligible?'Full pregame feature snapshot available':'not sufficient to fit this matchup'}. ${escapeHTML(x.reason||'')}.</p><p>Baseline home win ${pct(g.baselineHomeProbability??g.homeProbability)} · Final ${pct(g.homeProbability)} · Player-only change ${delta>=0?'+':''}${number(delta*100,2)} percentage points.</p></div>
 <div class="impact-stat-grid">${['away','home'].map(side=>{const v=x[side]||{};return `<div class="impact-side"><b>${escapeHTML(g[side])} · ${escapeHTML(v.projectedQB||'Projected QB unknown')}</b><span>${v.verifiedQBHistory?'Verified prior QB history':'Insufficient historical QB sample'} · ${v.qbSampleDropbacks??'—'} prior dropbacks</span><span>Depth snapshot: ${escapeHTML(v.depthAsOf||'unavailable')} · ${v.depthAgeDays??'—'} days old</span><span>Reported key out/doubtful: ${v.flaggedKeyAbsences??0} (not confirmed gameday absence)</span></div>`}).join('')}</div>
 ${ff?`<p class="source-meta">Signed toward home: QB EPA gap ${number(ff[0],3)} · Change indicator ${ff[1]} · QB sack gap ${number(ff[2],3)} · Reported absence indicator ${number(ff[3],2)}. Signals do not change this model unless the historical gate is active and selected.</p>`:'<p class="source-meta">Incomplete pregame coverage prevents a player-impact probability estimate. A missing injury record does not establish that a roster is healthy.</p>'}`;
}
function playerImpactLab(){const d=store.data||{},g=games(),v=d.playerValidation||{},eligible=g.filter(x=>playerImpactFor(x).eligible),flags=g.filter(x=>playerFlags(x).length),src=d.playerImpactSource||{};
 const rows=g.slice().sort((a,b)=>Number(playerImpactFor(b).eligible)-Number(playerImpactFor(a).eligible)||playerFlags(b).length-playerFlags(a).length);
 return warnBanner()+`<div class="summary">${metric('Eligible matchups',eligible.length,g.length+' upcoming fixtures','lime','♙')}${metric('Player flags',flags.length,'Observed injury or QB-change watches','orange','!')}${metric('Validated seasons',v.seasons?.length||0,'Completed-season walk-forward results','blue','∿')}${metric('Probability gate',d.overlaySelection==='player'?'SELECTED':'OFF',d.overlaySelection==='player'?'Historical selection passed':'Other overlay or insufficient evidence','','◎')}</div>`+
 panel('Player impact research board',`<div class="impact-board">${rows.length?rows.map(x=>{const impact=playerImpactFor(x),notes=playerFlags(x);return `<div class="impact-game" data-open="${escapeHTML(x.id)}" role="button" tabindex="0"><div><strong>${escapeHTML(x.away)} @ ${escapeHTML(x.home)}</strong><small>${date(x.kickoff)} · ${notes.length} player watches</small></div><div>${tag(impact.eligible?'ELIGIBLE FEATURES':'INPUTS MISSING',impact.eligible?'lime':'warn')}<small>${escapeHTML(impact.eligible?'Historical QB + archive coverage':'No fabricated missing-player weight')}</small></div><span class="impact-chevron">↗</span></div>`}).join(''):empty('No scheduled matchups','Run the NFL schedules importer to see eligible player-impact feature snapshots.')}</div>`,'A data-ready fixture is not proof that the player signals predict results')+
 panel('Player impact validation gate',impactGatePanel(),'Walk-forward research only; no player-specific causal points assumptions')+
 replacementAudit()+
 panel('Data coverage policy',`<div class="panel-body"><div class="data-item"><b>Depth-chart timeline</b><p>Point-in-time depth charts are available in the modern timestamped format from 2025. Earlier weekly charts are not treated as reliable kickoff-as-of projections.</p></div><div class="data-item"><b>Quarterback sample</b><p>Both teams need a recent projected QB on a dated chart plus at least 80 previous dropbacks for a comparable EPA and sack-rate sample.</p></div><div class="data-item"><b>Injury reporting</b><p>Only archive-backed injury statuses as of the prediction cutoff are read. OUT and DOUBTFUL remain reports, not certified inactive lists. Missing reports never imply full health.</p></div><div class="data-item"><b>No double counting</b><p>Historical selection gates allow at most one validated base overlay. Separately labelled provisional QB, replacement and injury scenarios can change displayed estimates, but have NOT passed independent forward calibration; each component is archived.</p></div></div>`,'Data first; no unsupported automatic player adjustments');
}
function favouriteAmbush(g){
 const o=oddsFor(g); if(!o||o.homeHandicap===null||o.homeHandicap===undefined||o.homeHandicap==='')return null;
 const line=Number(o.homeHandicap);if(!Number.isFinite(line)||Math.abs(line)<7)return null;
 const side=line<=-7?'home':'away';const other=side==='home'?'away':'home';
 const weak=(situationFor(g).signals||[]).filter(x=>
   (x.side===side&&x.direction==='fade'&&['empty_tank','thursday_road_ot','repeat_road'].includes(x.id))||
   (x.side===other&&x.direction==='back'&&['blowout_bounce','nuclear_bounce','rest_edge'].includes(x.id)));
 return weak.length?{favorite:g[side],line,weaknesses:weak}:null;
}
function valueFor(g){const o=oddsFor(g);if(!o||!(o.price>1))return null;const p=o.side===g.home?g.homeProbability:g.awayProbability;return {side:o.side,book:o.book,price:o.price,p,ev:p*o.price-1,breakeven:1/o.price}}
function gameRow(g){const favored=g.homeProbability>=.5?g.home:g.away,prob=Math.max(g.homeProbability,g.awayProbability);const o=valueFor(g);
 return `<div class="game-row" tabindex="0" role="button" aria-label="Open ${escapeHTML(g.awayName)} at ${escapeHTML(g.homeName)}" data-open="${escapeHTML(g.id)}"><div><div class="game-teams">${initials(g.away)}<div style="min-width:0"><div class="team-line">${escapeHTML(g.away)} <span class="versus">@</span> ${escapeHTML(g.home)}</div><div class="game-meta">${date(g.kickoff)} · W${g.week} · Open full matchup ↗ ${situationBadge(g)}${tacticalFor(g).status==='ready'?` <span class="situation-badge">◎ tactical</span>`:''}${playerFlags(g).length?` <span class="situation-badge">♙ ${playerFlags(g).length} player watch</span>`:''}${g.personnelScenario?.affectsPrediction?' <span class="situation-badge">PROVISIONAL QB/INJURY FORECAST</span>':''}</div></div></div></div><div><div class="prob-head"><span>${escapeHTML(favored)} win</span><b>${pct(prob)}</b></div><div class="prob-track"><div class="prob-fill" style="width:${Math.round(prob*100)}%"></div></div><div class="game-meta">${o?`<span style="color:${o.ev>0?'#bef780':'#e7ac69'}">${o.ev>0?'+':''}${pct(o.ev)} model EV</span>`:'Market odds not entered'}</div></div><div class="game-proj"><strong>${Math.round(g.predAway)}–${Math.round(g.predHome)}</strong><small>PROJ. SCORE</small></div></div>`}
function rankingRow(r,i){return `<div class="rank-item"><span class="pos">${i+1}.</span><div class="name">${initials(r.team)} <span style="vertical-align:middle;margin-left:5px">${escapeHTML(r.team)}</span></div><div class="rating">${r.rating}</div></div>`}
function getAlerts(){const alerts=[];if(!store.data?.generatedAt)alerts.push({title:'First refresh required',body:'Publish real schedule data to activate forecasts.',type:'warn'});
 else{const age=(Date.now()-new Date(store.data.generatedAt))/3600000;if(age>18)alerts.push({title:'Data is ageing',body:`Last model update ${Math.floor(age)} hours ago. Check the workflow.`,type:'warn'});}
 games().filter(g=>(situationFor(g).signals||[]).some(s=>s.id==='empty_tank'||s.id==='thursday_road_ot')).slice(0,4).forEach(g=>alerts.push({title:`Situational matchup: ${g.away} @ ${g.home}`,body:(situationFor(g).signals||[]).filter(s=>s.id==='empty_tank'||s.id==='thursday_road_ot').map(x=>x.name+' — '+x.reason).join(' | ')+' (adjustment only if model gate is active)',type:'warn'}));
 games().filter(g=>playerFlags(g).length).slice(0,3).forEach(g=>alerts.push({title:`Player intelligence: ${g.away} @ ${g.home}`,body:playerFlags(g).join(' | ')+' · No automatic odds or probability adjustment',type:'warn'}));
 games().filter(g=>favouriteAmbush(g)).slice(0,3).forEach(g=>alerts.push({title:`Favourite Ambush watch: ${favouriteAmbush(g).favorite}`,body:`Manual spread ${favouriteAmbush(g).line>0?'+':''}${favouriteAmbush(g).line} home handicap; ${favouriteAmbush(g).weaknesses.map(x=>x.name).join(', ')}. Watch only, not a validated edge.`,type:'warn'}));
 const goodValues=games().map(g=>({g,v:valueFor(g)})).filter(x=>x.v&&x.v.ev>.04).sort((a,b)=>b.v.ev-a.v.ev);
 goodValues.slice(0,3).forEach(({g,v})=>alerts.push({title:`Potential value: ${v.side} ${Math.round(v.ev*100)}% EV`,body:`Based on your entered ${v.book||'bookmaker'} price of ${v.price.toFixed(2)}. Model uncertainty applies.`,type:'value'}));
 if(store.data?.generatedAt&&!goodValues.length)alerts.push({title:'No qualified value flags',body:'Enter bookmaker prices to compare, or check back when probabilities update.',type:'neutral'});
 alerts.push({title:'Live feed not connected',body:'Live scores, in-play props and push alerts are outside this free first release.',type:'neutral'});
 return alerts}
function alertContent(){return `<div class="panel-body alert-list">${getAlerts().map(a=>`<div class="alert"><span class="alert-icon">${a.type==='value'?'↗':a.type==='warn'?'⚠':'◌'}</span><div><strong>${escapeHTML(a.title)}</strong><p>${escapeHTML(a.body)}</p></div></div>`).join('')}</div>`}
function overview(){const g=games(),perf=store.data?.recentPerformance||store.data?.performance||{},fp=store.data?.forwardPerformance||{};
 const values=g.map(x=>valueFor(x)).filter(Boolean);const positives=values.filter(x=>x.ev>.04);
 const metrics=`<div class="summary">${metric('Upcoming matchups',g.length,'Next available NFL fixtures','lime','◇')}${metric('Model favourites',g.filter(x=>Math.max(x.homeProbability,x.awayProbability)>=.65).length,'65%+ forecast win probability','blue','◎')}${metric('Value watchlist',positives.length,`${values.length} manual prices compared`,'orange','↗')}${metric('Backtest Brier',perf.brier==null?'—':number(perf.brier,3),`${perf.count||0} sequential test games`,'','∿')}</div>`;
 const slate=panel('Upcoming fixtures',g.length?`<div>${g.slice(0,12).map(gameRow).join('')}</div>`:empty('Fixtures will appear here','Once the first nflverse data refresh succeeds, genuine upcoming matchups and computed probabilities will populate this list.'),'Open a matchup for forecast details',`<button class="btn btn-sm" data-nav="matchups">View all →</button>`);
 const rec=store.data?.predictionRecord||{}, graded=rec.completed?.games||0, finalPicks=rec.completed?.latest||{};
 const recordCard=panel('Actual prediction record',
   `<div class="panel-body"><div class="record-home-number">${finalPicks.wins??0}–${finalPicks.losses??0} <span>${graded?pct(finalPicks.accuracy):'—'} correct</span></div>
   <p>${graded} completed NFL game${graded===1?'':'s'} graded from real, timestamped predictions — ${graded<30?'too few to judge predictive accuracy.':'graded separately from historical backtests.'}</p>
   <p class="source-meta">Original picks: ${rec.completed?.original?.wins??0}–${rec.completed?.original?.losses??0}. ${rec.upcomingCount??0} future fixtures tracked; each counts once when final.</p>
   <button class="btn btn-sm btn-ghost" data-nav="performance">See complete prediction record →</button></div>`,
   'Not a reconstructed backtest');
 const perfPanel=panel('Model reliability',`<div class="panel-body">${perf.count?`<div class="stat-pair"><span>Correct favourite</span><strong>${pct(perf.accuracy)}</strong></div><div class="stat-pair"><span>Brier score <span title="Lower is better" class="info-icon">?</span></span><strong>${number(perf.brier,3)}</strong></div><div class="stat-pair"><span>50/50 baseline Brier</span><strong>${number(perf.baselineBrier,3)}</strong></div><div class="stat-pair"><span>Forward-tested games</span><strong>${fp.count||0}</strong></div>`:'<p class="instruction">Run the NFL data importer to calculate sequential historical test metrics.</p>'}<p class="panel-note" style="margin-top:13px">Backtests use historical records only; they are not archived real-time predictions. Betting profitability is not established.</p><button class="btn btn-sm btn-ghost" style="margin-top:10px" data-nav="performance">Explore performance →</button></div>`);
 const rankings=panel('Power ratings',`<div class="panel-body">${(store.data?.powerRankings||[]).length?(store.data.powerRankings.slice(0,6).map(rankingRow).join('')):'<p class="instruction">Ratings appear after the first data run.</p>'}</div>`,'Elo adjusted for previous games, not injuries');
 return warnBanner()+metrics+`<div class="grid-main"><div>${recordCard}${slate}${perfPanel}</div><div class="right-stack">${panel('Intelligence alerts',alertContent(),'Situational effects are applied only after the validation gate passes',tag('WATCHLIST'))}${rankings}</div></div>`}
function matchups(){const g=games().filter(x=>(x.homeName+' '+x.awayName+' '+x.home+' '+x.away).toLowerCase().includes(store.query.toLowerCase()));
 return warnBanner()+panel('Matchup board',`<div class="panel-body"><div class="search-row"><input aria-label="Search matchups" class="input" id="searchGames" placeholder="Search a team..." value="${escapeHTML(store.query)}"/><span class="tiny">${g.length} matches · Model Elo + scoring form</span></div><div class="note-box">Probabilities start with prior results and scoring form. Overtime, rest, bounce-back and consecutive road signals are detected. Adjustments activate only if the historical research gate passes. Recent QB/injury media observations can inform an unvalidated provisional forecast; automated player props remain unconnected.</div></div><div id="gameRows">${g.length?g.map(gameRow).join(''):empty('No upcoming matchups',store.query?'Try another team name.':'Waiting for the NFL schedule feed.')}</div>`,'Select a game to view its simulation distribution, uncertainty and alternative scripts');}
function radar(){const g=games();const rated=g.map(x=>({g:x,v:valueFor(x)})).filter(x=>x.v).sort((a,b)=>b.v.ev-a.v.ev);
 const upset=g.map(x=>({g:x,prob:Math.min(x.homeProbability,x.awayProbability),underdog:x.homeProbability<.5?x.home:x.away})).filter(x=>x.prob>=.33).sort((a,b)=>b.prob-a.prob);
 const cols=`<div class="value-row value-head"><div>Market / Matchup</div><div>Model p</div><div>Price</div><div>Break-even</div><div>Model EV</div></div>`;
 const rows=rated.map(({g,v})=>`<div class="value-row"><div><strong>${escapeHTML(v.side)} to win</strong><small>${escapeHTML(g.away)} @ ${escapeHTML(g.home)} · ${escapeHTML(v.book||'Manual')}</small></div><div class="value-col">${pct(v.p)}</div><div class="value-col">${v.price.toFixed(2)}</div><div class="value-col">${pct(v.breakeven)}</div><div><strong class="${v.ev>0?'value-highlight':'value-danger'}">${v.ev>0?'+':''}${pct(v.ev)}</strong> <button class="pill-action" data-odds="${escapeHTML(g.id)}">Edit</button></div></div>`).join('');
 return warnBanner()+`<div class="summary">${metric('Priced selections',rated.length,'Manually entered UK prices','lime','▤')}${metric('Model-positive prices',rated.filter(x=>x.v.ev>0).length,'Positive EV before model error','blue','↗')}${metric('Strongest raw EV',rated.length?pct(rated[0].v.ev):'—','Model-implied, not assured value','orange','◎')}${metric('Upset candidates',upset.length,'Underdogs 33%+ by active model','','◇')}</div>`+
 panel('Odds comparison',`<div class="table-wrap">${rated.length?cols+rows:empty('No bookmaker prices yet','Open any matchup and enter a decimal price. The dashboard will compare it with the current model without pretending the odds are live.')}</div>`,'Prices are provided by you; no current UK bookmaker odds feed is connected')+
 panel('Situational Radar',`<div>${g.some(x=>(situationFor(x).signals||[]).length)?g.filter(x=>(situationFor(x).signals||[]).length).sort((a,b)=>b.situation.signals.length-a.situation.signals.length).map(x=>`<div class="signal-radar-item" role="button" tabindex="0" data-open="${escapeHTML(x.id)}"><div class="signal-radar-top"><strong>${escapeHTML(x.away)} @ ${escapeHTML(x.home)}</strong>${tag(x.situation.signals.length+' MATCHUP FLAGS','warn')}</div><div class="signal-radar-list">${x.situation.signals.map(s=>`<span>${escapeHTML(s.name)} · ${escapeHTML(s.team)}</span>`).join('')}</div><p>Tap for previous results, recovery windows and signal definitions.</p></div>`).join(''):empty('No situational flags','This card will populate when a fixture matches Empty Tank+, Thursday Road Fatigue, Blowout Bounce, Rest Advantage or consecutive road games.')}</div>`,'Context alerts · not independent proof of betting value')+
 panel('Favourite Ambush watch',`<div>${g.some(x=>favouriteAmbush(x))?g.filter(x=>favouriteAmbush(x)).map(x=>`<div class="signal-radar-item" data-open="${escapeHTML(x.id)}" role="button" tabindex="0"><div class="signal-radar-top"><strong>${escapeHTML(favouriteAmbush(x).favorite)} · Big favourite vulnerability</strong>${tag('MANUAL SPREAD','warn')}</div><div class="signal-radar-list">${favouriteAmbush(x).weaknesses.map(s=>`<span>${escapeHTML(s.name)} · ${escapeHTML(s.team)}</span>`).join('')}</div><p>${escapeHTML(x.away)} @ ${escapeHTML(x.home)}. Triggers require ≥7-point market favourite and an opposing situational factor.</p></div>`).join(''):empty('No Favourite Ambush triggers','In a matchup, enter a bookmaker moneyline and optional home-team point handicap. Only favourites giving 7+ with an adverse situational factor will appear.')}</div>`,'Historical favourite upset pattern · watchlist only, not a calibrated bet')+
 panel('Upset radar',`<div>${upset.length?upset.slice(0,10).map(x=>`<div class="game-row" data-open="${escapeHTML(x.g.id)}" role="button" tabindex="0"><div class="game-teams">${initials(x.underdog)}<div><div class="team-line">${escapeHTML(x.underdog)} upset</div><div class="game-meta">${escapeHTML(x.g.away)} @ ${escapeHTML(x.g.home)}</div><div class="game-meta intel-upset-hint">${escapeHTML((window.NFLMatchupIntelligence?.analyze(x.g).forUnderdog||[]).filter(y=>y.category!=='availability').map(y=>y.title).slice(0,2).join(' · ')||'No validated matchup edge identified')}</div></div></div><div><div class="prob-head"><span>Underdog win</span><b>${pct(x.prob)}</b></div><div class="prob-track"><div class="prob-fill" style="width:${Math.round(x.prob*100)}%"></div></div></div><div class="game-proj"><strong>${x.g.confidence}</strong><small>FAV. CONF.</small></div></div>`).join(''):empty('No upset candidates yet','Underdogs close to even money will be highlighted once predictions are available.')}</div>`,'A plausible upset is not automatically a value bet')+
 `<div class="note-box">EV = (model-estimated win probability × decimal price) − 1. These are research-stage model estimates and may be inaccurate. No real wagering recommendations are being made.</div>`}
function predictionRecordPanel(){
 const d=store.data||{}, r=d.predictionRecord, link='https://github.com/WW2ModellerHub/nfl-prediction-lab/blob/main/data/prediction-results.json';
 if(!r)return panel('Prediction Record',`<div class="panel-body"><p>The first verified results snapshot is not yet published. Archived predictions remain preserved and will be graded against confirmed final scores.</p></div>`);
 const total=r.completed?.games||0, first=r.completed?.original||{},last=r.completed?.latest||{},recent=r.recent10?.latest||{};
 const fn=x=>x==null?'—':pct(x);
 const measured=total>=30;
 const scored=(r.latestResults||[]).map(x=>{
   const firstLabel=x.originalCorrect?'Correct':'Missed',lastLabel=x.latestCorrect?'Correct':'Missed';
   return `<div class="record-result">
     <div class="record-result-main"><strong>${escapeHTML(x.away)} @ ${escapeHTML(x.home)}</strong>
     <span>${escapeHTML(date(x.kickoff))} · W${escapeHTML(x.week??'—')}</span>
     <b>FINAL: ${escapeHTML(x.away)} ${escapeHTML(x.awayScore)} – ${escapeHTML(x.home)} ${escapeHTML(x.homeScore)}</b></div>
     <div class="record-pick"><small>ORIGINAL</small><strong>${escapeHTML(x.originalPick)} ${pct(x.originalWinProbability)}</strong><span class="${x.originalCorrect?'record-hit':'record-miss'}">${firstLabel}</span></div>
     <div class="record-pick"><small>LAST PRE-KICKOFF</small><strong>${escapeHTML(x.latestPick)} ${pct(x.latestWinProbability)}</strong><span class="${x.latestCorrect?'record-hit':'record-miss'}">${lastLabel}</span></div>
     <div class="record-result-source">First recorded ${escapeHTML(date(x.originalRecordedAt))} · Last recorded ${escapeHTML(date(x.latestRecordedAt))}${x.revisionCount?' · '+x.revisionCount+' saved update(s)':''}. ${x.changed?'Probabilities changed before kickoff.':'No changed pregame pick recorded.'}</div>
   </div>`;
 }).join('');
 const weekly=(r.byWeek||[]).slice(0,20).map(x=>`<tr><td>${escapeHTML(x.season)} · Week ${escapeHTML(x.week)}</td><td>${x.games}</td><td>${x.original.wins}–${x.original.losses}</td><td>${x.latest.wins}–${x.latest.losses}</td><td>${fn(x.latest.accuracy)}</td></tr>`).join('');
 const upcoming=(r.upcoming||[]).slice(0,48).map(x=>`<div class="record-pending-row">
 <strong>${escapeHTML(x.away)} @ ${escapeHTML(x.home)}</strong>
 <span>${escapeHTML(x.originalPick)} ${pct(x.originalProbability)} original</span>
 <span>${escapeHTML(x.latestPick)} ${pct(x.latestProbability)} latest</span>
 <small>${escapeHTML(date(x.kickoff))} · Not graded</small></div>`).join('');
 const mini=`<div class="record-metrics">
 <div><small>Original picks</small><strong>${first.wins??0}–${first.losses??0}</strong><span>${fn(first.accuracy)} correct · ${total} graded</span></div>
 <div><small>Latest pregame picks</small><strong>${last.wins??0}–${last.losses??0}</strong><span>${fn(last.accuracy)} correct · ${total} graded</span></div>
 <div><small>Probability error</small><strong>${last.brier==null?'—':number(last.brier,4)}</strong><span>Brier score (lower is better)</span></div>
 <div><small>Upcoming tracked</small><strong>${r.upcomingCount??0}</strong><span>${r.awaitingFinalCount??0} awaiting verified final</span></div></div>`;
 const gradeMessage=total<30?`<strong>Early sample:</strong> ${total} graded game${total===1?'':'s'}. ${fn(last.accuracy)} is the observed win rate, but too few games exist to call this a reliable success rate. This is not a historical backtest.`:
  `<strong>Forward record:</strong> ${total} completed games graded from timestamped predictions, not reconstructed historical backtests.`;
 return `<section class="prediction-record" aria-label="Automatic prediction success tracker">
  <div class="record-header"><div><h2>Our actual prediction record</h2><p>One result per NFL game. Original picks never rewritten.</p></div>${tag(total+' GAMES GRADED',total>=30?'lime':'warn')}</div>
  ${mini}
  <div class="record-sample-note">${gradeMessage}</div>
  <div class="record-title"><h3>Every completed prediction</h3><a href="${link}" target="_blank" rel="noopener noreferrer">Complete source log ↗</a></div>
  <div class="record-list">${scored||'<p class="instruction">No confirmed final scores for saved pre-kickoff predictions yet.</p>'}</div>
  <details class="record-details"><summary>Weekly win/loss record <span>${r.byWeek?.length||0} weeks</span></summary>
    <div class="table-wrap"><table class="data-table"><thead><tr><th>Week</th><th>Graded</th><th>Original W–L</th><th>Latest W–L</th><th>Latest win %</th></tr></thead><tbody>${weekly||'<tr><td colspan="5">No completed games yet.</td></tr>'}</tbody></table></div>
  </details>
  <details class="record-details"><summary>Predictions waiting for kickoff <span>${r.upcomingCount||0} games</span></summary>
    <div class="record-pending-list">${upcoming||'<p class="instruction">No future predictions awaiting kickoff.</p>'}</div>
  </details>
  ${r.awaitingFinalCount?`<p class="source-meta">${r.awaitingFinalCount} game(s) have kicked off but do not have a verified final in the current source. They are not treated as losses or wins.</p>`:''}
  <p class="record-method">Automatically updated after the scheduled NFL refresh when final scores are verified. Original = earliest saved pre-kickoff forecast; latest = last actually saved forecast before kickoff. Each game counts once. No postgame edits, no invented picks, no hypothetical betting ROI.</p>
 </section>`;
}
function perf(){const d=store.data||{},p=d.performance||{},r=d.recentPerformance||{},f=d.forwardPerformance||{};
 const metrics=`<div class="summary">${metric('Sequential backtests',p.count||0,'2024 onward · prior results only','lime','▥')}${metric('Winner accuracy',pct(p.accuracy),'Backtest favourite performance','blue','✓')}${metric('Brier score',number(p.brier,3),'Lower is better','','∿')}${metric('Recorded forward picks',d.forwardPredictions||0,`${f.count||0} games settled`,'orange','◇')}</div>`;
 const cal=(p.calibration||[]);const chart=cal.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Forecast band</th><th>Mean forecast</th><th>Observed win rate</th><th>Games</th></tr></thead><tbody>${cal.map(x=>`<tr><td>${escapeHTML(x.label)}</td><td class="num">${x.pred}%</td><td class="num">${x.actual}%</td><td>${x.count}</td></tr>`).join('')}</tbody></table></div>`:empty('No calibration data','Historical forecasting results will appear after the first pipeline run.');
 const rows=(d.forwardResults||[]).map(x=>`<tr><td>${escapeHTML(x.away)} @ ${escapeHTML(x.home)}</td><td class="num">${pct(x.homeProbability)}</td><td class="num">${x.awayScore}–${x.homeScore}</td><td class="${(x.outcome===1)===(x.homeProbability>=.5)?'positive':'negative'}">${(x.outcome===1)===(x.homeProbability>=.5)?'Correct':'Missed'}</td><td>${escapeHTML(x.recordedAt?.slice(0,10)||'')}</td></tr>`).join('');
 return warnBanner()+predictionRecordPanel()+metrics+`<div class="grid-main"><div>${panel('Historical calibration',chart,'Forecast bins versus actual home win frequencies')}${panel('Forward prediction archive',`<div class="table-wrap">${rows?`<table class="data-table"><thead><tr><th>Game</th><th>Home probability</th><th>Final (away–home)</th><th>Winner</th><th>Recorded</th></tr></thead><tbody>${rows}</tbody></table>`:empty('Forward testing begins after the first live run','When future games conclude, recorded picks will be graded without changing their original probabilities.')}</div>`,'Only genuine pre-kickoff recorded picks appear here')}</div><div>${panel('Validation breakdown',`<div class="panel-body"><div class="stat-pair"><span>Backtest sample</span><strong>${p.count||0}</strong></div><div class="stat-pair"><span>Backtest log loss</span><strong>${number(p.logLoss,3)}</strong></div><div class="stat-pair"><span>50/50 Brier benchmark</span><strong>${number(p.baselineBrier,3)}</strong></div><div class="stat-pair"><span>Recent 100-game Brier</span><strong>${number(r.brier,3)}</strong></div><div class="stat-pair"><span>Archived forward Brier</span><strong>${number(f.brier,3)}</strong></div></div>`)}${panel('Audit notes',`<div class="panel-body"><div class="data-item"><b>Backtest is not forward testing</b><p>Historical probabilities are computed sequentially with only earlier recorded results. They are not timestamped historical advice.</p></div><div class="data-item"><b>No historical odds ROI</b><p>Closing odds at a single book are not a point-in-time UK bookmaker archive. This MVP cannot prove historical betting value.</p></div><div class="data-item"><b>Calibration before confidence</b><p>Do not equate a high model probability with a reliable chance until calibration is demonstrated on unseen games.</p></div></div>`)}</div></div>`}
function activeAudit(){const fresh=store.data?.historicalAudit;if(fresh?.overall?.baseline?.games>0)return {data:fresh,reference:Boolean(fresh.reference||fresh.status==='independent-provisional-snapshot')};return store.auditReference?{data:store.auditReference,reference:true}:{data:null,reference:false};}
function marketAudit(){const {data:a,reference}=activeAudit();if(!a)return warnBanner()+empty('Historical market audit not loaded','Run a verified nflverse schedule refresh. The independent research snapshot is also available as a separate JSON file.');
 const o=a.overall||{},b=o.baseline||{},m=o.market||{},gap=o.modelMinusMarketBrier;
 const ci=o.modelMinusMarketBrier95CI;
 const rows=(a.seasons||[]).map(r=>`<tr><td><strong>${r.season}</strong>${r.season===2026?' <small>(partial)</small>':''}</td><td>${r.baseline?.games||0}</td><td class="num">${pct(r.baseline?.accuracy)}</td><td class="num">${number(r.baseline?.brier,4)}</td><td class="num">${number(r.market?.brier,4)}</td><td class="${r.modelMinusMarketBrier>0?'negative':'positive'}">${r.modelMinusMarketBrier>0?'+':''}${number(r.modelMinusMarketBrier,4)}</td></tr>`).join('');
 const blocks=[{name:'Elo + scoring form',v:b.brier,label:'Historical reconstructed model',cls:'model'},{name:'Closing no-vig market',v:m.brier,label:'Historical closing odds benchmark',cls:'market'}];
 const chart=`<div class="audit-score-chart">${blocks.map(x=>`<div class="audit-score-line"><div class="audit-score-title"><strong>${escapeHTML(x.name)}</strong><span>${number(x.v,4)}</span></div><div class="audit-score-track"><div class="audit-score-fill ${x.cls}" style="width:${Math.max(0,Math.min(100,(x.v||0)/.30*100))}%"></div></div><small>${escapeHTML(x.label)}</small></div>`).join('')}</div>`;
 const prov=store.data?.dataProvenance||{},source=a.source||store.data?.sourceUrl||'nflverse';
 return warnBanner()+`<div class="audit-status">${tag(reference?'FROZEN INDEPENDENT SNAPSHOT':'RECOMPUTED FROM CURRENT DATA',reference?'warn':'lime')} <span>As of ${escapeHTML((a.asOf||'unknown').slice(0,16).replace('T',' '))} UTC · ${escapeHTML(a.marketDefinition||'No-vig closing odds')}</span></div>`+
 `<div class="summary">${metric('Historical model accuracy',pct(b.accuracy),`${b.games||0} non-tied completed games`,'lime','✓')}${metric('Closing market accuracy',pct(m.accuracy),`${m.games||0} available paired prices`,'blue','▤')}${metric('Model Brier',number(b.brier,4),'Lower is better','','∿')}${metric('Market Brier',number(m.brier,4),'Closing price benchmark','orange','◇')}</div>`+
 panel('Probability calibration against the market',`<div class="panel-body">${chart}<div class="note-box">${gap==null?'No paired market data':gap>0?`The baseline was <b>less accurate</b> than the closing market by ${number(gap,4)} Brier points on paired games.`:`The baseline had a lower Brier score than the closing market by ${number(-gap,4)} on paired games.`} ${ci?'Approximate 95% season-week block-bootstrap interval for the model-minus-market difference: ['+ci.map(x=>number(x,4)).join(', ')+'].':'A confidence interval is not available in this snapshot.'}</div></div>`,'Both predictions assessed on identical market-covered games when available')+
 panel('Season-by-season audit',`<div class="table-wrap"><table class="data-table"><thead><tr><th>Season</th><th>Games</th><th>Model win %</th><th>Model Brier</th><th>Market Brier</th><th>Model − market</th></tr></thead><tbody>${rows}</tbody></table></div>`,'2026 is incomplete; lower Brier scores are better')+
 panel('Source & integrity checks',`<div class="panel-body"><div class="stat-pair"><span>Market price sample</span><strong>${o.marketCoverage??0} / ${o.baseline?.games??0}</strong></div><div class="stat-pair"><span>Snapshot provenance</span><strong>${reference?'PINNED · NOT LIVE':'VERIFIED REFRESH'}</strong></div><div class="stat-pair"><span>Refresh mode</span><strong>${escapeHTML(store.data?.refreshMode||'Reference')}</strong></div><div class="stat-pair"><span>Source fingerprint</span><strong title="${escapeHTML(prov.sha256||source)}">${escapeHTML((prov.sha256||'blob 3d3b8292').slice(0,12))}</strong></div><div class="note-box"><b>What this does not prove</b><p>These are reconstructed predictions using historical results in sequence. Closing prices are retrospective, not prices you could necessarily have obtained before kickoff. This is not CLV, historical UK bookmaker ROI, or evidence of a profitable strategy.</p></div><p class="source-meta">${escapeHTML(a.method||a.model||'')} · ${escapeHTML(source)}</p><div class="inline-cta"><button class="btn btn-sm btn-primary" data-export-audit="true">↓ Export audit JSON</button></div></div>`,'Data lineage and performance reporting')+
 `<div class="note-box">${(a.notes||[]).map(x=>escapeHTML(x)).join(' · ')}</div>`;
}
function situationalValidationPanel(v){
 if(!v)return empty('Validation pending','Run the real schedule importer to calculate year-by-year Brier scores and test whether situational adjustments merit activation. The offline demonstration does not contain genuine audited results.');
 const status=v.enabled?tag('ACTIVE','lime'):tag('OFF · NOT PROVEN','warn');
 const years=(v.seasons||[]);
 const table=years.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Season tested</th><th>Games</th><th>Baseline Brier</th><th>Situational Brier</th><th>Gain / loss</th></tr></thead><tbody>${years.map(r=>`<tr><td>${r.season}</td><td>${r.games}</td><td>${number(r.baselineBrier,4)}</td><td>${number(r.adjustedBrier,4)}</td><td class="${r.brierGain>0?'positive':'negative'}">${r.brierGain>0?'+':''}${number(r.brierGain,4)}</td></tr>`).join('')}</tbody></table></div>`:'<div class="note-box">Insufficient completed historical seasons for season-forward testing.</div>';
 const effects=(v.effects||[]).map(x=>`<div class="stat-pair"><span>${escapeHTML(({'empty_tank':'Empty Tank+','thursday_road_ot':'Thursday Road Fatigue','blowout_bounce':'Blowout Bounce','nuclear_bounce':'Nuclear Bounce','rest_edge':'Rest Advantage','repeat_road':'Consecutive Road'})[x.id]||x.id)} <small>(${x.observations} observed)</small></span><strong>${x.approxPpAtEven>0?'+':''}${number(x.approxPpAtEven,2)} pp ${x.applied?'· ON':'· OFF'}</strong></div>`).join('');
 return `<div class="panel-body"><div class="validation-head"><div><strong>${escapeHTML(v.status)}</strong><p>${v.trainedThroughSeason?'Trained through '+v.trainedThroughSeason:'No completed historical training seasons'} · ${v.selectionSample||0} games in last three evaluation seasons · ${v.selectionYearsPositive||0}/${v.selectionYearsTested||0} improved</p></div>${status}</div>${table}<div class="note-box">Eligibility: at least ${v.thresholds?.minGames??350} validation games, Brier gain ≥${number(v.thresholds?.minBrierGain??0.001,3)}, and improvements in at least two tested seasons. This research-window evaluation is used for model selection and is <b>not an untouched blind test</b>. After activation, timestamped forward predictions provide independent evidence.</div><details class="effects-details"><summary>Learned signal effects (research estimates)</summary><div class="effects-grid">${effects}</div><p class="source-meta">Shown as an approximate change in home-win probability at a 50% baseline when the signed factor favours the home team. Effects may reflect correlation, not causation; they are zero-weighted when the gate is OFF.</p></details></div>`;
}
function tacticalValidationPanel(v,selected){if(!v)return empty('Awaiting tactical research','Fetch free NFL play-by-play before any historical tactical validation can run.');
 const rows=(v.seasons||[]).map(x=>`<tr><td>${x.season}</td><td>${x.games}</td><td class="num">${number(x.baselineBrier,4)}</td><td class="num">${number(x.adjustedBrier,4)}</td><td class="${x.brierGain>0?'positive':'negative'}">${x.brierGain>0?'+':''}${number(x.brierGain,4)}</td></tr>`).join('');
 return `<div class="panel-body"><div class="validation-head"><div><strong>${escapeHTML(v.status)}</strong><p>${v.sampleSize||0} eligible historical games · ${v.evaluationGames||0} evaluated games · ${v.improvingSeasons||0} improved seasons</p></div>${tag(selected==='tactical'?'SELECTED':'NOT SELECTED',selected==='tactical'?'lime':'warn')}</div><div class="table-wrap">${rows?`<table class="data-table"><thead><tr><th>Test season</th><th>Games</th><th>Baseline Brier</th><th>Tactical Brier</th><th>Gain</th></tr></thead><tbody>${rows}</tbody></table>`:empty('No eligible evaluation years','Need sufficiently complete previous-season play-by-play plus future test seasons.')}</div><div class="note-box">Ablation adjusts baseline log-odds using four penalised team-level mismatch indicators. It is selected only after at least 350 evaluation games, ≥0.001 Brier gain and improvement in two years. Even if eligible, only the better of tactical or situational can be used; prospective prediction logs are the independent check.</div></div>`;
}
function researchEvidenceLab(){
 const e=store.researchEvidence;
 if(!e)return warnBanner()+empty('Research audit not loaded','The pinned historical strategy dataset has not been loaded yet.');
 const t=e.evaluation||{},base=t.baseline||{},sit=t.situational||{},market=t.closingMarket||{};
 const delta=(sit.brier??0)-(base.brier??0);
 const gate=e.gate||{};
 const years=(e.seasonResults||[]).map(x=>`<tr><td><b>${x.season}</b>${x.season===2026?' <small>(partial)</small>':''}</td><td>${x.n}</td><td class="num">${number(x.baselineBrier,5)}</td><td class="num">${number(x.situationalBrier,5)}</td><td class="num">${number(x.closingMarketBrier,5)}</td><td class="${x.situationalBrier>x.baselineBrier?'negative':'positive'}">${x.situationalBrier>x.baselineBrier?'+':''}${number(x.situationalBrier-x.baselineBrier,5)}</td></tr>`).join('');
 const signals=(e.strategySignals||[]).map(s=>{const train=s.train||[0,0,0],test=s.test||[0,0,0],small=test[0]+test[1]<30;return `<tr><td><b>${escapeHTML(s.name)}</b>${small?' '+tag('SMALL SAMPLE','warn'):''}</td><td>${train.join('–')}</td><td class="num">${number(s.trainATSPct,1)}%</td><td>${test.join('–')}</td><td class="num">${number(s.testATSPct,1)}%</td></tr>`}).join('');
 return `<div class="data-banner"><div><strong>HISTORICAL RESEARCH · NOT LIVE PREDICTIONS</strong><p>Pinned nflverse games source, completed games through ${escapeHTML(e.latestObservedFinalDate||'unknown')}. Research logistic adjustment is independent of the Python production model. Tactical and player injury data are not in this audit.</p></div>${tag('ARCHIVED SOURCE','warn')}</div>`+
 `<div class="summary">${metric('Evaluated games',e.holdoutGames||0,'2024–2026, excluding tied games','lime','▥')}${metric('Baseline Brier',number(base.brier,5),'Original Elo + scoring form','','∿')}${metric('With situational factors',number(sit.brier,5),delta>0?'WORSE than baseline':'Better than baseline',delta>0?'orange':'lime','⌁')}${metric('Market Brier',number(market.brier,5),'Historical no-vig closing odds','blue','◇')}</div>`+
 panel('Probability adjustment decision',`<div class="panel-body"><div class="audit-status">${tag(gate.enabled?'ENABLED':'DISABLED',gate.enabled?'lime':'warn')} <span>Adjustment gate based on 2024–2025 only</span></div><p class="panel-note">${escapeHTML(gate.reason||'')}</p><div class="stat-pair"><span>2024–25 baseline Brier</span><strong>${number(e.selection?.baselineBrier,5)}</strong></div><div class="stat-pair"><span>2024–25 adjusted Brier</span><strong>${number(e.selection?.situationalBrier,5)}</strong></div><div class="stat-pair"><span>2026 adjusted vs baseline</span><strong>${number((e.seasonResults||[]).find(x=>x.season===2026)?.situationalBrier-(e.seasonResults||[]).find(x=>x.season===2026)?.baselineBrier,5)}</strong></div><div class="note-box">The adjustment helped the partial 2026 sample but failed both complete validation years. A short run of success is not enough to override earlier evidence.</div></div>`, 'Research decision · no forced probability uplift')+
 panel('Year-by-year Brier scores',`<div class="table-wrap"><table class="data-table"><thead><tr><th>Season</th><th>Games</th><th>Baseline</th><th>Situational</th><th>Market</th><th>Adjusted − baseline</th></tr></thead><tbody>${years}</tbody></table></div>`, 'All models graded on completed, non-tied games; lower is better')+
 panel('Specific strategies vs closing spreads',`<div class="table-wrap"><table class="data-table"><thead><tr><th>Pattern</th><th>2016–23 W–L–P</th><th>ATS rate</th><th>2024–26 W–L–P</th><th>ATS rate</th></tr></thead><tbody>${signals}</tbody></table></div><div class="panel-body"><div class="note-box">These descriptive ATS records use retrospective closing spreads and do not prove profitable bets. Small samples and correlated signals can make apparent edges unstable.</div></div>`, 'Fading a fatigue flag or backing a bounce-back side, as specified in original rules')+
 panel('Data provenance and outstanding checks',`<div class="panel-body"><div class="stat-pair"><span>Source snapshot</span><strong>${escapeHTML(e.publishedDate||'unknown')}</strong></div><div class="stat-pair"><span>Training seasons</span><strong>${escapeHTML(e.trainYears)}</strong></div><div class="stat-pair"><span>Source last final</span><strong>${escapeHTML(e.latestObservedFinalDate||'unknown')}</strong></div><p class="source-meta">${escapeHTML(e.source||'')}.</p>${(e.outstanding||[]).map(x=>`<div class="data-item"><p>${escapeHTML(x)}</p></div>`).join('')}<div class="inline-cta"><button class="btn btn-primary btn-sm" data-export-evidence="yes">↓ Export independent research JSON</button></div></div>`, 'The full Python source refresh and live publication are still outstanding');
}
function accuracyHistoricalLock(a,score,gain){
 const h=a.lockedHoldout||{},o=h.holdout||null;
 if(!o)return `<div class="panel-body"><p class="instruction">A historical feature choice cannot be evaluated until there are at least two qualifying pre-2024 selection seasons and subsequent 2024+ fixtures.</p><p class="source-meta">Selection: ${h.selectionGames||0} games · Later comparison: ${h.holdoutGames||0} games. ${escapeHTML(h.status||'Unavailable')}</p></div>`;
 const ci=o.brierGain95CI;
 const rows=(o.seasons||[]).map(s=>`<tr><td>${s.season}</td><td>${s.games}</td><td>${score(s.baselineBrier)}</td><td>${score(s.selectedBrier)}</td><td class="${s.brierGain>0?'positive':'negative'}">${gain(s.brierGain)}</td></tr>`).join('');
 return `<div class="panel-body"><div class="note-box">A single feature was chosen using only test seasons through 2023. Its name was then frozen when examining 2024–2025 results. This is a <b>retrospective time split</b>, NOT a new blind or preregistered study; each season’s coefficients were estimated using earlier data only.</div>
 <div class="stat-pair"><span>Historically selected approach</span><strong>${escapeHTML(h.selectedName||'None')}</strong></div>
 <div class="stat-pair"><span>Pre-2024 selection games</span><strong>${h.selectionGames} · ${(h.selectionSeasons||[]).join(', ')}</strong></div>
 <div class="stat-pair"><span>Later check games</span><strong>${o.games}</strong></div>
 <div class="stat-pair"><span>Baseline Brier</span><strong>${score(o.baseline?.brier)}</strong></div>
 <div class="stat-pair"><span>Selected Brier</span><strong>${score(o.selected?.brier)}</strong></div>
 <div class="stat-pair"><span>Paired Brier gain</span><strong class="${o.brierGain>0?'positive':'negative'}">${gain(o.brierGain)}</strong></div>
 <div class="stat-pair"><span>95% exploratory interval</span><strong>${ci?ci.map(gain).join(' to '):'Insufficient weekly blocks'}</strong></div>
 <p class="source-meta">Model weight from this research: 0. Historical evidence is not independently proven betting value.</p></div>
 <div class="table-wrap"><table class="data-table"><thead><tr><th>Later season</th><th>Games</th><th>Baseline Brier</th><th>Selected Brier</th><th>Gain</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
function signalAccuracyLab(){
 const a=store.data?.signalAccuracyLab||{},base=a.baseline||{},c=a.candidates||[],years=a.evaluatedSeasons||[];
 const score=v=>v==null?'—':Number(v).toFixed(5),gain=v=>v==null?'—':(v>0?'+':'')+Number(v).toFixed(5);
 const research=c.filter(x=>x.warrantsForwardResearch);
 const table=c.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Candidate</th><th>Games</th><th>Brier (↓)</th><th>Gain vs base</th><th>95% paired interval</th><th>Verdict</th></tr></thead><tbody>${c.map(x=>`<tr><td><b>${escapeHTML(x.name)}</b></td><td>${x.games}</td><td class="num">${score(x.brier)}</td><td class="${x.brierGain>0?'positive':'negative'}">${gain(x.brierGain)}</td><td class="num">${x.brierGain95CI?x.brierGain95CI.map(gain).join(' to '):'—'}</td><td>${tag(x.warrantsForwardResearch?'FORWARD TEST CANDIDATE':'NOT PROVEN',x.warrantsForwardResearch?'lime':'warn')}</td></tr>`).join('')}</tbody></table></div>`:empty('No eligible historical play-by-play cohort','Full PBP refresh required. Schedules-only data cannot validate tactical matchup effects.');
 const seasons=c.find(x=>x.key==='combined')?.seasons||[];
 const series=seasons.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Season</th><th>Games</th><th>Baseline Brier</th><th>All four Brier</th><th>Gain</th></tr></thead><tbody>${seasons.map(s=>`<tr><td>${s.season}</td><td>${s.games}</td><td>${score(s.baselineBrier)}</td><td>${score(s.candidateBrier)}</td><td class="${s.brierGain>0?'positive':'negative'}">${gain(s.brierGain)}</td></tr>`).join('')}</tbody></table></div>`:empty('No completed evaluation season','Requires at least 350 earlier-season games and 80 games in a subsequent completed season.');
 const cal=a.calibration||{},bb=cal.baseline||[],cc=cal.combined||[];
 const bins=bb.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Band</th><th>Baseline n</th><th>Baseline p</th><th>Actual</th><th>All four n</th><th>All four p</th><th>Actual</th></tr></thead><tbody>${bb.map((x,i)=>{const y=cc[i]||{};return `<tr><td>${escapeHTML(x.band)}</td><td>${x.games}</td><td>${pct(x.meanForecast)}</td><td>${pct(x.actualHomeWinRate)}</td><td>${y.games||0}</td><td>${pct(y.meanForecast)}</td><td>${pct(y.actualHomeWinRate)}</td></tr>`}).join('')}</tbody></table></div>`:empty('No historical calibration','Matching prediction and outcome records are required.');
 const summary=`<div class="summary">${metric('Paired games',a.evaluatedGames||0,'Same games for every method','lime','▥')}${metric('Test seasons',years.length,years.join(', ')||'Awaiting data','blue','∿')}${metric('Baseline Brier',score(base.brier),'Lower is better','','◇')}${metric('Live weighting','ZERO','Research cannot change picks','orange','⊘')}</div>`;
 return warnBanner()+`<div class="accuracy-title"><h2>Signal Accuracy Lab</h2><p>Season-forward historical tests, using only earlier completed seasons for each new fit.</p>${tag('RESEARCH ONLY','warn')}</div>`+summary+
 panel('Five matched signal tests',`<div class="panel-body"><p class="instruction">${a.evaluatedGames?'All '+a.evaluatedGames+' historical games are compared fairly on the same paired sample. '+research.length+' signals meet an exploratory screen for future prospective testing.':'No sufficient play-by-play research sample yet.'} Production model weights from this audit remain zero. Source years requested: ${(a.requestedSeasons||[]).join(', ')||'unknown'}; loaded: ${(a.loadedSeasons||[]).join(', ')||'none'}.</p><p class="source-meta">Source: ${escapeHTML(a.sourceStatus||'unavailable')} · Status: ${escapeHTML(a.status||'unavailable')} · Calculated ${escapeHTML(a.generatedAt||'unknown')}</p></div>${table}`,'Positive Brier gain means lower historical squared prediction error')+
 panel('Earlier feature choice · later historical check',accuracyHistoricalLock(a,score,gain),'Simulated 2023/2024 research split, not untouched prospective data')+
 panel('Combined signal performance by season',series,'Each season evaluated without fitting on its outcomes')+
 panel('Probability calibration',bins,'Historical probability bins; small samples are noisy')+
 panel('Research safeguards',`<div class="panel-body"><div class="note-box">Five alternatives were tested, so a favourable result can be noise. Exploratory confidence intervals are paired by game week but do not correct for multiple comparisons. The date-split feature check is reconstructed retrospectively, not blind prospective validation or evidence of betting profit.</div><ul class="accuracy-notes">${(a.notes||[]).map(x=>`<li>${escapeHTML(x)}</li>`).join('')}</ul><p class="source-meta">Published probabilities, selection gates and archived pregame picks are unchanged.</p></div>`,'Independent prospective evaluation is required before any model promotion');
}
function models(){const d=store.data||{},ranking=d.powerRankings||[];
 const situationalStats=d.situationalStats||[];const v=d.situationalValidation||null;const adjOn=d.overlaySelection==='situational';const tv=d.tacticalValidation||null;
 const qb=d.qbValidation||{},ch=d.challengerValidation||{},fwd=d.shadowForwardPerformance||{},usage=d.playerUsageSource||{},weather=d.weatherSource||{},player=d.playerValidation||{},injury=d.injurySource||{},tactical=d.tacticalSource||{};
 const count=n=>n==null?'—':Number(n).toLocaleString('en-GB');
 const gain=n=>n==null?'—':(n>=0?'+':'')+Number(n).toFixed(5);
 const overlay=d.overlaySelection||'none';
 const models=[
  {id:'M01',name:'Elo & scoring form',category:'forecast',state:'ACTIVE',what:'The published baseline: earlier results, venue advantage, recent offence/defence scoring and expected margin.',proof:'IN FORECAST · no player, weather or market-data adjustment is implied.'},
  {id:'M02',name:'Tactical EPA matchup',category:'forecast',state:overlay==='tactical'?'ACTIVE':'RESEARCH',what:'Pass/rush efficiency, hit-and-sack proxy and explosive-play mismatch features.',proof:count(d.tacticalValidation?.evaluationGames||0)+' completed games evaluated · '+(d.tacticalValidation?.enabled?'gate eligible':'Brier gain not yet sufficient')+'.'},
  {id:'M03',name:'Rest & overtime overlay',category:'forecast',state:overlay==='situational'?'ACTIVE':'GATED',what:'Short rest, overtime fatigue, repeat road games, rest differences and previous blowout effects.',proof:'Season-forward validation did not pass · current probability weight zero.'},
  {id:'M04',name:'Observed QB intelligence',category:'player',state:'CONTEXT',what:'Previous recorded starters, projected depth-chart QBs, prior dropbacks, EPA, sack rate and completion rate.',proof:'QB feed: '+String(d.qbSource?.status||'unavailable')+' · projected starters are not confirmed.'},
  {id:'M05',name:'Injury & practice watch',category:'player',state:'CONTEXT',what:'Dated media observations alongside distinct NFL injury-report snapshots; no absence is assumed from a blank report.',proof:'NFL report: '+String(injury.status||'unavailable')+' · ESPN: '+String(d.additionalInjurySource?.status||'unavailable')+'.'},
  {id:'M06',name:'QB-only adjustment',category:'forecast',state:qb.enabled&&overlay==='qb'?'ACTIVE':'RESEARCH',what:'Learns the incremental influence of QB efficiency, sack exposure and recent starting-QB changes.',proof:count(qb.evaluationGames||0)+' games · Brier gain '+gain(qb.brierGain)+' · '+(qb.enabled?'qualified':'below activation threshold')+'.'},
  {id:'M07',name:'Full player-impact overlay',category:'forecast',state:overlay==='player'?'ACTIVE':'GATED',what:'Pregame projected-QB data combined with reported key-player absences; strict timestamp requirements.',proof:count(player.evaluationGames||0)+' evaluated games · '+(player.enabled?'gate passed':'not enough qualified historical evidence')+'.'},
  {id:'M08',name:'XGBoost multi-factor challenger',category:'forecast',state:'SHADOW',what:'Historical team, QB, rest and tactical features trained in a separate gradient-boosted model.',proof:count(ch.evaluationGames||0)+' evaluated games · Brier '+(ch.challengerBrier==null?'—':Number(ch.challengerBrier).toFixed(5))+' vs baseline '+(ch.baselineBrier==null?'—':Number(ch.baselineBrier).toFixed(5))+' · 0% live weighting.'},
  {id:'M09',name:'Player snap participation',category:'player',state:usage.status==='loaded'?'CONTEXT':'DATA LIMITED',what:'Prior snap share distinguishes heavily used starters from limited-role or seldom-used players on injury lists.',proof:usage.status==='loaded'?count(usage.records)+' rows from nflreadpy / PFR':'Source '+String(usage.status||'unavailable')+'; upstream download may fail.'},
  {id:'M10',name:'Stadium-area weather',category:'player',state:weather.status==='loaded'?'CONTEXT':'PARTIAL',what:'Kickoff-time venue-area wind, temperature and precipitation with roof and forecast-window flags.',proof:count(weather.statuses?.forecast||0)+' outdoor forecasts · '+count(weather.statuses?.indoor||0)+' indoor/covered · no model weight.'},
  {id:'M11',name:'Closing-market benchmark',category:'validation',state:'AUDIT',what:'Measures retrospective win-probability accuracy against no-vig closing moneylines.',proof:count(d.historicalAudit?.overall?.marketCoverage||0)+' matched historical games · never a pregame model input.'},
  {id:'M12',name:'Immutable forward-test tracker',category:'validation',state:'TRACKING',what:'Locks pregame baseline and challenger predictions before kickoff and grades their actual results later.',proof:count(fwd.recordedPicks||0)+' shadow forecasts archived · '+count(fwd.gradedGames||0)+' graded.'},
  {id:'M13',name:'Manual market-value radar',category:'validation',state:'MANUAL',what:'Compare the forecast to personally entered UK bookmaker odds and track price, paper value and outcomes.',proof:'No automatic live odds or proven positive expected value.'},
  {id:'M14',name:'Score-margin Monte Carlo',category:'forecast',state:'PARTIAL',what:'Samples approximate final score, total and margin distributions from the baseline assumptions.',proof:'Normal-margin simulation only; not a possession-by-possession engine.'},
  {id:'M15',name:'Signal Accuracy Lab',category:'validation',state:'AUDIT',what:'Test pass, rush, pressure and explosive-play signals against the same historical Elo baseline.',proof:count(d.signalAccuracyLab?.evaluatedGames||0)+' paired historical games · no automatic weight.'},
  {id:'M16',name:'Opponent-adjusted efficiency',category:'roadmap',state:'PLANNED',what:'Adjust EPA and production for strength of opposing defences and schedule quality.',proof:'Requires rigorous pregame feature history and leakage checks.'},
  {id:'M17',name:'Replacement-value injury model',category:'roadmap',state:'PLANNED',what:'Estimate missing-player impact from usage, efficiency and evidence on the expected replacement.',proof:'Requires historical timestamped availability and starter/replacement observations.'},
  {id:'M18',name:'Coaching / fourth-down tendencies',category:'roadmap',state:'PLANNED',what:'Test team-specific fourth-down aggression and clock management as pregame predictors.',proof:'Potential nfl4th research integration; no active coefficients.'},
  {id:'M19',name:'Live in-game win probability',category:'roadmap',state:'DATA NEEDED',what:'Refresh win chances based on possession, field position, score, clock and remaining timeouts.',proof:'Requires permission-compatible near-live drive/play feed; not connected.'},
  {id:'M20',name:'Player prop distributions',category:'roadmap',state:'DATA NEEDED',what:'Forecast passing, rushing and receiving distributions conditioned on usage and matchups.',proof:'Requires position-specific historical features and independent calibration.'}
 ];
 const groups=[['all','All models'],['forecast','Forecast engines'],['player','Player & venue'],['validation','Testing & value'],['roadmap','Future research']];
 const filter=groups.some(([id])=>id===(store.modelFilter||'all'))?(store.modelFilter||'all'):'all';
 const shown=filter==='all'?models:models.filter(x=>x.category===filter);
 const active=models.filter(x=>x.state==='ACTIVE').length;
 const full=models.filter(x=>x.state==='PLANNED'||x.state==='DATA NEEDED').length;
 const statusTone=s=>s==='ACTIVE'?'lime':['GATED','PARTIAL','DATA LIMITED','DATA NEEDED'].includes(s)?'warn':'';
 const filters=groups.map(([id,label])=>'<button type="button" class="model-filter'+(filter===id?' selected':'')+'" data-model-filter="'+id+'" aria-pressed="'+(filter===id?'true':'false')+'">'+label+' <span>'+models.filter(x=>id==='all'||x.category===id).length+'</span></button>').join('');
 const registry='<div class="panel-body"><div class="model-registry-summary"><strong>'+models.length+' research components</strong><span>'+active+' actively influence the published forecast · '+full+' future / data-dependent · rest informational or gated</span></div><div class="model-registry-controls" role="group" aria-label="Filter model registry">'+filters+'</div><div class="lab-grid model-registry-grid">'+shown.map(x=>'<article class="lab-card model-registry-card"><div class="tiny model-registry-kicker"><span>'+escapeHTML(x.id)+'</span> · '+tag(x.state,statusTone(x.state))+'</div><h3>'+escapeHTML(x.name)+'</h3><p>'+escapeHTML(x.what)+'</p><p class="model-registry-proof">'+escapeHTML(x.proof)+'</p></article>').join('')+'</div><p class="source-meta">Registry labels describe implementation and validation status. Only ACTIVE components are allowed to change displayed probabilities; SHADOW, CONTEXT, AUDIT, GATED and PLANNED do not. Historical selection results are not proof of a betting edge.</p></div>';
 return warnBanner()+panel('Model registry',registry,'Live status and evidence from the last data refresh')+
 panel('Player impact validation gate',impactGatePanel(),'Player probability effects remain zero without sufficient season-forward evidence')+
 panel('Tactical validation gate',tacticalValidationPanel(tv,d.overlaySelection),'Walk-forward matchups · seasonal Brier comparison · current-season outcomes excluded')+
 panel('Situational validation gate',situationalValidationPanel(v),'Three-season research window · lower Brier is better · 2026 forward predictions remain the real test')+
 panel('Strategy audit · exploratory ATS record',`<div class="table-wrap">${situationalStats.length?`<table class="data-table"><thead><tr><th>Pattern / angle</th><th>Occurrences</th><th>ATS W–L–P</th><th>ATS hit rate</th><th>2024+ subset</th></tr></thead><tbody>${situationalStats.map(s=>`<tr><td><b>${escapeHTML(s.name)}</b><br><span class="tiny">${s.direction==='fade'?'Fade flagged team':'Back flagged team'}</span></td><td>${s.observed}</td><td>${s.atsWins}–${s.atsLosses}–${s.atsPushes}</td><td>${s.atsRate==null?'—':pct(s.atsRate)}</td><td>${s.holdoutWins+s.holdoutLosses?`${s.holdoutWins}–${s.holdoutLosses} (${pct(s.holdoutRate)})`:'—'}</td></tr>`).join('')}</tbody></table>`:empty('Historical strategy results awaiting pipeline','Run the latest schedule importer to evaluate overtime and recovery situations against historical closing point spreads.')}</div><div class="note-box">These are retrospective ATS outcomes at historical closing lines, not UK bookmaker fills or a forward-tested profitable strategy. Probability weights are zero unless the separate season-forward Brier evaluation clears its gate. Subset ATS results are descriptive, not independent validation.</div>`,'Source: historical schedules · closing spread data only, no leakage into pregame model')+
 `<div class="grid-main"><div>${panel('Power ratings — all teams',`<div class="panel-body">${ranking.length?ranking.map(rankingRow).join(''):empty('Ratings awaiting data','The next successful pipeline run populates the power table.')}</div>`,'Elo reflects past results; no injury correction')}</div><div>${panel('Prediction methodology',`<div class="panel-body"><div class="data-item"><b>01 · Rating gap</b><p>Elo ratings use earlier match outcomes. Home advantage is +55 rating points unless the game is neutral.</p></div><div class="data-item"><b>02 · Scoring form</b><p>Recent points for and allowed are shrunk toward 22 points per team, preventing extreme reactions to small samples.</p></div><div class="data-item"><b>03 · Probability blend</b><p>A 60/40 Elo and normal-margin probability blend is used as an initial uncalibrated baseline.</p></div><div class="data-item"><b>04 · Simulation assumption</b><p>Normal margin and total distributions illustrate outcome uncertainty. They are not yet detailed drive-level NFL simulations.</p></div><div class="data-item"><b>05 · Situational validation</b><p>Residual logistic adjustments are regularised and evaluated on later seasons. Only prior completed seasons contribute to the current model. The gate can remain off.</p></div><div class="data-item"><b>06 · Forward testing</b><p>Pregame probabilities are appended to a prediction log and later graded without revision.</p></div></div>`,'Transparent baseline algorithm')}</div></div>`}
function bets(){const b=store.bets||[];const totalStake=b.filter(x=>x.result==='W' || x.result==='L' || x.result==='V').reduce((a,x)=>a+Number(x.stake),0),
 settled=b.filter(x=>x.result==='W'||x.result==='L'||x.result==='V');
 const profit=settled.reduce((a,x)=>a+(x.result==='W'?x.stake*(x.odds-1):x.result==='L'?-x.stake:0),0);
 const rows=b.map(x=>`<tr><td>${escapeHTML(x.pick)}</td><td>${escapeHTML(x.game)}</td><td>${escapeHTML(x.book||'Manual')}</td><td class="num">${number(x.odds,2)}</td><td class="num">${money(x.stake)}</td><td><select class="select" aria-label="Result of ${escapeHTML(x.pick)}" data-result="${escapeHTML(x.id)}"><option value="P" ${x.result==='P'?'selected':''}>Pending</option><option value="W" ${x.result==='W'?'selected':''}>Win</option><option value="L" ${x.result==='L'?'selected':''}>Loss</option><option value="V" ${x.result==='V'?'selected':''}>Void</option></select></td><td><button class="btn btn-sm" data-deletebet="${escapeHTML(x.id)}">Remove</button></td></tr>`).join('');
 const g=games();return warnBanner()+`<div class="summary">${metric('Recorded bets',b.length,'This device only','lime','▤')}${metric('Settled stake',money(totalStake),'Wins, losses and voids','blue','£')}${metric('Net P/L',money(profit),'Manual settlement',profit>=0?'lime':'orange','↗')}${metric('Settled ROI',totalStake?number(profit/totalStake*100,1)+'%':'—','Not a model-validation metric','','∿')}</div>`+
 panel('Add personal bet',`<div class="panel-body"><form id="betForm"><div class="form-row"><label><span class="field-label">Fixture</span><select class="select" id="betGame" required>${g.length?g.map(x=>`<option value="${escapeHTML(x.id)}">${escapeHTML(x.away)} @ ${escapeHTML(x.home)} · ${date(x.kickoff)}</option>`).join(''):'<option value="manual">Other / manual fixture</option>'}</select></label><label><span class="field-label">Selection</span><input id="betPick" class="input" required maxlength="80" placeholder="e.g. BUF moneyline"/></label></div><div class="form-row three"><label><span class="field-label">Bookmaker</span><input id="betBook" class="input" maxlength="50" placeholder="e.g. Sky Bet"/></label><label><span class="field-label">Decimal odds</span><input id="betOdds" class="input" inputmode="decimal" type="number" step="0.01" min="1.01" max="1000" required placeholder="2.10" /></label><label><span class="field-label">Stake (£)</span><input id="betStake" class="input" inputmode="decimal" type="number" step="0.01" min="0.01" max="100000" required placeholder="5.00" /></label></div><button type="submit" class="btn btn-primary">+ Record bet</button><p class="help-line">Records stay in browser storage. Export backups regularly. No financial transactions are placed.</p></form></div>`,'Manual actual-bet ledger; not automatically treated as a model pick')+
 panel('Bet ledger',`<div class="table-wrap">${b.length?`<table class="data-table"><thead><tr><th>Pick</th><th>Matchup</th><th>Bookmaker</th><th>Odds</th><th>Stake</th><th>Result</th><th></th></tr></thead><tbody>${rows}</tbody></table>`:empty('No bets entered','Add your first bet using the form above. This ledger is independent of the prediction backtest.')}</div>`,'Settlement is manual; ROI reflects only entered bets')+
 `<div class="inline-cta"><button class="btn" data-import="bets">↑ Import ledger backup</button><button class="btn" data-export="bets">↓ Export backup</button><input type="file" id="importFile" accept="application/json" hidden/></div>`}
function intelligencePanel(g){
 const api=window.NFLMatchupIntelligence;
 if(!api||typeof api.analyze!=="function")return '<section class="intel-section"><h3>Matchup Intelligence</h3><p class="instruction">Matchup evidence module unavailable. Existing forecast remains unchanged.</p></section>';
 const r=api.analyze(g);
 const escape=escapeHTML;
 const caseHtml=(arr,team,emptyMessage)=>`<div class="intel-argument">
  <h4>${escape(team)}</h4>
  ${arr.length?`<ol>${arr.map(x=>`<li><strong>${escape(x.title)}</strong><p>${escape(x.detail)}</p><small>${escape(x.source)}</small></li>`).join('')}</ol>`:`<p class="instruction">${escape(emptyMessage)}</p>`}
  </div>`;
 const tacticalRows=r.matchup.map(m=>`<div class="intel-factor">
  <div class="intel-factor-heading"><strong>${escape(m.label)}</strong>${m.status==="unavailable"?tag('DATA MISSING','warn'):m.status==="notable"?tag('NOTABLE · '+m.favors,'lime'):tag('OBSERVED','')}</div>
  <p>${escape(m.details)}</p>
  <div class="intel-factor-meta">${escape(m.sample||'')}${m.sample?' · ':''}${escape(m.source)}</div>
 </div>`).join('');
 const availability=side=>{
  const v=r.injury[side],name=g[side];
  const flags=v.entries.slice(0,5);
  return `<article class="intel-availability">
   <header><strong>${escape(name)} · Availability watch</strong>${tag(v.status,v.qbFlagCount?'warn':'')}</header>
   <div class="intel-availability-counts"><div><b>${v.outCount}</b><span>Out/doubtful/IR flags</span></div><div><b>${v.questionableCount}</b><span>Uncertain reports</span></div><div><b>${v.projectedStarterFlagCount}</b><span>Depth-chart starters flagged</span></div></div>
   ${flags.length?`<ul>${flags.map(x=>`<li><b>${escape(x.name)} · ${escape(x.position)}</b><span>${escape(x.status)} · ${escape(x.source)}${x.starterOnDepthChart?' · projected starter':''}</span></li>`).join('')}</ul>`:'<p class="instruction">No observed relevant player flags. Missing reports do not mean full health.</p>'}
   <p class="intel-evidence-caption">${escape(v.coverage)}${v.cached?' · CACHED, NOT LIVE':''} · As of ${escape(v.reportedAsOf)}. Statuses are observations, not confirmed gameday availability or measured point penalties.</p>
  </article>`;
 };
 const qbHtml=r.qb.map(p=>`<div class="intel-qb"><strong>${escape(p.team)} · ${escape(p.name)}</strong><span>Historical EPA/dropback ${p.epaPerDropback==null?'unavailable':(p.epaPerDropback>=0?'+':'')+number(p.epaPerDropback,3)} · ${p.sampleGames??'—'} games / ${p.sampleDropbacks??'—'} dropbacks · <b>Starter unconfirmed</b>${p.changeWatch?' · PROJECTED QB CHANGE':''}</span></div>`).join('');
 const yesNo=x=>x.available?'AVAILABLE':'MISSING';
 const coverage=r.coverage.map(x=>`<span class="${x.available?'intel-coverage-on':'intel-coverage-off'}">${escape(x.name)}: ${yesNo(x)}</span>`).join('');
 return `<section class="intel-section" aria-label="Evidence-backed game intelligence">
  <div class="intel-title"><div><div class="eyebrow">PREGAME INTELLIGENCE · RESEARCH, NOT A NEW FORECAST</div><h3>Why each team could win</h3><p>Strength against weakness, documented uncertainty, and the plausible upset route.</p></div>${tag(r.matchup.filter(m=>m.status==='notable').length+' notable contrasts','')}
  </div>
  <div class="intel-summary-strip"><div><small>MODEL FAVOURITE</small><b>${escape(r.favourite||'Unknown')}</b></div><div><small>UNDERDOG</small><b>${escape(r.underdog||'Unknown')} ${r.underdogProbability==null?'':'· '+pct(r.underdogProbability)}</b></div><div><small>UPSET-ROUTE ANGLES</small><b>${r.upsetContextCount}</b><span>Not independently predictive</span></div></div>
  <div class="intel-cases">${caseHtml(r.forFavourite,r.favourite||'Favourite','No qualifying above-threshold tactical or situational advantage found in available data.')}${caseHtml(r.forUnderdog,(r.underdog||'Underdog')+' · Upset route','No above-threshold verified strength-versus-weakness or situational angle currently supports a special upset case. This does not make an upset impossible.')}</div>
  <p class="intel-takeaway">${escape(r.upsetSummary)}</p>
  <div class="intel-subsection"><h4>Observed strength versus weakness</h4><div class="intel-factor-grid">${tacticalRows}</div></div>
  <div class="intel-subsection"><h4>Quarterback history <span class="intel-subtle">Not confirmed starters</span></h4><div class="intel-qb-grid">${qbHtml}</div></div>
  <div class="intel-subsection"><h4>Player availability exposure <span class="intel-subtle">No invented injury point values</span></h4><div class="intel-availability-grid">${availability('away')}${availability('home')}</div></div>
  <div class="intel-subsection"><h4>Source coverage</h4><div class="intel-coverage">${coverage}</div><p class="intel-evidence-caption">Active probability overlay: ${escape(r.modelOverlayType)}. ${escape(r.caveat)} The scoring model uses regressed Elo and form; matchup flags can be informative without being reliably predictive.</p></div>
 </section>`;
}

function qbReplacementDetail(g){
 const r=g.qbReplacement||{},scenarios=Array.isArray(r.scenarios)?r.scenarios:[],checks=Array.isArray(r.teamChecks)?r.teamChecks:[],active=!!r.affectsPrediction;
 const feed=g.qbSourceEvidence||{};
 const extra=Array.isArray(['home','away'])?['home','away'].map(side=>{
   const e=feed[side]||{};
   return `<div class="qb-evidence-provider"><b>${escapeHTML(e.team||side)}</b>
   <div><span>nflverse</span><strong>${escapeHTML(e.nflverseProjectedQB||'Not available')}</strong></div>
   <div><span>ESPN ranked depth</span><strong>${escapeHTML(e.espnProjectedQB||e.espnDepthStatus||'Unavailable')}</strong></div>
   <div><span>ESPN roster QBs (not starters)</span><strong>${escapeHTML((e.espnRosterQBs||[]).join(', ')||e.espnRosterStatus||'Unavailable')}</strong></div>
   <div><span>Dated QB injuries</span><strong>${escapeHTML((e.datedQBInjuryReports||[]).map(x=>x.name+' · '+x.status).join('; ')||'No individually dated report in available ESPN league feed')}</strong></div>
   <div><span>Comparison</span><strong>${e.sourceConflict?'SOURCES DISAGREE':e.sourcesAgree?'PROJECTIONS AGREE':escapeHTML(e.evidenceStatus||'Not checked')}</strong></div>
   <small>ESPN ranked-depth snapshot observed: ${e.espnObservedAt?escapeHTML(date(e.espnObservedAt)):'unavailable'} · Roster feed: ${escapeHTML(e.espnRosterStatus||'unavailable')} · Injury designations: ESPN league injury feed</small>
   </div>`;
 }).join(''):'';
 const coverage=r.coverageStatus||'unknown',reason=r.coverageSummary||r.reason||'The data source has not supplied a verified QB replacement estimate.';
 const checkRows=checks.map(c=>{
   const issues=Array.isArray(c.missingReasons)?c.missingReasons:[];
   const status=c.injuryReportStatus||(
      c.injuryFeedStatus==='loaded'?'No matching OUT/DOUBTFUL report':'Media injury feed unavailable or cached');
   return `<div class="qb-evidence-team">
    <strong>${escapeHTML(c.team||c.side)}</strong>
    <div class="qb-evidence-pair"><span>Established starter by prior season starts</span><b>${escapeHTML(c.establishedQB||'Not established')} ${c.establishedQB?'('+number(c.establishedStarts,0)+' starts)':''}</b></div>
    <div class="qb-evidence-pair"><span>Established QB injury</span><b>${escapeHTML(c.establishedQBStatus||'Not verified out')}</b></div>
    <div class="qb-evidence-pair"><span>Last-game starter</span><b>${escapeHTML(c.lastRecordedQB||'Not recorded')}</b></div>
    <div class="qb-evidence-pair"><span>Two QB absences evidenced</span><b>${c.doubleAbsenceReported?'YES · distinct reported absences':c.alreadyMissingFromLastGame?'Established QB missed last game; check last-game starter':'Not established'}</b></div>
    <div class="qb-evidence-pair"><span>Projected QB</span><b>${escapeHTML(c.projectedQB||'Not verified')}</b></div>
    <div class="qb-evidence-pair"><span>Outgoing QB injury</span><b>${escapeHTML(status)}</b></div>
    <div class="qb-evidence-pair"><span>Prior QB dropbacks</span><b>${number(c.outgoingPriorDropbacks,0)}</b></div>
    ${issues.length?`<p class="qb-evidence-missing">${issues.map(x=>escapeHTML(x)).join(' · ')}</p>`:`<p class="qb-evidence-ok">Available projected QB inputs checked</p>`}
    <p class="source-meta">Previous game observation: ${c.lastRecordedAt?escapeHTML(date(c.lastRecordedAt)):'missing'} · Depth chart: ${c.depthChartAsOf?escapeHTML(date(c.depthChartAsOf)):'missing'}</p>
   </div>`;
 }).join('');
 const details=`<details class="qb-evidence-details"><summary>What QB evidence was checked? <span>View both teams</span></summary>
  ${feed.status?`<div class="qb-evidence-provider-grid">${extra}</div>`:''}
  ${checks.length?`<div class="qb-evidence-grid">${checkRows}</div>`:'<p class="instruction">The full source refresh has not populated a QB evidence checklist for this matchup yet.</p>'}
  <p class="source-meta">The depth chart is a projection, not confirmation of a starting QB. Media reports must be recent and specifically match the outgoing QB. Missing evidence is never treated as a healthy roster.</p>
  </details>`;
 const qbRoom=checks.filter(c=>c.establishedQB&&c.lastRecordedQB&&c.establishedQB!==c.lastRecordedQB)
 .map(c=>`<div class="qb-room-chain"><b>${escapeHTML(c.team)}</b> · Established by prior starts: <strong>${escapeHTML(c.establishedQB)}</strong> (${escapeHTML(c.establishedQBStatus||'availability not verified')}) · Last-game starter: <strong>${escapeHTML(c.lastRecordedQB)}</strong> (${escapeHTML(c.injuryReportStatus||'availability not verified')}) · Projected: <strong>${escapeHTML(c.projectedQB||'unverified')}</strong> ${c.doubleAbsenceReported?'<span class="qb-chain-warning">TWO REPORTED ABSENCES · no double deduction</span>':''}</div>`).join('');
 const noScenario=!scenarios.length;
 const label=noScenario?(coverage==='established-qb-already-absent'?'ESTABLISHED QB ALREADY ABSENT':coverage==='conflicting-sources'?'SOURCES DISAGREE':coverage==='missing-data'?'QB DATA INCOMPLETE':coverage==='reported-absence-unpriced'?'REPORTED OUT · REPLACEMENT UNKNOWN':coverage==='no-change'?'NO QB CHANGE DETECTED':'NO VERIFIED REPLACEMENT'):active?'REPORTED ABSENCE · PROVISIONAL':'PROJECTED SWITCH · SCENARIO ONLY';
 const note=noScenario?(coverage==='established-qb-already-absent'?'Earlier QB absence can already affect the Elo/form baseline; no second deduction applied.':coverage==='no-change'?'No replacement adjustment needed.':coverage==='conflicting-sources'?'Conflicting projected starters require human verification.':coverage==='missing-data'?'Cannot calculate replacement value from the available sources.':'Replacement effect not supported by the available evidence.'):'',
       narrative=noScenario?(reason):'The estimated effect uses historical QB efficiency and prior completed first starts. It is not proof of who will start.';
 if(noScenario){
  return `<section class="matchup-panel matchup-wide qb-replace-panel qb-replace-compact" aria-label="QB replacement evidence">
    <div class="qb-replace-head"><h3>QB Replacement</h3>${tag(label,coverage==='reported-absence-unpriced'?'warn':'')}</div>
    <p class="qb-replace-summary">${escapeHTML(narrative)}</p>
    ${qbRoom}
    <p class="qb-replace-small">${escapeHTML(note)} <b>No separate QB replacement percentage has been applied.</b> Other QB-efficiency adjustments may still appear in the overall forecast above.</p>
    ${details}</section>`;
 }
 const show=scenarios.map(x=>{
  const better=x.fullAbsencePoints>0?'possible downgrade':x.fullAbsencePoints<0?'possible upgrade':'neutral';
  return `<div class="qb-replace-card"><div class="qb-replace-head"><strong>${escapeHTML(x.team)} · ${escapeHTML(x.outgoingQB)} → ${escapeHTML(x.replacementQB)}</strong>${tag(x.mode==='reported-absence'?'FRESH OUT/DOUBTFUL REPORT':'PROJECTED ONLY',x.mode==='reported-absence'?'warn':'')}</div>
  <div class="qb-replace-grid">
  <div><small>Outgoing prior EPA/dropback</small><b>${statEPA(x.outgoingExpectedEPA)}</b></div>
  <div><small>Replacement EPA/dropback</small><b>${statEPA(x.replacementExpectedEPA)}</b></div>
  <div><small>Conditional team scoring effect</small><b>${number(x.fullAbsencePoints,1)} pts</b></div>
  <div><small>If replacement starts · ${escapeHTML(g.home)} wins</small><b>${pct(x.conditionalHomeProbability)}</b></div></div>
  ${x.establishedQB&&x.establishedQB!==x.outgoingQB?`<p class="qb-chain-note"><b>QB chain:</b> Established starter ${escapeHTML(x.establishedQB)} (${escapeHTML(x.establishedQBStatus||'status unverified')}) → last-game starter ${escapeHTML(x.lastGameQB)} → projected ${escapeHTML(x.replacementQB)}. ${x.twoQBAbsencesReported?'Two separate recent unavailable reports found.':'No two-absence confirmation.'} The model uses only the <b>last-game QB to next replacement</b> change; it does not penalise the original starter a second time.</p>`:''}
  <p class="source-meta">${escapeHTML(x.outgoingQB)}: ${number(x.oldQBdropbacks,0)} prior dropbacks · ${escapeHTML(x.replacementQB)}: ${number(x.replacementQBdropbacks,0)} prior dropbacks. ${x.firstStartObservations?`Inexperienced replacement reference: ${number(x.firstStartObservations,0)} earlier first starts.`:''} This is a ${escapeHTML(better)} estimate, not a confirmed starter or a calibrated injury impact.</p>
  <p class="source-meta">Illustrative scenario sensitivity for ${escapeHTML(g.home)}: ${pct(x.illustrativeLow)}–${pct(x.illustrativeHigh)} (not a statistical confidence interval).</p></div>`;
 }).join('');
 return `<section class="matchup-panel matchup-wide qb-replace-panel" aria-label="QB replacement evidence">
  <div class="qb-replace-head"><h3>QB Replacement</h3>${tag(label,active?'warn':'')}</div>
  <p class="qb-replace-summary">${escapeHTML(narrative)}</p>
  ${qbRoom}
  ${show}
  ${active?`<div class="stat-pair"><span>Replacement adjustment applied to ${escapeHTML(g.home)} win probability</span><strong>${r.homeDelta>0?'+':''}${number(r.homeDelta*100,1)} percentage points</strong></div>`:
  `<p class="qb-replace-small"><b>Conditional scenario only — the published win probability has not been changed by this QB replacement estimate.</b> No verified matching absence was available.</p>`}
  ${details}
  <details class="qb-evidence-details"><summary>Model safeguards and limitations</summary><p class="source-meta">A reported OUT/DOUBTFUL outgoing QB, an independently dated replacement projection and adequate prior performance history are required for an applied effect. Questionable is not treated as OUT. NFL first-start distributions and the EPA-to-points conversion are research assumptions; the model is not independently prospectively calibrated.</p></details>
 </section>`;
}
function replacementAudit(){
 const d=store.data||{},research=d.qbReplacementResearch||{},src=d.qbReplacementSource||{},cs=(d.nextGames||[]).filter(g=>(g.qbReplacement?.scenarios||[]).length);
 const n=src.counts||{};
 return panel('Quarterback replacement research',`<div class="panel-body"><p>The published replacement model estimates the drop-off using dated pregame QB projections, prior-game QB efficiency and observed first-start history. It <b>never</b> imports a future actual starter or same-game QB EPA.</p>
 <div class="stat-pair"><span>Historical projection-change research games</span><strong>${research.eligibleProjectedChangeGames||0}</strong></div>
 <div class="stat-pair"><span>Historical baseline Brier (matched)</span><strong>${number(research.baselineBrier,5)}</strong></div>
 <div class="stat-pair"><span>Conditional scenario Brier (matched)</span><strong>${number(research.conditionalScenarioBrier,5)}</strong></div>
 <div class="stat-pair"><span>Provisional reported-QB replacement adjustments this refresh</span><strong>${n.replacementQB||0}</strong></div>
 <div class="stat-pair"><span>Fixtures with conditional QB-change scenarios</span><strong>${n.conditionalQBScenarios||0}</strong></div>
 <p class="source-meta">Historical study: ${escapeHTML(research.status||'Unavailable')}. The comparison uses projected changes, not confirmed injury outcomes; it does not approve a production betting edge. ${cs.length?'Current fixtures with evidence: '+cs.map(g=>g.away+' @ '+g.home).join(', '):'No current matchup qualifies for a conditional scenario.'}</p>
 </div>`,'No historical hindsight; point mapping is research-only');
}
function personnelSummary(g){
 const s=g.personnelScenario||{},p=g.prePersonnelProbability??g.baselineHomeProbability??g.homeProbability;
 const flags=Array.isArray(s.factors)?s.factors:[];
 return `<section class="matchup-panel matchup-wide personnel-panel"><h3>Quarterback & injury-aware estimate ${tag(s.affectsPrediction?'PROVISIONAL ADJUSTMENT':'NO QUALIFYING ADJUSTMENT',s.affectsPrediction?'warn':'')}</h3>
 <div class="revision-numbers"><div><small>BEFORE PERSONNEL ASSUMPTIONS · HOME</small><strong>${pct(p)}</strong><span>${escapeHTML(g.home)}</span></div><div><small>CURRENT FORECAST · HOME</small><strong>${pct(g.homeProbability)}</strong><span>${escapeHTML(g.home)}</span></div><div><small>INJURY/QB EFFECT</small><strong>${s.homeDelta==null?'—':(s.homeDelta>0?'+':'')+number(s.homeDelta*100,1)+' pp'}</strong><span>Assumed, not validated</span></div></div>
 ${flags.length?flags.map(x=>`<div class="personnel-flag"><b>${escapeHTML(x.team)}: ${escapeHTML(x.player)} (${escapeHTML(x.status)})</b><p>${escapeHTML(x.evidence||'')} · ${number(x.pointsAgainstTeam,2)} assumed team-point impact (positive means penalty, negative means improvement). ${escapeHTML(x.assumption||'')}</p></div>`).join(''):`<p class="instruction">${escapeHTML(s.reason||'No current verified injury-report signal; not proof of full health.')}</p>`}
 <p class="source-meta">Source observed ${escapeHTML(s.sourceObservedAt||'not refreshed')} · ${escapeHTML(s.status||'unavailable')}. ESPN media reports and projected depth-chart QBs are not official gameday starters or inactives. This provisional adjustment uses explicit point assumptions, not a validated injury-value model. Questionable status never counts as OUT.</p></section>`;
}
function forecastHero(g){
 const p=Number(g.homeProbability),homeFav=p>=.5;
 const fav=homeFav?(g.homeName||g.home):(g.awayName||g.away),other=homeFav?(g.awayName||g.away):(g.homeName||g.home);
 const chance=homeFav?p:1-p,otherChance=1-chance;
 const e=g.forecastExplanation||{},provisional=e.status==='provisional',quality=e.status==='partially-unverified';
 const badge=provisional?'PROVISIONAL QB / INJURY ESTIMATE':quality?'ATTRIBUTION PARTLY UNVERIFIED':'STATISTICAL ESTIMATE · DATA NOT FULLY VERIFIED';
 return `<div class="one-forecast">
  <div class="one-forecast-label">ONE PREDICTION · ${escapeHTML(badge)}</div>
  <div class="one-forecast-number">${pct(chance)}</div>
  <div class="one-forecast-winner">${escapeHTML(fav)} to win</div>
  <div class="one-forecast-comparison">${escapeHTML(other)} ${pct(otherChance)} <span aria-hidden="true">·</span> Projected score ${g.predAway==null||g.predHome==null?'unavailable':`${escapeHTML(g.away)} ${Math.round(g.predAway)} – ${escapeHTML(g.home)} ${Math.round(g.predHome)}`}</div>
  <div class="matchup-prob-track"><div style="width:${Math.max(0,Math.min(100,100*chance))}%"></div></div>
  <p class="one-forecast-fine">Model estimate, not a guaranteed outcome or bookmaker probability. ${escapeHTML(g.model||'Elo and scoring form')} · Updated ${escapeHTML(store.data?.generatedAt?date(store.data.generatedAt):'date unavailable')}.</p>
 </div>`;
}
function forecastLayerCard(g){
 const e=g.forecastExplanation||{},homeFav=Number(g.homeProbability)>=.5,win=homeFav?g.home:g.away;
 const current=homeFav?Number(g.homeProbability):1-Number(g.homeProbability);
 const rows=Array.isArray(e.layers)?e.layers:[];
 const valid=rows.length&&e.reconciles!==false&&Number.isFinite(e.homeProbability)&&Math.abs(e.homeProbability-Number(g.homeProbability))<.0002;
 const signed=v=>Math.abs(v*100)<.045?'0.0 pp':`${v>0?'+':'−'}${number(Math.abs(v)*100,1)} pp`;
 if(!valid)return `<section class="matchup-panel matchup-wide forecast-attribution" aria-label="Forecast calculation">
 <div class="forecast-attribution-title"><h3>How we got to ${pct(current)}</h3>${tag('LAYER AUDIT PENDING','warn')}</div>
 <p class="instruction">The one-number forecast is available, but a complete reconciled layer breakdown has not been published for this fixture yet. We will not invent percentage-point contributions.</p>
 </section>`;
 const used=rows.filter(x=>x.applied),unused=rows.filter(x=>!x.applied);
 const shown=used.map((x,i)=>{
   const impact=homeFav?x.deltaHome:-x.deltaHome;
   const after=homeFav?x.afterHome:1-x.afterHome;
   const cls=x.kind==='provisional'?'provisional':x.kind==='unverified'?'unverified':x.kind==='validated'?'validated':'core';
   return `<div class="forecast-layer-row ${cls}">
    <div class="forecast-layer-name"><b>${escapeHTML(x.label)}</b><small>${escapeHTML(x.kind==='provisional'?'Provisional model input':x.kind==='validated'?'Historically selected model layer':x.kind==='unverified'?'Unverified contribution':'Baseline model component')}</small></div>
    <div class="forecast-layer-move ${impact<-.00045?'down':impact>.00045?'up':'flat'}">${signed(impact)}</div>
    <div class="forecast-layer-after">${pct(after)}<small>running</small></div>
   </div>`;
 }).join('');
 const notApplied=unused.map(x=>`<div class="forecast-not-applied-item"><strong>${escapeHTML(x.label)}</strong><span>Not applied</span><small>${escapeHTML(x.explanation||'Not weighted in this prediction')}</small></div>`).join('');
 const warnings=(e.warnings||[]).map(w=>`<li>${escapeHTML(w)}</li>`).join('');
 return `<section class="matchup-panel matchup-wide forecast-attribution" aria-label="Reconciled forecast layers">
  <div class="forecast-attribution-title"><div><h3>How we got to ${pct(current)}</h3><p>Every applied layer, measured in percentage points for ${escapeHTML(win)}.</p></div>${tag(e.status==='provisional'?'PROVISIONAL':e.status==='partially-unverified'?'PARTLY UNVERIFIED':'MODEL-DERIVED',e.status==='provisional'||e.status==='partially-unverified'?'warn':'')}</div>
  <div class="forecast-layer-headers"><span>Layer</span><span>Chance moves</span><span>Running win %</span></div>
  <div class="forecast-layer-start"><strong>Starting reference</strong><span>50.0%</span></div>
  ${shown}
  <div class="forecast-layer-final"><strong>${escapeHTML(win)} to win</strong><span>${pct(current)}</span></div>
  <details class="forecast-layer-hidden"><summary>${unused.length} other layers evaluated, but not weighted <span>See evidence</span></summary>
   ${notApplied}
  </details>
  ${warnings?`<details class="forecast-layer-hidden"><summary>Model uncertainty <span>Important limits</span></summary><ul class="forecast-layer-warnings">${warnings}</ul></details>`:''}
  <p class="forecast-layer-note">50/50 is an attribution reference, not an extra model forecast. Only applied layers move the published number. Differences of 0.1 pp may arise from display rounding.</p>
 </section>`;
}
function fullMatchupPage(g){
 const slate=games(), index=slate.findIndex(x=>x.id===g.id);
 const prev=slate[index-1],next=slate[index+1];
 const o=valueFor(g);
 const simulations=Array.isArray(g.simulation)?g.simulation:[];
 const scenarios=Array.isArray(g.scenarios)?g.scenarios:[];
 const sourceDate=store.data?.generatedAt?date(store.data.generatedAt):'No verified refresh timestamp';
 return `<div class="matchup-page">
 <div class="matchup-actions"><button class="btn btn-secondary" data-back-matchups="1">← All fixtures</button><button class="btn btn-secondary" data-share-game="${escapeHTML(g.id)}">Copy matchup link</button><button class="btn btn-primary" data-full-game="${escapeHTML(g.id)}">Open classic analysis ↗</button></div>
 <section class="matchup-hero" aria-label="Game forecast summary">
  <div class="eyebrow">WEEK ${escapeHTML(g.week??'—')} · ${escapeHTML(date(g.kickoff))} · PRE-GAME RESEARCH</div>
  <h2>${escapeHTML(g.awayName||g.away)} <span class="muted">@</span> ${escapeHTML(g.homeName||g.home)}</h2>
  ${forecastHero(g)}
 </section>
 ${forecastLayerCard(g)}
 <details class="matchup-evidence" aria-label="Full supporting evidence">
  <summary>Explore all QB, injury, tactical and matchup data <span>Open detailed analysis</span></summary>
  <div class="matchup-evidence-body">
 ${qbReplacementDetail(g)}
 ${personnelSummary(g)}
 ${intelligencePanel(g)}
 ${fullMatchupReport(g)}
 <div class="matchup-detail-grid">
  <section class="matchup-panel matchup-wide"><h3>Quarterbacks, practice and injuries</h3><p class="matchup-sub">Dated observations, not confirmed starters or inactive lists.</p>${playerDetails(g)}</section>
  <section class="matchup-panel matchup-wide"><h3>Player impact model audit</h3>${impactDetail(g)}</section>
  <section class="matchup-panel matchup-wide"><h3>Pass, rush and pressure matchup</h3>${tacticalDetails(g)}</section>
  <section class="matchup-panel"><h3>Recovery, travel and overtime</h3>${signalDetails(g)}</section>
  <section class="matchup-panel"><h3>Forecast assumptions</h3><div class="stat-pair"><span>Baseline home win</span><strong>${pct(g.baselineHomeProbability??g.homeProbability)}</strong></div><div class="stat-pair"><span>Published home win</span><strong>${pct(g.homeProbability)}</strong></div><div class="stat-pair"><span>Selected adjustment</span><strong>${escapeHTML(g.adjustmentActive?g.overlayType||'validated overlay':'none')}</strong></div><p class="source-meta">The published estimate may include explicitly provisional QB/injury assumptions. The unadjusted baseline is shown above and no provisional player points have yet passed prospective validation.</p></section>
  <section class="matchup-panel matchup-wide"><h3>Winning-margin simulation</h3>${simulations.length?barChart(simulations):'<p class="instruction">Simulation sample unavailable for this fixture.</p>'}<p class="source-meta">Illustrative distribution based on model assumptions; not drive-by-drive simulation or an independently verified market forecast.</p></section>
  <section class="matchup-panel matchup-wide"><h3>Alternative game scripts</h3>${scenarios.length?`<div class="scenarios">${scenarios.map(s=>`<div class="scenario"><strong>${escapeHTML(s.name)}</strong><p>${escapeHTML(s.text)}</p></div>`).join('')}</div>`:'<p class="instruction">No game scripts have been produced for this fixture.</p>'}</section>
  <section class="matchup-panel matchup-wide"><h3>Bookmaker comparison</h3><p>${o?`${escapeHTML(o.book||'Manually entered market')}: ${escapeHTML(o.side)} at ${o.price.toFixed(2)} decimal odds · implied break-even ${pct(o.breakeven)} · model EV ${o.ev>=0?'+':''}${pct(o.ev)}.`:'No bookmaker price entered for this fixture. Prices are manual; no live odds feed is connected.'}</p><button class="btn btn-primary" data-odds="${escapeHTML(g.id)}">${o?'Edit market odds':'Enter decimal odds'}</button></section>
 </div>
 </div>
 </details>
 <div class="matchup-pagination">${prev?`<button class="btn" data-open="${escapeHTML(prev.id)}">← ${escapeHTML(prev.away)} @ ${escapeHTML(prev.home)}</button>`:'<span></span>'}${next?`<button class="btn" data-open="${escapeHTML(next.id)}">${escapeHTML(next.away)} @ ${escapeHTML(next.home)} →</button>`:'<span></span>'}</div>
 </div>`;
}

function openGamePage(id){
 const g=games().find(x=>String(x.id)===String(id));
 if(!g)return;
 store.activeGameId=String(g.id);
 store.tab='matchups';
 const hash='#game='+encodeURIComponent(g.id);
 if(window.location&&window.location.hash!==hash)window.location.hash=hash;
 render();
 if(window.scrollTo)window.scrollTo({top:0,behavior:'smooth'});
}

function syncRoute(){
 const hash=String(window.location?.hash||'');
 if(hash.startsWith('#game=')){
  let id=null;
  try{id=decodeURIComponent(hash.slice(6))}catch{}
  store.activeGameId=id;
  store.tab='matchups';
 }else{
  store.activeGameId=null;
  if(hash.startsWith('#tab=')){
   const tab=hash.slice(5);
   if(TABS[tab])store.tab=tab;
  }
 }
 render();
}

function shareGameLink(id){
 const link=window.location.href.split('#')[0]+'#game='+encodeURIComponent(id);
 if(navigator.clipboard?.writeText)navigator.clipboard.writeText(link).then(()=>toast('Shareable matchup link copied')).catch(()=>window.prompt('Copy matchup URL',link));
 else window.prompt('Copy matchup URL',link);
}

function render(){
 const t=store.tab,d=store.data,selected=store.activeGameId?games().find(g=>String(g.id)===String(store.activeGameId)):null;
 byId('pageTitle').innerHTML=(selected?escapeHTML(selected.away+' @ '+selected.home):escapeHTML(TABS[t][0]))+'<span class="title-dot">.</span>';
 byId('pageIntro').textContent=selected?'Detailed pregame intelligence, evidence and uncertainty for this fixture.':TABS[t][1];
 byId('breadcrumb').textContent=selected?'FULL MATCHUP':TABS[t][0].toUpperCase();
 byId('dataAge').textContent=latest();
 document.querySelectorAll('[data-tab]').forEach(btn=>{btn.classList.toggle('active',btn.dataset.tab===t);btn.setAttribute('aria-current',btn.dataset.tab===t?'page':'false')});
 byId('appContent').innerHTML=!d?'<div class="loading"><span>◈</span><p>Loading prediction dataset...</p></div>'
 :store.activeGameId?(selected?warnBanner()+fullMatchupPage(selected):warnBanner()+empty('Matchup no longer on this slate','The fixture may have already kicked off or moved out of the published forecast window.')+'<div class="matchup-actions"><button class="btn btn-primary" data-back-matchups="1">View upcoming fixtures</button></div>')
 :t==='overview'?overview():t==='matchups'?matchups():t==='tactics'?tacticalRadar():t==='players'?playerRadar():t==='impact'?playerImpactLab():t==='radar'?radar():t==='performance'?perf():t==='accuracy'?signalAccuracyLab():t==='audit'?marketAudit():t==='evidence'?researchEvidenceLab():t==='models'?models():bets();
}

function navigate(tab){
 if(!TABS[tab])return;
 store.tab=tab;store.activeGameId=null;store.query='';
 byId('mobileMenu').setAttribute('aria-expanded','false');
 $('.sidebar').classList.remove('open');
 const hash='#tab='+tab;
 if(window.location&&window.location.hash!==hash)window.location.hash=hash;
 render();
 if(window.scrollTo)window.scrollTo({top:0,behavior:'smooth'});
}
function barChart(sim){const max=Math.max(1,...sim.map(x=>x.share));return `<div class="p-bars">${sim.map(x=>`<div class="p-bar" style="--val:${Math.max(1,Math.round(x.share/max*100))}%"><div class="bar-caption">${number(x.share,1)}%</div><div class="bar" style="height:${Math.max(1,Math.round(x.share/max*100))}%"></div><label>${escapeHTML(x.bucket)}</label></div>`).join('')}</div><div class="p-chart-space"></div>`}
function openGame(id){const g=games().find(x=>x.id===id);if(!g)return;const pHome=g.homeProbability;const o=valueFor(g);
 const html=`<div class="dialog-header"><div><div class="eyebrow" style="font-size:9px">WEEK ${g.week} · ${date(g.kickoff).toUpperCase()}</div><h2 class="modal-title">${escapeHTML(g.awayName)} <span class="muted">@</span> ${escapeHTML(g.homeName)}</h2><div class="modal-sub">${escapeHTML(g.model)} · Pregame research model · ${tag(g.confidence+' favourite confidence',g.confidence==='High'?'lime':'')}</div></div><button class="close" data-close="gameDialog" aria-label="Close matchup">×</button></div><div class="dialog-content"><div class="detail-prob"><div class="detail-stat"><b>${pct(g.awayProbability)}</b><span>${escapeHTML(g.away)} wins</span></div><div class="detail-stat"><b>${Math.round(g.predAway)}–${Math.round(g.predHome)}</b><span>Projected score</span></div><div class="detail-stat"><b>${pct(pHome)}</b><span>${escapeHTML(g.home)} wins</span></div></div><div class="prob-track" style="margin-bottom:21px;height:11px"><div class="prob-fill" style="width:${pHome*100}%"></div></div><div class="form-row"><div class="lab-card"><h3>Expected total</h3><div class="model-readout">${number(g.predTotal,1)}</div><p>Combined projected points</p></div><div class="lab-card"><h3>Home margin</h3><div class="model-readout">${g.predMargin>0?'+':''}${number(g.predMargin,1)}</div><p>Positive values favour home</p></div></div><div class="divider"></div>${fullMatchupReport(g)}${g.shadowEnsemble?`<div class="note-box"><b>Experimental XGBoost challenger (NOT used for picks):</b> ${pct(g.shadowEnsemble.homeProbability)} home win. Team, QB, rest and tactical inputs where available. Baseline primary probability is unchanged. Research validation: ${escapeHTML(store.data?.challengerValidation?.status||"unavailable")}.</div>`:""}<div class="divider"></div><h3 class="mini-title">SIMULATION · WINNING MARGIN DISTRIBUTION</h3>${barChart(g.simulation||[])}<p class="source-meta">2,500 deterministic samples from assumed normal score/margin distributions. This is not a drive-by-drive simulator.</p><div class="divider"></div><h3 class="mini-title">MODEL INTELLIGENCE</h3><div class="form-row"><div class="data-item"><b>${escapeHTML(g.home)} Elo</b><p>${g.eloHome} · scoring form ${g.formHome} PPG · allowed ${g.allowedHome}</p></div><div class="data-item"><b>${escapeHTML(g.away)} Elo</b><p>${g.eloAway} · scoring form ${g.formAway} PPG · allowed ${g.allowedAway}</p></div></div><div class="note-box">Injury reports: ${escapeHTML(g.injuryStatus)}. Weather adjustments: ${escapeHTML(g.weatherStatus)}. No confirmed gameday inactives, automated player props or live tactical data.</div><div class="divider"></div><h3 class="mini-title">QUARTERBACK & INJURY INTELLIGENCE</h3>${playerDetails(g)}<div class="divider"></div><h3 class="mini-title">PLAYER IMPACT VALIDATION</h3>${impactDetail(g)}<div class="divider"></div><h3 class="mini-title">TACTICAL MATCHUP INTELLIGENCE</h3>${tacticalDetails(g)}<div class="model-adjustment"><strong>TACTICAL ADJUSTMENT: ${g.overlayType==='tactical'?'ENABLED':'OFF'}</strong><p>Only a model passing the completed-season selection rule may influence win percentages. Tactical probability difference: ${(100*(g.tacticalProbabilityDelta||0))>=0?'+':''}${number(100*(g.tacticalProbabilityDelta||0),2)} percentage points. Never inferred from descriptive mismatches alone.</p></div><div class="divider"></div><h3 class="mini-title">SITUATIONAL MATCHUP INTELLIGENCE</h3><div class="model-adjustment"><strong>${g.overlayType==='situational'?'SITUATIONAL ADJUSTMENT ENABLED':'SITUATIONAL ADJUSTMENT OFF'}</strong><p>Baseline home win: ${pct(g.baselineHomeProbability??g.homeProbability)} · Final model: ${pct(g.homeProbability)} · Difference: ${(100*(g.situationalProbabilityDelta||0))>=0?'+':''}${number(100*(g.situationalProbabilityDelta||0),2)} percentage points. ${g.overlayType==='situational'?'Selected from prior completed-season validation. Score forecast and histogram remain baseline assumptions.':'No situational probability effect is applied.'}</p></div>${signalDetails(g)}<div class="divider"></div><h3 class="mini-title">ALTERNATIVE GAME SCRIPTS</h3><div class="scenarios">${(g.scenarios||[]).map(x=>`<div class="scenario"><strong>${escapeHTML(x.name)}</strong><p>${escapeHTML(x.text)}</p></div>`).join('')}</div><div class="divider"></div><h3 class="mini-title">BOOKMAKER CHECK</h3><p class="instruction">${o?`Your ${escapeHTML(o.book)} price of ${o.price.toFixed(2)} for ${escapeHTML(o.side)} implies ${pct(o.breakeven)} break-even; our model implies ${pct(o.p)} (${o.ev>=0?'+':''}${pct(o.ev)} raw expected return).`:'No bookmaker odds are stored for this fixture.'}</p><div class="inline-cta"><button class="btn btn-primary" data-odds="${escapeHTML(g.id)}">${o?'Edit':'Enter'} bookmaker odds →</button><button class="btn btn-secondary" data-close="gameDialog">Close</button></div></div>`;
 byId('dialogContent').innerHTML=html;byId('gameDialog').showModal();}
function oddsDialog(gameId){const g=games().find(x=>x.id===gameId);if(!g)return;const o=store.odds[gameId]||{side:g.home,price:'',book:''};byId('oddsContent').innerHTML=`<div class="dialog-header"><div><div class="eyebrow" style="font-size:9px">MANUAL MARKET INPUT</div><h2 class="modal-title">Enter bookmaker odds</h2><div class="modal-sub">${escapeHTML(g.away)} @ ${escapeHTML(g.home)}</div></div><button type="button" class="close" data-close="oddsDialog">×</button></div><div class="dialog-content"><label class="field-label" for="marketSide">Selection (moneyline)</label><select id="marketSide" class="select" style="margin-bottom:15px"><option value="${escapeHTML(g.home)}" ${o.side===g.home?'selected':''}>${escapeHTML(g.home)} to win</option><option value="${escapeHTML(g.away)}" ${o.side===g.away?'selected':''}>${escapeHTML(g.away)} to win</option></select><div class="form-row"><label><span class="field-label">Decimal odds</span><input class="input" id="marketPrice" required type="number" min="1.01" max="1000" step="0.01" value="${escapeHTML(o.price)}" placeholder="2.10"></label><label><span class="field-label">Bookmaker</span><input class="input" id="marketBook" maxlength="50" value="${escapeHTML(o.book||'')}" placeholder="Sky Bet"></label></div><label><span class="field-label">Optional home-team handicap (e.g. -7.5 if home gives 7.5)</span><input class="input" id="marketHomeHandicap" type="number" min="-40" max="40" step="0.5" value="${escapeHTML(o.homeHandicap??'')}" placeholder="-7.5"></label><p class="instruction" style="margin-top:10px">The optional spread is for Favourite Ambush detection ONLY; spread EV and automatic market data are not supported. Negative = home favourite. Positive = away favourite.</p><div class="inline-cta"><button class="btn btn-primary" type="submit" value="save">Save odds</button><button class="btn" type="button" data-clear-odds="${escapeHTML(gameId)}">Clear</button><button class="btn" type="button" data-close="oddsDialog">Cancel</button></div></div>`;byId('oddsForm').dataset.gameId=gameId;byId('oddsDialog').showModal()}
function downloadJson(filename,obj){const blob=new Blob([JSON.stringify(obj,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function exportLedger(){downloadJson('nfl-lab-personal-ledger.json',{exportedAt:new Date().toISOString(),format:'nfl-lab-ledger-v1',bets:store.bets,odds:store.odds});toast('Local ledger exported')}
async function refresh(){if(store.busy)return;if(window.NFL_LAB_EMBEDDED_DATA){store.data=window.NFL_LAB_EMBEDDED_DATA;render();return;}store.busy=true;byId('dataAge').textContent='CHECKING DATA';try{try{const ar=await fetch('data/audit-reference.json?ts='+Date.now(),{cache:'no-store'});if(ar.ok)store.auditReference=await ar.json()}catch{}try{const er=await fetch('data/situational-research.json?ts='+Date.now(),{cache:'no-store'});if(er.ok)store.researchEvidence=await er.json()}catch{}const res=await fetch('data/dashboard.json?ts='+Date.now(),{cache:'no-store'});if(!res.ok)throw Error('HTTP '+res.status);const d=await res.json();if(!Array.isArray(d.nextGames))throw Error('Unsupported dataset');store.data=d;render();toast(d.generatedAt?'Forecast data loaded':'Waiting for the first published NFL data run')}catch(e){store.data={dataStatus:'unavailable',nextGames:[],recentResults:[],performance:{count:0}};render();toast('Could not load dashboard data. Use a local web server or GitHub Pages.')}finally{store.busy=false}}
function handleClick(e){const btn=e.target.closest('[data-model-filter],[data-tab],[data-nav],[data-open],[data-full-game],[data-back-matchups],[data-share-game],[data-odds],[data-close],[data-clear-odds],[data-deletebet],[data-export],[data-import],[data-export-audit],[data-export-evidence]');if(!btn)return;
 if(btn.dataset.modelFilter){store.modelFilter=btn.dataset.modelFilter;render();return;}
 if(btn.dataset.tab)navigate(btn.dataset.tab);
 if(btn.dataset.nav)navigate(btn.dataset.nav);
 if(btn.dataset.open)openGamePage(btn.dataset.open);
  if(btn.dataset.fullGame)openGame(btn.dataset.fullGame);
  if(btn.dataset.backMatchups)navigate('matchups');
  if(btn.dataset.shareGame)shareGameLink(btn.dataset.shareGame);
 if(btn.dataset.odds){byId('gameDialog').close();oddsDialog(btn.dataset.odds)}
 if(btn.dataset.close)byId(btn.dataset.close).close();
 if(btn.dataset.clearOdds){delete store.odds[btn.dataset.clearOdds];save('odds',store.odds);byId('oddsDialog').close();render();toast('Bookmaker price cleared')}
 if(btn.dataset.deletebet){store.bets=store.bets.filter(b=>b.id!==btn.dataset.deletebet);save('bets',store.bets);render();toast('Bet removed')}
 if(btn.dataset.export)exportLedger();
 if(btn.dataset.exportAudit){const audit=activeAudit().data;if(audit)downloadJson('nfl-lab-historical-audit.json',audit)}
 if(btn.dataset.exportEvidence&&store.researchEvidence)downloadJson('nfl-lab-situational-research.json',store.researchEvidence);
 if(btn.dataset.import){const inp=byId('importFile');if(inp)inp.click()}
}
function handleChange(e){if(e.target.matches('[data-result]')){const b=store.bets.find(x=>x.id===e.target.dataset.result);if(!b)return;b.result=e.target.value;save('bets',store.bets);render();toast('Bet result updated')}}
function handleSubmit(e){if(e.target.id==='oddsForm'){e.preventDefault();const id=e.target.dataset.gameId;const price=Number(byId('marketPrice').value),side=byId('marketSide').value,book=byId('marketBook').value.trim();if(!Number.isFinite(price)||price<=1||price>1000){toast('Enter valid decimal odds above 1.00');return}const rawHandicap=byId('marketHomeHandicap').value.trim();const homeHandicap=rawHandicap===''?null:Number(rawHandicap);
 if(rawHandicap!==''&&(!Number.isFinite(homeHandicap)||Math.abs(homeHandicap)>40)){toast('Home handicap must be between -40 and +40');return}
 store.odds[id]={side,price,book,homeHandicap,enteredAt:new Date().toISOString()};save('odds',store.odds);byId('oddsDialog').close();render();toast('Bookmaker odds saved locally')}
 if(e.target.id==='betForm'){e.preventDefault();const gameId=byId('betGame').value;const g=games().find(x=>x.id===gameId);const odds=Number(byId('betOdds').value),stake=Number(byId('betStake').value);if(!(odds>1&&odds<=1000&&stake>.0&&stake<=100000)){toast('Check odds and stake');return}store.bets.unshift({id:String(Date.now())+'-'+Math.random().toString(36).slice(2,7),game:g?`${g.away} @ ${g.home}`:'Manual fixture',gameId,pick:byId('betPick').value.trim(),book:byId('betBook').value.trim(),odds,stake,result:'P',enteredAt:new Date().toISOString()});save('bets',store.bets);render();toast('Bet saved to your personal ledger')}}
async function importFile(e){const file=e.target.files?.[0];if(!file)return;try{const o=JSON.parse(await file.text());if(o.format!=='nfl-lab-ledger-v1'||!Array.isArray(o.bets)||!o.odds||typeof o.odds!=='object')throw Error('Invalid format');if(o.bets.length>5000)throw Error('Too many records');store.bets=o.bets.filter(b=>b&&typeof b.pick==='string'&&typeof b.id==='string'&&Number.isFinite(Number(b.stake))&&Number.isFinite(Number(b.odds)));store.odds=Object.fromEntries(Object.entries(o.odds).filter(([k,v])=>k.length<100&&v&&Number(v.price)>1&&Number(v.price)<=1000));save('bets',store.bets);save('odds',store.odds);render();toast('Ledger imported')}catch(err){toast('Import failed: invalid backup file')}e.target.value=''}
function start(){byId('nav').addEventListener('click',handleClick);byId('appContent').addEventListener('click',handleClick);byId('appContent').addEventListener('change',handleChange);byId('appContent').addEventListener('submit',handleSubmit);byId('gameDialog').addEventListener('click',handleClick);byId('oddsDialog').addEventListener('click',handleClick);byId('oddsForm').addEventListener('submit',handleSubmit);
 byId('appContent').addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.matches('[data-open]')){e.preventDefault();openGame(e.target.dataset.open)}});
 byId('appContent').addEventListener('input',e=>{if(e.target.id==='searchGames'){
   store.query=e.target.value;
   const match=games().filter(x=>(x.homeName+' '+x.awayName+' '+x.home+' '+x.away).toLowerCase().includes(store.query.toLowerCase()));
   const target=byId('gameRows');if(target)target.innerHTML=match.length?match.map(gameRow).join(''):empty('No matchups found','Try another team name.');
 }});
 byId('appContent').addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.id==='searchGames'){store.query=e.target.value;render();byId('searchGames')?.focus()}});
 byId('refreshBtn').addEventListener('click',refresh);byId('exportBtn').addEventListener('click',exportLedger);
 byId('mobileMenu').addEventListener('click',()=>{const open=$('.sidebar').classList.toggle('open');byId('mobileMenu').setAttribute('aria-expanded',String(open))});
 byId('appContent').addEventListener('change',e=>{if(e.target.id==='importFile')importFile(e)});
 window.addEventListener('keydown',e=>{if(e.key==='Escape')$('.sidebar').classList.remove('open')});
  window.addEventListener('hashchange',syncRoute);
 syncRoute();refresh();}
window.addEventListener('DOMContentLoaded',start);
})();
