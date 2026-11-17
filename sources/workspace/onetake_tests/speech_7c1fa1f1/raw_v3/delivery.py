"""Deliver a 4K-source 1080p preview, preserving its NEW AAC and prior versions."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
PROJECT=BASE.parent.parent
OUTPUT=HERE/'output'
PREVIEW=HERE/'preview'
VIDEO=OUTPUT/'onetake_raw_v3_1080p30.mp4'
OLD=BASE/'ending_v2/output/onetake_ending_v2_1080p30.mp4'
V1=BASE/'output/onetake_speech_edit_1080p30.mp4'
SOURCE=HERE/'assets/source.mp4'
RT=json.loads((PROJECT/'enterprise_demo/runtime_status.json').read_text(encoding='utf-8'))
INPUTS=json.loads((HERE/'analysis/input_manifest.json').read_text(encoding='utf-8'))
ALIGNMENT=json.loads((HERE/'analysis/alignment.json').read_text(encoding='utf-8'))


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe(path):
    return json.loads(subprocess.check_output([RT['ffprobe']['path'],'-v','error','-count_frames',
                  '-show_streams','-show_format','-of','json',str(path)],text=True,encoding='utf-8'))


def packets(path):
    rows=json.loads(subprocess.check_output([RT['ffprobe']['path'],'-v','error','-select_streams','a:0',
             '-show_packets','-show_data_hash','sha256','-show_entries','packet=size,data_hash','-of','json',
             str(path)],text=True,encoding='utf-8'))['packets']
    return [(int(r['size']),r['data_hash']) for r in rows]


def pcm(path):
    return subprocess.check_output([RT['ffmpeg']['path'],'-v','error','-i',str(path),'-map','0:a:0',
                                   '-vn','-ac','2','-ar','44100','-f','s16le','pipe:1'])


def audio_packet_times(path):
    rows=json.loads(subprocess.check_output([RT['ffprobe']['path'],'-v','error','-select_streams','a:0',
           '-show_packets','-show_entries','packet=pts,dts','-of','json',str(path)],
           text=True,encoding='utf-8'))['packets']
    return [(int(r['pts']),int(r['dts'])) for r in rows]


def build_page():
    oracle=''
    if (HERE/'analysis/oracle_report.txt').is_file():
        oracle='<a href="analysis/oracle_report.txt">自动验收原始报告</a>'
    if (HERE/'analysis/oracle_interpretation.json').is_file():
        oracle+='<a href="analysis/oracle_interpretation.json">自动验收解释</a>'
    page='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>4K原片重合成 V3｜1080p预览</title><style>
:root{--paper:#f7f5ef;--ink:#28322a;--green:#3b6046;--rust:#9a4e36;--line:#d9ddd3;--mute:#72796f}*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.8 "Microsoft YaHei",sans-serif}main{max-width:1360px;margin:auto;padding:26px 30px 50px}
.eyebrow{font-size:11px;letter-spacing:.16em;color:var(--mute)}h1{font-size:30px;line-height:1.4;margin:8px 0}h2{font-size:21px;margin:7px 0 10px}
p{margin:8px 0 15px}.quiet{font-size:13px;color:var(--mute)}.row{display:flex;align-items:center;flex-wrap:wrap;gap:12px}.meta{margin-left:auto;color:var(--mute);font-size:13px}
a{color:var(--green);text-underline-offset:4px}button,.button{font:inherit;border:1px solid #a5b09f;border-radius:999px;background:transparent;color:var(--ink);padding:8px 16px;cursor:pointer;text-decoration:none}
button.primary{background:var(--rust);border-color:var(--rust);color:white}button:hover,.button:hover{box-shadow:0 0 0 3px #69816413}a:focus-visible,button:focus-visible{outline:3px solid #9cb195;outline-offset:3px}
video{display:block;width:100%;aspect-ratio:16/9;background:#232823;border-radius:14px}#movie{margin:17px 0 12px}.seek{margin:12px 0}.seek button{font-size:13px;padding:6px 13px}
details{margin-top:27px;padding-top:20px;border-top:1px solid var(--line)}summary{cursor:pointer}#old{max-width:920px;margin-top:14px}.note{border-left:3px solid #829678;padding-left:13px}.links{display:flex;gap:17px;flex-wrap:wrap;font-size:13px}
.comparison{display:block;max-width:100%;margin-top:18px;border-radius:9px}@media(max-width:720px){main{padding:18px 12px 35px}h1{font-size:25px}.meta{margin-left:0}}
</style></head><body><main>
<div class="eyebrow">ONETAKE / 4K-SOURCE RECOMPOSITION / V3</div>
<div class="row"><h1>已换用4K原片，重新合成</h1><span class="meta">15.13 秒 · 1080p30 预览</span></div>
<p class="quiet">不再使用720p中间片。口播画面直接从3840×2160原片一次缩至1080p无损PNG，动效、字幕时间及V2加强结尾保持原方案。</p>
<div class="row"><button id="play" class="primary">从头播放高清源 V3</button><button id="ending">看新结尾 · 12.0秒起</button><a class="button" href="output/onetake_raw_v3_1080p30.mp4" download>下载1080p预览</a></div>
<video id="movie" controls preload="metadata" poster="preview/encoded_ending_poster.jpg" src="output/onetake_raw_v3_1080p30.mp4"></video>
<div class="row seek"><button data-t="13.2">关键词落位</button><button data-t="14.2">结尾定格</button><button id="align">V2 / V3 同时刻 · 12秒</button><button id="quality">清晰度对照 · 0.5秒</button></div>
<details id="compare"><summary>与低清源 V2 的同一时刻对照</summary><p class="quiet">两版只定位到同一时刻，播放互斥，避免两条原声同时响起。V2仅作历史对照，不是当前交付。</p>
<div class="row"><button id="old-ending">播放低清 V2 当前时刻</button><a href="../ending_v2/index.html">打开 V2 存档</a><a href="assets/source.mp4">查看3840×2160原片</a></div>
<video id="old" controls preload="none" src="../ending_v2/output/onetake_ending_v2_1080p30.mp4"></video>
<img class="comparison" src="preview/encoded_quality_comparison.jpg" alt="0.5秒同一时刻：左为V2低清源，右为V3高清源1080p输出">
<p class="quiet">左：V2（720p输入）；右：V3（4K输入直接合成1080p）。同刻编码画面对照，不是4K成片，也不代表完整运动或审美验收。</p></details>
<details><summary>技术与使用说明</summary><p class="quiet note">本轮是个人非商业用途的 onetake 测试。编码／原声保留检查与自动宣传片评分分开；oracle分数不是审美保证，也不为了分数给原声插入静音或降低音量。</p>
<p class="quiet">原声保留检查通过；宣传片自动音频阈值未通过。原片是连续口播，不为自动分数改音量或插入静音，因此不能宣称所有自动验收项目通过。</p>
<p class="quiet">本轮使用新4K原片自身的AAC音轨，按新原片逐包核验，不拿旧压缩版的音频哈希作标准。没有更换配音、加背景音乐或为了自动分数改动音量和停顿。</p>
<p class="quiet">这是1080p30预览，不是4K成片；没有超分或额外锐化。V1、V2及新旧原素材仍保留。四张人物图按确认的1→4顺序呈现，没有AI降噪或重生成人像。</p>
<div class="links"><a href="output/final_qa.json">编码与新原声音轨检查</a><a href="output/browser_validation.json">播放检查</a><a href="output/render_manifest.json">渲染记录</a><a href="analysis/composition_checks.json">合成与时间轴检查</a><a href="analysis/source_visual_review.json">原片清晰度审查</a><a href="preview/encoded_per_second.jpg">成片逐秒图</a>__ORACLE__</div>
<p class="quiet">未进行完整听审，不宣称用户已验收通过。</p></details>
</main><script>
const movie=document.getElementById('movie'),old=document.getElementById('old');
const ready=v=>{if(v.readyState>=1)return Promise.resolve();v.load();return new Promise((resolve,reject)=>{v.addEventListener('loadedmetadata',resolve,{once:true});v.addEventListener('error',reject,{once:true});});};
movie.addEventListener('play',()=>old.pause());old.addEventListener('play',()=>movie.pause());
document.getElementById('play').onclick=async()=>{old.pause();movie.currentTime=0;await movie.play();};
document.getElementById('ending').onclick=async()=>{old.pause();movie.currentTime=12;await movie.play();};
document.querySelectorAll('[data-t]').forEach(b=>b.onclick=()=>{movie.pause();movie.currentTime=Number(b.dataset.t);});
const alignAt=async(t)=>{document.getElementById('compare').open=true;movie.pause();old.pause();await Promise.all([ready(movie),ready(old)]);movie.currentTime=t;old.currentTime=t;};
document.getElementById('align').onclick=()=>alignAt(12);
document.getElementById('quality').onclick=()=>alignAt(.5);
document.getElementById('old-ending').onclick=async()=>{await ready(old);movie.pause();await old.play();};
</script></body></html>'''.replace('__ORACLE__',oracle)
    assert '????' not in page
    (HERE/'index.html').write_text(page,encoding='utf-8')


def make_sheet(path,items):
    face=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',15)
    board=Image.new('RGB',(1920,math.ceil(len(items)/5)*240),'#28322a')
    for i,(n,im) in enumerate(items):
        x=i%5*384;y=i//5*240;board.paste(im,(x,y))
        ImageDraw.Draw(board).text((x+7,y+219),f'F{n:04d} / {n/30:.3f}s',font=face,fill='white')
    board.save(path,quality=94)


def read_frame(path,seconds):
    cap=cv2.VideoCapture(str(path));assert cap.isOpened()
    # Decode sequentially. Random seeking near the ending has returned stale
    # video/caption frames with this local OpenCV/codec combination.
    target=min(round(seconds*30),int(cap.get(cv2.CAP_PROP_FRAME_COUNT))-1)
    for _ in range(target+1):
        ok,bgr=cap.read();assert ok
    cap.release()
    return Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))


def verify_video():
    manifest=json.loads((OUTPUT/'render_manifest.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'analysis/composition_checks.json').read_text(encoding='utf-8'))
    vdata=probe(VIDEO);sdata=probe(SOURCE)
    video=next(s for s in vdata['streams'] if s['codec_type']=='video')
    source_video=next(s for s in sdata['streams'] if s['codec_type']=='video')
    audio=next(s for s in vdata['streams'] if s['codec_type']=='audio')
    source_audio=next(s for s in sdata['streams'] if s['codec_type']=='audio')
    original_packets,final_packets=packets(SOURCE),packets(VIDEO)
    original_times,final_times=audio_packet_times(SOURCE),audio_packet_times(VIDEO)
    original_pcm,final_pcm=pcm(SOURCE),pcm(VIDEO)
    preserved=[]
    seen=set()
    for group in ('sources','previous_sources'):
        for item in INPUTS[group]:
            identity=(item['original'],item['copy'])
            if identity in seen:continue
            seen.add(identity)
            preserved.append({'group':group,'order':item['order'],'file':Path(item['original']).name,
                              'original_hash_matches':sha(item['original'])==item['sha256'],
                              'copy_hash_matches':sha(item['copy'])==item['sha256']})
    cap=cv2.VideoCapture(str(VIDEO));assert cap.isOpened()
    seconds=[];endings=[];means=[];stds=[];n=0
    while True:
        ok,bgr=cap.read()
        if not ok:break
        assert bgr.shape==(1080,1920,3)
        gray=cv2.resize(cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY),(192,108)).astype(np.float32)
        means.append(float(gray.mean()));stds.append(float(gray.std()))
        if n%30==0 or n==453 or (n>=360 and n%3==0):
            im=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)).resize((384,216),Image.Resampling.LANCZOS)
            if n%30==0 or n==453:seconds.append((n,im))
            if n>=360:endings.append((n,im))
        n+=1
    cap.release()
    make_sheet(PREVIEW/'encoded_per_second.jpg',seconds)
    make_sheet(PREVIEW/'encoded_ending.jpg',endings)
    read_frame(VIDEO,14.2).save(PREVIEW/'encoded_ending_poster.jpg',quality=95)
    board=Image.new('RGB',(1920,620),'#f7f5ef');draw=ImageDraw.Draw(board)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',27)
    draw.text((22,11),'V2 / 720p source / 0.50s',font=font,fill='#28322a')
    draw.text((982,11),'V3 / 4K source -> 1080p / 0.50s',font=font,fill='#28322a')
    board.paste(read_frame(OLD,.5).resize((960,540)),(0,55))
    board.paste(read_frame(VIDEO,.5).resize((960,540)),(960,55))
    board.save(PREVIEW/'encoded_quality_comparison.jpg',quality=95)
    frame_dimensions={str(n):list(Image.open(HERE/'assets/speech_frames'/f'{n:06d}.png').size) for n in (0,226,452)}
    result={'file':str(VIDEO),'sha256':sha(VIDEO),'render_manifest_hash_matches':sha(VIDEO)==manifest['sha256'],
            'frames':n,'expected_frames':454,'width':video['width'],'height':video['height'],'fps':video['avg_frame_rate'],
            'duration_seconds':float(vdata['format']['duration']),'audio_codec':audio['codec_name'],
            'audio_sample_rate':int(audio['sample_rate']),'source_audio_duration_seconds':float(source_audio['duration']),
            'output_audio_duration_seconds':float(audio['duration']),'source_audio_packets':len(original_packets),
            'output_audio_packets':len(final_packets),'original_aac_packet_payloads_identical':original_packets==final_packets,
            'new_source_audio_pts_dts_identical':original_times==final_times,
            'source_pcm_sha256':hashlib.sha256(original_pcm).hexdigest(),'output_pcm_sha256':hashlib.sha256(final_pcm).hexdigest(),
            'decoded_pcm_identical':original_pcm==final_pcm,
            'audio_reference':'NEW raw_v3/assets/source.mp4, not the previous compressed AAC encoding',
            'new_source_pcm_matches_alignment':hashlib.sha256(original_pcm).hexdigest()==ALIGNMENT['new_decoded_pcm_sha256'],
            'old_v1_sha256':sha(V1),'old_v1_unchanged':sha(V1)==INPUTS['previous_v1_sha256'],
            'old_v2_sha256':sha(OLD),'old_v2_unchanged':sha(OLD)==INPUTS['previous_v2_sha256'],
            'old_v2_comp_unchanged':sha(BASE/'ending_v2/comp.html')==INPUTS['previous_comp_sha256'],'source_files':preserved,
            'composition_check_pass':checks['pass'],'composition_check_hash_current':sha(HERE/'comp.html')==checks['composition_sha256'],
            'encoded_prefix_pixel_identity_claimed':False,'black_frame_candidates':sum(x<2 for x in means),
            'empty_frame_candidates':sum(x<2 for x in stds),
            'source_video_resolution':[source_video['width'],source_video['height']],
            'source_video_frames':int(source_video['nb_read_frames']),
            'decoded_png_sample_dimensions':frame_dimensions,'frame_pipeline':INPUTS['frame_pipeline'],
            'output_is_4k_claimed':False,'ai_upscaling_or_added_sharpening_claimed':False,
            'full_speed_perceptual_listening_verified':False,'user_aesthetic_acceptance_claimed':False,
            'all_oracle_legs_pass_claimed':False,'new_paid_api_calls':0,'personal_noncommercial_test':True}
    result['pass']=(n==454 and (video['width'],video['height'],video['avg_frame_rate'])==(1920,1080,'30/1')
                    and abs(result['duration_seconds']-454/30)<.04 and result['render_manifest_hash_matches']
                    and result['original_aac_packet_payloads_identical'] and result['decoded_pcm_identical']
                    and result['new_source_audio_pts_dts_identical']
                    and abs(result['source_audio_duration_seconds']-result['output_audio_duration_seconds'])<.025
                    and result['new_source_pcm_matches_alignment']
                    and result['old_v1_unchanged'] and result['old_v2_unchanged'] and result['old_v2_comp_unchanged']
                    and result['source_video_resolution']==[3840,2160] and result['source_video_frames']==453
                    and all(d==[1920,1080] for d in frame_dimensions.values())
                    and all(p['original_hash_matches'] and p['copy_hash_matches'] for p in preserved)
                    and result['composition_check_pass'] and result['composition_check_hash_current']
                    and result['black_frame_candidates']==0 and result['empty_frame_candidates']==0)
    (OUTPUT/'final_qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    assert result['pass'],result
    return result


def verify_browser(digest):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            browser=p.chromium.connect_over_cdp('http://127.0.0.1:9333',timeout=4000)
            context=browser.contexts[0];surface='existing_local_browser'
        except Exception:
            browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':1000})
            surface='headless_validation_only'
        url=(HERE/'index.html').as_uri()
        tab=next((t for t in context.pages if '/raw_v3/index.html' in t.url),None) or context.new_page()
        errors=[];tab.on('pageerror',lambda e:errors.append(str(e)))
        tab.goto(url,wait_until='load');tab.wait_for_function("document.getElementById('movie').readyState>=1")
        tab.evaluate('document.fonts.ready')
        chinese='V3' in tab.title() and '????' not in tab.inner_text('body')
        tab.evaluate("document.getElementById('movie').muted=true")
        tab.click('#play');tab.wait_for_timeout(900)
        advanced=tab.evaluate("document.getElementById('movie').currentTime")
        tab.click('#ending');tab.wait_for_timeout(700)
        ending=tab.evaluate("document.getElementById('movie').currentTime")
        tab.evaluate("document.getElementById('movie').pause()")
        seeks=[]
        for t in (13.2,14.2):
            tab.click(f'[data-t="{t}"]');tab.wait_for_function("!document.getElementById('movie').seeking")
            seeks.append(tab.evaluate("document.getElementById('movie').currentTime"))
        tab.click('#align');tab.wait_for_function("document.getElementById('old').readyState>=1&&!document.getElementById('old').seeking&&!document.getElementById('movie').seeking")
        aligned=tab.evaluate("[document.getElementById('movie').currentTime,document.getElementById('old').currentTime]")
        tab.click('#quality');tab.wait_for_function("!document.getElementById('old').seeking&&!document.getElementById('movie').seeking")
        quality_aligned=tab.evaluate("[document.getElementById('movie').currentTime,document.getElementById('old').currentTime]")
        tab.evaluate("document.getElementById('old').muted=true;document.getElementById('old').play()")
        tab.wait_for_timeout(400)
        old_exclusive=tab.evaluate("document.getElementById('movie').paused&&!document.getElementById('old').paused")
        tab.evaluate("document.getElementById('movie').play()")
        tab.wait_for_timeout(400)
        new_exclusive=tab.evaluate("document.getElementById('old').paused&&!document.getElementById('movie').paused")
        tab.evaluate("document.getElementById('movie').pause()")
        tab.wait_for_function("Array.from(document.querySelectorAll('img')).every(i=>i.complete&&i.naturalWidth>0)")
        links=tab.eval_on_selector_all('a[href]','es=>es.map(e=>e.getAttribute("href"))')
        missing=[s for s in links if s!='output/browser_validation.json' and not (HERE/s).resolve().exists()]
        tab.evaluate("(()=>{const m=document.getElementById('movie'),o=document.getElementById('old');m.pause();o.pause();m.muted=false;o.muted=false;m.load();document.querySelectorAll('details').forEach(d=>d.open=false);window.scrollTo(0,0)})()")
        tab.wait_for_function("document.getElementById('movie').readyState>=1")
        tab.screenshot(path=str(PREVIEW/'browser_player.png'),full_page=False)
        if surface=='existing_local_browser':tab.bring_to_front()
        else:browser.close()
        result={'url':url,'file_sha256':digest,'surface':surface,'user_browser_opened':surface=='existing_local_browser',
                'chinese_intact':chinese,'main_playback_advanced_seconds':advanced,'ending_playback_position':ending,
                'seek_times':seeks,'aligned_v3_v2_times':aligned,'quality_aligned_v3_v2_times':quality_aligned,
                'old_playback_pauses_v3':old_exclusive,
                'v3_playback_pauses_old':new_exclusive,'missing_local_links':missing,'javascript_errors':errors}
        result['pass']=(chinese and advanced>.3 and 12.2<ending<13.2 and all(abs(x-y)<.1 for x,y in zip(seeks,(13.2,14.2)))
                        and all(abs(x-12)<.1 for x in aligned) and all(abs(x-.5)<.1 for x in quality_aligned)
                        and old_exclusive and new_exclusive and not missing and not errors)
    (OUTPUT/'browser_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    assert result['pass'],result
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--page-only',action='store_true');args=parser.parse_args()
    PREVIEW.mkdir(exist_ok=True);OUTPUT.mkdir(exist_ok=True);build_page()
    if args.page_only:print(HERE/'index.html');return
    assert VIDEO.is_file(),'Wait for root render-ready.'
    qa=verify_video();br=verify_browser(qa['sha256'])
    print(json.dumps({'file':str(VIDEO),'sha256':qa['sha256'],'technical_pass':qa['pass'],'browser_pass':br['pass'],
                      'page':str(HERE/'index.html')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
