"""Regression-lock unchanged prefix and assert the user's ending layout."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from playwright.sync_api import sync_playwright

HERE=Path(__file__).resolve().parent
PREV=HERE.parent/'raw_v3'


def main():
    errors=[];prefix=[];ending=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        old=browser.new_page(viewport={'width':1920,'height':1080});new=browser.new_page(viewport={'width':1920,'height':1080})
        for page,path in ((old,PREV/'comp.html'),(new,HERE/'comp.html')):
            page.on('pageerror',lambda e:errors.append(str(e)));page.goto(path.as_uri());page.evaluate('__ready')
        for t in (0,1.8,3.6,4.5,5.8,7.8,9.9,10.8,11.5,12.04):
            old.evaluate('(t)=>__seek(t)',t);new.evaluate('(t)=>__seek(t)',t)
            assert old.screenshot()==new.screenshot(),('Prefix changed',t)
            prefix.append(t)
        for t in (12.06,12.20,12.30,12.40,12.65,12.90,13.20,13.65,14.20,14.80,15.10):
            new.evaluate('(t)=>__seek(t)',t);a=new.evaluate('(t)=>__audit(t)',t)
            assert a['carrier']=={'x':0,'y':0,'w':1920,'h':1080},a
            assert a['modelFontSize']==210 and a['verbFontSize']==84,a
            assert a['modelFontSize']>a['verbFontSize']*2
            assert new.evaluate('getComputedStyle(document.getElementById("ending-model")).visibility')==('hidden' if t<13.10 else 'visible')
            b=a['endingModelRect'];assert b['x']>=0 and b['x']+b['w']<=1920 and b['y']+b['h']<=1060,a
            # Large text is on the lower torso, well below face/mouth; no crop.
            assert b['y']>=780 and b['x']>=700,a
            if t>=12.40 and a['caption']:
                b=a['captionRect'];assert abs(b['x']-84)<.1 and b['x']+b['w']<710 and b['y']+b['h']<=1060,a
            if t>=13.65:assert a['endingOpacity']==1
            if t in (12.30,12.65,13.20,13.65,14.20,15.10):
                new.screenshot(path=str(HERE/'preview'/f'overlay_{t:.2f}.jpg'),quality=95,type='jpeg')
            ending.append(a)
        unchanged_post_fix=[]
        draft=HERE/'comp_draft_with_leak.html'
        if draft.is_file():
            prior=browser.new_page(viewport={'width':1920,'height':1080})
            prior.goto(draft.as_uri());prior.evaluate('__ready')
            for t in (13.133333,13.2,13.65,14.2,15.1):
                prior.evaluate('(t)=>__seek(t)',t);new.evaluate('(t)=>__seek(t)',t)
                assert prior.screenshot()==new.screenshot(),('Post-cue pixels changed',t)
                unchanged_post_fix.append(t)
        for t in (12.65,14.2,15.1):
            new.evaluate('(t)=>__seek(t)',t);a=new.screenshot();new.evaluate('__seek(4)');new.evaluate('(t)=>__seek(t)',t)
            assert a==new.screenshot(),('Non-deterministic seek',t)
        browser.close()
    assert not errors,errors
    html=(HERE/'comp.html').read_text(encoding='utf-8');js='\n'.join(re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.S))
    (HERE/'analysis/script.js').write_text(js,encoding='utf-8')
    r=subprocess.run(['node','--check',str(HERE/'analysis/script.js')],capture_output=True,text=True);assert r.returncode==0,r.stderr
    report={'pass':True,'composition_sha256':hashlib.sha256((HERE/'comp.html').read_bytes()).hexdigest(),
            'unchanged_prefix_sample_times':prefix,'prefix_samples_pixel_identical':True,
            'ending_presenter_full_frame':True,'verb_font_size':84,'main_model_font_size':210,
            'caption_left_edge_px':84,'left_caption_applies_from_seconds':12.40,
            'ending_samples':ending,'javascript_errors':errors,'deterministic_seek_checked_at':[12.65,14.2,15.1],
            'model_hidden_before_cue_seconds':13.10,'post_leak_fix_pixel_identical_sample_times':unchanged_post_fix,
            'user_aesthetic_acceptance_claimed':False}
    (HERE/'analysis/composition_checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS: prefix pixel-identical at10 times; person full size; model210>verb84; captions left; seek deterministic.')


if __name__=='__main__':main()
