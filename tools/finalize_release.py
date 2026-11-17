"""Maintainer-only verified closeout. Tests never need GitHub or a real git repo.

Waits for existing uploader evidence; never starts an uploader, manufactures test
evidence, reads tokens, force-pushes refs, or replaces release assets. Run only
after reviewing this script and committing all production/support source files.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.request


REPO = '124-creator/talking-head-production-backup-20261117'
TAG = 'snapshot-20261117-current'
SNAPSHOT = '2026-11-17-current'
INSTALLER = 'python-3.13.5-amd64.exe'
INSTALLER_SHA = 'c1cb40978b28f696b111c36034a1bdeda17d25e35c74a08ef5e5ff405a63fc20'
PART_COUNT, ASSET_COUNT, FILE_COUNT = 286, 290, 12099
DOCUMENTS = ('reports/local-validation.json', 'reports/remote-release-verification.json', 'STATUS.md')
COMMIT_MESSAGE = 'chore: record verified Windows x64 production snapshot'
DISCLAIMER = '验证在当前 Windows x64 的独立恢复目录及全新隔离环境完成，不代表已在另一台实体电脑实测。'
LOCAL_PASSES = ('render_smoke', 'asr_smoke', 'private_download', 'local_transport_reassembly')
LOCAL_TRUE = ('unit_tests_passed', 'fresh_clone_clean', 'fresh_isolated_venvs', 'actual_verification_windows_x64')
SHA = re.compile(r'^[0-9a-f]{64}$')
REVISION = re.compile(r'^[0-9a-f]{40}$')


class GateError(RuntimeError):
    """A required precondition was not proven; do not publish."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def read_json(path: Path):
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode('utf-8-sig'))
    except (OSError, ValueError, UnicodeError) as exc:
        raise GateError(f'Required evidence/manifest is missing or invalid: {path.name}') from exc
    if not isinstance(value, dict):
        raise GateError(f'Expected a JSON object: {path.name}')
    return value, raw


def positive_int(value) -> bool:
    return type(value) is int and value > 0


