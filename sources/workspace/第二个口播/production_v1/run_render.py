"""Render with the installed onetake renderer; mux the source AAC without re-encoding."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROJECT = ROOT.parent


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    rt = json.loads((PROJECT / "enterprise_demo/runtime_status.json").read_text(encoding="utf-8"))
    checks = json.loads((HERE / "qa/composition_checks.json").read_text(encoding="utf-8"))
    original = json.loads((ROOT / "analysis/analysis_checks.json").read_text(encoding="utf-8"))
    assert checks["pass"] and checks["composition_sha256"] == sha(HERE / "comp.html")
    assert checks["data_sha256"] == sha(HERE / "data.js")
    assert sha(ROOT / "原视频.mp4") == original["source_sha256"]
    assert len(list((HERE / "assets/speech_frames").glob("*.png"))) == 2117
    final = HERE / "output/第二个口播_成片_v1_1080p30.mp4"
    assert not final.exists(), "Do not overwrite a previously delivered version."
    folder = HERE / "output" / ("render_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    folder.mkdir(exist_ok=False)
    silent = folder / "silent.mp4"
    env = os.environ.copy()
    env["PATH"] = str(Path(rt["ffmpeg"]["path"]).parent) + os.pathsep + env.get("PATH", "")
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PLAYWRIGHT_SKIP_BROWSER_GC="1")
    cmd = [sys.executable, str(Path.home() / ".codex/skills/onetake/scripts/render.py"),
           str(HERE / "comp.html"), "--out", str(silent), "--workers", "4",
           "--samples-min", "4", "--samples-max", "24", "--gap", "6",
           "--crf", "16", "--keep-frames"]
    started = time.monotonic()
    print("Rendering 2118 frames; original voice, original pacing, no generated media.", flush=True)
    with (folder / "render.log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", env=env)
        for line in proc.stdout:
            print(line, end="", flush=True); log.write(line); log.flush()
        assert proc.wait() == 0, f"Render failed: {folder}"
    subprocess.run([rt["ffmpeg"]["path"], "-hide_banner", "-loglevel", "error", "-n",
                    "-i", str(silent), "-i", str(ROOT / "原视频.mp4"),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy",
                    "-movflags", "+faststart", str(final)], check=True, env=env)
    meta = json.loads(silent.with_suffix(".render.json").read_text(encoding="utf-8"))
    final.with_suffix(".render.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"file": str(final), "sha256": sha(final), "source_sha256": sha(ROOT / "原视频.mp4"),
              "composition_sha256": sha(HERE / "comp.html"), "data_sha256": sha(HERE / "data.js"),
              "resolution": [1920, 1080], "source_resolution": [1280, 720], "output_is_native_4k": False,
              "original_aac_stream_copied": True, "generated_voice": False, "background_music_added": False,
              "source_audio_edited": False, "frames": 2118, "duration_seconds": 70.6,
              "visual_pause_treatment": "Shared photo stage held over natural 0.44s/0.42s audio pauses; no speech removed",
              "renderer": "Installed onetake render.py; deterministic HTML; adaptive 180-degree temporal shutter",
              "render_directory": str(folder), "render_metadata": meta,
              "elapsed_seconds": round(time.monotonic() - started, 2), "new_paid_api_calls": 0}
    (HERE / "output/render_manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", final, flush=True)


if __name__ == "__main__":
    main()
