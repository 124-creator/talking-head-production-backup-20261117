"""Render three bounded V2 experiments and assemble same-time V1/V2 comparisons."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CASES = [("a", 26.4, 4.0, "人物关键词"), ("b", 17.3, 7.2, "递进标签"), ("c", 47.0, 8.5, "新旧对照")]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    rt = json.loads((ROOT.parent / "enterprise_demo/runtime_status.json").read_text(encoding="utf-8"))
    checks = json.loads((HERE / "qa/preflight.json").read_text(encoding="utf-8"))
    inputs = json.loads((HERE / "input_checks.json").read_text(encoding="utf-8"))
    assert checks["pass"]
    assert all(sha(HERE / name) == value for name, value in checks["hashes"].items())
    assert sha(inputs["v1_file"]) == inputs["v1_sha256"]
    env = os.environ.copy()
    env["PATH"] = str(Path(rt["ffmpeg"]["path"]).parent) + os.pathsep + env.get("PATH", "")
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    ffmpeg = rt["ffmpeg"]["path"]
    source = ROOT / "原视频.mp4"
    outputs, comparisons = [], []
    started = time.monotonic()
    for case, offset, dur, title in CASES:
        folder = HERE / "output" / case; folder.mkdir(exist_ok=True)
        final = HERE / "output" / f"测试{case.upper()}_{title}.mp4"
        assert not final.exists(), "Never overwrite a previous experiment"
        silent = folder / "silent.mp4"
        cmd = [sys.executable, str(Path.home() / ".codex/skills/onetake/scripts/render.py"),
               str(HERE / f"test_{case}.html"), "--out", str(silent), "--workers", "4",
               "--samples-min", "4", "--samples-max", "24", "--gap", "6", "--crf", "16", "--keep-frames"]
        print(f"TEST {case.upper()}: source {offset:.2f}–{offset + dur:.2f}s, {round(dur * 30)} frames", flush=True)
        with (folder / "render.log").open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                    text=True, encoding="utf-8", errors="replace")
            for line in proc.stdout:
                print(line, end="", flush=True); log.write(line); log.flush()
            assert proc.wait() == 0, f"Render failed {case}"
        wav = HERE / "assets" / f"speech_{case}.wav"
        subprocess.run([ffmpeg, "-v", "error", "-n", "-i", str(source), "-vn", "-af",
                        f"atrim=start={offset}:end={offset + dur},asetpts=PTS-STARTPTS", "-c:a", "pcm_s16le", str(wav)], check=True)
        subprocess.run([ffmpeg, "-v", "error", "-n", "-i", str(silent), "-i", str(wav),
                        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                        "-movflags", "+faststart", str(final)], check=True)
        meta = json.loads(silent.with_suffix(".render.json").read_text(encoding="utf-8"))
        final.with_suffix(".render.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        outputs.append({"case": case, "title": title, "file": str(final), "offset": offset, "duration": dur,
                        "frames": round(dur * 30), "sha256": sha(final), "render_metadata": meta})
        plate = Image.new("RGBA", (1920, 660), (0, 0, 0, 0)); draw = ImageDraw.Draw(plate)
        font = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 34)
        small = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 24)
        draw.text((35, 17), "V1 / 当前版本", font=font, fill="#243329")
        draw.text((995, 17), f"V2 / {title}", font=font, fill="#243329")
        draw.text((35, 625), f"测试{case.upper()} · 相同口播 {offset:.2f}–{offset + dur:.2f}秒 · 左右同步，单路原声片段", font=small, fill="#687363")
        overlay = HERE / "assets" / f"comparison_{case}.png"; plate.save(overlay)
        comparison = HERE / "output" / f"对照{case.upper()}_{title}.mp4"
        filters = "[0:v]scale=960:540,setsar=1[l];[1:v]scale=960:540,setsar=1[r];[l][r]hstack=inputs=2,pad=1920:660:0:80:color=0xF5F3ED[base];[base][2:v]overlay=0:0[v]"
        subprocess.run([ffmpeg, "-v", "error", "-n", "-ss", str(offset), "-t", str(dur), "-i", inputs["v1_file"],
                        "-i", str(final), "-i", str(overlay), "-filter_complex", filters,
                        "-map", "[v]", "-map", "1:a:0", "-t", str(dur), "-r", "30",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(comparison)], check=True)
        comparisons.append(comparison)
        print("Completed", final.name, flush=True)
    summary = HERE / "output/V1_V2_优化测试对照合集.mp4"
    cmd = [ffmpeg, "-v", "error", "-n"]
    for path in comparisons: cmd += ["-i", str(path)]
    filters = "[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a]"
    cmd += ["-filter_complex", filters, "-map", "[v]", "-map", "[a]", "-r", "30",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(summary)]
    subprocess.run(cmd, check=True)
    assert sha(inputs["v1_file"]) == inputs["v1_sha256"]
    result = {"cases": outputs, "comparisons": [str(p) for p in comparisons], "summary": str(summary),
              "summary_sha256": sha(summary), "expected_total_seconds": sum(r[2] for r in CASES),
              "v1_unchanged": True, "full_v2_rendered": False, "audio_note": "Original speech segments decoded and re-encoded for bounded tests; no generated voice/music",
              "elapsed_seconds": round(time.monotonic() - started, 2)}
    (HERE / "output/test_render_manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("DONE:", summary, flush=True)


if __name__ == "__main__":
    main()
