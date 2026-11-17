"""V5: remove BOTH left text layers; keep only the floating phrase, in yellow."""
from pathlib import Path
import hashlib
import json
import shutil

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
PREV=BASE/'overlay_v4'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    for d in ('analysis','preview','output'):(HERE/d).mkdir(parents=True,exist_ok=True)
    inputs=json.loads((PREV/'analysis/input_manifest.json').read_text(encoding='utf-8'))
    prior=json.loads((PREV/'output/render_manifest.json').read_text(encoding='utf-8'))
    assert sha(prior['file'])==prior['sha256']=='87e57022996ac8e697224f04aa16fb461e4b9bd56e8ea35625a0e8846815ccb3'
    inputs.update(previous_v4_file=prior['file'],previous_v4_sha256=prior['sha256'],
                  previous_v4_comp_sha256=sha(PREV/'comp.html'),
                  revision='Ending only: delete left kicker and normal captions; keep verb/possessive/model overlay; model yellow#FFD84D')
    (HERE/'analysis/input_manifest.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2),encoding='utf-8')
    html=(PREV/'comp.html').read_text(encoding='utf-8')
    def once(old,new):
        nonlocal html
        assert html.count(old)==1,old[:100]
        html=html.replace(old,new,1)
    once('<title>图生图 · 人物全幅悬浮标题版</title>','<title>图生图 · 黄色主标题去重版</title>')
    once('</style>','\n#ending-kicker{display:none}\n#ending-model{color:#FFD84D}\n</style>')
    once('const sub=SUBS.find(([a,b])=>t>=a&&t<b);',
         'const sub=t<ENDING_START?SUBS.find(([a,b])=>t>=a&&t<b):undefined;')
    once('d=Math.max(d,Math.abs(E.model.y-F.model.y),1000*Math.abs(captionMix(a)-captionMix(b)));return d;',
         'd=Math.max(d,Math.abs(E.model.y-F.model.y));return d;')
    once("subtitleSafe:[0,DUR,'whole']", "subtitleSafe:[0,12.06,'whole']")
    once('endingOpacity:endingAt(t).op',
         "endingOpacity:endingAt(t).op,endingKickerDisplay:getComputedStyle($('ending-kicker')).display,mainModelColor:getComputedStyle($('ending-model')).color")
    (HERE/'comp.html').write_text(html,encoding='utf-8')
    shutil.copy2(PREV/'look.js',HERE/'look.js')
    # Reuse the already-validated, non-destructive partial-render runner.
    runner=(PREV/'run_render.py').read_text(encoding='utf-8')
    runner=runner.replace('onetake_overlay_v4_1080p30.mp4','onetake_overlay_v5_1080p30.mp4')
    anchor="assert sha(BASE/'raw_v3/comp.html')==inputs['previous_v3_comp_sha256']"
    assert runner.count(anchor)==1
    runner=runner.replace(anchor,anchor+"\n    assert sha(inputs['previous_v4_file'])==inputs['previous_v4_sha256']\n    assert sha(BASE/'overlay_v4/comp.html')==inputs['previous_v4_comp_sha256']")
    runner=runner.replace("'ending_caption_left_edge_px':84,'ending_caption_left_settled_seconds':12.4,",
                          "'ending_caption_hidden':True,'ending_left_kicker_hidden':True,'main_model_color':'#FFD84D',")
    runner=runner.replace('Full-size presenter with floating model-name type on lower torso; no reduced speaker panel',
                          'Full-size presenter; only floating verb/possessive/yellow model name; both left text layers removed')
    runner=runner.replace("'previous_v3_preserved':True,", "'previous_v3_preserved':True,'previous_v4_preserved':True,")
    (HERE/'run_render.py').write_text(runner,encoding='utf-8')
    print('Built: both left layers removed; main model color#FFD84D; full presenter and pre12.06s untouched.')


if __name__=='__main__':main()
