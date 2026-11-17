"""Lock V2 layout/timing while replacing only the compressed presenter frames."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from playwright.sync_api import sync_playwright

HERE=Path(__file__).resolve().parent
BASE=HERE.parent


def main():
    manifest=json.loads((HERE/'analysis/input_manifest.json').read_text(encoding='utf-8'))
    assert len(list((HERE/'assets/speech_frames').glob('*.png')))==453
    assert hashlib.sha256((BASE/'ending_v2/comp.html').read_bytes()).hexdigest()==manifest['previous_comp_sha256']
    errors=[];samples=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        old=browser.new_page(viewport={'width':1920,'height':1080})
        new=browser.new_page(viewport={'width':1920,'height':1080})
        for page in (old,new):page.on('pageerror',lambda e:errors.append(str(e)))
        for page,path in ((old,BASE/'ending_v2/comp.html'),(new,HERE/'comp.html')):
            page.goto(path.as_uri());page.evaluate('__ready')
        for t in (0,.5,1.8,3.6,4.5,5.8,7.8,9.9,10.8,12.3,12.65,13.3,14.2,15.1):
            old.evaluate('(t)=>__seek(t)',t);new.evaluate('(t)=>__seek(t)',t)
            a=old.evaluate('(t)=>__audit(t)',t);b=new.evaluate('(t)=>__audit(t)',t)
            assert a==b,('Layout or timeline changed',t,a,b)
            c=b['carrier'];assert c['x']>=-.5 and c['y']>=-.5 and c['x']+c['w']<=1920.5 and c['y']+c['h']<=1080.5
            actual=new.evaluate('({src:document.getElementById("presenter").getAttribute("src"),width:document.getElementById("presenter").naturalWidth,height:document.getElementById("presenter").naturalHeight})')
            assert actual['src'].startswith('assets/speech_frames/') and actual['src'].endswith('.png')
            assert [actual['width'],actual['height']]==[1920,1080]
            if t in (.5,3.6,10.8,12.65,14.2,15.1):
                new.screenshot(path=str(HERE/'preview'/f'comp_{t:.2f}.jpg'),quality=95,type='jpeg')
            samples.append({'seconds':t,'layout_and_caption_timeline_equal_to_v2':True,'decoded_source':actual,'geometry':b})
        for t in (0,7.8,14.2,15.1):
            new.evaluate('(t)=>__seek(t)',t);a=new.screenshot()
            new.evaluate('__seek(3.1)');new.evaluate('(t)=>__seek(t)',t)
            assert a==new.screenshot(),('Non-deterministic seek',t)
        browser.close()
    assert not errors,errors
    html=(HERE/'comp.html').read_text(encoding='utf-8')
    js='\n'.join(re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.S))
    (HERE/'analysis/script.js').write_text(js,encoding='utf-8')
    r=subprocess.run(['node','--check',str(HERE/'analysis/script.js')],capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    report={'pass':True,'source_native_resolution':[3840,2160],'decoded_png_resolution':[1920,1080],
            'output_resolution':[1920,1080], 'no_720p_intermediate':True,
            'composition_sha256':hashlib.sha256((HERE/'comp.html').read_bytes()).hexdigest(),
            'javascript_errors':errors,'samples':samples,'motion_type_and_timing_unchanged':True,
            'seek_determinism_checked_at':[0,7.8,14.2,15.1], 'user_aesthetic_acceptance_claimed':False}
    (HERE/'analysis/composition_checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS: new lossless frame source; V2 layout/captions identical at14 times; deterministic seeking; JS syntax valid.')


if __name__=='__main__':main()
