"""Re-render the 32 frames affected by pre-cue glyph-edge leakage."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[2]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    report_path=HERE/'output/render_manifest.json'
    prior=json.loads(report_path.read_text(encoding='utf-8'))
    checks=json.loads((HERE/'analysis/composition_checks.json').read_text(encoding='utf-8'))
    assert checks['pass'] and checks['composition_sha256']==sha(HERE/'comp.html')
    assert len(checks['post_leak_fix_pixel_identical_sample_times'])==5
    assert prior['composition_sha256']==sha(HERE/'comp_draft_with_leak.html')
    final=Path(prior['file']);assert sha(final)==prior['sha256']
    old_folder=Path(prior['render_folder'])
    backup=old_folder/'unpublished_before_title_hide.mp4'
    assert not backup.exists()
    report_backup=old_folder/'manifest_before_title_hide.json'
    shutil.copy2(report_path,report_backup)
    final.rename(backup)
    if final.with_suffix('.render.json').exists():
        final.with_suffix('.render.json').rename(backup.with_suffix('.render.json'))
    folder=HERE/'output'/('render_fix_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    folder.mkdir(exist_ok=False);frames=(folder/'_frames').resolve()
    assert folder.resolve().parent==(HERE/'output').resolve() and frames.parent==folder.resolve()
    assert not frames.exists();frames.mkdir()
    changed=set(range(362,394));cached=[]
    for n in range(454):
        if n in changed:continue
        src=old_folder/'_frames'/f'{n:05d}.png';dst=frames/src.name;shutil.copy2(src,dst)
        assert sha(src)==sha(dst);cached.append({'frame':n,'sha256':sha(dst)})
    rt=json.loads((PROJECT/'enterprise_demo/runtime_status.json').read_text(encoding='utf-8'))
    env=os.environ.copy();env['PATH']=str(Path(rt['ffmpeg']['path']).parent)+os.pathsep+env['PATH']
    env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PLAYWRIGHT_SKIP_BROWSER_GC='1')
    silent=folder/'draft_silent.mp4'
    cmd=[sys.executable,str(Path.home()/'.codex/skills/onetake/scripts/render.py'),str(HERE/'comp.html'),
         '--out',str(silent),'--workers','4','--samples-min','4','--samples-max','32','--gap','6','--resume','--keep-frames']
    start=time.monotonic();print('Repairing32 pre-title frames; cached422 unchanged frames verified.',flush=True)
    with (folder/'render.log').open('w',encoding='utf-8') as log:
        p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env)
        for line in p.stdout:log.write(line);log.flush();print(line,end='',flush=True)
        assert p.wait()==0,f'Repair failed; retained unpublished draft at{backup}'
    assert len(list(frames.glob('*.png')))==454
    assert all(sha(frames/f'{x["frame"]:05d}.png')==x['sha256'] for x in cached)
    subprocess.run([rt['ffmpeg']['path'],'-hide_banner','-loglevel','error','-n','-i',str(silent),
        '-i',str(HERE.parent/'raw_v3/assets/source.mp4'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','copy',
        '-movflags','+faststart',str(final)],check=True,env=env)
    meta=json.loads(silent.with_suffix('.render.json').read_text(encoding='utf-8'))
    meta.update(reused_prefix_pngs=362,reused_post_cue_v4_pngs=60,newly_rendered_frames=32,
        counters_scope='Capture/still counters describe the32-frame glyph-leak repair only; cached frames retain their original temporal renders')
    final.with_suffix('.render.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    report=dict(prior)
    report.update(sha256=sha(final),composition_sha256=sha(HERE/'comp.html'),render_folder=str(folder),render_metadata=meta,
                  newly_rendered_frames=32,reused_post_cue_v4_pngs=60,
                  initial_ending_render_manifest=str(report_backup),unpublished_draft_retained=str(backup),
                  glyph_leak_repair_frame_range=[362,393],glyph_leak_fixed=True,
                  repair_elapsed_seconds=time.monotonic()-start,
                  elapsed_seconds=prior['elapsed_seconds']+time.monotonic()-start)
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (HERE/'analysis/repair_cached_frames.json').write_text(json.dumps(cached,indent=2),encoding='utf-8')
    print(f'Repaired final ready; SHA256{report["sha256"]}',flush=True)


if __name__=='__main__':main()
