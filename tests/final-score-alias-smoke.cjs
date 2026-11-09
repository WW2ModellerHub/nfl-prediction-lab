/* Rams LA (nflverse) vs LAR (ESPN) and schedule final fallback. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const app=fs.readFileSync('assets/app.js','utf8');
const marker="window.addEventListener('DOMContentLoaded',start);";
assert(app.includes(marker));
const script=app.replace(marker,
  "window.__SCORE_TEST__={data:v=>store.data=v,get:id=>store.liveScores[id],"+
  "live:scoreFromESPN,groups:splitRecentlyStarted,select:effectiveGameState,refresh:refreshLiveScores};"+marker);
const elements={};
const element=id=>elements[id]||(elements[id]={id,innerHTML:'',textContent:'',dataset:{},setAttribute(){},classList:{toggle(){}},querySelector(){return null}});
const document={getElementById:element,querySelectorAll(){return []},querySelector(){return element('nav')},hidden:false};
const window={addEventListener(){},location:{hash:'',href:'https://example.org/'},scrollTo(){},NFLGameLiveModel:require('../assets/live-win-model.js')};
const kickoff='2026-11-08T18:00:00+00:00';
const game={id:'2026_09_LA_WAS',season:2026,week:9,home:'WAS',away:'LA',
 kickoff,homeProbability:.44084,awayProbability:.55916,archivedPregame:true,
 finalScoreFromSchedule:{home:13,away:20,source:'nflverse schedules — not a live score feed'}};
const ESPN={events:[{id:'123456789',date:kickoff,
 status:{type:{state:'post'},period:4,displayClock:'0:00'},
 competitions:[{competitors:[
 {id:'ws',homeAway:'home',team:{abbreviation:'WSH'},score:'13'},
 {id:'rams',homeAway:'away',team:{abbreviation:'LAR'},score:'20'}
 ]}]}]};
let requests=0,shouldFail=false;
const fetch=async url=>{requests++;if(shouldFail)throw new Error('feed unavailable');return {ok:true,json:async()=>ESPN}};
vm.runInNewContext(script,{window,document,localStorage:{getItem(){return null},setItem(){}},
 fetch,console,Date,Math,JSON,Intl,URL,navigator:{},setTimeout,clearTimeout},{filename:'app.js',timeout:5000});
const t=window.__SCORE_TEST__;
const data={recentKickoffs:[game],nextGames:[],predictionRecord:{latestResults:[{
 gameId:game.id,home:'WAS',away:'LA',homeScore:13,awayScore:20,latestCorrect:true}]}};
t.data(data);
assert.equal(t.live(game).main,'FINAL','The recorded result must appear even before the live feed responds');
assert.equal(t.live(game).detail,'LA 20 – WAS 13');
assert.equal(t.groups([game]).final.length,1,'Rams must be filed under final scores');
const waiting={...game,finalScoreFromSchedule:null};
t.data({...data,predictionRecord:{latestResults:[]}});
assert.equal(t.live(waiting).main,'SCORE PENDING','Missing scores must not create a fake final');
(async()=>{
 await t.refresh();
 const result=t.get(game.id);
 assert.equal(requests,1);
 assert(result,'ESPN result must not be discarded after LA/LAR mapping');
 assert.equal(result.home,'WAS');
 assert.equal(result.away,'LA');
 assert.equal(result.state,'post');
 assert.equal(result.homeScore,13);
 assert.equal(result.awayScore,20);
 assert.equal(t.live(waiting).main,'FINAL');
 assert.equal(t.groups([game]).final.length,1);
 shouldFail=true;
 // Failed refresh should not erase previously verified results.
 await t.refresh();
 assert.equal(t.get(game.id).state,'post');
 t.data(data);
 assert.equal(t.live(game).detail,'LA 20 – WAS 13');
 const rz=fs.readFileSync('assets/redzone.js','utf8');
 assert(rz.includes('Core.norm(x.away)===Core.norm(game.away)'), 'Red Zone must reconcile aliases too');
 console.log('Rams LA/LAR, WAS/WSH, frozen final result and live-feed fallback passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
