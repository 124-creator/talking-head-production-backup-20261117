'use strict';
const $=id=>document.getElementById(id),DUR=70.6,CLAMP=OM.clamp;
const FULL={x:0,y:0,w:1920,h:1080,r:0},PANEL={x:80,y:190,w:1392,h:783,r:24};
const OLD_FULL={x:96,y:202,w:1360,h:765,r:0},OLD_LEFT={x:180,y:220,w:600,h:730,r:0};
const WINDOWS=[{name:'negative',a:5.32,b:13.20},{name:'positive',a:14.54,b:26.62},{name:'edit',a:34.26,b:39.66},{name:'group',a:55.50,b:63.82}];
const PHOTOS=[
 {id:'M09',start:5.32,end:8.20,group:'negative'},{id:'M10',start:8.20,end:9.84,group:'negative'},{id:'M11',start:9.84,end:13.20,group:'negative'},
 {id:'M02',start:14.54,end:17.22,group:'positive'},{id:'M03',start:17.22,end:19.90,group:'positive'},{id:'M04',start:19.90,end:21.24,group:'positive'},
 {id:'M05',start:21.24,end:22.68,group:'positive'},{id:'M06',start:22.68,end:24.50,group:'positive'},{id:'M07',start:24.50,end:26.62,group:'positive'},
 {id:'M19',start:34.26,end:36.02,group:'edit'},{id:'M24',start:36.02,end:37.12,group:'edit'},{id:'M23',start:37.12,end:39.66,group:'edit'},
 {id:'M18',start:55.50,end:60.50,group:'group',zoom:true},{id:'M17',start:60.50,end:63.82,group:'group',zoom:true}
];
for(const p of PHOTOS){const box=document.createElement('div');box.id='p'+p.id;box.className='photo';box.innerHTML=`<img src="../production_v1/assets/${p.id}.png" alt="提供的样图 ${p.id}">`;$('photos').appendChild(box);}
const phase=(t,a,b,curve=OM.ease.sineInOut)=>curve(CLAMP((t-a)/(b-a)));
function riseState(t,start,dist=24){if(t>=start+1.1)return {op:1,y:0};if(t<start)return {op:0,y:dist};return OM.wordRise(t,start,{dist});}
function rise(el,t,start,dist=24){const v=riseState(t,start,dist);el.style.opacity=v.op;const y=+v.y.toFixed(3);el.style.transform=y===0?'none':`translateY(${y}px)`;return v.op;}
function windowAt(t){return WINDOWS.find(w=>t>=(w.name==='group'?w.a:w.a-.30)&&t<=w.b+(w.name==='edit'?.34:.42))||null;}
function photoAt(t){let out=null;for(const p of PHOTOS){if(t>=p.start)out=p;else break;}return out;}
function imageReveal(t,p){return phase(t,p.start,p.start+Math.min(.30,(p.end-p.start)*.16),OM.ease.expoInOut);}
function zoomAt(t,p){return p&&p.zoom?1+.34*phase(t,p.start+1.55,p.start+2.55):1;}
function carrierRect(t,w){if(!w)return {...FULL};if(w.name==='group')return t<=w.b-.08?{...PANEL}:OM.morphRect(t,w.b-.08,w.b+.42,PANEL,FULL,{curve:OM.ease.expoInOut});if(t<w.a+.28)return OM.morphRect(t,w.a-.30,w.a+.28,FULL,PANEL,{curve:OM.ease.expoInOut});if(w.name==='edit')return {...PANEL};return t>w.b-.08?OM.morphRect(t,w.b-.08,w.b+.42,PANEL,FULL,{curve:OM.ease.expoInOut}):{...PANEL};}
function modeAt(t,w){if(t>=39.66&&t<55.50)return 'ratio';return w?w.name:'person';}
function factsAt(t,mode){
 if(mode==='negative')return [{start:5.46,title:'光照 · 材质',note:'提供的对照样例'},{start:8.30,title:'皮肤纹理',note:'不同场景观察'},{start:9.95,title:'油亮与过曝',note:'观察原图高光'}];
 if(mode==='positive')return [{start:t<17.76?14.80:17.76,title:t<17.76?'5.5 人像':'纹理清楚',note:t<17.76?'六张提供的样图':'皮肤近景'},{start:20.00,title:'光影自然',note:'明暗过渡'},{start:22.76,title:'少塑料感',note:'样图观感'}];
 if(mode==='edit')return [{start:34.40,title:'改三视图',note:'完整正面侧背面'},{start:36.02,title:'换服装',note:'衬衫裤装到旗袍'},{start:37.12,title:'改分镜',note:'按提供样图展示'}];
 if(mode==='ratio')return [{start:39.80,title:'旧版问题',note:'提供的4.5样图'},{start:44.76,title:'人物变矮',note:'完整身体观察'},{start:46.34,title:'头身关系',note:'不作定量测量'}];
 if(mode==='group')return [{start:55.70,title:'群像样例',note:t<60.50?'6461 / 原图':'5921 / 原图'},{start:57.48,title:'相似脸型',note:'不作身份识别'},{start:60.50,title:'多人同框',note:'观察面部多样性'}];
 return [];
}
function oldRect(t){return OM.morphRect(t,48.25,48.95,OLD_FULL,OLD_LEFT,{curve:OM.ease.expoInOut});}
function captionAt(t){if(t<1.70||t>=65.78||(t>=27.92&&t<29.40))return null;return DATA.subtitles.find(r=>t>=r.start&&t<r.end)||null;}
function stateAt(t){
 const w=windowAt(t),p=photoAt(t),r=carrierRect(t,w),mode=modeAt(t,w);
 let carrierOp=1;if(t>=39.66&&t<40)carrierOp=1-phase(t,39.66,40);else if(t>=40&&t<55.5)carrierOp=0;else if(t>=55.5&&t<55.85)carrierOp=phase(t,55.5,55.85);
 const comparisonOp=phase(t,39.66,40)*(1-phase(t,55.50,55.85));
 let q=0;if(w){q=w.name==='group'?1:phase(t,w.a,w.a+.36,OM.ease.expoInOut);if(w.name!=='edit'&&t>w.b-.08)q*=1-phase(t,w.b-.08,w.b+.25);}
 let work=0;if(mode==='ratio'||(w&&w.name==='group'&&t<63.74))work=1;else if(w){work=phase(t,w.a-.02,w.a+.35)*(1-phase(t,w.b-.08,w.b+.24));if(w.name==='edit'&&t>=39.4)work=1;}
 const person=carrierOp>.001&&q<.999;
 const captionClass=(comparisonOp>.1||(w&&r.y+r.h<=980))?'paper':(w&&q>.001?'transition':'person');
 return {w,p,r,mode,q,carrierOp,comparisonOp,work,person,captionClass,facts:factsAt(t,mode),caption:captionAt(t)};
}
let loadedFrame=-1;
async function seek(t){
 t=CLAMP(t,0,DUR-1e-7);const s=stateAt(t),{w,p,r,mode,q,work}=s,c=$('carrier');
 for(const [name,value] of Object.entries({left:r.x,top:r.y,width:r.w,height:r.h,borderRadius:r.r}))c.style[name]=value+'px';c.style.opacity=s.carrierOp;
 $('photos').style.opacity=q;let edge=-1;
 for(const el of $('photos').children){el.style.opacity=0;el.style.clipPath='none';el.style.zIndex='0';el.firstElementChild.style.transform='none';}
 if(p){const i=PHOTOS.indexOf(p),previous=i>0?PHOTOS[i-1]:null,reveal=imageReveal(t,p),cur=$('p'+p.id);
  if(previous&&previous.group===p.group&&reveal<1){const el=$('p'+previous.id);el.style.opacity=1;const z=+zoomAt(Math.min(t,p.start-.001),previous).toFixed(5);el.firstElementChild.style.transform=z===1?'none':`scale(${z})`;}
  cur.style.opacity=1;cur.style.zIndex='1';cur.style.clipPath=`inset(0 ${100*(1-reveal)}% 0 0)`;const z=+zoomAt(t,p).toFixed(5);cur.firstElementChild.style.transform=z===1?'none':`scale(${z})`;if(reveal>0&&reveal<1)edge=reveal;
 }
 $('wipe').style.opacity=edge>=0?q*.65:0;$('wipe').style.left=Math.max(0,edge)*100+'%';
 $('comparison').style.opacity=s.comparisonOp;
 const old=oldRect(t);for(const [key,value] of Object.entries({left:old.x,top:old.y,width:old.w,height:old.h,borderRadius:old.r}))$('oldCard').style[key]=value+'px';
 const crop=phase(t,48.40,48.92);$('oldFull').style.opacity=1-crop;$('oldFront').style.opacity=crop;$('oldBadge').style.opacity=crop;
 const pop=t>=49.65?{op:1,dy:0,s:1}:OM.popIn(t,48.50,{rise:120,s0:.94}),dy=+pop.dy.toFixed(3),scale=+pop.s.toFixed(5);$('newCard').style.opacity=pop.op;$('newCard').style.transform=dy===0&&scale===1?'none':`translateY(${dy}px) scale(${scale})`;
 $('newBadge').style.opacity=phase(t,49.12,49.36);$('arrow').style.clipPath=`inset(0 ${100*(1-phase(t,48.39,48.83,OM.ease.expoOut))}% 0 0)`;
 $('ratioNote').style.opacity=phase(t,51.64,51.90);rise($('ratio7'),t,51.64,20);rise($('ratio8'),t,52.30,20);
 $('workspace').style.opacity=work;const titles={negative:'真实感，先看对照',positive:'真实感，让细节说话',edit:'改图能力，直接看结果',ratio:'三视图 · 头身比例',group:'群像，仍有老问题'};
 $('title').textContent=titles[mode]||'';$('comparisonNote').style.display=mode==='ratio'?'block':'none';
 const seq=mode==='positive'&&p?`${String(PHOTOS.filter(x=>x.group==='positive').indexOf(p)+1).padStart(2,'0')} / 06 · 人像样例`:mode==='group'?(t<60.5?'01 / 02 · 完整合照':'02 / 02 · 多人同框'):mode==='ratio'?'4.5 / 样图':mode==='negative'?'提供的对照样例':mode==='edit'?'三视图 · 服装 · 分镜':'';
 $('sequence').textContent=seq;$('sequence').style.opacity=mode==='ratio'?1-phase(t,48.18,48.45):1;
 for(let i=0;i<3;i++){const el=$('fact'+i),f=s.facts[i];if(!f){el.style.opacity=0;continue;}$('factText'+i).textContent=f.title;$('detail'+i).textContent=f.note;const clip=phase(t,f.start,f.start+.26,OM.ease.expoOut);el.style.clipPath=`inset(0 ${100*(1-clip)}% 0 0)`;el.style.opacity=(t>=f.start?1:0)*(mode==='ratio'?1-phase(t,48.18,48.45):1);rise($('factText'+i),t,f.start+.06,18);}
 $('humanOverlay').style.opacity=mode==='person'?1:0;
 const openExit=1-phase(t,1.42,1.70);rise($('chapterLead'),t,.04,18);$('chapterLead').style.opacity*=openExit;$('chapterPlate').style.opacity=openExit;$('chapterPlate').style.clipPath=`inset(0 ${100*(1-phase(t,.10,.36,OM.ease.expoOut))}% 0 0)`;rise($('chapterWord'),t,.15,24);
 const editExit=1-phase(t,29.38,29.72);rise($('aLead'),t,27,22);$('aLead').style.opacity*=editExit;$('aPlate').style.opacity=editExit;$('aPlate').style.clipPath=`inset(0 ${100*(1-phase(t,27.92,28.27,OM.ease.expoOut))}% 0 0)`;rise($('aWord'),t,28.02,38);
 const flowExit=1-phase(t,33.94,34.16);rise($('flowLead'),t,29.82,18);$('flowLead').style.opacity*=flowExit;for(const [id,start] of [['flow1',30.04],['flow2',32.62]]){$(id).style.opacity=(t>=start?1:0)*flowExit;$(id).style.clipPath=`inset(0 ${100*(1-phase(t,start,start+.30,OM.ease.expoOut))}% 0 0)`;}
 $('shade').style.opacity=Math.max(openExit*(t<1.7?1:0),phase(t,26.85,27.10)*editExit,phase(t,29.8,30.1)*flowExit)*.7;
 $('ending').style.opacity=phase(t,66.65,66.95);rise($('endTop'),t,66.72,22);rise($('endBut'),t,67.72,18);rise($('endPicture'),t,67.94,28);rise($('endClean'),t,68.60,42);rise($('endGPT'),t,69.66,17);
 $('subtitle').textContent=s.caption?s.caption.text:'';$('subtitle').style.display=s.caption?'block':'none';$('subtitle').className=s.captionClass;
 $('presenter').style.visibility=s.person?'visible':'hidden';if(s.person){const n=Math.min(2116,Math.floor(t*30+.5));if(n!==loadedFrame){loadedFrame=n;$('presenter').src=`../production_v1/assets/speech_frames/${String(n).padStart(6,'0')}.png`;}await $('presenter').decode();}return true;
}
window.__seek=seek;
window.__meta={dur:DUR,fps:30,sourceResolution:[1280,720],sourceFrames:2117,sourceAudioSeconds:70.589002,concept:'Complete V2: anchored bold headlines, semantic plates, accumulating facts, persistent old/new comparison, original speech',cuts:PHOTOS.map(p=>p.start).concat([39.66,48.25]),inFrame:{subtitle:[0,DUR,'whole']}};
window.__track=t=>({carrier:{...carrierRect(t,windowAt(t)),op:stateAt(t).carrierOp}});
window.__motion=(a,b)=>{const A=stateAt(a),B=stateAt(b);let d=Math.max(Math.abs(A.r.x-B.r.x),Math.abs(A.r.y-B.r.y),Math.abs(A.r.w-B.r.w),Math.abs(A.r.h-B.r.h));for(const p of PHOTOS){d=Math.max(d,1392*Math.abs(imageReveal(a,p)-imageReveal(b,p)),1392*Math.abs(zoomAt(a,p)-zoomAt(b,p)));}for(const f of [...A.facts,...B.facts])d=Math.max(d,320*Math.abs(phase(a,f.start,f.start+.26,OM.ease.expoOut)-phase(b,f.start,f.start+.26,OM.ease.expoOut)));const L=oldRect(a),R=oldRect(b);d=Math.max(d,Math.abs(L.w-R.w),Math.abs(L.h-R.h));for(const [s,w,dur] of [[.1,388,.26],[27.92,598,.35],[30.04,290,.3],[32.62,380,.3]])d=Math.max(d,w*Math.abs(phase(a,s,s+dur,OM.ease.expoOut)-phase(b,s,s+dur,OM.ease.expoOut)));return Math.max(d,140*Math.abs(phase(a,68.60,69.25)-phase(b,68.60,69.25)));};
window.__staticKey=t=>{
 if(t<0||t>=DUR)return null;const s=stateAt(t);if(s.person||s.work!==1)return null;
 if(s.mode==='ratio'){
  if(t<40.10||t>55.30||(t>48.12&&t<49.78)||(t>51.58&&t<53.50))return null;
  if(t<48.12&&s.facts.some(f=>t>f.start-.02&&t<f.start+1.20))return null;
  return JSON.stringify(['ratio',t>=49.78?'paired':'full',t>=51.64,t>=52.30,s.caption?s.caption.text:'',s.captionClass,s.facts.map(f=>[t>=f.start,f.title,f.note])]);
 }
 if(!s.w||!s.p||s.carrierOp!==1||s.q!==1||t<s.w.a+.68||t>s.w.b-.16)return null;
 if(t<s.p.start+.38||s.facts.some(f=>t>f.start-.02&&t<f.start+1.20))return null;
 if(s.p.zoom&&t>s.p.start+1.48&&t<s.p.start+2.65)return null;
 return JSON.stringify([s.mode,s.p.id,zoomAt(t,s.p).toFixed(5),s.caption?s.caption.text:'',s.captionClass,s.facts.map(f=>[t>=f.start,f.title,f.note])]);
};
window.__staticGroups=()=>{
 const groups={};
 for(let n=0;n<2118;n++){
  const t=n/30,key=__staticKey(t),before=__staticKey(Math.max(0,t-1/120)),after=__staticKey(Math.min(DUR-1e-7,t+1/120));
  if(key!==null&&key===before&&key===after){(groups[key]??=[]).push(n);}
 }
 return Object.entries(groups).map(([key,frames])=>({key,frames}));
};
window.__ready=Promise.all([document.fonts.ready,document.fonts.load('100px Smiley')]).then(async()=>{await Promise.all([...document.images].map(im=>im.decode()));await seek(0);});
const query=new URLSearchParams(location.search);if(query.has('t'))__ready.then(()=>seek(Number(query.get('t'))));if(query.has('play'))__ready.then(()=>{const start=performance.now();const tick=()=>seek((performance.now()-start)/1000%DUR).then(()=>requestAnimationFrame(tick));tick();});
