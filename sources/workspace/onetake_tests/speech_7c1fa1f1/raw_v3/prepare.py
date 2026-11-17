"""Use the user's 4K original, preserving the V2 timing, motion and type."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import numpy as np
from scipy.signal import correlate, correlation_lags

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PREVIOUS = BASE/'ending_v2'
PROJECT = BASE.parent.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    for p in ('analysis', 'assets/speech_frames', 'preview', 'output'):
        (HERE/p).mkdir(parents=True, exist_ok=True)
    rt = json.loads((PROJECT/'enterprise_demo/runtime_status.json').read_text(encoding='utf-8'))
    original = json.loads((BASE/'analysis/input_manifest.json').read_text(encoding='utf-8'))
    source = Path(original['sources'][0]['original']).with_name('7c1fa1f1aaae6edc410a3c1471c65f4d_raw.mp4')
    assert source.is_file()
    source_sha = sha(source)
    assert source_sha == '93dfe4aeddead66652af44422e2b643a9b6f258deaf683874f700955b2e03bd1'
    copied = HERE/'assets/source.mp4'
    if not copied.exists():
        shutil.copy2(source, copied)
    assert sha(copied) == source_sha
    probe = json.loads(subprocess.check_output([rt['ffprobe']['path'], '-v', 'error', '-show_streams',
                       '-show_format', '-of', 'json', str(copied)], encoding='utf-8'))
    (HERE/'analysis/source_probe.json').write_text(json.dumps(probe, ensure_ascii=False, indent=2), encoding='utf-8')
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    assert (video['width'], video['height'], video['avg_frame_rate'], int(video['nb_frames'])) == (3840,2160,'30/1',453)

    def packets(path):
        return json.loads(subprocess.check_output([rt['ffprobe']['path'], '-v', 'error', '-select_streams', 'a:0',
            '-show_packets', '-show_data_hash', 'sha256', '-show_entries', 'packet=pts,dts,duration,size,data_hash',
            '-of', 'json', str(path)], encoding='utf-8'))['packets']

    old_packets, new_packets = packets(BASE/'assets/source.mp4'), packets(copied)
    assert len(old_packets) == len(new_packets) == 652
    assert [(x['pts'],x['dts']) for x in old_packets] == [(x['pts'],x['dts']) for x in new_packets]
    def pcm(path):
        return subprocess.check_output([rt['ffmpeg']['path'], '-v', 'error', '-i', str(path),
            '-map', '0:a:0', '-vn', '-f', 's16le', '-ac', '2', '-ar', '44100', 'pipe:1'])
    old_pcm, new_pcm = pcm(BASE/'assets/source.mp4'), pcm(copied)
    assert len(old_pcm) == len(new_pcm)
    x = np.frombuffer(old_pcm,dtype='<i2').reshape(-1,2).astype(float).mean(axis=1)[::4]
    y = np.frombuffer(new_pcm,dtype='<i2').reshape(-1,2).astype(float).mean(axis=1)[::4]
    windows = []
    for t in (0,4,8,12):
        a,b=x[t*11025:(t+2)*11025],y[t*11025:(t+2)*11025]
        a=a-a.mean();b=b-b.mean();c=correlate(a,b,method='fft');lags=correlation_lags(len(a),len(b))
        keep=np.abs(lags)<=220;offset=int(lags[keep][np.argmax(c[keep])])
        corr=float(np.corrcoef(a,b)[0,1]);assert offset==0 and corr>.95,(t,offset,corr)
        windows.append({'start_seconds':t,'duration_seconds':2,'best_offset_samples_at_11025hz':offset,'zero_lag_correlation':corr})
    alignment = {'same_duration': float(video['duration']) == 15.1,
                 'same_video_frame_count': int(video['nb_frames']) == 453,
                 'same_video_fps': video['avg_frame_rate'] == '30/1',
                 'aac_pts_dts_identical_to_previous_source': True,
                 'aac_packet_payloads_identical_to_previous_source': old_packets == new_packets,
                 'aac_packet_count': len(new_packets),
                 'old_decoded_pcm_sha256':hashlib.sha256(old_pcm).hexdigest(),
                 'new_decoded_pcm_sha256':hashlib.sha256(new_pcm).hexdigest(),
                 'decoded_sample_count_equal':True, 'cross_correlation_windows':windows,
                 'last_packet_duration_difference_samples':old_packets[-1]['duration']-new_packets[-1]['duration'],
                 'conclusion': 'New original has a different AAC encoding. Speech timing matches at all packet PTS/DTS and four waveform windows with zero offset; reuse established word/caption timing. Output must preserve the NEW original AAC, not the previous compressed audio.'}
    (HERE/'analysis/alignment.json').write_text(json.dumps(alignment, ensure_ascii=False, indent=2), encoding='utf-8')
    manifest = {
        'source_resolution': [3840,2160], 'decoded_frame_resolution': [1920,1080],
        'frame_pipeline': '4K HEVC -> one Lanczos reduction to output-native 1080p -> lossless RGB PNG; no 720p intermediary, added sharpening or AI upscaling',
        'sources': [{'order':0, 'original':str(source), 'copy':str(copied), 'sha256':source_sha,
                     'bytes':source.stat().st_size, 'dimensions':[3840,2160]}]+original['sources'][1:],
        'previous_sources':original['sources'],
        'previous_v1_sha256': sha(BASE/'output/onetake_speech_edit_1080p30.mp4'),
        'previous_v2_sha256': sha(PREVIOUS/'output/onetake_ending_v2_1080p30.mp4'),
        'previous_comp_sha256': sha(PREVIOUS/'comp.html'),
        'image_order':[1,2,3,4], 'audio_timeline_unchanged':True
    }
    (HERE/'analysis/input_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    html = (PREVIOUS/'comp.html').read_text(encoding='utf-8')
    assert html.count('../assets/speech_frames/') == 2
    html = html.replace('../assets/speech_frames/', 'assets/speech_frames/')
    html = html.replace('assets/speech_frames/000000.jpg','assets/speech_frames/000000.png')
    assert html.count("padStart(6,'0')}.jpg") == 1
    html = html.replace("padStart(6,'0')}.jpg", "padStart(6,'0')}.png")
    html = html.replace('<title>图生图 · 结尾强化版</title>', '<title>图生图 · 4K原片重合成预览</title>')
    html = html.replace('sourceFrames:453,', 'sourceResolution:[3840,2160],decodedFrameResolution:[1920,1080],sourceFrames:453,')
    (HERE/'comp.html').write_text(html, encoding='utf-8')
    shutil.copy2(PREVIOUS/'look.js', HERE/'look.js')
    frames = HERE/'assets/speech_frames'
    existing = list(frames.glob('*.png'))
    if not existing:
        print('Extracting output-native PNG frames directly from 4K original...', flush=True)
        subprocess.run([rt['ffmpeg']['path'], '-hide_banner', '-loglevel', 'warning', '-n',
            '-i', str(copied), '-map', '0:v:0', '-an',
            '-vf', 'scale=1920:1080:flags=lanczos,format=rgb24', '-fps_mode', 'passthrough',
            '-compression_level', '3', '-start_number', '0', str(frames/'%06d.png')], check=True)
    else:
        assert len(existing) == 453, 'Partial extraction: inspect rather than overwrite.'
    assert len(list(frames.glob('*.png'))) == 453
    print('Prepared 4K-source composition and 453 lossless PNGs; timing aligned, new original audio retained.', flush=True)


if __name__ == '__main__':
    main()
