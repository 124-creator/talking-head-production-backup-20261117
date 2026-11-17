


'use strict';
const $=id=>document.getElementById(id),W=1920,H=1080,DUR=454/30;
const FULL={x:0,y:0,w:W,h:H,r:0},PHOTO={x:88,y:144,w:1408,h:792,r:28};
const START=[3.40,4.06,5.14,6.96],SPAN=[.34,.40,.42,.48];
const SUBS=[
 [0,1.34,'你有没有那种感觉'],[1.34,3.42,'用AI去做图生图'],
 [3.42,4.58,'改个两三次'],[4.58,6.42,'画面全是那种噪点'],
 [6.42,7.90,'然后你是越改越脏'],[7.90,9.62,'最后根本就没法用了'],
 [10.12,12.70,'今天这条视频可能会直接换掉'],[12.70,14.80,'你手里面的主力模型']
];
const TITLES=['起始\n画面','反复\n修改','出现\n噪点','越改\n越脏'];
const NOTES=['图1\n开始观察','图2\n继续修改','图3\n颗粒显现','图4\n细节更杂乱'];
const CUES={carrierIn:3.12,carrierSettled:3.78,returnStart:9.68,returnSettled:10.28,
 image01:START[0],image02:START[1],image03:START[2],image04:START[3]};
const K=OM.clamp,L=OM.lerp;
function phase(t,a,b,curve=OM.ease.sineInOut){return curve(K((t-a)/(b-a)));}
const ENDING_START=12.06,ENDING_PANEL={x:1040,y:265,w:800,h:450,r:24};
function rectAt(t){
 if(t>=ENDING_START)return {...FULL};
 if(t<3.78)return OM.morphRect(t,3.12,3.78,FULL,PHOTO,{curve:OM.ease.expoInOut});
 if(t>=9.68)return OM.morphRect(t,9.68,10.28,PHOTO,FULL,{curve:OM.ease.expoInOut});
 return {...PHOTO};
}
// A restrained operator follows the same picture plane; the long holds are
// genuinely flat. No seeded noise, fake enhancement, added grain, or particles.
function camAt(t){return OM.camera(t,[
 {t:0,x:960,y:540,zoom:1},{t:3.78,x:960,y:540,zoom:1},
 {t:4.02,x:960,y:540,zoom:1},{t:4.42,x:951,y:536,zoom:1.006,curve:OM.ease.sineInOut},
 {t:5.10,x:951,y:536,zoom:1.006},{t:5.56,x:958,y:541,zoom:1,curve:OM.ease.sineInOut},
 {t:6.92,x:958,y:541,zoom:1},{t:7.44,x:949,y:536,zoom:1.008,curve:OM.ease.sineInOut},
 {t:9.68,x:949,y:536,zoom:1.008},{t:10.00,x:960,y:540,zoom:1,curve:OM.ease.sineInOut},
 {t:10.28,x:960,y:540,zoom:1},
 {t:DUR,x:960,y:540,zoom:1}
]);}
function reveal(t,k){return phase(t,START[k],START[k]+SPAN[k],OM.ease.expoInOut);}
function railX(t){let x=20;for(let k=1;k<4;k++)x+=170*reveal(t,k);return x;}
function stateAt(t){
 const r=rectAt(t),camera=camAt(t),M=OM.view(camera),p=START.map((_,k)=>reveal(t,k));
 const out=phase(t,9.72,10.10,OM.ease.expoInOut);
 const workspace=phase(t,3.58,3.87)*(1-phase(t,9.68,10.05));
 let stage=0;for(let k=1;k<4;k++)if(t>=START[k])stage=k;
 return {r,camera,M,p,out,workspace,stage};
}
function endingAt(t){
 return {op:phase(t,ENDING_START,12.34),
 letters:[0,1].map(i=>OM.letterDrop(t,12.28,i,{dist:25,stagger:.075,zeta:.62,omega:24})),
 model:OM.maskRise(t,13.10,0,{dist:250,zeta:.70,omega:19}),
 rule:phase(t,12.94,13.35,OM.ease.expoOut)};
}
function drawEnding(t){
 const e=endingAt(t);$('ending').style.display=t>=ENDING_START?'block':'none';$('ending').style.opacity=e.op;
 const kicker=OM.wordRise(t,12.10,{dist:18});
 $('ending-kicker').style.opacity=kicker.op;$('ending-kicker').style.transform=`translateY(${kicker.y}px)`;
 // Quantize sub-pixel residue so a settled spring is a true identity matrix,
 // not a near-unit scale whose glyph raster cache depends on previous seeks.
 document.querySelectorAll('.ending-char').forEach((el,i)=>{const d=e.letters[i],y=+d.y.toFixed(3),sx=+d.sx.toFixed(5),sy=+d.sy.toFixed(5);el.style.opacity=d.op;el.style.transform=(y===0&&sx===1&&sy===1)?'none':`translateY(${y}px) scale(${sx},${sy})`;});
 const my=+e.model.y.toFixed(3);$('ending-model').style.transform=my===0?'none':`translateY(${my}px)`;
 $('ending-model').style.visibility=t<13.10?'hidden':'visible';
 $('ending-rule').style.width=(720*e.rule)+'px';
 $('ending-video-label').style.opacity=phase(t,12.52,12.90);
 $('ending-divider').style.transform=`scaleY(${phase(t,12.30,12.85,OM.ease.expoOut)})`;
}

