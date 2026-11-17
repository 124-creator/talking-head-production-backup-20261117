"""Ending revision: full-size presenter, small verb, large floating model name."""
from pathlib import Path
import hashlib
import json
import shutil

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
PREV=BASE/'raw_v3'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    for d in ('analysis','preview','output'):(HERE/d).mkdir(parents=True,exist_ok=True)
    manifest=json.loads((PREV/'analysis/input_manifest.json').read_text(encoding='utf-8'))
    render=json.loads((PREV/'output/render_manifest.json').read_text(encoding='utf-8'))
    assert sha(render['file'])==render['sha256']=='55b11dbb0c063ca0ed050481e919c71403b4ccebcef0b03eb1fd2509ecff3ef7'
    manifest.update(previous_v3_file=render['file'],previous_v3_sha256=render['sha256'],
                    previous_v3_comp_sha256=sha(PREV/'comp.html'),
                    previous_render_folder=render['render_folder'],
                    change_starts_seconds=12.06,reused_prefix_frames=362,
                    revision='End only: full-size presenter, floating enlarged model name, reduced verb and left-side captions')
    (HERE/'analysis/input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    html=(PREV/'comp.html').read_text(encoding='utf-8')
    def once(old,new):
        nonlocal html
        assert html.count(old)==1,old[:100]
        html=html.replace(old,new,1)
    html=html.replace('assets/speech_frames/','../raw_v3/assets/speech_frames/')
    once('<title>图生图 · 4K原片重合成预览</title>','<title>图生图 · 人物全幅悬浮标题版</title>')
    once('</style>', '''
/* V4: type floats on the footage; no separate paper end card or reduced speaker. */
#ending{color:#fffdf8;text-shadow:0 3px 4px #000b,0 8px 24px #0009}
#ending::before{content:"";position:absolute;inset:0;background:linear-gradient(0deg,rgba(5,10,8,.40),rgba(5,10,8,.13) 27%,transparent 50%)}
#ending-kicker{left:84px;top:812px;font-size:36px;color:#fffdf8}
#ending-big{left:740px;top:688px;font-size:84px;line-height:1.08;color:#f4cfa3}
#ending-model-mask{left:730px;top:800px;width:780px;height:250px}
#ending-model{font-size:210px;line-height:1.08;color:#fffdf8;-webkit-text-stroke:1px #15221855;text-shadow:0 3px 4px #000c,0 10px 28px #000a}
#ending-video-label{left:940px;top:721px;font-size:46px;color:#fffdf8}
#ending-rule,#ending-divider{display:none}
</style>''')
    once('<div id="ending-model-mask"><div id="ending-model">你的主力模型</div></div>',
         '<div id="ending-model-mask"><div id="ending-model">主力模型</div></div>')
    once('<div id="ending-video-label">今天这条视频</div>','<div id="ending-video-label">你的</div>')
    once('if(t>=ENDING_START)return OM.morphRect(t,ENDING_START,12.70,FULL,ENDING_PANEL,{curve:OM.ease.expoInOut});',
         'if(t>=ENDING_START)return {...FULL};')
    once('dist:78,stagger:.075,zeta:.56,omega:24','dist:25,stagger:.075,zeta:.62,omega:24')
    once('model:OM.maskRise(t,13.10,0,{dist:158,zeta:.65,omega:19})',
         'model:OM.maskRise(t,13.10,0,{dist:250,zeta:.70,omega:19})')
    # The oblique CJK glyph can paint a few pixels beyond its line box. Do not
    # let that edge show at the bottom of the mask before its spoken cue.
    once("const my=+e.model.y.toFixed(3);$('ending-model').style.transform=my===0?'none':`translateY(${my}px)`;",
         "const my=+e.model.y.toFixed(3);$('ending-model').style.transform=my===0?'none':`translateY(${my}px)`;\n $('ending-model').style.visibility=t<13.10?'hidden':'visible';")
    once('let loadedFrame=-1;', '''
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
let loadedFrame=-1;''')
    once("$('subtitle').textContent=sub?sub[2]:'';$('subtitle').style.display=sub?'block':'none';",
         "$('subtitle').textContent=sub?sub[2]:'';$('subtitle').style.display=sub?'block':'none';\n positionCaption(t);")
    once("if(t>=12.28){const b=$('ending-big').getBoundingClientRect();o.endingType={x:b.x,y:b.y,w:b.width,h:b.height,op:endingAt(t).op};}",
         "if(t>=13.10){const b=$('ending-model-mask').getBoundingClientRect();o.endingType={x:b.x,y:b.y,w:b.width,h:b.height,op:endingAt(t).op};}")
    once('d=Math.max(d,Math.abs(E.model.y-F.model.y),720*Math.abs(E.rule-F.rule));return d;',
         'd=Math.max(d,Math.abs(E.model.y-F.model.y),1000*Math.abs(captionMix(a)-captionMix(b)));return d;')
    once("endingOpacity:endingAt(t).op", "endingOpacity:endingAt(t).op,captionMix:captionMix(t),modelFontSize:parseFloat(getComputedStyle($('ending-model')).fontSize),verbFontSize:parseFloat(getComputedStyle($('ending-big')).fontSize),endingModelTextRect:rect('ending-model')")
    (HERE/'comp.html').write_text(html,encoding='utf-8')
    shutil.copy2(PREV/'look.js',HERE/'look.js')
    print('Built full-size-person overlay; four-character model name210px vs verb84px; ending captions move to left.')


if __name__=='__main__':main()
