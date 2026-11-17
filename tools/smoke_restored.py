#!/usr/bin/env python3
"""Read-only smoke check of restored talking-head projects (Windows x64).

Use the NEW render environment's Python, e.g.:
  DEST/environment/.venv-render/Scripts/python.exe tools/smoke_restored.py DEST

Checks PNGs, ffprobe metadata, exact existing master hashes, and a few browser
seeks. Does not render a full video, write screenshots, install packages, access
external websites, or overwrite a master. Cross-OS identical fonts are not
guaranteed. --skip-browser/--allow-system-python are partial diagnostics only.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import random
import struct
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import url2pathname
from typing import Any


FIRST = "workspace/onetake_tests/speech_7c1fa1f1"
SECOND = "workspace/第二个口播"
MASTERS = (
    {"name": "first_v5", "path": FIRST + "/overlay_v5/output/onetake_overlay_v5_1080p30.mp4",
     "composition": FIRST + "/overlay_v5/comp.html", "frames": 454, "seconds": 454 / 30,
     "sha256": "aaf606e5a03a4d927763e5272d3767e6598bd84ebe8dc06f29ffe546b6f658a4"},
    {"name": "second_v2", "path": SECOND + "/production_v2/output/第二个口播_优化成片_v2_1080p30.mp4",
     "composition": SECOND + "/production_v2/comp.html", "frames": 2118, "seconds": 2118 / 30,
     "sha256": "bdb63a29a513195bd5bdd6529f4463b0ef48f1509332ffc145bf2bcf2da55fb1"},
)


def contained(root: Path, path: Path, *, must_exist: bool = True) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Resource escapes restored destination: {path}")
    if must_exist and not path.is_file():
        raise FileNotFoundError(f"Missing restored file: {path}")
    return path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def environment_info() -> dict[str, Any]:
    prefix = Path(sys.prefix)
    cfg = prefix / "pyvenv.cfg"
    value = None
    if cfg.is_file():
        for line in cfg.read_text(encoding="utf-8-sig").splitlines():
            key, sep, content = line.partition("=")
            if sep and key.strip().casefold() == "include-system-site-packages":
                value = content.strip().casefold()
    isolated = sys.prefix != sys.base_prefix and value == "false"
    return {"executable": sys.executable, "prefix": sys.prefix,
            "base_prefix": sys.base_prefix, "python_version": platform.python_version(),
            "include_system_site_packages": value, "isolated_venv": isolated,
            "platform": platform.platform(), "machine": platform.machine(),
            "windows_x64": platform.system() == "Windows" and struct.calcsize("P") == 8
                           and platform.machine().casefold() in {"amd64", "x86_64"},
            "font_note": "Windows x64 baseline; cross-OS same-font/pixel output is not guaranteed."}



def verify_system_fonts(root: Path) -> tuple[dict[str, Any], list[str]]:
    """Read Windows font identities without bundling fonts or failing media checks."""
    names = ("msyh.ttc", "msyhbd.ttc", "consola.ttf", "consolab.ttf")
    reference = root / "environment/system-fonts.json"
    windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    directory = Path(windir) / "Fonts" if windir else None
    result: dict[str, Any] = {
        "reference": str(reference), "fonts_directory": str(directory) if directory else None,
        "bundled": False, "fonts": [], "requires_visual_qa": False,
    }
    warnings: list[str] = []
    qa_note = "Visual QA of any re-render is required; this is not evidence of existing-media corruption."
    try:
        contained(root, reference)
        records = json.loads(reference.read_text(encoding="utf-8-sig"))
        if not isinstance(records, list):
            raise ValueError("Expected a list of font records")
        expected = {}
        for record in records:
            if not isinstance(record, dict) or record.get("name") not in names:
                continue
            name, digest = record["name"], record.get("sha256")
            if name in expected or not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError(f"Invalid/duplicate font SHA256 reference: {name}")
            expected[name] = record
    except (OSError, ValueError, TypeError) as error:
        result.update(status="unavailable", requires_visual_qa=True, reference_error=str(error))
        warnings.append(f"System font reference could not be checked: {error}. {qa_note}")
        return result, warnings
    for name in names:
        record = expected.get(name)
        path = directory / name if directory else None
        row: dict[str, Any] = {"name": name, "path": str(path) if path else None,
                               "expected_sha256": record["sha256"] if record else None,
                               "actual_sha256": None}
        try:
            if record is None:
                row["status"] = "reference_missing"
            elif path is None or not path.is_file():
                row["status"] = "missing"
            else:
                row["actual_sha256"] = file_sha256(path)
                row["bytes"] = path.stat().st_size
                row["status"] = "matched" if row["actual_sha256"] == record["sha256"] else "different"
        except OSError as error:
            row.update(status="unreadable", error=str(error))
        if row["status"] != "matched":
            warnings.append(f"System font {name}: {row['status']}. {qa_note}")
        result["fonts"].append(row)
    result["requires_visual_qa"] = bool(warnings)
    result["status"] = "differences" if warnings else "matched"
    return result, warnings


def verify_pngs(root: Path) -> dict[str, Any]:
    from PIL import Image

    paths: set[Path] = set()
    for index in range(1, 5):
        paths.add(root / FIRST / f"assets/image_{index:02d}.png")
    # Top-level assets are small in number; do not open thousands of decoded or
    # rendered frames. Browser seeks verify additional dynamically chosen frames.
    for relative in (SECOND + "/production_v1/assets", SECOND + "/production_v2/assets"):
        directory = root / relative
        if not directory.is_dir():
            raise FileNotFoundError(f"Missing asset directory: {directory}")
        paths.update(directory.glob("*.png"))
    frame_sets = []
    for relative, expected in ((FIRST + "/raw_v3/assets/speech_frames", 453),
                               (SECOND + "/production_v1/assets/speech_frames", 2117)):
        directory = root / relative
        if not directory.is_dir() or not directory.resolve().is_relative_to(root):
            raise FileNotFoundError(f"Missing/unsafe decoded frame directory: {directory}")
        count = sum(1 for p in directory.glob("*.png") if p.is_file())
        if count != expected:
            raise ValueError(f"{relative}: expected {expected} decoded PNGs; found {count}")
        for number in (0, expected // 2, expected - 1):
            paths.add(directory / f"{number:06d}.png")
        frame_sets.append({"path": relative, "frame_count": count, "expected": expected})
    result = []
    for path in sorted(paths):
        contained(root, path)
        with Image.open(path) as image:
            if image.format != "PNG":
                raise ValueError(f"Not PNG format: {path}")
            size = image.size
            if min(size) <= 0:
                raise ValueError(f"Empty PNG: {path}")
            image.verify()
        result.append({"path": path.relative_to(root).as_posix(), "size": list(size)})
    return {"checked_images": len(result), "images": result, "decoded_frame_sets": frame_sets}


def verify_masters(root: Path) -> list[dict[str, Any]]:
    probe = contained(root, root / "runtimes/ffmpeg/bin/ffprobe.exe")
    results = []
    for master in MASTERS:
        path = contained(root, root / master["path"])
        digest = file_sha256(path)
        if digest != master["sha256"]:
            raise ValueError(f"Existing master SHA256 mismatch: {master['path']}; got {digest}")
        process = subprocess.run(
            [str(probe), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False,
        )
        if process.returncode:
            raise RuntimeError(f"ffprobe failed ({process.returncode}): {process.stderr[-2000:]}")
        metadata = json.loads(process.stdout)
        videos = [s for s in metadata.get("streams", []) if s.get("codec_type") == "video"]
        audios = [s for s in metadata.get("streams", []) if s.get("codec_type") == "audio"]
        if len(videos) != 1 or not audios:
            raise ValueError(f"Expected one video and preserved audio: {master['path']}")
        video = videos[0]
        if (video.get("width"), video.get("height")) != (1920, 1080):
            raise ValueError(f"Unexpected master dimensions: {master['path']}")
        num, denominator = map(int, video.get("avg_frame_rate", "0/1").split("/"))
        if not denominator or abs(num / denominator - 30) > 0.0001:
            raise ValueError(f"Unexpected master frame rate: {master['path']}")
        if int(video.get("nb_frames", 0)) != master["frames"]:
            raise ValueError(f"Unexpected master frame count: {master['path']}")
        duration = float(metadata["format"]["duration"])
        if abs(duration - master["seconds"]) > 0.1:
            raise ValueError(f"Unexpected master duration: {master['path']}")
        results.append({"name": master["name"], "path": master["path"], "sha256": digest,
                        "sha256_matches_original_master": True, "width": video["width"],
                        "height": video["height"], "frame_rate": video["avg_frame_rate"],
                        "frames": int(video["nb_frames"]), "duration": duration,
                        "audio_codecs": [audio.get("codec_name") for audio in audios]})
    delivery = root / SECOND / "第二个口播_优化成片_v2_1080p30.mp4"
    if delivery.exists():
        contained(root, delivery)
        digest = file_sha256(delivery)
        if digest != MASTERS[1]["sha256"]:
            raise ValueError("Second V2 root delivery copy differs from original canonical master")
        results[1]["root_delivery_copy_sha256"] = digest
    return results


def verify_browser(root: Path, random_seeks: int = 3) -> dict[str, Any]:
    from PIL import Image, ImageStat
    from playwright.sync_api import sync_playwright

    browsers = root / "runtimes/playwright"
    if not browsers.is_dir() or not browsers.resolve().is_relative_to(root):
        raise ValueError("Missing/unsafe bundled Playwright browser directory")
    previous = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)
    results: list[dict[str, Any]] = []
    try:
        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
            contained(root, executable)
            if not executable.resolve().is_relative_to(browsers.resolve()):
                raise ValueError("Playwright resolved a global browser instead of bundled browser")
            browser = playwright.chromium.launch(
                headless=True, args=["--allow-file-access-from-files"],
            )
            try:
                for number, master in enumerate(MASTERS):
                    errors: list[str] = []
                    blocked: list[str] = []
                    context = browser.new_context(viewport={"width": 1920, "height": 1080},
                                                  device_scale_factor=1, reduced_motion="no-preference")
                    page = context.new_page()
                    page.set_default_timeout(45_000)
                    page.on("pageerror", lambda error: errors.append(str(error)))

                    def guard(route: Any) -> None:
                        url = route.request.url
                        parsed = urlsplit(url)
                        if parsed.scheme in {"data", "blob", "about"}:
                            route.continue_()
                        elif parsed.scheme == "file":
                            local = Path(url2pathname(parsed.path))
                            if parsed.netloc or not local.resolve().is_relative_to(root):
                                blocked.append(url)
                                route.abort()
                            else:
                                route.continue_()
                        else:
                            blocked.append(url)
                            route.abort()

                    context.route("**/*", guard)
                    composition = contained(root, root / master["composition"])
                    try:
                        page.goto(composition.as_uri(), wait_until="load", timeout=45_000)
                        page.wait_for_function("typeof window.__seek === 'function' && !!window.__ready")
                        page.evaluate("""() => Promise.race([window.__ready,
                            new Promise((_, reject) => setTimeout(() => reject(new Error('__ready timeout')), 40000))])""")
                        last = master["seconds"] - 1 / 30
                        rng = random.Random(20261117 + number)
                        times = sorted(set([0.0, round(last / 2, 4), round(last, 4)] +
                                           [round(rng.uniform(0, last), 4) for _ in range(random_seeks)]))
                        seeks = []
                        for second in times:
                            page.evaluate("""t => Promise.race([Promise.resolve(window.__seek(t)),
                                new Promise((_, reject) => setTimeout(() => reject(new Error('__seek timeout')), 40000))])""", second)
                            page.evaluate("() => document.fonts.ready")
                            broken = page.evaluate("""() => [...document.images]
                                .filter(image => !image.complete || image.naturalWidth === 0)
                                .map(image => image.currentSrc || image.src)""")
                            if broken:
                                raise ValueError(f"Missing image(s) at {second}s: {broken[:5]}")
                            pixels = page.screenshot(type="png", animations="allow", full_page=False)
                            with Image.open(io.BytesIO(pixels)) as image:
                                image.load()
                                if image.size != (1920, 1080):
                                    raise ValueError("Unexpected browser viewport screenshot dimensions")
                                if max(ImageStat.Stat(image.convert("RGB")).stddev) < 1:
                                    raise ValueError(f"Uniform/blank browser output at {second}s")
                            seeks.append({"time": second, "screenshot_png_sha256": hashlib.sha256(pixels).hexdigest()})
                        fonts = page.evaluate("""() => ({status:document.fonts.status,
                            faces:[...document.fonts].map(font => ({family:font.family,status:font.status}))})""")
                        if any(face["status"] == "error" for face in fonts["faces"]):
                            raise ValueError(f"Failed local font: {fonts}")
                        if errors or blocked:
                            raise ValueError(f"Browser errors={errors[:5]}, blocked nonlocal resources={blocked[:5]}")
                        results.append({"name": master["name"], "composition": master["composition"],
                                        "seeks": seeks, "fonts": fonts, "page_errors": errors,
                                        "blocked_nonlocal_resources": blocked})
                    finally:
                        context.close()
            finally:
                browser.close()
    finally:
        if previous is None:
            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
        else:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = previous
    return {"browsers_path": str(browsers), "executable": str(executable),
            "compositions": results, "note": "Screenshots were checked in memory; no full video was rendered."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="Restored bundle root")
    parser.add_argument("--random-seeks", type=int, default=3, help="Seeded random seek count per composition (0-20)")
    parser.add_argument("--skip-browser", action="store_true", help="Partial archive diagnostic only; does not prove editable browser restore")
    parser.add_argument("--allow-system-python", action="store_true", help="Partial diagnostic only; bypass isolated-venv requirement")
    args = parser.parse_args(argv)
    if not 0 <= args.random_seeks <= 20:
        parser.error("--random-seeks must be between 0 and 20")
    root = args.destination.expanduser().resolve()
    report: dict[str, Any] = {"destination": str(root), "read_only": True,
                              "environment": environment_info(), "errors": [], "warnings": []}
    report["system_fonts"], report["warnings"] = verify_system_fonts(root)
    diagnostic = args.skip_browser or args.allow_system_python
    if not report["environment"]["windows_x64"]:
        report["errors"].append("Supported execution platform is Windows x64; cross-OS fonts are not guaranteed")
    if not report["environment"]["isolated_venv"] and not args.allow_system_python:
        report["errors"].append("Use the new isolated render venv's Python (include-system-site-packages=false)")
    if not report["errors"]:
        for name, check in (("pngs", lambda: verify_pngs(root)), ("masters", lambda: verify_masters(root))):
            try:
                report[name] = check()
            except Exception as error:
                report["errors"].append(f"{name}: {type(error).__name__}: {error}")
        if args.skip_browser:
            report["browser"] = {"status": "skipped", "note": "Partial diagnostic, not full restoration proof"}
        else:
            try:
                report["browser"] = verify_browser(root, args.random_seeks)
            except Exception as error:
                report["errors"].append(f"browser: {type(error).__name__}: {error}")
    report["status"] = "failed" if report["errors"] else ("diagnostic_passed" if diagnostic else "passed")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
