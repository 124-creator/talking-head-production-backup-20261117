from pathlib import Path
import hashlib
import json
import re
import subprocess
from playwright.sync_api import sync_playwright

HERE=Path(__file__).resolve().parent
BASE=HERE.parent


def main():
    baseline=json.loads((HERE/'analysis/baseline.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(Path(baseline['base_video']).read_bytes()).hexdigest()==baseline['base_sha256']
    errors=[];before=[];frames=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        old=browser.new_page(viewport={'width':1920,'height':1080})
        new=browser.new_page(viewport={'width':1920,'height':1080})
        for page in (old,new):page.on('pageerror',lambda e:errors.append(str(e)))
        old.goto((BASE/'comp.html').as_uri());old.evaluate('window.__ready')
        new.goto((HERE/'comp.html').as_uri());new.evaluate('window.__ready')
        for t in (0,1.7,3.5,3.9,4.7,5.8,7.8,9.9,10.5,11.5,12.04):
            old.evaluate('(t)=>__seek(t)',t);new.evaluate('(t)=>__seek(t)',t)
            same=old.screenshot()==new.screenshot()
            assert same,('Prefix changed',t)
            before.append({'seconds':t,'pixel_identical':same})
        for t in (12.06,12.20,12.30,12.45,12.65,12.90,13.20,13.65,14.20,14.80,15.10):
            new.evaluate('(t)=>__seek(t)',t)
            info=new.evaluate('(t)=>__audit(t)',t)
            c=info['carrier'];assert c['x']>=-.5 and c['y']>=-.5 and c['x']+c['w']<=1920.5 and c['y']+c['h']<=1080.5,info
            if t>=12.90:
                assert abs(c['x']-1040)<.5 and abs(c['w']-800)<.5,info
                assert abs(c['w']/c['h']-16/9)<.001
            if t>=13.65:
                b=info['endingRect'];m=info['endingModelRect']
                assert b['x']>=70 and b['x']+b['w']<=950,info
                assert m['y']+m['h']<=940,info
                assert info['endingOpacity']==1,info
            if info['caption']:
                b=info['captionRect'];assert b['x']>=20 and b['x']+b['w']<=1900 and b['y']+b['h']<=1060
            if t in (12.30,12.65,13.20,13.65,14.20,15.10):
                new.screenshot(path=str(HERE/'preview'/f'ending_{t:.2f}.jpg'),quality=95,type='jpeg')
            frames.append(info)
        new.evaluate('__seek(14.2)');a=new.screenshot();new.evaluate('__seek(4)');new.evaluate('__seek(14.2)');assert a==new.screenshot()
        browser.close()
    assert not errors,errors
    html=(HERE/'comp.html').read_text(encoding='utf-8')
    js='\n'.join(re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.S))
    (HERE/'analysis/script.js').write_text(js,encoding='utf-8')
    r=subprocess.run(['node','--check',str(HERE/'analysis/script.js')],capture_output=True,text=True);assert r.returncode==0,r.stderr
    report={'pass':True,'prefix_comparison':before,'base_version_preserved':True,
            'ending_hold_to_last_frame':True,'presenter_full_16by9_preserved':True,
            'conditional_wording_present':'这条视频，可能会' in html,
            'javascript_errors':errors,'composition_sha256':hashlib.sha256((HERE/'comp.html').read_bytes()).hexdigest(),
            'ending_keyframes':frames,'not_aesthetic_acceptance':True}
    (HERE/'analysis/checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS: prefix identical at11 sample times; ending safe, deterministic and holds through last frame.')


if __name__=='__main__':main()
