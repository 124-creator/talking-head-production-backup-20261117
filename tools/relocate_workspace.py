#!/usr/bin/env python3
"""Relocate a verified archive's mutable working copy (Windows x64).

Usage: python tools/relocate_workspace.py DEST [--apply]
Without --apply this command only prints a plan and writes nothing. Original
snapshot hashes remain historical evidence; relocated text has a new identity.
No user home configuration, model data, media, or original project is changed.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import tokenize
from typing import Any
from urllib.parse import quote


OLD_WORKSPACE = r"E:\Agent员工\研究自动剪辑"
OLD_HOME = r"C:\Users\Dreamboat"
OLD_STORAGE = OLD_HOME + r"\OneDrive\文档\WeChat Files\wxid_tnssm99dpsea22\FileStorage"
SNAPSHOT = "536b0662742c02347bc0e980a01041f333bce120"
MODEL_SUFFIX = ".cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots/" + SNAPSHOT
FIRST = "workspace/onetake_tests/speech_7c1fa1f1"
RUNTIME = "workspace/enterprise_demo/runtime_status.json"
RAW_SOURCE_NAME = "7c1fa1f1aaae6edc410a3c1471c65f4d_raw.mp4"
TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".jsonl", ".html", ".htm", ".js", ".mjs",
    ".cjs", ".jsx", ".ts", ".tsx", ".py", ".ps1", ".css", ".yaml",
    ".yml", ".toml", ".ini", ".cfg", ".srt", ".vtt", ".svg", ".xml",
}
MUTABLE_ROOTS = ("workspace", "skills", "environment")
EXCLUDED_DIRS = {".git", ".relocation", "__pycache__", ".venv", "venv", "node_modules"}
NOTICE = (
    "The restore command must verify original archive SHA256 before relocation. "
    "Historical checksums are not rewritten. This is a mutable working copy; "
    "original bytes and new before/after hashes are recorded separately. "
    "Windows x64 is the supported runtime; identical fonts across OSes are not guaranteed."
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _inside(root: Path, path: Path) -> Path:
    """Reject both lexical escapes and filesystem links escaping the bundle."""
    absolute = path.absolute()
    if not absolute.is_relative_to(root) or not path.resolve().is_relative_to(root):
        raise ValueError(f"Path escapes destination: {path}")
    return path


def validate_root(root: str | Path) -> Path:
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Destination must already exist: {root}")
    normalized = root.as_posix().rstrip("/").casefold()
    old = OLD_WORKSPACE.replace("\\", "/").casefold()
    if normalized == old or normalized.startswith(old + "/"):
        raise ValueError("Refusing to relocate the real original workspace or its children")
    if not (root / "workspace").is_dir():
        raise ValueError("Expected a restored destination containing workspace/")
    _inside(root, root / "workspace")
    return root


@lru_cache(maxsize=8)
def _aliases(root: Path) -> list[tuple[str, Path]]:
    first = root / FIRST
    videos = OLD_STORAGE + "\\Video\\2026-11\\"
    rows = [
        (videos + RAW_SOURCE_NAME, first / "raw_v3/assets/source.mp4"),
        (videos + "7c1fa1f1aaae6edc410a3c1471c65f4d.mp4", first / "assets/source.mp4"),
        (videos + "a7a87b4c54f8a1abe5efd6f6834decef_raw.mp4", root / "reference/approved_first.mp4"),
        (videos + "fd430e380a94fa855533d80b9f71fe1b_raw.mp4", root / "reference/style_reference.mp4"),
        (OLD_HOME + "\\" + MODEL_SUFFIX.replace("/", "\\"), root / "models/faster-whisper-small" / SNAPSHOT),
        (OLD_HOME + r"\.codex\skills\onetake", root / "skills/onetake"),
        (OLD_HOME + r"\AppData\Local\ms-playwright", root / "runtimes/playwright"),
    ]
    for version in ("9.0.2", "8.0"):
        old_ffmpeg = (
            OLD_HOME + "\\AppData\\Local\\Microsoft\\WinGet\\Packages\\"
            + "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\"
            + f"ffmpeg-{version}-full_build"
        )
        rows.append((old_ffmpeg, root / "runtimes/ffmpeg"))
    for index, basename in enumerate((
        "c6f1c46e77e1dfcf177f979469073d2.png",
        "3240d4bc8609f9d5a923cc1c900df7e.png",
        "4f98b2f1ce21006ccbcd93b6954cdee.png",
        "63303cdc6b75415123b12c0590b4b7a.png",
    ), 1):
        rows.append((OLD_STORAGE + "\\Temp\\" + basename, first / f"assets/image_{index:02d}.png"))
    rows.append((OLD_WORKSPACE, root / "workspace"))
    return sorted(rows, key=lambda row: len(row[0]), reverse=True)


def _replace_paths(text: str, root: Path) -> str:
    """Replace only named legacy roots/aliases, never arbitrary C:/ or E:/ paths."""
    folded = text.casefold()
    if "agent员工" not in folded and "dreamboat" not in folded and "file:///e:/agent%" not in folded:
        return text
    # A boundary prevents matching the sibling archive directory whose name
    # starts with the old workspace's name (研究自动剪辑_GitHub备份).
    boundary = r"(?![\w.\-])"
    for old, new in _aliases(root):
        slash_old = old.replace("\\", "/")
        for uri_old in ("file:///" + slash_old, "file:///" + slash_old.replace(" ", "%20"),
                        "file:///" + quote(slash_old, safe="/:")):
            text = re.sub(re.escape(uri_old) + boundary, lambda _: new.as_uri(), text, flags=re.IGNORECASE)
        # Backslash variants also cover paths embedded in JSON-string-like
        # content inside HTML/JS and text reports. New paths use forward slashes.
        variants = {old, slash_old, old.replace("\\", "\\\\")}
        for variant in sorted(variants, key=len, reverse=True):
            text = re.sub(re.escape(variant) + boundary, lambda _: new.as_posix(), text, flags=re.IGNORECASE)
    return text


_LITERAL = r'''(?:[rRuU]?(?:'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"))'''
_HOME_CHAIN = re.compile(r"Path\.home\s*\(\s*\)(?P<tail>(?:\s*/\s*" + _LITERAL + r")+)")
_LITERAL_TOKEN = re.compile(_LITERAL)


def _replace_home_chains(text: str, root: Path) -> str:
    def substitute(match: re.Match[str]) -> str:
        pieces = [ast.literal_eval(m.group(0)) for m in _LITERAL_TOKEN.finditer(match.group("tail"))]
        joined = "/".join(p.replace("\\", "/").strip("/") for p in pieces)
        target = None
        for old, new in ((".codex/skills/onetake", root / "skills/onetake"),
                         (MODEL_SUFFIX, root / "models/faster-whisper-small" / SNAPSHOT)):
            if joined == old or joined.startswith(old + "/"):
                target = new / joined[len(old):].lstrip("/")
                break
        if target is None:
            return match.group(0)
        return "Path(" + json.dumps(target.as_posix(), ensure_ascii=False) + ")"

    return _HOME_CHAIN.sub(substitute, text)


def _python_literals(text: str, root: Path) -> str:
    """Preserve Python string semantics even when a new path contains quotes."""
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    replacements = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for token in tokens:
            if token.type != tokenize.STRING:
                continue
            try:
                value = ast.literal_eval(token.string)
            except (ValueError, SyntaxError):
                continue
            if not isinstance(value, str):
                continue
            changed = _replace_paths(value, root)
            if changed != value:
                start = offsets[token.start[0] - 1] + token.start[1]
                end = offsets[token.end[0] - 1] + token.end[1]
                replacements.append((start, end, json.dumps(changed, ensure_ascii=False)))
    except (tokenize.TokenError, IndentationError):
        return text
    for start, end, replacement in reversed(replacements):
        text = text[:start] + replacement + text[end:]
    return text


def _json_literals(text: str, root: Path) -> str:
    # Token substitution retains all non-path fields, including historical SHA
    # values and ASR words/timings, and avoids reformatting full QA reports.
    def substitute(match: re.Match[str]) -> str:
        value = json.loads(match.group(0))
        changed = _replace_paths(value, root)
        return json.dumps(changed, ensure_ascii=False) if changed != value else match.group(0)

    return re.sub(r'"(?:\\.|[^"\\])*"', substitute, text)


def _runtime_text(root: Path) -> str:
    def tool(name: str) -> dict[str, Any]:
        path = root / f"runtimes/ffmpeg/bin/{name}.exe"
        return {"path": path.as_posix(), "available": path.is_file(),
                "verified_in_restored_environment": False}

    data = {
        "schema": "restored-runtime-v1", "target_platform": "Windows x64",
        "note": "Bundle locations only; run smoke_restored.py for fresh verification. "
                "Original runtime metadata is preserved in .relocation/originals/.",
        "ffmpeg": tool("ffmpeg"), "ffprobe": tool("ffprobe"),
        "browser": {"connected": False, "cdp_url": None,
                    "note": "A live browser/CDP session is not an archived resource."},
        "playwright": {"browsers_path": (root / "runtimes/playwright").as_posix()},
        "model": {"path": (root / "models/faster-whisper-small" / SNAPSHOT).as_posix()},
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def relocate_text(text: str, root: Path, relative: str) -> str:
    """Transform only known paths; this function itself performs no I/O."""
    suffix = Path(relative).suffix.lower()
    if relative == RUNTIME:
        return _runtime_text(root)
    if suffix == ".py":
        text = _replace_home_chains(text, root)
        text = _python_literals(text, root)
        if relative == FIRST + "/raw_v3/prepare.py":
            derived = (
                r'''Path\(\s*original\[['"]sources['"]\]\[0\]\[['"]original['"]\]\s*\)'''
                r'''\s*\.with_name\(\s*['"]''' + re.escape(RAW_SOURCE_NAME) + r'''['"]\s*\)'''
            )
            replacement = "Path(" + json.dumps((root / FIRST / "raw_v3/assets/source.mp4").as_posix(), ensure_ascii=False) + ")"
            text = re.sub(derived, lambda _: replacement, text)
    if suffix == ".ps1":
        text = re.sub(
            r'''Join-Path\s+\$HOME\s+(['"])\.codex[\\/]skills[\\/]onetake\1''',
            lambda _: "'" + (root / "skills/onetake").as_posix().replace("'", "''") + "'", text,
            flags=re.IGNORECASE,
        )
    if suffix in {".json", ".jsonl"}:
        return _json_literals(text, root)
    return _replace_paths(text, root)


@dataclass
class Change:
    relative: str
    original: bytes | None
    updated: bytes

    def summary(self) -> dict[str, Any]:
        return {"path": self.relative, "operation": "create" if self.original is None else "modify",
                "before_sha256": None if self.original is None else sha256(self.original),
                "after_sha256": sha256(self.updated),
                "original_bytes": None if self.original is None else len(self.original),
                "updated_bytes": len(self.updated)}


def build_plan(root: str | Path) -> tuple[Path, list[Change], dict[str, Any]]:
    root = validate_root(root)
    changes: list[Change] = []
    skipped: list[str] = []
    inspected = 0
    for directory in MUTABLE_ROOTS:
        base = root / directory
        if not base.exists():
            continue
        _inside(root, base)
        for current, directories, filenames in os.walk(base, followlinks=False):
            kept = []
            for name in directories:
                path = Path(current) / name
                if name in EXCLUDED_DIRS or name.startswith(".venv-"):
                    continue
                if path.is_symlink() or not path.resolve().is_relative_to(root):
                    skipped.append(path.relative_to(root).as_posix() + " (linked directory)")
                    continue
                kept.append(name)
            directories[:] = kept
            for name in sorted(filenames):
                path = Path(current) / name
                if path.suffix.lower() not in TEXT_EXTENSIONS:
                    continue
                relative = path.relative_to(root).as_posix()
                if path.is_symlink() or not path.resolve().is_relative_to(root):
                    skipped.append(relative + " (linked file)")
                    continue
                _inside(root, path)
                original = path.read_bytes()
                try:
                    text = original.decode("utf-8-sig")
                except UnicodeDecodeError:
                    skipped.append(relative + " (not UTF-8)")
                    continue
                inspected += 1
                updated_text = relocate_text(text, root, relative)
                if updated_text == text:
                    continue
                # A malformed rewrite is a hard error, not a partially applied
                # migration. Validate parseable source/JSON before any write.
                if path.suffix.lower() == ".py":
                    ast.parse(updated_text, filename=relative)
                elif path.suffix.lower() == ".json":
                    json.loads(updated_text)
                elif path.suffix.lower() == ".jsonl":
                    for line in updated_text.splitlines():
                        if line.strip():
                            json.loads(line)
                bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
                changes.append(Change(relative, original, bom + updated_text.encode("utf-8")))
    runtime = root / RUNTIME
    if not runtime.exists():
        _inside(root, runtime)
        changes.append(Change(RUNTIME, None, _runtime_text(root).encode("utf-8")))
    changes.sort(key=lambda change: change.relative)
    report = {"mode": "plan", "destination": str(root), "notice": NOTICE,
              "inspected_utf8_text_files": inspected, "changed_files": len(changes),
              "skipped": skipped, "changes": [change.summary() for change in changes]}
    return root, changes, report


def _write_atomic(root: Path, path: Path, data: bytes) -> None:
    _inside(root, path)
    _inside(root, path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    _inside(root, path.parent)
    fd, temporary = tempfile.mkstemp(prefix=".relocate-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _inside(root, path)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply_relocation(root: str | Path) -> dict[str, Any]:
    root, changes, report = build_plan(root)
    report["mode"] = "apply"
    report["applied_files"] = 0
    if not changes:
        return report
    metadata = _inside(root, root / ".relocation")
    backup_root = _inside(root, metadata / "originals")
    log_path = _inside(root, metadata / "relocation_log.json")
    # Preflight every target before writing any byte. Never follow a backup or
    # journal symlink outside the restored bundle.
    for change in changes:
        path = _inside(root, root / change.relative)
        _inside(root, backup_root / change.relative)
        actual = path.read_bytes() if path.exists() else None
        if actual != change.original:
            raise RuntimeError(f"Concurrent file modification: {change.relative}")
    if log_path.exists():
        journal = json.loads(log_path.read_text(encoding="utf-8"))
        if journal.get("schema_version") != 1:
            raise ValueError("Unsupported existing relocation log schema")
    else:
        journal = {"schema_version": 1, "notice": NOTICE, "runs": []}
    # Save all original bytes before the first working-copy write. An existing
    # backup is deliberately never replaced, including on later migrations.
    for change in changes:
        if change.original is None:
            continue
        backup = _inside(root, backup_root / change.relative)
        if not backup.exists():
            _write_atomic(root, backup, change.original)
    run = {"at_utc": datetime.now(timezone.utc).isoformat(), "status": "applying",
           "destination": str(root), "changes": [change.summary() for change in changes]}
    journal["runs"].append(run)
    _write_atomic(root, log_path, (json.dumps(journal, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    for change in changes:
        _write_atomic(root, root / change.relative, change.updated)
        report["applied_files"] += 1
    run["status"] = "complete"
    _write_atomic(root, log_path, (json.dumps(journal, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    report["original_backups"] = str(backup_root)
    report["relocation_log"] = str(log_path)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="Restored bundle root, not the original workspace")
    parser.add_argument("--apply", action="store_true", help="Apply the plan; save originals and an independent SHA journal")
    args = parser.parse_args(argv)
    try:
        report = apply_relocation(args.destination) if args.apply else build_plan(args.destination)[2]
    except (OSError, ValueError, RuntimeError, SyntaxError) as error:
        print(json.dumps({"error": str(error), "mode": "apply" if args.apply else "plan"}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
