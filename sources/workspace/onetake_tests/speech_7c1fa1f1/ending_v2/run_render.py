"""Render only the ending; reuse the unchanged, verified V1 PNG prefix."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PROJECT = BASE.parent.parent
SKILL = Path.home() / '.codex/skills/onetake'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    baseline = json.loads((HERE/'analysis/baseline.json').read_text(encoding='utf-8'))
    checks = json.loads((HERE/'analysis/checks.json').read_text(encoding='utf-8'))
    inputs = json.loads((BASE/'analysis/input_manifest.json').read_text(encoding='utf-8'))
    rt = json.loads((PROJECT/'enterprise_demo/runtime_status.json').read_text(encoding='utf-8'))
    assert checks['pass'] and checks['composition_sha256'] == sha(HERE/'comp.html')
    assert sha(baseline['base_video']) == baseline['base_sha256']
    assert sha(BASE/'comp.html') == baseline['base_comp_sha256']
    for item in inputs['sources']:
        assert sha(item['original']) == item['sha256']
        assert sha(item['copy']) == item['sha256']
    final = HERE/'output/onetake_ending_v2_1080p30.mp4'
    assert not final.exists(), 'Never overwrite an earlier delivery.'
    folder = HERE/'output'/('render_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    folder.mkdir(parents=True, exist_ok=False)
    frames = (folder/'_frames').resolve()
    assert folder.resolve().parent == (HERE/'output').resolve()
    assert frames.parent == folder.resolve() and frames.name == '_frames' and not frames.exists()
    frames.mkdir()
    old_frames = Path(baseline['base_render_folder'])/'_frames'
    reused = baseline['first_unchanged_render_frames']
    assert reused == 362 and (reused-1)/30+1/120 < baseline['change_starts_seconds']
    prefix_hashes = []
    for n in range(reused):
        src = old_frames/f'{n:05d}.png'
        dst = frames/src.name
        shutil.copy2(src, dst)
        a, b = sha(src), sha(dst)
        assert a == b
        prefix_hashes.append(a)
    silent = folder/'draft_silent.mp4'
    env = os.environ.copy()
    env['PATH'] = str(Path(rt['ffmpeg']['path']).parent)+os.pathsep+env.get('PATH','')
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PLAYWRIGHT_SKIP_BROWSER_GC='1')
    cmd = [sys.executable, str(SKILL/'scripts/render.py'), str(HERE/'comp.html'),
           '--out', str(silent), '--workers', '4', '--samples-min', '4',
           '--samples-max', '32', '--gap', '6', '--resume', '--keep-frames']
    start = time.monotonic()
    print(f'Reused {reused} verified original PNGs; rendering remaining 92 frames.', flush=True)
    with (folder/'render.log').open('w', encoding='utf-8') as log:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', errors='replace', env=env)
        for line in proc.stdout:
            log.write(line); log.flush(); print(line, end='', flush=True)
        assert proc.wait() == 0, f'Render failed; see {folder}/render.log'
    assert len(list(frames.glob('*.png'))) == 454
    for n, digest in enumerate(prefix_hashes):
        assert sha(frames/f'{n:05d}.png') == digest
    subprocess.run([rt['ffmpeg']['path'], '-hide_banner', '-loglevel', 'error', '-n',
                    '-i', str(silent), '-i', str(BASE/'assets/source.mp4'),
                    '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'copy',
                    '-movflags', '+faststart', str(final)], check=True, env=env)
    renderer_meta = json.loads(silent.with_suffix('.render.json').read_text(encoding='utf-8'))
    renderer_meta.update(reused_prefix_pngs=reused, newly_rendered_frames=92,
                         counters_scope='Capture/still counters cover ending-only resume run; 362 prefix PNGs retain V1 shutter render')
    final.with_suffix('.render.json').write_text(json.dumps(renderer_meta, ensure_ascii=False, indent=2), encoding='utf-8')
    report = {
        'file': str(final), 'sha256': sha(final), 'frames': 454, 'fps': 30,
        'duration_seconds': 454/30, 'resolution': [1920,1080],
        'change_starts_seconds': baseline['change_starts_seconds'],
        'unchanged_prefix_pngs_reused': reused, 'newly_rendered_frames': 92,
        'prefix_png_hashes': prefix_hashes,
        'prefix_comparison_scope': 'PNG pixel inputs identical; final lossy H264 bitstreams need not match',
        'original_speech_preserved_by': 'AAC stream copy; no voice, loudness, timing, music or SFX changes',
        'base_sha256': sha(baseline['base_video']), 'base_version_preserved': True,
        'new_paid_api_calls': 0, 'new_images_or_synthetic_noise_generated': False,
        'renderer': 'Installed onetake render.py --resume; motion.js; HTML pure time functions; temporal shutter sampling',
        'render_metadata': renderer_meta,
        'render_metadata_counts_scope': 'Frame count is full film; capture/still counters cover ending-only resume run',
        'composition_sha256': sha(HERE/'comp.html'), 'render_folder': str(folder),
        'elapsed_seconds': time.monotonic()-start,
        'full_speed_perceptual_listening_verified': False, 'user_aesthetic_acceptance_claimed': False
    }
    (HERE/'output/render_manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {final}; {report["elapsed_seconds"]:.1f}s; SHA256 {report["sha256"]}', flush=True)


if __name__ == '__main__':
    main()
