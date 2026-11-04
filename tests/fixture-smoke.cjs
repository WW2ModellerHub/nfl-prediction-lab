/* Regression test: every rendered fixture must open its matchup dossier. */
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'..','assets','app.js'),'utf8');
const marker="window.addEventListener('DOMContentLoaded',start);";
assert(source.includes(marker),'Dashboard startup signature changed');
const code=source.replace(marker,'window.__SMOKE__={setData:d=>{store.data=d},handleClick,openGame};'+marker);
const box={innerHTML:''};
const dialog={opened:false,showModal(){this.opened=true},close(){this.opened=false}};
const document={getElementById:id=>id==='dialogContent'?box:id==='gameDialog'?dialog:{}};
const window={addEventListener(){}};
vm.runInNewContext(code,{window,document,console,Date,Math,JSON,URL,Intl},{filename:'app.js',timeout:3000});
const game={id:'test_fixture',week:9,kickoff:'2026-11-06T01:15:00Z',
 away:'JAX',home:'BAL',awayName:'Jacksonville Jaguars',homeName:'Baltimore Ravens',
 model:'Elo and form',confidence:'Low',homeProbability:.47,awayProbability:.53,
 predHome:22,predAway:24,predTotal:46,predMargin:-2,formHome:22,formAway:24,
 allowedHome:24,allowedAway:20,eloHome:1500,eloAway:1540,
 injuryStatus:'Unknown',weatherStatus:'Unavailable',simulation:[],scenarios:[],
 situation:{signals:[],home:{fullRestDays:4,previous:{overtime:false}},away:{fullRestDays:5,previous:{overtime:true}}},
 tactical:{status:'unavailable',reason:'Pending feed',advantages:[]},
 qbIntelligence:{status:'observed',home:{qb:'Quarterback H',label:'Unconfirmed'},away:{qb:'Quarterback A',label:'Unconfirmed'}},
 injuryIntelligence:{status:'unavailable',home:[],away:[]}};
window.__SMOKE__.setData({nextGames:[game]});
window.__SMOKE__.handleClick({target:{closest:()=>({dataset:{open:game.id}})}});
assert(dialog.opened,'Fixture click failed to open modal');
assert.match(box.innerHTML,/FULL MATCHUP DOSSIER/i,'Dossier did not render');
assert.match(box.innerHTML,/QUARTERBACK/i,'Player section was lost');
dialog.opened=false;box.innerHTML='';
window.__SMOKE__.setData({nextGames:[{...game,situation:null,tactical:null,qbIntelligence:null,injuryIntelligence:null}]});
window.__SMOKE__.openGame(game.id);
assert(dialog.opened,'Fixture with missing feeds failed to open');
assert.match(box.innerHTML,/FULL MATCHUP DOSSIER/i);
console.log('PASS: fixture opens, complete dossier appears, missing feeds are safe');