"""Read-only source analysis using the existing offline speech-recognition model."""
from pathlib import Path
import json
import os
import time
import wave

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

import numpy as np
from faster_whisper import WhisperModel

HERE = Path(__file__).resolve().parent
MODEL = (
    Path.home() / ".cache/huggingface/hub/models--Systran--faster-whisper-small"
    / "snapshots/536b0662742c02347bc0e980a01041f333bce120"
)
assert (MODEL / "model.bin").is_file()
started = time.monotonic()
with wave.open(str(HERE / "speech_16k.wav"), "rb") as wav:
    assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)
    audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
model = WhisperModel(str(MODEL), device="cpu", compute_type="int8", cpu_threads=4, local_files_only=True)
segments, info = model.transcribe(
    audio, language="zh", beam_size=5, word_timestamps=True,
    vad_filter=False, condition_on_previous_text=False,
)
rows = []
for segment in segments:
    row = {
        "start": segment.start, "end": segment.end, "text": segment.text,
        "avg_logprob": segment.avg_logprob, "no_speech_prob": segment.no_speech_prob,
        "words": [
            {"start": word.start, "end": word.end, "word": word.word, "probability": word.probability}
            for word in (segment.words or [])
        ],
    }
    rows.append(row)
    print(f"{segment.start:.2f}-{segment.end:.2f}: {segment.text}", flush=True)
result = {
    "engine": "faster-whisper 1.2.1 / cached faster-whisper-small / CPU int8",
    "model_path": str(MODEL), "language": info.language,
    "language_probability": info.language_probability,
    "network_requests_for_recognition": 0, "paid_api_calls": 0,
    "elapsed_seconds": time.monotonic() - started,
    "note": "Machine transcript and word timestamps; not a human-audited subtitle track. No source edits.",
    "segments": rows, "text": "".join(row["text"] for row in rows),
}
(HERE / "asr_raw.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
(HERE / "口播识别原稿.txt").write_text(
    "\n".join(f"{row['start']:.2f}–{row['end']:.2f}  {row['text']}" for row in rows), encoding="utf-8"
)
print(f"ASR completed: {result['elapsed_seconds']:.2f}s", flush=True)
