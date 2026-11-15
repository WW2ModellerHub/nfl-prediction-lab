/* Every published prediction shows the full factor set: venue/home-away, Elo,
   form, QB, injuries, rest, tactical EPA and weather. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ctx={window:{}};vm.createContext(ctx);
vm.runInContext(fs.readFileSync('assets/prediction-factors.js','utf8'),ctx);
const PF=ctx.window.NFLPredictionFactors;
const html=fs.readFileSync('index.html','utf8'),app=fs.readFileSync('assets/app.js','utf8');
assert.ok(html.indexOf('assets/prediction-factors.js')>-1&&html.indexOf('assets/prediction-factors.js')<html.indexOf('assets/app.js'));
assert.match(html,/assets\/prediction-factors\.css/);
assert.equal((app.match(/NFLPredictionFactors\.panel\(/g)||[]).length,3,'matchup page, archived page and dialog');
assert.equal((app.match(/NFLPredictionFactors\.strip\(/g)||[]).length,2,'upcoming and started rows');
const KEYS=['venue','strength','form','qb','injuries','rest','tactical','weather'];
const d=JSON.parse(fs.readFileSync('data/dashboard.json','utf8'));
for(const g of d.nextGames){
  const f=PF.factors(g);
  assert.equal(f.map(x=>x.key).join(),KEYS.join(),g.id);
  const panel=PF.panel(g);
  for(const label of ['Venue','Elo','Scoring form','Quarterback','Injuries','Rest','EPA','Weather'])assert.ok(panel.includes(label),g.id+' '+label);
  assert.ok(!/undefined|NaN/.test(panel),g.id+' renders no undefined/NaN');
  assert.match(PF.strip(g),/QB /);
}
const base={id:'x',home:'NYJ',away:'BUF',stadium:'MetLife <b>',roof:'outdoors',eloHome:1500,eloAway:1600,
 qbIntelligence:{home:{qb:'Geno Smith',basis:'depth_chart_projection',sample:{epaPerDropback:.04}},away:{qb:'Josh Allen',confirmedStarter:true,starterChangeWatch:true,sample:{epaPerDropback:.2}}},
 weather:{status:'forecast',temperatureC:-8,windMph:22,precipitationChancePct:70},
 forecastExplanation:{layers:[{key:'elo',applied:true,deltaHome:-.1},{key:'qb-statistical',applied:true,deltaHome:-.02},{key:'weather',applied:false}]}};
const byKey=g=>Object.fromEntries(PF.factors(g).map(x=>[x.key,x]));
let f=byKey(base);
assert.equal(f.venue.edge,'home');assert.equal(f.strength.edge,'away');assert.equal(f.qb.edge,'away');
assert.match(f.qb.away,/confirmed/);assert.match(f.qb.home,/projected/);assert.ok(f.qb.warn);
assert.equal(f.qb.status.state,'applied');assert.equal(f.weather.status.state,'context');
assert.match(f.weather.note,/strong wind/);assert.match(f.weather.note,/severe cold/);assert.match(f.weather.note,/rain\/snow/);
assert.ok(PF.panel(base).includes('MetLife &lt;b&gt;'),'stadium name is escaped');
f=byKey({...base,neutral:true});assert.equal(f.venue.edge,'even');assert.match(f.venue.home,/Neutral/);
f=byKey({...base,weather:{status:'indoor',roof:'dome'}});assert.match(f.weather.span,/Indoors/);
f=byKey({id:'y',home:'A',away:'B'});assert.match(f.qb.away,/unconfirmed/);assert.equal(f.weather.span,'Weather not loaded');
// Started games: no snapshot → nothing rendered; snapshot → frozen panel.
assert.equal(PF.panel({id:'s',home:'NYJ',away:'BUF',archivedPregame:true}),'');
assert.match(PF.panel({id:'s',home:'NYJ',away:'BUF',archivedPregame:true,pregame:{...base,capturedAt:'2026-11-15T16:00:00Z'}},{archived:true}),/FROZEN/);
console.log(`Prediction factors validated for ${d.nextGames.length} published fixtures.`);
