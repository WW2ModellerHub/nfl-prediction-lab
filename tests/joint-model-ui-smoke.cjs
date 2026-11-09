const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const s=fs.readFileSync('assets/app.js','utf8'),m="window.addEventListener('DOMContentLoaded',start);";
assert(s.includes(m));
const code=s.replace(m,"window.__UI__={set:d=>store.data=d,open:openGamePage,click:handleClick,mode:()=>store.forecastMode};"+m);
const el=id=>elements[id]||(elements[id]={innerHTML:'',textContent:'',dataset:{},setAttribute(){},classList:{toggle(){},add(){},remove(){}}});
const elements={},doc={getElementById:el,querySelectorAll:()=>[],querySelector:()=>el('sidebar')};
const win={location:{hash:'',href:'https://example.org/'},addEventListener(){},scrollTo(){}};
vm.runInNewContext(code,{window:win,document:doc,localStorage:{getItem(){return null},setItem(){}},Date,Math,JSON,Intl,URL,console,navigator:{},setTimeout,clearTimeout},{timeout:5000});
const game={id:'x',home:'WAS',away:'LA',week:11,kickoff:'2026-11-23T18:00:00Z',homeProbability:.55,
 awayProbability:.45,predAway:20,predHome:23,simulation:[],scenarios:[],situation:{home:{},away:{},signals:[]},
 qbIntelligence:{},injuryIntelligence:{},tactical:{},
 forecastExplanation:{status:'model-derived',homeProbability:.55,reconciles:true,layers:[{
 key:'core',label:'Elo/form',deltaHome:.05,afterHome:.55,kind:'core',applied:true}]},
 shadowEnsemble:{homeProbability:.64,baselineHomeProbability:.55,productionWeight:0,
 researchOnly:true,reconciles:true,impactPP:9,layers:[
 {key:'calibration',label:'Model calibration',deltaHomePP:1.8,observed:true},
 {key:'rest',label:'Rest, travel & overtime',deltaHomePP:2.2,observed:true},
 {key:'qb',label:'Quarterback',deltaHomePP:5,observed:true}],
 missingEvidence:['Archived pregame weather']}};
const t=win.__UI__;t.set({nextGames:[game],generatedAt:'2026-11-10T00:00:00Z'});t.open('x');
let h=el('appContent').innerHTML;
assert(h.includes('one-forecast-number">55.0%'));assert(h.includes('Combined model'));
assert.equal(t.mode(),'published');
t.click({target:{closest:()=>({dataset:{forecastMode:'research'}})}});
h=el('appContent').innerHTML;
assert(h.includes('one-forecast-number">64.0%'));
assert(h.includes('EXPERIMENTAL · NOT A PUBLISHED PICK'));
assert(h.includes('Rest, travel &amp; overtime'));
assert(h.includes('+2.2 pp'));
assert(!h.includes('8 other layers evaluated'));
assert.equal((h.match(/class="one-forecast-number"/g)||[]).length,1);
assert.equal(game.homeProbability,.55);
t.click({target:{closest:()=>({dataset:{forecastMode:'published'}})}});
assert(el('appContent').innerHTML.includes('one-forecast-number">55.0%'));
console.log('Single-number forecast selector and research attribution passed.');