def required_sha(value, label: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise GateError(f'Invalid SHA256: {label}')
    return value


def expected_assets(repository: Path):
    """Derive all required bytes/digests in precisely the uploader's order."""
    snapshot, snapshot_raw = read_json(repository / 'manifests/snapshot.json')
    index, index_raw = read_json(repository / 'manifests/archives.json')
    bootstrap, _ = read_json(repository / 'environment/python-bootstrap.json')
    for manifest in (snapshot, index):
        if manifest.get('repo') != REPO or manifest.get('tag') != TAG:
            raise GateError('Manifest repository/tag does not match this fixed backup')
    if snapshot.get('snapshot_id') != SNAPSHOT or snapshot.get('file_count') != FILE_COUNT or not isinstance(snapshot.get('files'), list) or len(snapshot['files']) != FILE_COUNT:
        raise GateError('Snapshot identity or complete original file count changed')
    if bootstrap.get('installer') != INSTALLER or bootstrap.get('sha256') != INSTALLER_SHA or bootstrap.get('bytes') != 28838672:
        raise GateError('Pinned Python bootstrap metadata changed')
    expected = {}
    archives = index.get('assets')
    if not isinstance(archives, list) or not archives:
        raise GateError('Archive index is empty')
    archive_names = set()
    for archive in archives:
        if not isinstance(archive, dict):
            raise GateError('Invalid logical archive record')
        name = archive.get('name', '')
        if not re.fullmatch(r'snapshot-(?:core|cache)-\d{3}\.zip', name) or name in archive_names:
            raise GateError('Invalid or duplicate logical archive')
        archive_names.add(name)
        required_sha(archive.get('sha256'), name)
        parts = archive.get('parts')
        if not isinstance(parts, list) or not parts or not positive_int(archive.get('size')):
            raise GateError('Every archive must have indexed transport parts')
        if any(not isinstance(part, dict) or not positive_int(part.get('size')) for part in parts):
            raise GateError('Invalid transport part metadata')
        if sum(part['size'] for part in parts) != archive['size']:
            raise GateError('Transport sizes do not reconstruct the logical ZIP')
        for number, part in enumerate(parts, 1):
            wanted_name = f'transfer-{name[:-4]}-{number:03d}.bin'
            if part.get('name') != wanted_name or wanted_name in expected:
                raise GateError('Invalid, reordered, or duplicate transport part')
            expected[wanted_name] = {'name': wanted_name, 'size': part['size'],
                                     'sha256': required_sha(part.get('sha256'), wanted_name)}
    if len(expected) != PART_COUNT:
        raise GateError(f'Expected exactly {PART_COUNT} transport parts')
    for name, raw in (('snapshot.json', snapshot_raw), ('archives.json', index_raw)):
        expected[name] = {'name': name, 'size': len(raw), 'sha256': sha256(raw)}
    expected[INSTALLER] = {'name': INSTALLER, 'size': bootstrap['bytes'], 'sha256': INSTALLER_SHA}
    # upload_release.py uses Path.write_text(newline=None) on the Windows source.
    # Its authoritative SHA256SUMS has 289 CRLF-terminated ASCII lines.
    sums = ''.join(f"{asset['sha256']}  {asset['name']}\r\n" for asset in expected.values()).encode('ascii')
    expected['SHA256SUMS'] = {'name': 'SHA256SUMS', 'size': len(sums), 'sha256': sha256(sums)}
    if len(expected) != ASSET_COUNT:
        raise GateError('Required release asset count changed')
    return expected, {'snapshot': snapshot, 'snapshot_raw': snapshot_raw, 'index_raw': index_raw,
                      'snapshot_sha256': sha256(snapshot_raw), 'archive_index_sha256': sha256(index_raw)}


def validate_local(local: dict, context: dict):
    if local.get('status') != 'passed':
        raise GateError('Local validation status is not passed')
    for field in LOCAL_PASSES:
        if local.get(field) != 'passed':
            raise GateError(f'Required local gate did not pass: {field}')
    for field in LOCAL_TRUE:
        if local.get(field) is not True:
            raise GateError(f'Required local gate is not true: {field}')
    if type(local.get('snapshot_files_verified')) is not int or local['snapshot_files_verified'] != FILE_COUNT:
        raise GateError('Full snapshot file verification was not proven')
    if type(local.get('unit_tests_run')) is not int or local['unit_tests_run'] < 38:
        raise GateError('At least 38 passing unit tests are required')
    if type(local.get('git_source_blobs_matched')) is not int or local['git_source_blobs_matched'] != 253:
        raise GateError('Fresh GitHub source blob comparison was not proven')
    if type(local.get('system_font_mismatches')) is not int or local['system_font_mismatches'] != 0:
        raise GateError('System font baseline has mismatches or is unverified')
    if local.get('snapshot_manifest_sha256') != context['snapshot_sha256']:
        raise GateError('Local validation is for a different snapshot manifest')
    if not isinstance(local.get('validated_revision'), str) or not REVISION.fullmatch(local['validated_revision']):
        raise GateError('Local validation must pin a full Git commit SHA')
    if not isinstance(local.get('note'), str) or not local['note'].strip():
        raise GateError('Local evidence must disclose its actual verification context')


def wait_remote_report(path: Path, wait: bool, *, sleep=time.sleep, monotonic=time.monotonic):
    deadline = monotonic() + 12 * 60 * 60
    while True:
        try:
            report, raw = read_json(path)
            if report.get('status') == 'all_assets_verified':
                return report, raw
            failure = 'Uploader has not proven all_assets_verified'
        except GateError:
            failure = 'Uploader completion report is not yet available'
        if not wait:
            raise GateError(failure)
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise GateError('Timed out after at most 12 hours; no publication was attempted')
        print('Waiting for the existing uploader verification report (no uploader is started)...', flush=True)
        sleep(min(60, remaining))


def verify_asset_rows(rows, expected, *, reported: bool):
    if not isinstance(rows, list) or len(rows) != ASSET_COUNT:
        raise GateError(f'Expected exactly {ASSET_COUNT} release asset records')
    actual = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('name'), str) or row['name'] in actual:
            raise GateError('Duplicate or invalid release asset record')
        actual[row['name']] = row
    if actual.keys() != expected.keys():
        raise GateError('Release asset names have missing or unexpected entries')
    for name, wanted in expected.items():
        row = actual[name]
        digest_key = 'github_digest' if reported else 'digest'
        id_key = 'asset_id' if reported else 'id'
        if row.get('state') != 'uploaded' or type(row.get('size')) is not int or row['size'] != wanted['size'] or row.get(digest_key) != 'sha256:' + wanted['sha256'] or not positive_int(row.get(id_key)):
            raise GateError(f'Asset state, size, ID, or GitHub SHA256 mismatch: {name}')
        if reported and row.get('local_sha256') != wanted['sha256']:
            raise GateError(f'Uploader local SHA256 mismatch: {name}')
    return actual


