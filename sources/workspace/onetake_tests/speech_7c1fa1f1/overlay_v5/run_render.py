"""Ending-only official onetake render; verified high-quality V3 prefix reused."""
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
BASE=HERE.parent
PROJECT=HERE.parents[2]
SKILL=Path.home()/'.codex/skills/onetake'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    inputs=json.loads((HERE/'analysis/input_manifest.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'analysis/composition_checks.json').read_text(encoding='utf-8'))
    rt=json.loads((PROJECT/'enterprise_demo/runtime_status.json').read_text(encoding='utf-8'))
    assert checks['pass'] and checks['composition_sha256']==sha(HERE/'comp.html')
    assert sha(inputs['previous_v3_file'])==inputs['previous_v3_sha256']
    assert sha(BASE/'raw_v3/comp.html')==inputs['previous_v3_comp_sha256']
    assert sha(inputs['previous_v4_file'])==inputs['previous_v4_sha256']
    assert sha(BASE/'overlay_v4/comp.html')==inputs['previous_v4_comp_sha256']
    for item in inputs['sources']+inputs['previous_sources']:
        assert sha(item['original'])==item['sha256'] and sha(item['copy'])==item['sha256']
    final=HERE/'output/onetake_overlay_v5_1080p30.mp4'
    assert not final.exists(),'Never overwrite an earlier version.'
    folder=HERE/'output'/('render_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    folder.mkdir(parents=True,exist_ok=False)
    frames=(folder/'_frames').resolve()
    assert folder.resolve().parent==(HERE/'output').resolve()
    assert frames.parent==folder.resolve() and frames.name=='_frames' and not frames.exists()
    frames.mkdir()
    old=Path(inputs['previous_render_folder'])/'_frames'
    reused=inputs['reused_prefix_frames']
    assert reused==362 and (reused-1)/30+1/120<inputs['change_starts_seconds']
    hashes=[]
    for n in range(reused):
        src=old/f'{n:05d}.png';dst=frames/src.name;shutil.copy2(src,dst)
        assert sha(src)==sha(dst);hashes.append(sha(dst))
    silent=folder/'draft_silent.mp4'
    env=os.environ.copy();env['PATH']=str(Path(rt['ffmpeg']['path']).parent)+os.pathsep+env.get('PATH','')
    env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PLAYWRIGHT_SKIP_BROWSER_GC='1')
    cmd=[sys.executable,str(SKILL/'scripts/render.py'),str(HERE/'comp.html'),'--out',str(silent),
         '--workers','4','--samples-min','4','--samples-max','32','--gap','6','--resume','--keep-frames']
    start=time.monotonic();print('Reused362 unchanged 4K-source V3 PNGs; rendering92 ending frames.',flush=True)
    with (folder/'render.log').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env)
        for line in proc.stdout:log.write(line);log.flush();print(line,end='',flush=True)
        assert proc.wait()==0,f'Render failed; see{folder}/render.log'
    assert len(list(frames.glob('*.png')))==454
    assert all(sha(frames/f'{n:05d}.png')==v for n,v in enumerate(hashes))
    subprocess.run([rt['ffmpeg']['path'],'-hide_banner','-loglevel','error','-n','-i',str(silent),
        '-i',str(BASE/'raw_v3/assets/source.mp4'),'-map','0:v:0','-map','1:a:0',
        '-c:v','copy','-c:a','copy','-movflags','+faststart',str(final)],check=True,env=env)
    meta=json.loads(silent.with_suffix('.render.json').read_text(encoding='utf-8'))
    meta.update(reused_prefix_pngs=reused,newly_rendered_frames=92,
                counters_scope='Capture/still counters cover ending-only resume run; prefix PNGs retain V3 shutter render')
    final.with_suffix('.render.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'file':str(final),'sha256':sha(final),'frames':454,'fps':30,'duration_seconds':454/30,
            'resolution':[1920,1080],'source_video_resolution':[3840,2160],'output_is_4k':False,
            'change_starts_seconds':12.06,'unchanged_prefix_pngs_reused':reused,'newly_rendered_frames':92,
            'prefix_png_hashes':hashes,'prefix_comparison_scope':'PNG inputs identical; final lossy H264 bitstreams need not match',
            'presenter_ending_geometry':[0,0,1920,1080],'verb_font_size':84,'model_name_font_size':210,
            'ending_caption_hidden':True,'ending_left_kicker_hidden':True,'main_model_color':'#FFD84D',
            'layout':'Full-size presenter; only floating verb/possessive/yellow model name; both left text layers removed',
            'source_audio_file':str(BASE/'raw_v3/assets/source.mp4'),
            'original_speech_preserved_by':'NEW supplied4K original AAC stream-copy; no voice, level or timing edits',
            'source_pipeline':inputs['frame_pipeline'],'new_paid_api_calls':0,
            'renderer':'Installed onetake render.py --resume; HTML pure time functions; temporal shutter samples',
            'render_metadata':meta,'composition_sha256':sha(HERE/'comp.html'),'render_folder':str(folder),
            'elapsed_seconds':time.monotonic()-start,'previous_v3_preserved':True,'previous_v4_preserved':True,
            'full_speed_perceptual_listening_verified':False,'user_aesthetic_acceptance_claimed':False}
    (HERE/'output/render_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Wrote {final}; {report["elapsed_seconds"]:.1f}s; SHA256{report["sha256"]}',flush=True)


if __name__=='__main__':main()
