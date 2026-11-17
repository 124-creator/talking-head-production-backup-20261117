"""Fresh full-film render from the actual 4K original, not 720p proxies."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
PROJECT=BASE.parent.parent
SKILL=Path.home()/'.codex/skills/onetake'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    source=json.loads((HERE/'analysis/input_manifest.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'analysis/composition_checks.json').read_text(encoding='utf-8'))
    rt=json.loads((PROJECT/'enterprise_demo/runtime_status.json').read_text(encoding='utf-8'))
    assert checks['pass'] and checks['composition_sha256']==sha(HERE/'comp.html')
    for item in source['sources']+source['previous_sources']:
        assert sha(item['original'])==item['sha256'] and sha(item['copy'])==item['sha256']
    assert sha(BASE/'output/onetake_speech_edit_1080p30.mp4')==source['previous_v1_sha256']
    assert sha(BASE/'ending_v2/output/onetake_ending_v2_1080p30.mp4')==source['previous_v2_sha256']
    final=HERE/'output/onetake_raw_v3_1080p30.mp4'
    assert not final.exists(),'Never overwrite an earlier delivery.'
    folder=HERE/'output'/('render_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    folder.mkdir(parents=True,exist_ok=False)
    frames=(folder/'_frames').resolve()
    assert folder.resolve().parent==(HERE/'output').resolve()
    assert frames.parent==folder.resolve() and frames.name=='_frames' and not frames.exists()
    # Resume suppresses upstream deletion even in this fresh, empty directory.
    frames.mkdir()
    silent=folder/'draft_silent.mp4'
    env=os.environ.copy();env['PATH']=str(Path(rt['ffmpeg']['path']).parent)+os.pathsep+env.get('PATH','')
    env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PLAYWRIGHT_SKIP_BROWSER_GC='1')
    cmd=[sys.executable,str(SKILL/'scripts/render.py'),str(HERE/'comp.html'),'--out',str(silent),
         '--workers','4','--samples-min','4','--samples-max','32','--gap','6','--resume','--keep-frames']
    start=time.monotonic();print('Fresh full render: 4K source -> lossless1080 PNGs -> onetake1080p30, 4workers.',flush=True)
    with (folder/'render.log').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env)
        for line in proc.stdout:log.write(line);log.flush();print(line,end='',flush=True)
        assert proc.wait()==0,f'Render failed; see {folder}/render.log'
    assert len(list(frames.glob('*.png')))==454
    subprocess.run([rt['ffmpeg']['path'],'-hide_banner','-loglevel','error','-n','-i',str(silent),
                    '-i',str(HERE/'assets/source.mp4'),'-map','0:v:0','-map','1:a:0',
                    '-c:v','copy','-c:a','copy','-movflags','+faststart',str(final)],check=True,env=env)
    meta=json.loads(silent.with_suffix('.render.json').read_text(encoding='utf-8'))
    final.with_suffix('.render.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'file':str(final),'sha256':sha(final),'frames':454,'fps':30,'duration_seconds':454/30,
            'source_video_resolution':[3840,2160],'decoded_png_resolution':[1920,1080],'resolution':[1920,1080],
            'output_is_4k':False,'source_pipeline':source['frame_pipeline'],
            'fresh_full_film_render':True,'reused_720p_video_frames':0,
            'motion_and_caption_timing':'Same as ending_v2; only underlying presenter footage/audio encoding replaced',
            'original_speech_preserved_by':'NEW 4K original AAC stream copy; no voice or timing edits',
            'source_audio_file':'assets/source.mp4','new_paid_api_calls':0,
            'new_images_or_synthetic_noise_generated':False,
            'renderer':'Installed onetake render.py + motion.js + look.js; temporal shutter sampling',
            'composition_sha256':sha(HERE/'comp.html'),'render_metadata':meta,'render_folder':str(folder),
            'elapsed_seconds':time.monotonic()-start,'previous_v1_preserved':True,'previous_v2_preserved':True,
            'full_speed_perceptual_listening_verified':False,'user_aesthetic_acceptance_claimed':False}
    (HERE/'output/render_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Wrote {final}; {report["elapsed_seconds"]:.1f}s; SHA256 {report["sha256"]}',flush=True)


if __name__=='__main__':main()
