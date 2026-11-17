"""Local delivery and encoded-output checks for the confirmed speech/photo edit.

Writes only delivery artifacts. It never edits the composition or input assets.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
OUTPUT = HERE / 'output'
PREVIEW = HERE / 'preview'
VIDEO = OUTPUT / 'onetake_speech_edit_1080p30.mp4'
SOURCE = HERE / 'assets/source.mp4'
RT = json.loads((PROJECT / 'enterprise_demo/runtime_status.json').read_text(encoding='utf-8'))
INPUTS = json.loads((HERE / 'analysis/input_manifest.json').read_text(encoding='utf-8'))
CUES = [3.7, 4.5, 5.8, 7.8, 11.2]
EXPECTED_FRAMES = 454


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_page():
    page = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>图生图口播｜onetake 个人测试</title>
<style>
:root{--paper:#f7f5ef;--ink:#252d27;--mute:#6d756e;--line:#d7ddd3;--green:#385b42}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.8 "Microsoft YaHei",sans-serif}
main{max-width:1360px;margin:auto;padding:25px 30px 48px}.eyebrow{font-size:11px;letter-spacing:.16em;color:var(--mute)}
h1{font-size:30px;line-height:1.4;margin:9px 0}h2{font-size:22px;margin:0 0 10px}p{margin:8px 0 15px}.quiet{color:var(--mute);font-size:13px}
.row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.meta{margin-left:auto;color:var(--mute);font-size:13px}
button,.button{font:inherit;border:1px solid #98a694;border-radius:999px;padding:8px 17px;background:transparent;color:var(--ink);cursor:pointer;text-decoration:none}
button:hover,.button:hover{background:#e9eee4}button:focus-visible,a:focus-visible{outline:3px solid #6b8d69;outline-offset:3px}
button.primary{background:var(--green);border-color:var(--green);color:white}a{color:var(--green);text-underline-offset:4px}
video{display:block;width:100%;aspect-ratio:16/9;background:#202420;border-radius:14px}.movie{margin:16px 0 12px}
.seek{margin:12px 0}.seek button{font-size:13px;padding:6px 13px}section,details{margin-top:25px;padding-top:20px;border-top:1px solid var(--line)}
.photos{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.photos figure{margin:0}.photos img{display:block;width:100%;aspect-ratio:16/9;object-fit:contain;border-radius:7px;background:#e6e6df}
figcaption{font-size:12px;color:var(--mute);padding-top:5px}.note{border-left:3px solid #799477;padding-left:13px}.links{font-size:13px;display:flex;gap:18px;flex-wrap:wrap}summary{cursor:pointer}.source{max-width:800px;margin-top:15px}
@media(max-width:720px){main{padding:18px 12px 35px}h1{font-size:25px}.photos{grid-template-columns:repeat(2,1fr)}.meta{margin-left:0}}
</style></head><body><main>
<div class="eyebrow">ONETAKE / SPEECH-LED EDIT / PERSONAL TEST</div>
<div class="row"><h1>图生图：为什么越改越脏？</h1><span class="meta">15.13 秒 · 1080p30 输出</span></div>
<p class="quiet">按已确认的图1 → 图4表现噪点累积；用同一画框连续衔接，结尾回到主讲人。原口播完整保留。</p>
<div class="row"><button class="primary" id="play">从头播放测试版</button><a class="button" href="output/onetake_speech_edit_1080p30.mp4" download>下载 MP4</a></div>
<video class="movie" id="movie" controls preload="metadata" poster="preview/encoded_poster.jpg" src="output/onetake_speech_edit_1080p30.mp4"></video>
<div class="row seek"><button data-t="3.7">进入配图</button><button data-t="4.5">连续修改</button><button data-t="5.8">噪点</button><button data-t="7.8">越改越脏</button><button data-t="11.2">回到口播</button></div>
<p class="quiet note">这是个人非商业用途的 onetake 测试。照片按用户提供的阶段顺序呈现，未对照片执行 AI 降噪、加噪或人像重生成，也没有捏造噪点百分比。</p>
<section><h2>四张原图顺序</h2><div class="photos">
<figure><img src="assets/image_01.png" alt="图1：起始照片"><figcaption>图1 / 起始</figcaption></figure>
<figure><img src="assets/image_02.png" alt="图2：下一阶段"><figcaption>图2 / 连续修改</figcaption></figure>
<figure><img src="assets/image_03.png" alt="图3：下一阶段"><figcaption>图3 / 连续修改</figcaption></figure>
<figure><img src="assets/image_04.png" alt="图4：最后阶段"><figcaption>图4 / 最后阶段</figcaption></figure>
</div></section>
<details><summary>查看原口播对照与检查记录</summary>
<p class="quiet">原视频为 1280×720；1080p 是合成输出尺寸，不代表原口播变成了原生 1080p。没有替换声音或额外生成配音，没有添加背景音乐。</p>
<p class="quiet note">编码与原声保留检查单独通过；宣传片自动音频阈值未通过。原片是连续口播，本版保留原声，未为了自动分数插入静音或降低音量，因此不宣称所有自动验收项目通过。</p>
<video class="source" id="source" controls preload="none" src="assets/source.mp4"></video>
<div class="links"><a href="preview/encoded_per_second.jpg" target="_blank">成片逐秒图</a><a href="output/final_qa.json">文件与原声检查</a><a href="output/browser_validation.json">播放检查</a><a href="analysis/oracle_report.txt">宣传片自动验收原始报告</a><a href="analysis/input_manifest.json">原素材记录</a></div>
</details>
<p class="quiet">技术检查与审美验收分开记录；未冒称完整听审或已达到某条参考成片的质量。</p>
</main><script>
const movie=document.getElementById('movie'), source=document.getElementById('source');
document.getElementById('play').onclick=async()=>{source.pause();movie.currentTime=0;await movie.play();};
document.querySelectorAll('[data-t]').forEach(b=>b.onclick=()=>{movie.pause();movie.currentTime=Number(b.dataset.t);});
source.addEventListener('play',()=>movie.pause());movie.addEventListener('play',()=>source.pause());
</script></body></html>'''
    assert '????' not in page
    (HERE / 'index.html').write_text(page, encoding='utf-8')


def probe(path):
    return json.loads(subprocess.check_output([
        RT['ffprobe']['path'], '-v', 'error', '-count_frames', '-show_streams',
        '-show_format', '-of', 'json', str(path)], text=True, encoding='utf-8'))


def audio_packets(path):
    data = json.loads(subprocess.check_output([
        RT['ffprobe']['path'], '-v', 'error', '-select_streams', 'a:0', '-show_packets',
        '-show_data_hash', 'sha256', '-show_entries', 'packet=data_hash,size',
        '-of', 'json', str(path)], text=True, encoding='utf-8'))['packets']
    payloads = [(int(p['size']), p['data_hash']) for p in data]
    return payloads, hashlib.sha256(json.dumps(payloads).encode()).hexdigest()


def audio_pcm(path):
    return subprocess.check_output([
        RT['ffmpeg']['path'], '-v', 'error', '-i', str(path), '-map', '0:a:0',
        '-vn', '-ac', '2', '-ar', '44100', '-f', 's16le', 'pipe:1'])


def sheet(path, frames, cols=5):
    face = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 15)
    board = Image.new('RGB', (1920, math.ceil(len(frames) / cols) * 240), '#252d27')
    for i, (n, image) in enumerate(frames):
        x, y = i % cols * 384, i // cols * 240
        board.paste(image, (x, y))
        ImageDraw.Draw(board).text((x + 7, y + 219), f'F{n:04d} / {n/30:.3f}s', font=face, fill='white')
    board.save(path, quality=94)


def verify_video():
    final = probe(VIDEO)
    original = probe(SOURCE)
    video = next(s for s in final['streams'] if s['codec_type'] == 'video')
    audio = next(s for s in final['streams'] if s['codec_type'] == 'audio')
    source_audio = next(s for s in original['streams'] if s['codec_type'] == 'audio')
    preserved = []
    for item in INPUTS['sources']:
        preserved.append({'order': item['order'], 'original': item['original'], 'copy': item['copy'],
                          'original_exists': Path(item['original']).is_file(),
                          'original_hash_matches': Path(item['original']).is_file() and digest(item['original']) == item['sha256'],
                          'copy_hash_matches': digest(item['copy']) == item['sha256']})
    source_packets, source_packet_sha = audio_packets(SOURCE)
    final_packets, final_packet_sha = audio_packets(VIDEO)
    source_pcm, final_pcm = audio_pcm(SOURCE), audio_pcm(VIDEO)
    source_pcm_sha, final_pcm_sha = hashlib.sha256(source_pcm).hexdigest(), hashlib.sha256(final_pcm).hexdigest()
    cap = cv2.VideoCapture(str(VIDEO))
    assert cap.isOpened()
    events = {round(t * 30) for t in (3.42, 4.06, 5.14, 6.96, 9.62, 10.12, *CUES)}
    edges = {e + offset for e in events for offset in (-6, -2, -1, 0, 1, 2, 6) if 0 <= e + offset < EXPECTED_FRAMES}
    means, stds, diffs, seconds, boundary = [], [], [], [], []
    n, previous = 0, None
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        assert bgr.shape == (1080, 1920, 3), (n, bgr.shape)
        gray = cv2.resize(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), (192, 108)).astype(np.float32)
        means.append(float(gray.mean()))
        stds.append(float(gray.std()))
        diffs.append(float(np.abs(gray - previous).mean()) if previous is not None else 0.)
        previous = gray
        if n % 30 == 0 or n == EXPECTED_FRAMES - 1 or n in edges:
            image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).resize((384, 216), Image.Resampling.LANCZOS)
            if n % 30 == 0 or n == EXPECTED_FRAMES - 1:
                seconds.append((n, image))
            if n in edges:
                boundary.append((n, image))
        if n == round(7.8 * 30):
            Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).save(PREVIEW / 'encoded_poster.jpg', quality=95)
        n += 1
    cap.release()
    sheet(PREVIEW / 'encoded_per_second.jpg', seconds)
    for first in range(0, len(boundary), 40):
        sheet(PREVIEW / f'encoded_cues_{first//40:02d}.jpg', boundary[first:first + 40])
    result = {
        'file': str(VIDEO), 'sha256': digest(VIDEO), 'frames': n, 'expected_frames': EXPECTED_FRAMES,
        'width': video['width'], 'height': video['height'], 'fps': video['avg_frame_rate'],
        'duration_seconds': float(final['format']['duration']),
        'audio_codec': audio['codec_name'], 'audio_sample_rate': int(audio['sample_rate']),
        'source_audio_duration_seconds': float(source_audio['duration']),
        'output_audio_duration_seconds': float(audio['duration']),
        'source_audio_packets': len(source_packets), 'output_audio_packets': len(final_packets),
        'source_audio_payload_sha256': source_packet_sha, 'output_audio_payload_sha256': final_packet_sha,
        'exact_original_audio_packet_payloads': source_packets == final_packets,
        'source_decoded_pcm_sha256': source_pcm_sha, 'output_decoded_pcm_sha256': final_pcm_sha,
        'decoded_pcm_identical': source_pcm_sha == final_pcm_sha,
        'source_files': preserved, 'black_frame_candidates': sum(x < 2 for x in means),
        'empty_frame_candidates': sum(x < 2 for x in stds),
        'largest_adjacent_gray_change': max(diffs), 'largest_change_frame': int(np.argmax(diffs)),
        'image_order_confirmed': [1, 2, 3, 4],
        'confirmed_visual_meaning': 'Noise accumulation / 越改越脏; user confirmed after ambiguity check.',
        'source_video_resolution': [1280, 720], 'native_1080p_source_claimed': False,
        'ai_denoising_or_portrait_regeneration_performed': False, 'invented_noise_percentages': False,
        'full_speed_perceptual_listening_verified': False, 'user_aesthetic_acceptance_claimed': False,
        'caption_spatial_acceptance': 'Not certified by this encoder scan; root checks composed keyframes separately.',
        'new_paid_api_calls': 0, 'personal_noncommercial_test': True,
    }
    result['pass'] = (n == EXPECTED_FRAMES and (video['width'], video['height'], video['avg_frame_rate']) == (1920, 1080, '30/1')
                      and abs(result['duration_seconds'] - EXPECTED_FRAMES / 30) < .04
                      and abs(result['source_audio_duration_seconds'] - result['output_audio_duration_seconds']) < .025
                      and (result['exact_original_audio_packet_payloads'] or result['decoded_pcm_identical'])
                      and all(p['original_hash_matches'] and p['copy_hash_matches'] for p in preserved)
                      and result['black_frame_candidates'] == 0 and result['empty_frame_candidates'] == 0)
    (OUTPUT / 'final_qa.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    assert result['pass'], result
    return result


def verify_browser(sha):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        connection = None
        try:
            browser = p.chromium.connect_over_cdp('http://127.0.0.1:9333', timeout=4000)
            connection = 'existing_local_browser'
            context = browser.contexts[0]
        except Exception:
            browser = p.chromium.launch(headless=True)
            connection = 'headless_validation_only'
            context = browser.new_context(viewport={'width':1440, 'height':1000})
        url = (HERE / 'index.html').as_uri()
        tab = next((t for t in context.pages if '/speech_7c1fa1f1/index.html' in t.url), None) or context.new_page()
        errors = []
        tab.on('pageerror', lambda error: errors.append(str(error)))
        tab.goto(url, wait_until='load')
        tab.wait_for_function("document.getElementById('movie').readyState>=1")
        tab.evaluate('document.fonts.ready')
        chinese = '图生图' in tab.title() and '????' not in tab.inner_text('body')
        tab.evaluate("document.getElementById('movie').muted=true;document.getElementById('movie').play()")
        tab.wait_for_timeout(1100)
        advanced = tab.evaluate("document.getElementById('movie').currentTime")
        tab.evaluate("document.getElementById('movie').pause()")
        seeks = []
        for t in CUES:
            tab.click(f'[data-t="{t}"]')
            tab.wait_for_function("!document.getElementById('movie').seeking")
            actual = tab.evaluate("document.getElementById('movie').currentTime")
            assert abs(actual - t) < .1, (t, actual)
            seeks.append(actual)
        tab.wait_for_function("Array.from(document.querySelectorAll('img')).every(i=>i.complete&&i.naturalWidth>0)")
        links = tab.eval_on_selector_all('a[href]', 'els=>els.map(a=>a.getAttribute("href"))')
        missing = [a for a in links if a != 'output/browser_validation.json' and not (HERE / a).resolve().exists()]
        tab.evaluate("(()=>{const v=document.getElementById('movie');v.pause();v.muted=false;v.load();window.scrollTo(0,0)})()")
        tab.wait_for_function("document.getElementById('movie').readyState>=1")
        tab.screenshot(path=str(PREVIEW / 'browser_player.png'), full_page=False)
        if connection == 'existing_local_browser':
            tab.bring_to_front()
        else:
            browser.close()
        result = {'url':url, 'file_sha256':sha, 'validation_surface':connection,
                  'user_browser_opened':connection == 'existing_local_browser', 'chinese_intact':chinese,
                  'main_playback_advanced_seconds':advanced, 'seek_times':seeks,
                  'missing_local_links':missing, 'javascript_errors':errors,
                  'pass':chinese and advanced > .3 and not errors and not missing}
    (OUTPUT / 'browser_validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    assert result['pass'], result
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--page-only', action='store_true')
    args = parser.parse_args()
    PREVIEW.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    build_page()
    if args.page_only:
        print(HERE / 'index.html')
        return
    assert VIDEO.is_file(), 'Wait for root render-ready before final delivery.'
    qa = verify_video()
    browser = verify_browser(qa['sha256'])
    result = {'video':str(VIDEO), 'sha256':qa['sha256'], 'page':str(HERE / 'index.html'),
              'technical_qa_pass':qa['pass'], 'browser_pass':browser['pass'],
              'audio_preserved':qa['exact_original_audio_packet_payloads'] or qa['decoded_pcm_identical'],
              'limitations':['Encoded sample and browser tests are not aesthetic approval.', 'No full-speed perceptual listening certified.']}
    (OUTPUT / 'delivery_manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