def verify_report(report: dict, expected):
    if report.get('status') != 'all_assets_verified' or report.get('repo') != REPO or report.get('tag') != TAG:
        raise GateError('Uploader report identity/status does not match')
    if not positive_int(report.get('release_id')) or report.get('asset_count') != ASSET_COUNT or report.get('total_bytes') != sum(a['size'] for a in expected.values()):
        raise GateError('Uploader release ID, count, or total size is invalid')
    return verify_asset_rows(report.get('assets'), expected, reported=True)


def documents_for(local: dict, local_raw: bytes, report: dict, live: dict, expected, context):
    public_local = {'status': 'passed', 'snapshot_files_verified': FILE_COUNT,
                    'unit_tests_run': local['unit_tests_run'], 'unit_tests_passed': True}
    public_local.update({field: local[field] for field in (*LOCAL_PASSES, *LOCAL_TRUE)})
    public_local.update({'git_source_blobs_matched': 253, 'system_font_mismatches': 0,
                         'snapshot_manifest_sha256': context['snapshot_sha256'],
                         'validated_revision': local['validated_revision'],
                         'source_evidence_sha256': sha256(local_raw), 'note': DISCLAIMER})
    public_remote = {'status': 'all_assets_verified', 'repo': REPO, 'tag': TAG,
                     'release_id': report['release_id'], 'asset_count': ASSET_COUNT,
                     'total_bytes': sum(a['size'] for a in expected.values()),
                     'snapshot_manifest_sha256': context['snapshot_sha256'],
                     'archive_index_sha256': context['archive_index_sha256'], 'live_rechecked': True,
                     'assets': [{'name': name, 'size': wanted['size'], 'local_sha256': wanted['sha256'],
                                 'github_digest': live[name]['digest'], 'asset_id': live[name]['id'],
                                 'state': 'uploaded'} for name, wanted in expected.items()]}
    status = f'''# 备份内容与恢复验证：已完成

- 私有仓库：https://github.com/{REPO}
- 恢复包：https://github.com/{REPO}/releases/tag/{TAG}
- 原始快照：{SNAPSHOT}，共 {FILE_COUNT:,} 个文件。
- 远端：{PART_COUNT} 个传输分块及 4 个元数据/安装器资产，共 {ASSET_COUNT} 项；逐项核对 GitHub SHA256、大小和 uploaded 状态。
- 本地：{local['unit_tests_run']} 项单元测试通过；完整文件恢复、独立环境、两条成片/浏览器、离线 ASR、私有下载及分块重组验证通过。
- 原始快照 SHA256：`{context['snapshot_sha256']}`。
- {DISCLAIMER}

完整证据见 `reports/`。本文件不包含账户凭证或本机私密路径，也不声称迁移了操作系统、登录状态或原聊天窗口。
新电脑按 README 执行 `Restore.ps1`；先读 `RESTORE_CONTEXT.md`，不要覆盖既有成片。
最终 Release 草稿状态以 GitHub API/页面为准；维护脚本仅在所有门控通过且提交、标签推送成功后发布。
'''
    return {DOCUMENTS[0]: json_bytes(public_local), DOCUMENTS[1]: json_bytes(public_remote), DOCUMENTS[2]: status.encode('utf-8')}


