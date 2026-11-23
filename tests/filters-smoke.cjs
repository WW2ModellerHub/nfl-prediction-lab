/* Matchup board filters: week, toggles, sort, clear, and the rebuilt fixture card. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'..','assets','app.js'),'utf8');
const marker="window.addEventListener('DOMContentLoaded',start);";
assert(source.includes(marker));
const code=source.replace(marker,'window.__T__={store,filteredUpcoming,boardHTML,filterBar,gameRow,FILTER_DEFAULTS};'+marker);
const el=()=>({innerHTML:'',dataset:{},classList:{add(){},remove(){},toggle(){}}});
const document={getElementById:el,querySelectorAll:()=>[],querySelector:()=>null};
const window={location:{hash:'',href:'https://example.org/'},scrollTo(){},addEventListener(){}};
const saved={};const localStorage={getItem:k=>saved[k]??null,setItem:(k,v)=>{saved[k]=v}};
vm.runInNewContext(code,{window,document,localStorage,console,Date,Math,JSON,URL,Intl,navigator:{},setTimeout,clearTimeout});
const T=window.__T__;
const g=(id,week,p,extra={})=>({id,week,season:2026,home:'H'+id,away:'A'+id,homeName:'Home '+id,awayName:'Away '+id,kickoff:`2026-11-${20+week}T18:00:00Z`,
  homeProbability:p,awayProbability:1-p,predHome:24,predAway:21,forecastQuality:{level:'review'},...extra});
T.store.data={nextGames:[
  g('a',12,.85,{shootout:{rating:80,tier:'Shootout'},forecastQuality:{level:'checked'}}),
  g('b',12,.55,{shootout:{rating:30,tier:'Low'},weather:{status:'forecast',windMph:20}}),
  g('c',13,.52,{shootout:{rating:65,tier:'High'},qbIntelligence:{home:{starterChangeWatch:true}}}),
  g('d',13,.70,{forecastQuality:{level:'hold'}})]};
const ids=()=>T.filteredUpcoming().map(x=>x.id).join();
assert.equal(ids(),'a,b,c,d');
T.store.filters.week='12';assert.equal(ids(),'a,b');
T.store.filters.week='all';T.store.filters.heat=true;assert.equal(ids(),'a,c');
T.store.filters.heat=false;T.store.filters.close=true;assert.equal(ids(),'b,c');
T.store.filters.close=false;T.store.filters.checked=true;assert.equal(ids(),'a');
T.store.filters.checked=false;T.store.filters.weather=true;assert.equal(ids(),'b');
T.store.filters.weather=false;T.store.filters.qb=true;assert.equal(ids(),'c,d','starter change watch and hold');
T.store.filters.qb=false;
T.store.filters.sort='heat';assert.equal(ids(),'a,c,b,d');
T.store.filters.sort='close';assert.equal(ids(),'c,b,d,a');
T.store.filters.sort='fav';assert.equal(ids(),'a,d,b,c');
assert.match(T.filterBar(),/Clear filters/);
T.store.query='Away c';assert.equal(ids(),'c');
T.store.query='zzz';assert.match(T.boardHTML(),/No matchups match these filters/);
T.store.query='';Object.assign(T.store.filters,T.FILTER_DEFAULTS);
assert.doesNotMatch(T.filterBar(),/Clear filters/);
assert.match(T.boardHTML(),/UPCOMING FIXTURES · 4/);
const card=T.gameRow(T.store.data.nextGames[0]);
assert.match(card,/class="game-row fx-row"/);assert.match(card,/fx-tags/);assert.match(card,/Sources checked/);
assert.match(T.gameRow(T.store.data.nextGames[3]),/Evidence hold/);
console.log('Matchup filters and fixture card validated.');
