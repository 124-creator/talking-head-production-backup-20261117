"""Maintainer helper: resumable upload with server-side SHA256 verification.

Uses gh's existing credential store; no credentials are read or persisted here.
Never replaces a different asset with the same name.
"""
from pathlib import Path
import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from urllib.parse import quote


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def gh(*args):
    environment = os.environ.copy()
    # Go/gh does not read Windows' configured static proxy, unlike urllib.
    # Honor the user's existing network configuration without changing it.
    for scheme, address in urllib.request.getproxies().items():
        key = scheme.upper() + '_PROXY'
        if scheme in {'http', 'https', 'no'} and not environment.get(key):
            environment[key] = address
    for attempt in range(4):
        result = subprocess.run(['gh', *args], capture_output=True, text=True, encoding='utf-8', env=environment)
        if not result.returncode:
            return result.stdout
        if 'DELETE' in args and 'HTTP 404' in result.stderr:
            return ''
        if attempt == 3 or args[:2] == ('release', 'upload') or 'POST' in args:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        time.sleep(3 * (attempt + 1))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository', type=Path, required=True)
    p.add_argument('--artifacts', type=Path, required=True)
    p.add_argument('--installer', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--jobs', type=int, default=2)
    p.add_argument('--names', nargs='+', help='Upload/verify only these assets (parallel maintenance lane)')
    p.add_argument('--verify-only', action='store_true')
    p.add_argument('--retry-own-starters', action='store_true', help='Maintainer only: retry incomplete assets when no other process uploads the SAME names')
    args = p.parse_args()
    index = json.loads((args.repository / 'manifests/archives.json').read_text(encoding='utf-8'))
    repo, tag = index['repo'], index['tag']
    paths = []
    required = []
    for asset in index['assets']:
        if asset.get('parts'):
            paths.extend(args.artifacts / 'transport' / a['name'] for a in asset['parts'])
            required.extend(asset['parts'])
        else:
            paths.append(args.artifacts / asset['name'])
            required.append(asset)
    paths += [args.artifacts / 'snapshot.json', args.artifacts / 'archives.json', args.installer]
    expected = {path.name: {'name': path.name, 'size': path.stat().st_size, 'sha256': digest(path), 'path': path} for path in paths}
    for asset in required:
        assert expected[asset['name']]['sha256'] == asset['sha256']
    sums = args.artifacts / 'SHA256SUMS'
    sums.write_text(''.join(f"{a['sha256']}  {a['name']}\n" for a in expected.values()), encoding='ascii')
    expected[sums.name] = {'name': sums.name, 'size': sums.stat().st_size, 'sha256': digest(sums), 'path': sums}
    if args.names:
        unknown = set(args.names) - expected.keys()
        if unknown:
            raise ValueError(f'Unknown assets: {unknown}')
        expected = {name: expected[name] for name in args.names}
    releases = json.loads(gh('api', f'repos/{repo}/releases?per_page=100'))
    release = next(r for r in releases if r['tag_name'] == tag)
    release_id = release['id']

    def remote_assets():
        pages = json.loads(gh('api', f'repos/{repo}/releases/{release_id}/assets?per_page=100', '--paginate', '--slurp'))
        return {a['name']: a for page in pages for a in page}

    def matches(wanted, remote):
        return (remote.get('state') == 'uploaded' and remote['size'] == wanted['size']
                and remote.get('digest') == 'sha256:' + wanted['sha256'])

    remote = remote_assets()
    for name in expected.keys() & remote.keys():
        if not matches(expected[name], remote[name]):
            if args.retry_own_starters and remote[name].get('state') == 'starter':
                gh('api', '-X', 'DELETE', f"repos/{repo}/releases/assets/{remote[name]['id']}")
                del remote[name]
                continue
            raise RuntimeError(f'Existing asset differs or lacks server checksum: {name}; not overwriting')

    def upload(asset):
        name = asset['name']
        if name in remote:
            print(f'Already verified {name}', flush=True)
            return
        started = time.monotonic()
        for attempt in range(1, 6):
            print(f"Uploading {name} ({asset['size'] / 1024**2:.1f} MiB), attempt {attempt}", flush=True)
            try:
                # Direct official asset API avoids resolving the draft tag and
                # GraphQL on every part. gh still owns auth in its keyring.
                if attempt == 1:
                    url = f'https://uploads.github.com/repos/{repo}/releases/{release_id}/assets?name={quote(name, safe="")}'
                    actual = json.loads(gh('api', '--hostname', 'github.com', '--method', 'POST', url,
                                           '--header', 'Accept: application/vnd.github+json',
                                           '--header', 'Content-Type: application/octet-stream',
                                           '--input', str(asset['path'])))
                else:
                    gh('release', 'upload', tag, str(asset['path']), '--repo', repo)
                    actual = remote_assets().get(name)
                if not actual or not matches(asset, actual):
                    raise RuntimeError(f'Server checksum mismatch after upload: {name}')
                print(f'Verified uploaded {name}, {time.monotonic() - started:.0f}s', flush=True)
                return
            except Exception as exc:
                print(f'Upload attempt failed for {name}: {exc}', flush=True)
                actual = remote_assets().get(name)
                if actual and matches(asset, actual):
                    print(f'Verified after transient response: {name}', flush=True)
                    return
                if actual:
                    if args.retry_own_starters and actual.get('state') == 'starter':
                        gh('api', '-X', 'DELETE', f"repos/{repo}/releases/assets/{actual['id']}")
                    else:
                        raise RuntimeError(f'Incomplete/different server asset, not automatically deleting {name}: {exc}')
                if attempt == 5:
                    raise
                print(f'Retrying {name}: {exc}', flush=True)
                time.sleep(10 * attempt)

    if not args.verify_only:
        failures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            tasks = {pool.submit(upload, asset): name for name, asset in expected.items()}
            for task in concurrent.futures.as_completed(tasks):
                try:
                    task.result()
                except Exception as exc:
                    failures.append({'name': tasks[task], 'error': str(exc)})
                    print(f'FAILED after retries: {tasks[task]}: {exc}', flush=True)
        if failures:
            args.report.write_text(json.dumps({'status': 'incomplete', 'failures': failures}, indent=2), encoding='utf-8')
            raise RuntimeError(f'{len(failures)} assets remain incomplete; safe to rerun for missing parts')
    remote = remote_assets()
    checks = []
    for name, asset in expected.items():
        actual = remote.get(name)
        if not actual or not matches(asset, actual):
            raise RuntimeError(f'Final remote verification failed: {name}')
        checks.append({'name': name, 'size': actual['size'], 'local_sha256': asset['sha256'],
                       'github_digest': actual['digest'], 'asset_id': actual['id'], 'state': actual['state']})
    report = {'status': 'selected_assets_verified' if args.names else 'all_assets_verified', 'repo': repo, 'tag': tag,
              'release_id': release_id, 'asset_count': len(checks),
              'total_bytes': sum(a['size'] for a in checks), 'assets': checks}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"COMPLETE: {len(checks)} assets / {report['total_bytes']} bytes server SHA256 verified", flush=True)


if __name__ == '__main__':
    main()