def atomic_write(path: Path, data: bytes, root: Path):
    root = root.resolve()
    if not path.resolve().is_relative_to(root):
        raise GateError('Output path escapes its approved directory')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == data:
        return
    descriptor, temporary = tempfile.mkstemp(prefix='.finalize-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class ProductionBackend:
    def __init__(self, repository: Path):
        self.repository = repository.resolve()
        self._gh_function = None

    def gh(self, *args):
        if self._gh_function is None:
            spec = importlib.util.spec_from_file_location('_verified_upload_helper', self.repository / 'tools/upload_release.py')
            if spec is None or spec.loader is None:
                raise GateError('Cannot load the reviewed GitHub transport helper')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # __main__ is deliberately not invoked.
            self._gh_function = module.gh
        try:
            return self._gh_function(*args)
        except Exception as exc:
            raise GateError('GitHub operation failed; check gh authentication/network without exposing credentials') from exc

    def gh_json(self, *args):
        try:
            return json.loads(self.gh(*args))
        except ValueError as exc:
            raise GateError('GitHub returned invalid JSON') from exc

    def git(self, *args, network=False, allowed=(0,)):
        environment = os.environ.copy()
        for scheme, address in urllib.request.getproxies().items():
            key = scheme.upper() + '_PROXY'
            if scheme in {'http', 'https', 'no'} and not environment.get(key):
                environment[key] = address
        command = ['git']
        if network:
            command += ['-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential']
        result = subprocess.run(command + list(args), cwd=self.repository, env=environment,
                                capture_output=True, text=True, encoding='utf-8', timeout=300)
        if result.returncode not in allowed:
            raise GateError(f'Git operation failed (exit {result.returncode}); no refs are forced or overwritten')
        return result.stdout

    def state(self):
        if Path(self.git('rev-parse', '--show-toplevel').strip()).resolve() != self.repository:
            raise GateError('Not the requested Git repository root')
        for arguments in (('remote', 'get-url', 'origin'), ('remote', 'get-url', '--push', 'origin')):
            if self.git(*arguments).strip().removesuffix('.git') != 'https://github.com/' + REPO:
                raise GateError('origin fetch/push URL does not match the approved private repository')
        return {'head': self.git('rev-parse', 'HEAD').strip(),
                'branch': self.git('symbolic-ref', '--quiet', '--short', 'HEAD').strip(),
                'clean': not self.git('status', '--porcelain=v1', '--untracked-files=all').strip()}

    def prior_closeout(self, head: str, validated: str, documents: dict):
        return (self.git('log', '-1', '--format=%P', head).strip() == validated
                and self.git('log', '-1', '--format=%s', head).strip() == COMMIT_MESSAGE
                and set(self.git('diff', '--name-only', validated, head).splitlines()).issubset(DOCUMENTS)
                and self.documents_match(documents))

    def documents_match(self, documents):
        return all((self.repository / name).is_file() and (self.repository / name).read_bytes() == data
                   for name, data in documents.items())

    def tags(self):
        local = None
        # Missing refs are a normal first-run case; for-each-ref exits zero.
        references = self.git('for-each-ref', '--format=%(objectname) %(refname)', 'refs/tags/' + TAG)
        raw = next((line for line in references.splitlines() if line.split()[-1] == 'refs/tags/' + TAG), '')
        if raw:
            local = {'object': raw.split()[0], 'annotated': self.git('cat-file', '-t', 'refs/tags/' + TAG).strip() == 'tag',
                     'commit': self.git('rev-parse', 'refs/tags/' + TAG + '^{commit}').strip()}
        rows = self.git('ls-remote', '--tags', 'origin', 'refs/tags/' + TAG, 'refs/tags/' + TAG + '^{}', network=True)
        remote_rows = dict(line.split('\t', 1)[::-1] for line in rows.splitlines() if line)
        ref = 'refs/tags/' + TAG
        remote = None if ref not in remote_rows else {'object': remote_rows[ref],
                 'annotated': ref + '^{}' in remote_rows, 'commit': remote_rows.get(ref + '^{}', remote_rows[ref])}
        return local, remote

    def live_release(self, release_id: int):
        repo = self.gh_json('repo', 'view', REPO, '--json', 'isPrivate,nameWithOwner')
        if repo.get('isPrivate') is not True or repo.get('nameWithOwner') != REPO:
            raise GateError('Repository is not the approved private repository')
        release = self.gh_json('api', f'repos/{REPO}/releases/{release_id}')
        pages = self.gh_json('api', f'repos/{REPO}/releases/{release_id}/assets?per_page=100', '--paginate', '--slurp')
        if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
            raise GateError('Invalid paginated GitHub assets response')
        return release, [row for page in pages for row in page]

    def record_documents(self, documents, expected_head):
        if self.state() != {'head': expected_head, 'branch': 'main', 'clean': True}:
            raise GateError('Git changed during verification; no documentation was written')
        for name, data in documents.items():
            atomic_write(self.repository / name, data, self.repository)
        rows = self.git('status', '--porcelain=v1', '-z', '--untracked-files=all').split('\0')
        if any(row and (len(row) < 4 or row[3:] not in DOCUMENTS or 'R' in row[:2] or 'C' in row[:2]) for row in rows):
            raise GateError('Unrelated concurrent Git edits detected; nothing will be committed')
        self.git('add', '--', *DOCUMENTS)
        staged = set(filter(None, self.git('diff', '--cached', '--name-only', '-z').split('\0')))
        if not staged.issubset(DOCUMENTS):
            raise GateError('Unrelated staged changes detected; nothing will be committed')
        if staged:
            self.git('commit', '-m', COMMIT_MESSAGE, '--only', '--', *DOCUMENTS)
        state = self.state()
        if state['branch'] != 'main' or not state['clean']:
            raise GateError('Git is not clean on main after the evidence commit')
        return state['head']

    def push_refs(self, head):
        if self.state() != {'head': head, 'branch': 'main', 'clean': True}:
            raise GateError('Git changed before push')
        self.git('push', 'origin', head + ':refs/heads/main', network=True)
        remote_main = self.git('ls-remote', 'origin', 'refs/heads/main', network=True).strip()
        if not remote_main or remote_main.split()[0] != head:
            raise GateError('Remote main does not match the verified closeout commit')
        local, remote = self.tags()
        check_tags(local, remote, head, documents_match=True)
        if local is None and remote is not None:
            self.git('fetch', 'origin', 'tag', TAG, network=True)
        elif local is None:
            self.git('tag', '-a', TAG, '-m', 'Verified complete Windows x64 talking-head production snapshot', head)
        self.git('push', 'origin', 'refs/tags/' + TAG, network=True)
        local, remote = self.tags()
        check_tags(local, remote, head, documents_match=True)
        if local is None or remote is None or local['object'] != remote['object']:
            raise GateError('Annotated tag is not identical locally and on GitHub')

    def publish_release(self, release_id):
        release = self.gh_json('api', f'repos/{REPO}/releases/{release_id}')
        verify_release_identity(release, release_id)
        if release['draft']:
            notes = ('两条口播完整工程、素材、历史版本、缓存、skills、离线运行环境均已备份。'
                     '290项资产已逐项核对GitHub SHA256；Windows x64独立目录恢复验证通过。'
                     '新电脑先clone仓库，按README运行Restore.ps1；git clone本身不含大文件。'
                     '未迁移账户凭证或原聊天窗口；非另一台实体电脑实测。')
            self.gh('release', 'edit', TAG, '--repo', REPO, '--draft=false', '--latest', '--notes', notes)
        release = self.gh_json('api', f'repos/{REPO}/releases/{release_id}')
        verify_release_identity(release, release_id)
        if release['draft'] is not False:
            raise GateError('Release is still a draft after publication request')


def verify_release_identity(release, release_id):
    if not isinstance(release, dict) or release.get('id') != release_id or release.get('tag_name') != TAG or type(release.get('draft')) is not bool:
        raise GateError('Live Release ID, tag, or draft state differs')


def check_tags(local, remote, head, *, documents_match):
    for tag in (local, remote):
        if tag is not None and (tag.get('commit') != head or tag.get('annotated') is not True):
            raise GateError('Existing snapshot tag points elsewhere or is not annotated; it will not be moved')
    if local is not None and remote is not None and local['object'] != remote['object']:
        raise GateError('Local and remote annotated tag objects differ; no force push is allowed')
    if not documents_match and (local is not None or remote is not None):
        raise GateError('Existing tag predates the final evidence commit; refusing to move it')


def finalize(repository: Path, verification: Path, *, wait=False, backend=None):
    repository, verification = repository.resolve(), verification.resolve()
    expected, context = expected_assets(repository)
    local_path, remote_path = verification / 'local-validation.json', verification / 'remote-release-verification.json'
    local, local_raw = read_json(local_path)
    validate_local(local, context)
    report, report_raw = wait_remote_report(remote_path, wait)
    recorded = verify_report(report, expected)
    backend = backend if backend is not None else ProductionBackend(repository)
    state = backend.state()
    if state.get('branch') != 'main' or state.get('clean') is not True:
        raise GateError('Git must be clean on main before closeout')
    release, rows = backend.live_release(report['release_id'])
    verify_release_identity(release, report['release_id'])
    live = verify_asset_rows(rows, expected, reported=False)
    if any(live[name]['id'] != recorded[name]['asset_id'] for name in expected):
        raise GateError('Uploader evidence and current GitHub asset IDs differ')
    documents = documents_for(local, local_raw, report, live, expected, context)
    if state['head'] != local['validated_revision'] and not backend.prior_closeout(state['head'], local['validated_revision'], documents):
        raise GateError('HEAD is neither the validated revision nor its identical three-file closeout commit')
    check_tags(*backend.tags(), state['head'], documents_match=backend.documents_match(documents))
    if local_path.read_bytes() != local_raw or remote_path.read_bytes() != report_raw or (repository / 'manifests/snapshot.json').read_bytes() != context['snapshot_raw'] or (repository / 'manifests/archives.json').read_bytes() != context['index_raw']:
        raise GateError('Input evidence/manifests changed during verification')
    head = backend.record_documents(documents, state['head'])
    backend.push_refs(head)
    backend.publish_release(report['release_id'])
    completion = {'status': 'complete', 'repo': REPO, 'url': 'https://github.com/' + REPO,
                  'release_url': f'https://github.com/{REPO}/releases/tag/{TAG}', 'release_id': report['release_id'],
                  'commit': head, 'tag': TAG, 'asset_count': ASSET_COUNT, 'snapshot_files_verified': FILE_COUNT,
                  'total_asset_bytes': sum(asset['size'] for asset in expected.values()),
                  'snapshot_manifest_sha256': context['snapshot_sha256'], 'note': DISCLAIMER}
    atomic_write(verification / 'final-completion.json', json_bytes(completion), verification)
    return completion


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--verification', type=Path, required=True)
    parser.add_argument('--wait', action='store_true', help='Wait up to 12 hours, polling the existing uploader report every 60 seconds')
    args = parser.parse_args(argv)
    try:
        result = finalize(args.repository, args.verification, wait=args.wait)
    except (GateError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'not_finalized', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
