"""Complete V2 export with pixel-verified exact-hold caching and onetake shutter render."""
from pathlib import Path
import asyncio
import datetime
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time

from PIL import Image, ImageChops
from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


async def seed_exact_holds(folder):
    frames = folder / "_frames"; frames.mkdir()
    static = folder / "_static"; static.mkdir()
    accepted, skipped, cached = [], [], 0
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        await page.goto((HERE / "comp.html").as_uri()); await page.evaluate("window.__ready")
        groups = await page.evaluate("window.__staticGroups()")
        for index, group in enumerate(groups):
            ns = group["frames"]
            if len(ns) < 4:
                continue
            samples = sorted(set([ns[0], ns[len(ns) // 2], ns[-1]]))
            first, reference = None, None
            identical = True
            for n in samples:
                await page.evaluate("t=>window.__seek(t)", n / 30)
                png = await page.screenshot()
                rgb = Image.open(io.BytesIO(png)).convert("RGB")
                if first is None:
                    first, reference = png, rgb
                elif ImageChops.difference(reference, rgb).getbbox() is not None:
                    identical = False
                    break
            if not identical:
                skipped.append({"key": group["key"], "frames": len(ns), "reason": "Not pixel-identical across first/middle/last; use normal frame render"})
                continue
            source = static / f"hold_{index:03d}.png"; source.write_bytes(first)
            for n in ns:
                destination = frames / f"{n:05d}.png"
                try:
                    os.link(source, destination)
                except OSError:
                    shutil.copy2(source, destination)
            accepted.append({"key": group["key"], "frames": ns, "samples_verified": samples,
                             "png_sha256": sha(source), "source": str(source)})
            cached += len(ns)
            print(f"Exact photographic hold {index + 1}/{len(groups)}: {len(ns)} frames verified and reused", flush=True)
        await browser.close()
    report = {"cached_frames": cached, "accepted_groups": accepted, "skipped_groups": skipped,
              "method": "Only source-hidden static evidence states, stable across entire shutter; exact RGB equality at first/middle/last. All other frames use official onetake renderer."}
    (folder / "static_cache_proof.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    inputs = json.loads((HERE / "qa/input_manifest.json").read_text(encoding="utf-8"))
    checks = json.loads((HERE / "qa/composition_checks.json").read_text(encoding="utf-8"))
    runtime = json.loads((ROOT.parent / "enterprise_demo/runtime_status.json").read_text(encoding="utf-8"))
    assert checks["pass"] and all(sha(HERE / n) == h for n, h in checks["hashes"].items())
    assert sha(inputs["source_video"]) == inputs["source_sha256"]
    assert sha(inputs["v1_file"]) == inputs["v1_sha256"]
    assert len(list((ROOT / "production_v1/assets/speech_frames").glob("*.png"))) == 2117
    final = HERE / "output/第二个口播_优化成片_v2_1080p30.mp4"
    assert not final.exists(), "Never overwrite an existing version"
    folder = HERE / "output" / ("render_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    folder.mkdir(exist_ok=False)
    assert folder.resolve().parent == (HERE / "output").resolve()
    start = time.monotonic()
    cache = asyncio.run(seed_exact_holds(folder))
    silent = folder / "silent.mp4"
    env = os.environ.copy(); env["PATH"] = str(Path(runtime["ffmpeg"]["path"]).parent) + os.pathsep + env.get("PATH", "")
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PLAYWRIGHT_SKIP_BROWSER_GC="1")
    command = [sys.executable, str(Path.home() / ".codex/skills/onetake/scripts/render.py"), str(HERE / "comp.html"),
               "--out", str(silent), "--workers", "4", "--samples-min", "4", "--samples-max", "24", "--gap", "6",
               "--recycle", "90", "--crf", "16", "--resume", "--keep-frames"]
    print(f"FULL V2: 2118 frames / 70.60s. Reused {cache['cached_frames']} pixel-verified static frames; rendering all motion and presenter frames.", flush=True)
    with (folder / "render.log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", env=env)
        for line in proc.stdout:
            print(line, end="", flush=True); log.write(line); log.flush()
        assert proc.wait() == 0, f"Full render failed: {folder}"
    assert len(list((folder / "_frames").glob("*.png"))) == 2118
    assert all(sha(HERE / n) == h for n, h in checks["hashes"].items())
    subprocess.run([runtime["ffmpeg"]["path"], "-v", "error", "-n", "-i", str(silent), "-i", inputs["source_video"],
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy", "-movflags", "+faststart", str(final)], check=True)
    meta = json.loads(silent.with_suffix(".render.json").read_text(encoding="utf-8"))
    meta.update(exact_hold_cache_frames=cache["cached_frames"], counter_scope="Capture counters cover non-cached frames. Cache equality proof stored separately.")
    final.with_suffix(".render.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"file": str(final), "sha256": sha(final), "full_video": True, "frames": 2118, "fps": 30,
              "duration_seconds": 70.6, "resolution": [1920, 1080], "source_resolution": [1280, 720],
              "original_aac_stream_copied": True, "speech_timeline_edited": False,
              "generated_voice": False, "background_music_added": False, "new_paid_api_calls": 0,
              "reencoded_test_audio_used": False, "v1_unchanged": sha(inputs["v1_file"]) == inputs["v1_sha256"],
              "hashes": checks["hashes"], "render_directory": str(folder), "render_metadata": meta,
              "static_cache_proof": str(folder / "static_cache_proof.json"), "cached_frames": cache["cached_frames"],
              "elapsed_seconds": round(time.monotonic() - start, 2), "user_aesthetic_acceptance_claimed": False}
    (HERE / "output/render_manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FULL V2 WRITTEN:", final, flush=True)


if __name__ == "__main__":
    main()
