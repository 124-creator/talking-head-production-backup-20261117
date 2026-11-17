'use strict';
const CASES={a:{offset:26.4,dur:4,name:'人物关键词底板'},b:{offset:17.3,dur:7.2,name:'递进语义标签'},c:{offset:47,dur:8.5,name:'旧图让位新图落位'}};
const TYPE=document.body.dataset.case,CFG=CASES[TYPE],$=id=>document.getElementById(id);
const header=title=>`<div id="title" class="heavy">${title}</div><div id="brand">SEEDREAM 5.5 · V2 TEST</div><div id="rule"></div>`;
if(TYPE==='a')document.body.insertAdjacentHTML('beforeend','<img id="presenter" src="../production_v1/assets/speech_frames/000792.png"><div id="shade"></div><div id="aLead" class="heavy">更重要的是</div><div id="aPlate"><div id="aWord">改图能力强</div></div>');
if(TYPE==='b')document.body.insertAdjacentHTML('beforeend',header('真实感，让细节说话')+`<div id="photoStage">${['M03','M04','M05','M06'].map(id=>`<img class="evidence" id="${id}" src="../production_v1/assets/${id}.png">`).join('')}</div><section id="facts">${[['纹理清楚','皮肤近景'],['光影自然','明暗过渡'],['少塑料感','样图观感']].map(([text,note],i)=>`<div class="fact" id="fact${i}"><div class="number">0${i+1}</div><div class="factDetail">${note}</div><div class="factTitle heavy" id="factText${i}">${text}</div></div>`).join('')}</section>`);
if(TYPE==='c')document.body.insertAdjacentHTML('beforeend',header('三视图 · 头身比例')+'<div id="comparisonNote">所供样图 · 服装、姿态不同 · 非定量测量</div><div id="oldCard" class="modelCard"><img id="oldFull" src="../production_v1/assets/M08.png"><img id="oldFront" src="assets/M08_front.png"><div id="oldBadge" class="badge">4.5</div></div><div id="newCard" class="modelCard"><img src="assets/M01_front.png"><div id="newBadge" class="badge">5.5</div></div><div id="arrow"></div><div id="ratioNote">口播引用</div><div id="ratio7" class="ratio">1:7</div><div id="ratio8" class="ratio">1:8</div>');
document.body.insertAdjacentHTML('beforeend','<div id="subtitle"></div>');
const phase=(t,a,b,curve=OM.ease.sineInOut)=>curve(OM.clamp((t-a)/(b-a)));
function rise(el,t,start,dist=24){const v=OM.wordRise(t,start,{dist});el.style.opacity=v.op;const y=+v.y.toFixed(3);el.style.transform=y===0?'none':`translateY(${y}px)`;}
const FULL={x:96,y:202,w:1360,h:765,r:0},LEFT={x:180,y:220,w:600,h:730,r:0};
function oldRect(s){return OM.morphRect(s,48.25,48.95,FULL,LEFT,{curve:OM.ease.expoInOut});}
let frame=-1;
async function seek(t){
 t=OM.clamp(t,0,CFG.dur-1e-7);const s=CFG.offset+t;
 if(TYPE==='a'){
  const n=Math.min(2116,Math.floor(s*30+.5));if(n!==frame){frame=n;$('presenter').src=`../production_v1/assets/speech_frames/${String(n).padStart(6,'0')}.png`;}
  const exit=1-phase(s,29.38,29.72);rise($('aLead'),s,27.00,22);$('aLead').style.opacity*=exit;
  const p=phase(s,27.92,28.27,OM.ease.expoOut);$('aPlate').style.opacity=exit;$('aPlate').style.clipPath=`inset(0 ${100*(1-p)}% 0 0)`;
  const m=OM.wordRise(s,28.02,{dist:38});$('aWord').style.opacity=m.op;$('aWord').style.transform=`translateY(${m.y.toFixed(3)}px)`;
  await $('presenter').decode();
 }
 if(TYPE==='b'){
  const scenes=[['M03',17.22],['M04',19.90],['M05',21.24],['M06',22.68]];
  let current=scenes[0];for(const scene of scenes)if(s>=scene[1])current=scene;
  const index=scenes.indexOf(current),p=phase(s,current[1],current[1]+.30,OM.ease.expoInOut);
  for(const [id] of scenes){$(id).style.opacity=0;$(id).style.zIndex='0';$(id).style.clipPath='none';}
  if(index>0&&p<1)$(scenes[index-1][0]).style.opacity=1;
  $(current[0]).style.opacity=1;$(current[0]).style.zIndex='1';$(current[0]).style.clipPath=`inset(0 ${100*(1-p)}% 0 0)`;
  for(const [i,start] of [17.76,20.00,22.76].entries()){
   const el=$('fact'+i),q=phase(s,start,start+.30,OM.ease.expoOut);el.style.clipPath=`inset(0 ${100*(1-q)}% 0 0)`;el.style.opacity=s>=start?1:0;
   rise($('factText'+i),s,start+.08,19);
  }
 }
 if(TYPE==='c'){
  const r=oldRect(s),el=$('oldCard');for(const [key,v] of Object.entries({left:r.x,top:r.y,width:r.w,height:r.h,borderRadius:r.r}))el.style[key]=v+'px';
  const q=phase(s,48.40,48.92);$('oldFull').style.opacity=1-q;$('oldFront').style.opacity=q;$('oldBadge').style.opacity=q;
  const pop=OM.popIn(s,48.50,{rise:120,s0:.94}),dy=+pop.dy.toFixed(3),scale=+pop.s.toFixed(5);$('newCard').style.opacity=pop.op;$('newCard').style.transform=dy===0&&scale===1?'none':`translateY(${dy}px) scale(${scale})`;
  $('newBadge').style.opacity=phase(s,49.12,49.36);$('arrow').style.clipPath=`inset(0 ${100*(1-phase(s,48.39,48.83,OM.ease.expoOut))}% 0 0)`;
  $('ratioNote').style.opacity=phase(s,51.64,51.90);rise($('ratio7'),s,51.64,20);rise($('ratio8'),s,52.30,20);
 }
 const row=DATA.subtitles.find(r=>s>=r.start&&s<r.end),show=row&&!(TYPE==='a'&&s>=27.92&&s<29.40);
 $('subtitle').textContent=show?row.text:'';$('subtitle').style.display=show?'block':'none';return true;
}
window.__seek=seek;
window.__meta={dur:CFG.dur,fps:30,testCase:TYPE,sourceOffset:CFG.offset,testName:CFG.name,sourceResolution:[1280,720],inFrame:{subtitle:[0,CFG.dur,'whole']}};
window.__motion=(a,b)=>{const s0=CFG.offset+a,s1=CFG.offset+b;if(TYPE==='a')return Math.max(598*Math.abs(phase(s0,27.92,28.27,OM.ease.expoOut)-phase(s1,27.92,28.27,OM.ease.expoOut)),38*Math.abs(phase(s0,28.02,28.65)-phase(s1,28.02,28.65)));if(TYPE==='b')return Math.max(...[17.22,19.90,21.24,22.68].map(s=>1392*Math.abs(phase(s0,s,s+.30,OM.ease.expoInOut)-phase(s1,s,s+.30,OM.ease.expoInOut))),...[17.76,20,22.76].map(s=>320*Math.abs(phase(s0,s,s+.30,OM.ease.expoOut)-phase(s1,s,s+.30,OM.ease.expoOut))));const A=oldRect(s0),B=oldRect(s1);return Math.max(Math.abs(A.x-B.x),Math.abs(A.w-B.w),Math.abs(A.h-B.h),120*Math.abs(OM.popIn(s0,48.5,{rise:120,s0:.94}).dy-OM.popIn(s1,48.5,{rise:120,s0:.94}).dy)/120);};
window.__ready=Promise.all([document.fonts.ready,document.fonts.load('100px Smiley')]).then(async()=>{await Promise.all([...document.images].map(im=>im.decode()));await seek(0);});
const params=new URLSearchParams(location.search);if(params.has('t'))__ready.then(()=>seek(Number(params.get('t'))));if(params.has('play'))__ready.then(()=>{const start=performance.now();const tick=()=>seek((performance.now()-start)/1000%CFG.dur).then(()=>requestAnimationFrame(tick));tick();});
