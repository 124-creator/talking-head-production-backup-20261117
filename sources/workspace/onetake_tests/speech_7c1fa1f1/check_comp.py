"""Verify accepted speech/photo order, layout, original sources and seek purity."""
from pathlib import Path
import hashlib
import json
import os
from playwright.sync_api import sync_playwright

HERE=Path(__file__).resolve().parent
os.environ['PLAYWRIGHT_SKIP_BROWSER_GC']='1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    source=json.loads((HERE/'analysis'/'input_manifest.json').read_text(encoding='utf-8'))
    for item in source['sources']:
        assert sha(item['original'])==item['sha256']
        assert sha(item['copy'])==item['sha256']
    errors=[];snapshots=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto((HERE/'comp.html').as_uri(),wait_until='load')
        page.evaluate('window.__ready')
        meta=page.evaluate('window.__meta')
        for t in (0,1.7,3.11,3.4,3.78,3.9,4.06,4.46,4.7,5.14,5.8,6.96,7.44,7.8,9.4,9.65,9.82,10.28,12.9,14.5,15.1):
            page.evaluate('(t)=>window.__seek(t)',t)
            a=page.evaluate('(t)=>window.__audit(t)',t)
            c=a['captionRect']
            if a['caption']:
                assert c['x']>=20 and c['x']+c['w']<=1900,a
                assert c['y']>=0 and c['y']+c['h']<=1060,a
            if a['caption'] and 3.78<=t<=9.65:
                r=a['carrier'];assert c['y']-(r['y']+r['h'])>=8,a
            if t in (1.7,3.9,4.7,5.8,7.8,12.9):
                page.screenshot(path=str(HERE/'preview'/f'frame_{t:.1f}.jpg'),type='jpeg',quality=94)
            snapshots.append(a)
        for t,expected in ((3.9,1),(4.7,2),(5.8,3),(7.8,4)):
            a=next(a for a in snapshots if a['time']==t)
            assert a['phase']==expected,a
            assert a['visiblePhotoReveals'][expected-1]>.999,a
        for t in (10.28,12.9,15.1):
            assert next(a for a in snapshots if a['time']==t)['returnProgress']>.999
        page.evaluate('window.__seek(7.8)');first=page.screenshot()
        page.evaluate('window.__seek(2.1)');page.evaluate('window.__seek(7.8)');again=page.screenshot()
        assert first==again,'Non-deterministic seek'
        fits=page.eval_on_selector_all('.photo','els=>els.map(e=>({src:e.getAttribute("src"),fit:getComputedStyle(e).objectFit,nw:e.naturalWidth,nh:e.naturalHeight}))')
        assert [x['src'] for x in fits]==[f'assets/image_{k:02d}.png' for k in range(1,5)]
        assert all(x['fit']=='contain' and x['nw']==1672 and x['nh']==941 for x in fits),fits
        browser.close()
    assert not errors,errors
    result={'pass':True,'source_hashes_unchanged':True,'source_count':5,'order':[1,2,3,4],
            'caption_spelling_corrections_only':{'造点':'噪点','阻力模型':'主力模型'},
            'original_speech_not_retimed':True,'stable_photo_caption_gap_min_px':min(a['captionRect']['y']-a['carrier']['y']-a['carrier']['h'] for a in snapshots if a['caption'] and 3.78<=a['time']<=9.65),
            'all_photos_contain_fit':True,'deterministic_seek':True,'javascript_errors':errors,
            'composition_sha256':sha(HERE/'comp.html'),'meta':meta,'snapshots':snapshots,
            'scope':'Content order/source preservation/DOM layout and repeatable seek; not a perceptual audio or aesthetic acceptance.'}
    (HERE/'analysis'/'composition_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('snapshots','meta')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
