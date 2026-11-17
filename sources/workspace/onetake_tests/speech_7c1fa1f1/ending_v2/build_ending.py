"""Ending-only derivative; preserve the accepted composition before 12.06s."""
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
html=(BASE/'comp.html').read_text(encoding='utf-8')


def once(old,new):
    global html
    assert html.count(old)==1,old[:100]
    html=html.replace(old,new,1)


once('<title>图生图 · 噪点累积口播配图</title>','<title>图生图 · 结尾强化版</title>')
html=html.replace('src="assets/','src="../assets/').replace('`assets/speech_frames/','`../assets/speech_frames/')
once('<script src="motion.js">','<script src="../motion.js">')
once('</style>','''
#closing-word{display:none}
#ending{display:none;position:absolute;inset:0;pointer-events:none;opacity:0;color:var(--ink)}
#ending-kicker{position:absolute;left:108px;top:208px;font-family:var(--text);font-size:47px;color:var(--accent)}
#ending-big{position:absolute;left:100px;top:300px;white-space:nowrap;font-family:var(--display);font-size:360px;line-height:1.05;font-weight:400;color:var(--accent2)}
.ending-char{display:inline-block;transform-origin:50% 88%}
#ending-rule{position:absolute;left:110px;top:730px;height:8px;background:var(--accent);width:0;transform-origin:0 50%}
#ending-model-mask{position:absolute;left:100px;top:763px;width:820px;height:162px;overflow:hidden}
#ending-model{font-family:var(--display);font-size:125px;line-height:1.18;white-space:nowrap;font-weight:400;color:var(--ink);transform-origin:0 0}
#ending-video-label{position:absolute;left:1048px;top:207px;font-size:37px;color:var(--mute)}
#ending-divider{position:absolute;left:945px;top:210px;width:2px;height:690px;background:var(--line);transform-origin:50% 0}
</style>''')
once('<div id="subtitle"></div>', '''<div id="ending">
 <div id="ending-kicker">这条视频，可能会</div>
 <div id="ending-big"><span class="ending-char">换</span><span class="ending-char">掉</span></div>
 <div id="ending-rule"></div>
 <div id="ending-model-mask"><div id="ending-model">你的主力模型</div></div>
 <div id="ending-video-label">今天这条视频</div><div id="ending-divider"></div>
</div>
<div id="subtitle"></div>''')
once('function rectAt(t){','''const ENDING_START=12.06,ENDING_PANEL={x:1040,y:265,w:800,h:450,r:24};
function rectAt(t){
 if(t>=ENDING_START)return OM.morphRect(t,ENDING_START,12.70,FULL,ENDING_PANEL,{curve:OM.ease.expoInOut});''')
once('let loadedFrame=-1;', '''function endingAt(t){
 return {op:phase(t,ENDING_START,12.34),
 letters:[0,1].map(i=>OM.letterDrop(t,12.28,i,{dist:78,stagger:.075,zeta:.56,omega:24})),
 model:OM.maskRise(t,13.10,0,{dist:158,zeta:.65,omega:19}),
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
 $('ending-rule').style.width=(720*e.rule)+'px';
 $('ending-video-label').style.opacity=phase(t,12.52,12.90);
 $('ending-divider').style.transform=`scaleY(${phase(t,12.30,12.85,OM.ease.expoOut)})`;
}
let loadedFrame=-1;''')
once('const closing=OM.wordRise(t,12.28,{dist:30});','const closing=OM.wordRise(t,12.28,{dist:30});\n drawEnding(t);')
once("inFrame:{carrier:[0,DUR,'whole'],photoFace:[3.78,9.68,'whole'],subtitleSafe:[0,DUR,'whole']}",
     "inFrame:{carrier:[0,DUR,'whole'],photoFace:[3.78,9.68,'whole'],subtitleSafe:[0,DUR,'whole'],endingType:[13.85,DUR,'whole']}")
once('const o={carrier,photoFace:face};','''const o={carrier,photoFace:face};
 if(t>=12.28){const b=$('ending-big').getBoundingClientRect();o.endingType={x:b.x,y:b.y,w:b.width,h:b.height,op:endingAt(t).op};}''')
once('d=Math.max(d,Math.abs(x.out-y.out)*Math.max(x.r.w,y.r.w));return d;', '''d=Math.max(d,Math.abs(x.out-y.out)*Math.max(x.r.w,y.r.w));
 const E=endingAt(a),F=endingAt(b);
 for(let k=0;k<2;k++)d=Math.max(d,Math.abs(E.letters[k].y-F.letters[k].y)+400*Math.abs(E.letters[k].sy-F.letters[k].sy)+300*Math.abs(E.letters[k].sx-F.letters[k].sx));
 d=Math.max(d,Math.abs(E.model.y-F.model.y),720*Math.abs(E.rule-F.rule));return d;''')
once("openingRect:rect('opening-word'),closingRect:rect('closing-word')", "openingRect:rect('opening-word'),closingRect:rect('closing-word'),endingRect:rect('ending-big'),endingModelRect:rect('ending-model-mask'),endingOpacity:endingAt(t).op")
(HERE/'comp.html').write_text(html,encoding='utf-8')
print(HERE/'comp.html')
