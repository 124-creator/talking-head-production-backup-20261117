"""Transcribe only the supplied speech locally with the already cached model."""
from pathlib import Path
import json
import os
import time
import wave
import numpy as np

os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
from faster_whisper import WhisperModel

HERE=Path(__file__).resolve().parent
MODEL=Path.home()/'.cache'/'huggingface'/'hub'/'models--Systran--faster-whisper-small'/'snapshots'/'536b0662742c02347bc0e980a01041f333bce120'
assert (MODEL/'model.bin').is_file()
start=time.monotonic()
model=WhisperModel(str(MODEL),device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
with wave.open(str(HERE/'assets'/'speech_16k.wav'),'rb') as wav:
    assert (wav.getframerate(),wav.getnchannels(),wav.getsampwidth())==(16000,1,2)
    audio=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)/32768.
# The local PyAV build changed its path-decoder kwargs; supplying exact PCM
# avoids that unrelated decoder branch and never alters the source recording.
segments,info=model.transcribe(audio,language='zh',beam_size=5,
                              word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
rows=[]
for s in segments:
    row={'start':s.start,'end':s.end,'text':s.text,'avg_logprob':s.avg_logprob,
         'no_speech_prob':s.no_speech_prob,
         'words':[{'start':w.start,'end':w.end,'word':w.word,'probability':w.probability} for w in (s.words or [])]}
    rows.append(row)
    print(f'{s.start:.2f}-{s.end:.2f}: {s.text}',flush=True)
result={'engine':'faster-whisper 1.2.1 / cached Systran faster-whisper-small / CPU int8',
        'model_path':str(MODEL),'language':info.language,'language_probability':info.language_probability,
        'network_requests_for_recognition':0,'paid_api_calls':0,'seconds':time.monotonic()-start,
        'note':'Machine transcript; do not silently substitute inferred copy for spoken content.',
        'segments':rows,'text':''.join(r['text'] for r in rows)}
(HERE/'analysis'/'asr_raw.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(HERE/'analysis'/'口播识别原稿.txt').write_text('\n'.join(f"{r['start']:.2f}–{r['end']:.2f}  {r['text']}" for r in rows),encoding='utf-8')
print('ASR completed',result['seconds'],flush=True)
