/* Shootout Heat panel renders the current week ranked by heat, safely. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ctx={window:{}};vm.createContext(ctx);
vm.runInContext(fs.readFileSync('assets/shootout-radar.js','utf8'),ctx);
vm.runInContext(fs.readFileSync('assets/prediction-factors.js','utf8'),ctx);
const SH=ctx.window.NFLShootout,PF=ctx.window.NFLPredictionFactors;
const html=fs.readFileSync('index.html','utf8'),app=fs.readFileSync('assets/app.js','utf8');
assert.ok(html.indexOf('shootout-radar.js')>-1&&html.indexOf('shootout-radar.js')<html.indexOf('prediction-factors.js'));
assert.equal((app.match(/NFLShootout\.panel\(/g)||[]).length,2,'command centre and full matchup board');
const s=(rating,rank,extra={})=>({rating,tier:rating>=80?'Shootout':rating>=60?'High':rating>=40?'Average':'Low',shootoutTotal:36+rating/5,
  projectedTotal:45,components:{projectedTotal:45,passingMatchup:1,explosivePlays:0,weather:-1},weatherReasons:['wind 16 mph'],weekRank:rank,weekGames:3,...extra});
const g=(id,week,kick,sh)=>({id,season:2026,week,home:'H<'+id,away:'A'+id,kickoff:kick,shootout:sh});
const data={nextGames:[g('b',12,'2026-11-22T18:00:00Z',s(40,2)),g('a',12,'2026-11-22T21:00:00Z',s(90,1)),
  g('c',13,'2026-11-26T18:00:00Z',s(99,1)),{id:'x',week:12}],shootoutRecord:{gradedWeeks:2,gradedGames:28,top3HitRate:.5,meanRankCorrelation:.31,meanProjectedTotalRankCorrelation:.22}};
const week=SH.currentWeek(data.nextGames);
assert.equal(week.map(x=>x.id).join(),'a,b','current week only, ranked');
const out=SH.panel(data);
assert.ok(out.indexOf('Aa @')<out.indexOf('Ab @'));
assert.ok(!out.includes('H<a')&&out.includes('H&lt;a'),'escaped');
assert.match(out,/50% of our top-3/);assert.match(out,/beats the plain projected total/);assert.match(out,/Small sample/);
assert.match(SH.panel(data,{limit:1}),/All 2 games/);
assert.match(SH.panel({nextGames:[]}),/after the next data refresh/);
assert.match(SH.panel({nextGames:data.nextGames.slice(0,2),shootoutRecord:{gradedWeeks:0,pendingGames:5}}),/Track record starts/);
const f=PF.factors(data.nextGames[1]).find(x=>x.key==='shootout');
assert.ok(f&&f.status.label==='CONTEXT ONLY'&&/Heat 90\/100/.test(f.span));
assert.match(PF.strip(data.nextGames[1]),/🔥 90 Shootout/);
assert.equal(PF.factors({id:'n',home:'A',away:'B'}).some(x=>x.key==='shootout'),false);
console.log('Shootout Heat panel validated.');
