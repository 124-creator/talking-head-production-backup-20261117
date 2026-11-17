"""Capture only the dependency closure used by the speech-editing projects."""
from pathlib import Path
import argparse
import importlib.metadata as metadata
import json
import platform
import sys

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOTS = {
    "render": ["playwright", "Pillow", "numpy", "scipy", "matplotlib", "fonttools", "Brotli", "opencv-python-headless"],
    "asr": ["faster-whisper", "ctranslate2", "av", "numpy", "onnxruntime"],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=ROOTS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    pending = list(ROOTS[args.mode]); selected = {}
    while pending:
        name = pending.pop()
        key = canonicalize_name(name)
        if key in selected:
            continue
        dist = metadata.distribution(name)
        selected[key] = {"name": dist.metadata["Name"], "version": dist.version}
        for spec in dist.requires or []:
            req = Requirement(spec)
            if req.marker is None or req.marker.evaluate({"extra": ""}):
                pending.append(req.name)
    args.output.mkdir(parents=True, exist_ok=True)
    packages = [selected[k] for k in sorted(selected)]
    lock = "\n".join(f"{p['name']}=={p['version']}" for p in packages) + "\n"
    (args.output / f"requirements-{args.mode}.lock.txt").write_text(lock, encoding="utf-8")
    report = {"mode": args.mode, "python": sys.version, "executable": sys.executable,
              "platform": platform.platform(), "roots": ROOTS[args.mode], "packages": packages,
              "note": "Dependency closure, not an export of unrelated globally installed packages. OpenCV selects the actual headless 4.13 runtime only."}
    (args.output / f"captured-{args.mode}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(lock)


if __name__ == "__main__":
    main()
