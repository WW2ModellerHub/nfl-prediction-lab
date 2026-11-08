/* Started games must remain navigable without becoming invented in-game forecasts. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const s=fs.readFileSync('assets/app.js','utf8');
const marker="window.addEventListener('DOMContentLoaded',start);";
assert(s.includes(marker));
const code=s.replace(marker,"window.__STARTED_TEST__={setData:d=>store.data=d,setLive:d=>store.liveScores=d,live:scoreFromESPN,archive:recentKickoffRow,matchups,overview,openGamePage,render};"+marker);
const elements={};
const el=id=>elements[id]||(elements[id]={innerHTML:'',textContent:'',dataset:{},setAttribute(){},classList:{add(){},remove(){},toggle(){}},close(){},showModal(){}});
const document={getElementById:el,querySelectorAll:()=>[],querySelector:()=>el('sidebar'),hidden:false};
const window={location:{hash:'',href:'https://example.com/index.html'},addEventListener(){},scrollTo(){}};
const localStorage={getItem(){return null},setItem(){}};
vm.runInNewContext(code,{window,document,localStorage,console,Date,Math,JSON,Intl,URL,navigator:{},setTimeout,clearTimeout},{filename:'app.js',timeout:5000});
const t=window.__STARTED_TEST__;
t.setData({generatedAt:'2026-11-08T21:15:00Z',nextGames:[],
  recentKickoffs:[{id:'2026_09_DAL_NYG',home:'NYG',away:'DAL',kickoff:'2026-11-08T18:00:00Z',
   archivedPregame:true,homeProbability:.44,awayProbability:.56,originalHomeProbability:.48,
   lastPregameRecordedAt:'2026-11-08T17:15:00Z',originalRecordedAt:'2026-11-04T15:00:00Z',week:9,model:'historical model'}],
  predictionRecord:{completed:{games:0,latest:{},original:{}}},performance:{count:0},dataStatus:'ok'});
const html=t.overview();
assert(html.includes('Today’s live & recently started games'));
assert(html.includes('DAL @ NYG'));
assert(html.includes('LAST SAVED PRE-KICKOFF PICK'));
assert(html.includes('NOT')===false || html.includes('pregame')); // show frozen labels
assert(t.matchups().includes('DAL @ NYG'));
t.openGamePage('2026_09_DAL_NYG');
assert(el('appContent').innerHTML.includes('FROZEN PRE-KICKOFF FORECAST'));
assert(el('appContent').innerHTML.includes('NOT A LIVE PROBABILITY'));
t.setLive({'2026_09_DAL_NYG':{status:'in',period:3,clock:'6:10',away:'DAL',home:'NYG',awayScore:17,homeScore:10}});
assert.equal(t.live({id:'2026_09_DAL_NYG'}).main,'LIVE Q3 6:10');
assert.equal(t.live({id:'2026_09_DAL_NYG'}).detail,'DAL 17 – NYG 10');
console.log('Started fixtures, frozen pregame archive and external live status smoke tests passed.');
