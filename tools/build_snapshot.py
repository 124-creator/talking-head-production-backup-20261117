"""Build a complete, deduplicated, SHA256-indexed snapshot without changing sources."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import os
import re
import shutil
import time
import zipfile

TEXT_SUFFIXES = {".py", ".js", ".html", ".css", ".json", ".txt", ".md", ".yaml", ".yml", ".ps1", ".toml", ".srt", ".cfg"}
STORED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".zip", ".whl", ".woff", ".woff2", ".gz"}
SECRET_PATTERNS = [
    re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    re.compile(rb"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
    re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b"),
    re.compile(rb'''["'](?:access_token|refresh_token|client_secret|api_key)["']\s*:\s*["'][A-Za-z0-9_./+\-=]{20,}["']''', re.I),
]


def digest_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def is_cache(path):
    parts = Path(path).parts
    return any(p in {"_frames", "speech_frames", "_static", "__pycache__"} for p in parts)


def files_from_spec(spec):
    found = []
    for item in spec["roots"]:
        source, target = Path(item["source"]), Path(item["target"])
        if not source.exists():
            raise FileNotFoundError(source)
        if source.is_file():
            found.append((source, target.as_posix()))
            continue
        for base, dirs, names in os.walk(source):
            dirs[:] = sorted(d for d in dirs if d not in {".git", ".svn", "node_modules"})
            for name in sorted(names):
                if name in {"auth.json", "credentials.json", ".env", ".env.local", "hosts.yml"}:
                    raise RuntimeError(f"Credential-shaped file in explicit scope: {Path(base) / name}")
                p = Path(base) / name
                found.append((p, (target / p.relative_to(source)).as_posix()))
    targets = [p for _, p in found]
    if len(targets) != len(set(targets)):
        raise RuntimeError("Snapshot destination path collision")
    return sorted(found, key=lambda pair: (is_cache(pair[1]), pair[1]))


def inventory(spec, out, repository):
    records, hashes, objects, totals = [], {}, {}, collections.defaultdict(lambda: [0, 0])
    started = time.monotonic()
    all_files = files_from_spec(spec)
    scanned = 0
    for index, (source, target) in enumerate(all_files, 1):
        before = source.stat()
        identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if identity not in hashes:
            hashes[identity] = digest_file(source)
        sha = hashes[identity]
        if source.suffix.lower() in TEXT_SUFFIXES or source.name in {"LICENSE", "NOTICE", "COPYING"}:
            if before.st_size <= 8 * 1024 * 1024:
                content = source.read_bytes()
                if any(pattern.search(content) for pattern in SECRET_PATTERNS):
                    raise RuntimeError(f"Possible secret detected; do not upload: {source}")
                scanned += 1
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f"Source changed during snapshot: {source}")
        category = "cache" if is_cache(target) else "core"
        record = {"path": target, "sha256": sha, "size": before.st_size, "mtime_ns": before.st_mtime_ns, "category": category}
        records.append(record)
        if sha not in objects:
            objects[sha] = {"source": str(source), "size": before.st_size, "category": category,
                            "mtime_ns": before.st_mtime_ns, "suffix": source.suffix.lower()}
        elif category == "core":
            objects[sha]["category"] = "core"
        key = "/".join(Path(target).parts[:2]); totals[key][0] += 1; totals[key][1] += before.st_size
        if target.startswith(("workspace/", "skills/")) and before.st_size <= 2 * 1024 * 1024 and (source.suffix.lower() in TEXT_SUFFIXES or source.name in {"LICENSE", "NOTICE", "COPYING"}):
            mirror = repository / "sources" / Path(target); mirror.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, mirror)
        if index % 250 == 0:
            print(f"Inventory {index}/{len(all_files)} files; unique bytes {sum(o['size'] for o in objects.values()) / 1024**3:.2f} GiB; elapsed {time.monotonic() - started:.0f}s", flush=True)
    result = {"snapshot_id": spec["snapshot_id"], "repo": spec["repo"], "tag": spec["tag"], "files": records,
              "objects": objects, "file_count": len(records), "logical_bytes": sum(r["size"] for r in records),
              "unique_bytes": sum(o["size"] for o in objects.values()), "groups": dict(totals),
              "text_files_scanned_for_secrets": scanned, "secrets_detected": 0, "all_explicit_roots_included": True}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Inventory complete: {len(records)} paths / {len(objects)} objects / {result['unique_bytes'] / 1024**3:.2f} GiB unique", flush=True)
    return result


def pack(inv, artifact_dir, repository, limit):
    artifact_dir.mkdir(parents=True, exist_ok=True)
    all_objects = sorted(inv["objects"].items(), key=lambda pair: (pair[1]["category"] != "core", pair[0]))
    batches = []
    for category in ["core", "cache"]:
        current, size = [], 0
        for sha, obj in all_objects:
            if obj["category"] != category:
                continue
            if obj["size"] > limit:
                raise RuntimeError(f"Object needs its own larger part: {obj['source']}")
            if current and size + obj["size"] > limit:
                batches.append((category, current)); current, size = [], 0
            current.append((sha, obj)); size += obj["size"]
        if current:
            batches.append((category, current))
    assets, object_map = [], {}
    counters = collections.Counter()
    for index, (category, batch) in enumerate(batches, 1):
        counters[category] += 1
        name = f"snapshot-{category}-{counters[category]:03d}.zip"
        path = artifact_dir / name
        assert not path.exists(), f"Do not overwrite an existing snapshot part: {path}"
        print(f"Packing {index}/{len(batches)} {name}: {len(batch)} unique objects", flush=True)
        with zipfile.ZipFile(path, "w", allowZip64=True, strict_timestamps=False) as archive:
            for sha, obj in batch:
                source = Path(obj["source"]); stat = source.stat()
                if (stat.st_size, stat.st_mtime_ns) != (obj["size"], obj["mtime_ns"]):
                    raise RuntimeError(f"Source changed before packing: {source}")
                member = "objects/" + sha
                kind = zipfile.ZIP_STORED if obj["suffix"] in STORED_SUFFIXES else zipfile.ZIP_DEFLATED
                archive.write(source, member, compress_type=kind, compresslevel=3)
                object_map[sha] = {"archive": name, "member": member, "size": obj["size"]}
        size = path.stat().st_size
        assert size < 2 * 1024**3, "GitHub Release asset must be smaller than 2 GiB"
        assets.append({"name": name, "size": size, "sha256": digest_file(path), "category": category, "objects": len(batch)})
        print(f"Packed {name}: {size / 1024**2:.1f} MiB", flush=True)
    manifest = {k: v for k, v in inv.items() if k != "objects"}
    manifest["objects"] = object_map; manifest["format_version"] = 1
    manifest["restore_layout"] = "workspace + skills + runtimes + models + reference + environment"
    manifests = repository / "manifests"; manifests.mkdir(exist_ok=True)
    (manifests / "snapshot.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (manifests / "archives.json").write_text(json.dumps({"repo": inv["repo"], "tag": inv["tag"], "assets": assets}, ensure_ascii=False, indent=2), encoding="utf-8")
    (artifact_dir / "SHA256SUMS").write_text("\n".join(f"{a['sha256']}  {a['name']}" for a in assets) + "\n", encoding="ascii")
    (artifact_dir / "snapshot.json").write_bytes((manifests / "snapshot.json").read_bytes())
    (artifact_dir / "archives.json").write_bytes((manifests / "archives.json").read_bytes())
    print(f"Complete: {len(assets)} parts / {sum(a['size'] for a in assets) / 1024**3:.2f} GiB upload", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--repository", type=Path, required=True)
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--artifacts", type=Path, required=True)
    p.add_argument("--part-mib", type=int, default=768)
    p.add_argument("--reuse-inventory", action="store_true")
    args = p.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    inv = json.loads(args.inventory.read_text(encoding="utf-8")) if args.reuse_inventory else inventory(spec, args.inventory, args.repository)
    pack(inv, args.artifacts, args.repository, args.part_mib * 1024**2)


if __name__ == "__main__":
    main()
