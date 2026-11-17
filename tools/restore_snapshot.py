"""Download and restore ALL snapshot volumes. Python standard library only.

Files are independent copies, not shared hardlinks. Existing unrelated or
modified files are never overwritten. Release assets require gh authentication
for the private repository; credentials stay in gh's own credential store.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import subprocess
import tempfile
import time
import zipfile

SHA = re.compile(r'^[0-9a-f]{64}$')
STATE = '.restore-state.json'
SUPPORT = ('AGENTS.md', 'README.md', 'RESTORE_CONTEXT.md', 'THIRD_PARTY_NOTICES.md',
           'Restore.ps1', 'Activate-Project.ps1')


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def safe_relative(value: str) -> Path:
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or '\x00' in value:
        raise ValueError(f'Unsafe manifest path: {value!r}')
    p = PurePosixPath(value)
    if p.is_absolute() or PureWindowsPath(value).is_absolute() or any(x in ('', '.', '..') for x in value.split('/')):
        raise ValueError(f'Unsafe manifest path: {value!r}')
    for part in p.parts:
        if part.rstrip(' .') != part or part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
            raise ValueError(f'Windows-invalid manifest path: {value!r}')
    return Path(*p.parts)


def contained(root: Path, path: Path) -> Path:
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Path or linked directory escapes restore root: {path}')
    if path.is_symlink():
        raise ValueError(f'Refusing linked restore file: {path}')
    return path


def atomic_write(root: Path, path: Path, content: bytes):
    contained(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    contained(root, path)
    fd, temporary = tempfile.mkstemp(prefix='.restore-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_manifest(manifest, index):
    if manifest.get('format_version') != 1:
        raise ValueError('Unsupported snapshot format')
    if (manifest['repo'], manifest['tag']) != (index['repo'], index['tag']):
        raise ValueError('Archive and snapshot indexes disagree')
    assets = {}
    for a in index['assets']:
        if safe_relative(a['name']).name != a['name'] or not a['name'].endswith('.zip') or not SHA.fullmatch(a['sha256']) or a['size'] < 0:
            raise ValueError('Invalid archive metadata')
        if a['name'] in assets:
            raise ValueError('Duplicate archive name')
        assets[a['name']] = a
    seen = set()
    for entry in manifest['files']:
        safe_relative(entry['path'])
        key = entry['path'].casefold()
        if key in seen:
            raise ValueError(f"Duplicate/case-colliding path: {entry['path']}")
        seen.add(key)
        sha = entry['sha256']
        if not SHA.fullmatch(sha) or sha not in manifest['objects'] or entry['size'] < 0:
            raise ValueError('Invalid file/object metadata')
        if entry['size'] != manifest['objects'][sha]['size']:
            raise ValueError('File and object size disagree')
    for sha, obj in manifest['objects'].items():
        if not SHA.fullmatch(sha) or obj['archive'] not in assets or obj['member'] != 'objects/' + sha or obj['size'] < 0:
            raise ValueError('Invalid content-addressed object')
    if manifest.get('file_count') != len(manifest['files']):
        raise ValueError('Incorrect file count')
    return assets


def verify_archive(path: Path, asset):
    if not path.is_file() or path.stat().st_size != asset['size']:
        raise ValueError(f"Archive missing/wrong size: {path}")
    if digest_file(path) != asset['sha256']:
        raise ValueError(f"Archive SHA256 mismatch: {path}")


def prepare_archives(repository: Path, index, archives_dir: Path | None):
    folder = archives_dir.resolve() if archives_dir else repository / '.downloads'
    folder.mkdir(parents=True, exist_ok=True)
    for number, asset in enumerate(index['assets'], 1):
        path = contained(folder, folder / safe_relative(asset['name']))
        if not path.exists():
            if archives_dir:
                raise FileNotFoundError(f'Local archive missing: {path}')
            if shutil.which('gh') is None:
                raise RuntimeError('GitHub CLI (gh) is required; install it and run gh auth login for this private repository')
            # Keep gh partial downloads separate; only verified assets become final.
            with tempfile.TemporaryDirectory(prefix='.download-', dir=folder) as temporary:
                print(f"Downloading {number}/{len(index['assets'])}: {asset['name']}", flush=True)
                subprocess.run(['gh', 'release', 'download', index['tag'], '--repo', index['repo'],
                                '--pattern', asset['name'], '--dir', temporary], check=True)
                fetched = Path(temporary) / asset['name']
                verify_archive(fetched, asset)
                os.replace(fetched, path)
        verify_archive(path, asset)
        print(f"Archive verified {number}/{len(index['assets'])}: {asset['name']}", flush=True)
    return folder


def relocation_hashes(root):
    journal = contained(root, root / '.relocation/relocation_log.json')
    if not journal.exists():
        return {}
    latest = {}
    for run in read_json(journal).get('runs', []):
        for change in run.get('changes', []):
            safe_relative(change['path'])
            # Interrupted atomic relocation can contain old or new bytes. Both
            # are checked, never used to overwrite modified user work.
            latest[change['path']] = change
    return latest


def verified_existing(root, record, relocated):
    path = contained(root, root / safe_relative(record['path']))
    if not path.exists():
        return False
    if not path.is_file():
        raise ValueError(f'Not a regular restore file: {path}')
    actual = digest_file(path)
    if actual == record['sha256']:
        return True
    change = relocated.get(record['path'])
    if change and change['before_sha256'] == record['sha256'] and actual == change['after_sha256']:
        backup = contained(root, root / '.relocation/originals' / safe_relative(record['path']))
        if backup.is_file() and digest_file(backup) == record['sha256']:
            return True
    raise ValueError(f'Refusing to overwrite modified file: {path}. Restore to a new empty destination instead.')


def install_support(repository, root):
    paths = [(repository / name, root / name) for name in SUPPORT if (repository / name).is_file()]
    for folder in ('tools', 'manifests'):
        for path in (repository / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                paths.append((path, root / path.relative_to(repository)))
    for source, destination in paths:
        contained(root, destination)
        if destination.exists():
            if digest_file(destination) != digest_file(source):
                raise ValueError(f'Refusing to replace changed support file: {destination}')
        else:
            atomic_write(root, destination, source.read_bytes())


def restore(repository: Path, destination: Path, archives_dir: Path | None = None):
    repository = repository.resolve()
    unresolved = destination.expanduser().absolute()
    for ancestor in (unresolved, *unresolved.parents):
        if ancestor.is_symlink() or (hasattr(ancestor, 'is_junction') and ancestor.is_junction()):
            raise ValueError(f'Restore destination cannot use a linked directory: {ancestor}')
    root = unresolved.resolve()
    if root == repository or root.is_relative_to(repository) or repository.is_relative_to(root):
        raise ValueError('Restore destination and repository must be separate, non-nested directories')
    manifest_path = repository / 'manifests/snapshot.json'
    manifest, index = read_json(manifest_path), read_json(repository / 'manifests/archives.json')
    assets = validate_manifest(manifest, index)
    manifest_sha = digest_file(manifest_path)
    marker = contained(root, root / STATE)
    if root.exists() and any(root.iterdir()):
        if not marker.is_file():
            raise ValueError('Destination must be empty or contain this tool\'s matching .restore-state.json; no existing project is overwritten')
        old = read_json(marker)
        if old.get('snapshot_id') != manifest['snapshot_id'] or old.get('manifest_sha256') != manifest_sha:
            raise ValueError('Destination belongs to a different snapshot')
    root.mkdir(parents=True, exist_ok=True)
    state = {'snapshot_id': manifest['snapshot_id'], 'manifest_sha256': manifest_sha,
             'status': 'restoring', 'destination': str(root)}
    started = time.monotonic()
    relocated = relocation_hashes(root)
    grouped = defaultdict(list)
    existing = 0
    for record in manifest['files']:
        if verified_existing(root, record, relocated):
            existing += 1
        else:
            grouped[record['sha256']].append(record)
    missing_bytes = sum(r['size'] for records in grouped.values() for r in records)
    # No hardlinks: later edits to one version must not alter another version.
    free = shutil.disk_usage(root).free
    download_bytes = 0 if archives_dir else sum(a['size'] for a in assets.values() if not (repository / '.downloads' / a['name']).is_file())
    if free < missing_bytes + download_bytes + 512 * 1024**2:
        raise RuntimeError(f'Insufficient free space: need about {(missing_bytes + download_bytes)/1024**3:.1f} GiB plus environment space')
    archives = prepare_archives(repository, index, archives_dir)
    # Do not downgrade a usable, verified workspace when a resume preflight
    # rejects a later user edit, missing volume, or corrupt archive.
    atomic_write(root, marker, json.dumps(state, ensure_ascii=False, indent=2).encode('utf-8'))
    by_archive = defaultdict(list)
    for sha, records in grouped.items():
        by_archive[manifest['objects'][sha]['archive']].append((sha, records))
    written = 0
    for number, asset in enumerate(index['assets'], 1):
        expected_members = {obj['member']: obj for obj in manifest['objects'].values() if obj['archive'] == asset['name']}
        with zipfile.ZipFile(archives / asset['name']) as archive:
            infos = archive.infolist()
            if len(infos) != len(expected_members) or len({i.filename for i in infos}) != len(infos):
                raise ValueError(f"Unexpected/duplicate archive members: {asset['name']}")
            for member in infos:
                if member.filename not in expected_members or member.file_size != expected_members[member.filename]['size']:
                    raise ValueError(f'Unexpected archive member/size: {member.filename}')
            for sha, records in by_archive[asset['name']]:
                canonical = contained(root, root / safe_relative(records[0]['path']))
                canonical.parent.mkdir(parents=True, exist_ok=True)
                contained(root, canonical)
                fd, temporary = tempfile.mkstemp(prefix='.restore-', dir=canonical.parent)
                h, size = hashlib.sha256(), 0
                try:
                    with os.fdopen(fd, 'wb') as output, archive.open('objects/' + sha) as input_file:
                        for block in iter(lambda: input_file.read(8 * 1024 * 1024), b''):
                            h.update(block); size += len(block); output.write(block)
                    if h.hexdigest() != sha or size != records[0]['size']:
                        raise ValueError(f'Object content SHA/size mismatch: {sha}')
                    if canonical.exists():
                        raise ValueError(f'Concurrent restore file creation: {canonical}')
                    os.replace(temporary, canonical)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
                for pos, record in enumerate(records):
                    target = contained(root, root / safe_relative(record['path']))
                    if pos:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        contained(root, target)
                        fd, temporary = tempfile.mkstemp(prefix='.restore-', dir=target.parent)
                        try:
                            with os.fdopen(fd, 'wb') as output, canonical.open('rb') as source:
                                shutil.copyfileobj(source, output, 8 * 1024 * 1024)
                            if digest_file(Path(temporary)) != sha:
                                raise ValueError(f'Duplicate copy SHA mismatch: {target}')
                            if target.exists():
                                raise ValueError(f'Concurrent restore file creation: {target}')
                            os.replace(temporary, target)
                        finally:
                            if os.path.exists(temporary):
                                os.unlink(temporary)
                    os.utime(target, ns=(record['mtime_ns'], record['mtime_ns']))
                    written += 1
        print(f"Restored volume {number}/{len(index['assets'])}: {asset['name']}; {written} new files", flush=True)
    # Independent post-extraction read/hash of EVERY logical file, not just ZIP
    # checksums, proves duplicates and member->path assignments as well.
    for pos, record in enumerate(manifest['files'], 1):
        if not verified_existing(root, record, relocated):
            raise ValueError(f"Missing restored file: {record['path']}")
        if pos % 1000 == 0:
            print(f"Verified restored file hashes {pos}/{len(manifest['files'])}", flush=True)
    install_support(repository, root)
    report = {'status': 'verified', 'snapshot_id': manifest['snapshot_id'], 'manifest_sha256': manifest_sha,
              'file_count': len(manifest['files']), 'logical_bytes': manifest['logical_bytes'],
              'archives_verified': len(index['assets']), 'new_files': written, 'existing_verified_files': existing,
              'all_files_sha256_verified': True, 'relocated_files_with_verified_original_backups': len(relocated),
              'destination': str(root), 'verified_at_utc': datetime.now(timezone.utc).isoformat(),
              'elapsed_seconds': round(time.monotonic() - started, 2),
              'note': 'Original snapshot hashes verified. Relocation changes working text only and logs independent before/after hashes.'}
    atomic_write(root, marker, json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8'))
    atomic_write(root, root / 'restore-verification.json', json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8'))
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--archives-dir', type=Path, help='Use already downloaded local volumes; do not access GitHub')
    args = parser.parse_args()
    restore(args.repository, args.destination, args.archives_dir)


if __name__ == '__main__':
    main()
