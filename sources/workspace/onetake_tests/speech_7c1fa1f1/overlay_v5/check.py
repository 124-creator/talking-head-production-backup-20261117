from pathlib import Path
import hashlib
import json
import re
import subprocess
from playwright.sync_api import sync_playwright

HERE=Path(__file__).resolve().parent


def main():
    errors=[];prefix=[];samples=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        old=browser.new_page(viewport={'width':1920,'height':1080});new=browser.new_page(viewport={'width':1920,'height':1080})
        for page,path in ((old,HERE.parent/'overlay_v4/comp.html'),(new,HERE/'comp.html')):
            page.on('pageerror',lambda e:errors.append(str(e)));page.goto(path.as_uri());page.evaluate('__ready')
        for t in (0,1.8,3.6,4.5,5.8,7.8,9.9,10.8,11.5,12.04):
            old.evaluate('(t)=>__seek(t)',t);new.evaluate('(t)=>__seek(t)',t)
            assert old.screenshot()==new.screenshot(),('Prefix changed',t);prefix.append(t)
        for t in (12.06,12.20,12.40,12.65,12.90,13.20,13.65,14.20,14.80,15.10):
            new.evaluate('(t)=>__seek(t)',t);a=new.evaluate('(t)=>__audit(t)',t)
            assert a['carrier']=={'x':0,'y':0,'w':1920,'h':1080}
            assert a['caption']=='' and a['captionRect']['w']==0,a
            assert a['endingKickerDisplay']=='none',a
            assert a['mainModelColor']=='rgb(255, 216, 77)',a
            assert a['modelFontSize']==210 and a['verbFontSize']==84,a
            assert new.evaluate('getComputedStyle(document.getElementById("ending-model")).visibility')==('hidden' if t<13.10 else 'visible')
            visible_text=new.evaluate('Array.from(document.querySelectorAll("#ending-kicker,#ending-big,#ending-model,#ending-video-label,#subtitle")).filter(e=>{const c=getComputedStyle(e),b=e.getBoundingClientRect();return c.display!=="none"&&c.visibility!=="hidden"&&+c.opacity>0&&b.width&&b.height}).map(e=>e.textContent)')
            assert '这条视频，可能会' not in visible_text
            if t>=13.65:assert visible_text==['换掉','主力模型','你的'],visible_text
            if t in (12.65,13.20,14.20,15.10):new.screenshot(path=str(HERE/'preview'/f'clean_{t:.2f}.jpg'),quality=95,type='jpeg')
            samples.append({'seconds':t,'visible_text':visible_text,'audit':a})
        for t in (12.65,14.2,15.1):
            new.evaluate('(t)=>__seek(t)',t);a=new.screenshot();new.evaluate('__seek(4)');new.evaluate('(t)=>__seek(t)',t);assert a==new.screenshot()
        browser.close()
    assert not errors,errors
    html=(HERE/'comp.html').read_text(encoding='utf-8')
    js='\n'.join(re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.S));(HERE/'analysis/script.js').write_text(js,encoding='utf-8')
    r=subprocess.run(['node','--check',str(HERE/'analysis/script.js')],capture_output=True,text=True);assert r.returncode==0,r.stderr
    report={'pass':True,'composition_sha256':hashlib.sha256((HERE/'comp.html').read_bytes()).hexdigest(),
            'unchanged_prefix_sample_times':prefix,'prefix_samples_pixel_identical':True,'ending_presenter_full_frame':True,
            'ending_caption_hidden':True,'ending_left_kicker_hidden':True,'main_model_color':'#FFD84D',
            'only_ending_overlay_words':['换掉','你的','主力模型'],'main_model_font_size':210,'verb_font_size':84,
            'samples':samples,'javascript_errors':errors,'seek_deterministic':True,'user_aesthetic_acceptance_claimed':False}
    (HERE/'analysis/composition_checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS: prefix unchanged; no left text or duplicate captions; model yellow; full actor; deterministic seek.')


if __name__=='__main__':main()
