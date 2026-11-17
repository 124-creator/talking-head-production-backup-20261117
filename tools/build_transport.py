"""Split unchanged logical ZIP volumes into small, SHA256-indexed upload parts.

The snapshot content/object manifest stays unchanged. Transport parts reduce
lost progress on unreliable long-lived upload connections. Never overwrites a
different existing part. Use only on an unpublished snapshot under maintenance.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def build(repository, artifacts, part_mib=48):
    if not 1 <= part_mib <= 48:
        raise ValueError('Transport parts must be between 1 and 48 MiB')
    folder = artifacts / 'transport'
    folder.mkdir(parents=True, exist_ok=True)
    path = repository / 'manifests/archives.json'
    index = json.loads(path.read_text(encoding='utf-8'))
    count = 0
    for asset in index['assets']:
        source = artifacts / asset['name']
        if source.stat().st_size != asset['size'] or digest(source) != asset['sha256']:
            raise ValueError(f"Logical ZIP checksum mismatch: {asset['name']}")
        parts, parent = [], hashlib.sha256()
        with source.open('rb') as stream:
            while block := stream.read(part_mib * 1024**2):
                number = len(parts) + 1
                name = f'transfer-{source.stem}-{number:03d}.bin'
                target = folder / name
                sha = hashlib.sha256(block).hexdigest()
                parent.update(block)
                if target.exists():
                    if target.stat().st_size != len(block) or digest(target) != sha:
                        raise ValueError(f'Refusing to overwrite different transport part: {target}')
                else:
                    with target.open('xb') as output:
                        output.write(block)
                parts.append({'name': name, 'size': len(block), 'sha256': sha})
                count += 1
        if parent.hexdigest() != asset['sha256']:
            raise ValueError('Logical ZIP changed during split')
        asset['parts'] = parts
        print(f"Split {asset['name']}: {len(parts)} parts", flush=True)
    index['transport'] = {'kind': 'ordered-binary-parts', 'max_part_bytes': part_mib * 1024**2,
                          'part_count': count, 'note': 'Concatenate parts in listed order, then verify the original ZIP SHA256.'}
    content = json.dumps(index, ensure_ascii=False, indent=2).encode('utf-8')
    temporary = path.with_suffix('.json.transport-tmp')
    temporary.write_bytes(content)
    os.replace(temporary, path)
    (artifacts / 'archives.json').write_bytes(content)
    print(f'Complete: {count} transport parts; logical ZIPs and snapshot.json unchanged', flush=True)
    return index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository', type=Path, required=True)
    p.add_argument('--artifacts', type=Path, required=True)
    p.add_argument('--part-mib', type=int, default=48)
    args = p.parse_args()
    build(args.repository, args.artifacts, args.part_mib)


if __name__ == '__main__':
    main()