function captionMix(t){return phase(t,ENDING_START,12.40,OM.ease.expoInOut);}
function positionCaption(t){
 const el=$('subtitle');
 for(const k of ['font-size','left','top','bottom','transform'])el.style.removeProperty(k);
 if(t<ENDING_START||el.style.display==='none')return;
 const q=captionMix(t);el.style.fontSize=L(57,48,q)+'px';
 const b=el.getBoundingClientRect();
 el.style.left=L((W-b.width)/2,84,q).toFixed(3)+'px';
 el.style.top=L(H-28-b.height,904,q).toFixed(3)+'px';
 el.style.bottom='auto';el.style.transform='none';
}
let loadedFrame=-1;
async function seek(t){
 t=K(t,0,DUR-1e-7);const s=stateAt(t),{r,M,p,out,workspace,stage}=s;
 $('world').style.transform=`matrix(${M.join(',')})`;
 const carrier=$('carrier');carrier.style.transform=`translate(${r.x}px,${r.y}px)`;
 carrier.style.width=r.w+'px';carrier.style.height=r.h+'px';carrier.style.borderRadius=r.r+'px';
 const shadow=phase(t,3.12,3.78)*(1-phase(t,9.68,10.28));
 carrier.style.boxShadow=shadow>.001?`0 ${24*shadow}px ${48*shadow}px -18px rgba(32,43,30,${.2*shadow})`:'none';
 $('photos').style.clipPath=`inset(0 ${100*out}% 0 0)`;
 let edge=-1;
 for(let k=0;k<4;k++){
   const fullyCovered=k<3 && p[k+1]>=1;
   const el=$('photo'+(k+1));el.style.opacity=p[k]>0&&!fullyCovered?1:0;
   el.style.clipPath=`inset(0 ${100*(1-p[k])}% 0 0)`;
   if(p[k]>0&&p[k]<1)edge=p[k];
 }
 if(out>0&&out<1)edge=1-out;
 $('wipe').style.opacity=edge>=0? .75:0;$('wipe').style.left=(Math.max(0,edge)*100)+'%';
 $('workspace').style.opacity=workspace;
 $('rail-marker').style.left=railX(t)+'px';
 $('stage-num').textContent=String(stage+1).padStart(2,'0');
 $('stage-title').textContent=TITLES[stage];$('stage-note').textContent=NOTES[stage];
 const titleIn=OM.wordRise(t,START[stage]+.16,{dist:22});
 $('stage-title').style.opacity=titleIn.op;$('stage-title').style.transform=`translateY(${titleIn.y}px)`;
 const noteIn=OM.wordRise(t,START[stage]+.29,{dist:15});
 $('stage-note').style.opacity=noteIn.op;$('stage-note').style.transform=`translateY(${noteIn.y}px)`;
 const opening=OM.wordRise(t,1.72,{dist:25});
 $('opening-word').style.opacity=opening.op*(1-phase(t,2.94,3.18));
 $('opening-word').style.transform=`translateY(${opening.y}px)`;
 const closing=OM.wordRise(t,12.28,{dist:30});
 drawEnding(t);
 $('closing-word').style.opacity=closing.op*(1-phase(t,14.82,15.10));
 $('closing-word').style.transform=`translateY(${closing.y}px)`;
 const sub=SUBS.find(([a,b])=>t>=a&&t<b);
 $('subtitle').textContent=sub?sub[2]:'';$('subtitle').style.display=sub?'block':'none';
 positionCaption(t);
 $('hud').textContent=`${t.toFixed(3)}s · photo ${stage+1}`;
 const n=Math.min(452,Math.floor(t*30+1e-6));
 if(n!==loadedFrame){loadedFrame=n;$('presenter').src=`../raw_v3/assets/speech_frames/${String(n).padStart(6,'0')}.png`;}
 await $('presenter').decode();return true;
}
window.__seek=seek;
window.__meta={dur:DUR,fps:30,sourceResolution:[3840,2160],decodedFrameResolution:[1920,1080],sourceFrames:453,sourceVideoSeconds:15.1,sourceAudioSeconds:15.116009,
 confirmedConcept:'A: one persistent photo carrier; sequence 1 to 4; noise accumulation; original speech unchanged',
 inFrame:{carrier:[0,DUR,'whole'],photoFace:[3.78,9.68,'whole'],subtitleSafe:[0,DUR,'whole'],endingType:[13.85,DUR,'whole']}};
