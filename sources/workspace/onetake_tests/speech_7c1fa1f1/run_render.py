"""Render the approved onetake composition and copy the untouched source AAC."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parent.parent
SKILL=Path.home()/'.codex'/'skills'/'onetake'
RUNTIME=json.loads((PROJECT/'enterprise_demo'/'runtime_status.json').read_text(encoding='utf-8'))
FFMPEG=RUNTIME['ffmpeg']['path']


def main():
    source=json.loads((HERE/'analysis'/'input_manifest.json').read_text(encoding='utf-8'))
    for item in source['sources']:
        assert hashlib.sha256(Path(item['original']).read_bytes()).hexdigest()==item['sha256']
    comp=HERE/'comp.html'
    checks=json.loads((HERE/'analysis'/'composition_checks.json').read_text(encoding='utf-8'))
    digest=hashlib.sha256(comp.read_bytes()).hexdigest()
    assert checks['pass'] and digest==checks['composition_sha256']
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    folder=HERE/'output'/('render_'+stamp)
    folder.mkdir()
    frames=(folder/'_frames').resolve()
    # Upstream uses recursive cleanup of _frames. Validate its exact fresh path
    # within the task's new render directory before any upstream invocation.
    assert folder.resolve().parent==(HERE/'output').resolve()
    assert frames.parent==folder.resolve() and frames.name=='_frames' and not frames.exists()
    silent=folder/'draft_silent.mp4'
    final=HERE/'output'/'onetake_speech_edit_1080p30.mp4'
    assert not final.exists(),'Do not overwrite a previously delivered version.'
    env=os.environ.copy()
    env['PATH']=str(Path(FFMPEG).parent)+os.pathsep+env.get('PATH','')
    env.update(PYTHONIOENCODING='utf-8',PYTHONUTF8='1',PLAYWRIGHT_SKIP_BROWSER_GC='1')
    cmd=[sys.executable,str(SKILL/'scripts'/'render.py'),str(comp),'--out',str(silent),
         '--workers','4','--samples-min','4','--samples-max','32','--gap','6','--keep-frames']
    start=time.monotonic()
    print('1080p30 onetake shutter render started (4 workers)',flush=True)
    with (folder/'render.log').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env)
        for line in proc.stdout:
            log.write(line);log.flush();print(line,end='',flush=True)
        code=proc.wait()
    assert code==0,f'Render failed; see {folder}/render.log'
    # Exact encoded AAC copied, no retiming, loudness filter, re-voicing or music.
    mux=[FFMPEG,'-hide_banner','-loglevel','error','-n','-i',str(silent),'-i',str(HERE/'assets'/'source.mp4'),
         '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','copy','-movflags','+faststart',str(final)]
    subprocess.run(mux,check=True,env=env)
    report={'file':str(final),'sha256':hashlib.sha256(final.read_bytes()).hexdigest(),
            'frames':454,'fps':30,'duration_seconds':454/30,'resolution':[1920,1080],
            'source_video_resolution':[1280,720],'native_1080_source_claimed':False,
            'image_order':[1,2,3,4],'concept':'confirmed A: same persistent frame, accumulated noise, return to original speaker',
            'original_speech_preserved_by':'AAC stream copy, no speech edits or new voice',
            'source_audio_file':'assets/source.mp4','new_paid_api_calls':0,
            'new_images_or_synthetic_noise_generated':False,
            'renderer':'Installed onetake render.py + motion.js + generated look.js; HTML/JS; real temporal shutter samples',
            'render_metadata':json.loads(silent.with_suffix('.render.json').read_text(encoding='utf-8')),
            'composition_sha256':digest,'render_folder':str(folder),'elapsed_seconds':time.monotonic()-start,
            'full_speed_perceptual_listening_verified':False,'user_aesthetic_acceptance_claimed':False}
    (HERE/'output'/'render_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