window.__track=t=>{
 const s=stateAt(t),r=s.r;
 const carrier=OM.projectBox(s.M,{...r,op:1});
 const face=OM.projectBox(s.M,{x:r.x+r.w*.24,y:r.y+r.h*.015,w:r.w*.56,h:r.h*.92,op:s.workspace});
 const o={carrier,photoFace:face};
 if(t>=13.10){const b=$('ending-model-mask').getBoundingClientRect();o.endingType={x:b.x,y:b.y,w:b.width,h:b.height,op:endingAt(t).op};}
 if($('subtitle').style.display!=='none'){
  const b=$('subtitle').getBoundingClientRect();o.subtitleSafe={x:b.x,y:b.y,w:b.width,h:b.height,op:1};
 }
 if(s.workspace>.05)o.iterationMarker=OM.projectBox(s.M,{x:832+railX(t)-15,y:96,w:30,h:30,op:s.workspace});
 for(let k=0;k<4;k++){
  const visible=(k===3? s.p[k]:Math.max(0,s.p[k]-s.p[k+1]))*(1-s.out);
  if(visible>.03)o['photo'+(k+1)]=OM.projectBox(s.M,{x:r.x,y:r.y,w:r.w*visible,h:r.h,op:visible});
 }
 return o;
};
window.__motion=(a,b)=>{
 const x=stateAt(a),y=stateAt(b),box=s=>OM.projectBox(s.M,{...s.r,op:1});
 const A=box(x),B=box(y);
 let d=Math.max(Math.hypot(A.x-B.x,A.y-B.y),Math.hypot(A.x+A.w-B.x-B.w,A.y+A.h-B.y-B.h));
 d=Math.max(d,Math.abs(railX(a)-railX(b)),OM.screenTravel(x.camera,y.camera,camAt((a+b)/2)));
 for(let k=0;k<4;k++)d=Math.max(d,Math.abs(x.p[k]-y.p[k])*Math.max(x.r.w,y.r.w));
 d=Math.max(d,Math.abs(x.out-y.out)*Math.max(x.r.w,y.r.w));
 const E=endingAt(a),F=endingAt(b);
 for(let k=0;k<2;k++)d=Math.max(d,Math.abs(E.letters[k].y-F.letters[k].y)+400*Math.abs(E.letters[k].sy-F.letters[k].sy)+300*Math.abs(E.letters[k].sx-F.letters[k].sx));
 d=Math.max(d,Math.abs(E.model.y-F.model.y),1000*Math.abs(captionMix(a)-captionMix(b)));return d;
};
window.__audit=t=>{
 const s=stateAt(t),rect=id=>{const r=$(id).getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};};
 return {time:t,phase:s.stage+1,visiblePhotoReveals:s.p,returnProgress:s.out,
 carrier:rect('carrier'),caption:$('subtitle').textContent,captionRect:rect('subtitle'),
 stageTitle:$('stage-title').textContent,stageRect:rect('stage-title'),
 openingRect:rect('opening-word'),closingRect:rect('closing-word'),endingRect:rect('ending-big'),endingModelRect:rect('ending-model-mask'),endingOpacity:endingAt(t).op,captionMix:captionMix(t),modelFontSize:parseFloat(getComputedStyle($('ending-model')).fontSize),verbFontSize:parseFloat(getComputedStyle($('ending-big')).fontSize),endingModelTextRect:rect('ending-model')};
};
window.__ready=LOOK.ready.then(async()=>{await Promise.all(Array.from(document.querySelectorAll('img')).map(i=>i.decode()));await seek(0);});
const query=new URLSearchParams(location.search);
if(query.has('hud'))$('hud').style.display='block';
if(query.has('t'))__ready.then(()=>seek(Number(query.get('t'))));
if(query.has('play'))__ready.then(()=>{const start=performance.now();function tick(){seek(((performance.now()-start)/1000)%DUR).then(()=>requestAnimationFrame(tick));}tick();});
