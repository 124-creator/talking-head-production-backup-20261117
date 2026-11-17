from pathlib import Path
import copy
import contextlib
import io
import os
import subprocess
import threading
import hashlib
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('restore', Path(__file__).resolve().parents[1] / 'tools/restore_snapshot.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo, self.archives, self.dest = self.base / 'repo', self.base / 'archives', self.base / 'dest'
        (self.repo / 'manifests').mkdir(parents=True)
        (self.repo / 'tools').mkdir()
        self.archives.mkdir()
        self.content = b'original media\0\xff'
        self.sha = hashlib.sha256(self.content).hexdigest()
        archive = self.archives / 'snapshot-core-001.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('objects/' + self.sha, self.content)
        asset = {'name': archive.name, 'sha256': r.digest_file(archive), 'size': archive.stat().st_size}
        self.m = {'format_version': 1, 'snapshot_id': 'fixture', 'repo': 'a/b', 'tag': 't',
                  'file_count': 2, 'logical_bytes': len(self.content) * 2,
                  'files': [{'path': path, 'sha256': self.sha, 'size': len(self.content), 'mtime_ns': 1700000000000000000}
                            for path in ('workspace/a.mp4', 'workspace/b.mp4')],
                  'objects': {self.sha: {'archive': archive.name, 'member': 'objects/' + self.sha, 'size': len(self.content)}}}
        self.index = {'repo': 'a/b', 'tag': 't', 'assets': [asset]}
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        (self.repo / 'manifests/snapshot.json').write_text(json.dumps(self.m), encoding='utf-8')
        (self.repo / 'manifests/archives.json').write_text(json.dumps(self.index), encoding='utf-8')

    def test_full_restore_and_resume_independent_copies(self):
        report = r.restore(self.repo, self.dest, self.archives)
        self.assertTrue(report['all_files_sha256_verified'])
        report = r.restore(self.repo, self.dest, self.archives)
        self.assertEqual(report['new_files'], 0)
        (self.dest / 'workspace/a.mp4').write_bytes(b'edit')
        self.assertEqual((self.dest / 'workspace/b.mp4').read_bytes(), self.content)
        with self.assertRaisesRegex(ValueError, 'modified file'):
            r.restore(self.repo, self.dest, self.archives)
        self.assertEqual(r.read_json(self.dest / r.STATE)['status'], 'verified')

    def test_destination_existing_not_owned(self):
        self.dest.mkdir(); (self.dest / 'user.txt').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'must be empty'):
            r.restore(self.repo, self.dest, self.archives)
        self.assertEqual((self.dest / 'user.txt').read_text(), 'keep')

    def test_traversal_and_windows_paths(self):
        for path in ('../x', '/x', 'C:/x', 'a/../../x', 'a\\x', 'a//x', 'a/./x', 'NUL.txt', 'x./y'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                r.safe_relative(path)

    def test_path_case_collision(self):
        self.m['files'][1]['path'] = 'WORKSPACE/A.mp4'
        with self.assertRaisesRegex(ValueError, 'colliding'):
            r.validate_manifest(self.m, self.index)

    def test_corrupt_archive(self):
        archive = self.archives / self.index['assets'][0]['name']
        data = bytearray(archive.read_bytes()); data[20] ^= 1; archive.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            r.restore(self.repo, self.dest, self.archives)

    def test_missing_archive_does_not_download_when_local(self):
        (self.archives / self.index['assets'][0]['name']).unlink()
        with self.assertRaises(FileNotFoundError):
            r.restore(self.repo, self.dest, self.archives)

    def test_object_wrong_content_detected_even_archive_checksum_valid(self):
        archive = self.archives / self.index['assets'][0]['name']
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('objects/' + self.sha, b'X' * len(self.content))
        self.index['assets'][0].update(size=archive.stat().st_size, sha256=r.digest_file(archive)); self.save()
        with self.assertRaisesRegex(ValueError, 'Object content SHA'):
            r.restore(self.repo, self.dest, self.archives)

    def test_extra_zip_member_rejected(self):
        archive = self.archives / self.index['assets'][0]['name']
        with zipfile.ZipFile(archive, 'a') as z:
            z.writestr('../escape', 'bad')
        self.index['assets'][0].update(size=archive.stat().st_size, sha256=r.digest_file(archive)); self.save()
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            r.restore(self.repo, self.dest, self.archives)
        self.assertFalse((self.base / 'escape').exists())

    def test_relocated_resume_preserves_backup_and_rejects_later_edit(self):
        r.restore(self.repo, self.dest, self.archives)
        path = self.dest / 'workspace/a.mp4'
        backup = self.dest / '.relocation/originals/workspace/a.mp4'
        backup.parent.mkdir(parents=True)
        backup.write_bytes(self.content)
        relocated = b'working path relocated'
        path.write_bytes(relocated)
        journal = {'schema_version': 1, 'runs': [{'status': 'complete', 'changes': [
            {'path': 'workspace/a.mp4', 'before_sha256': self.sha,
             'after_sha256': hashlib.sha256(relocated).hexdigest()}]}]}
        (self.dest / '.relocation/relocation_log.json').write_text(json.dumps(journal))
        report = r.restore(self.repo, self.dest, self.archives)
        self.assertEqual(report['new_files'], 0)
        self.assertEqual(path.read_bytes(), relocated)
        path.write_bytes(b'new edit')
        with self.assertRaisesRegex(ValueError, 'modified file'):
            r.restore(self.repo, self.dest, self.archives)
        self.assertEqual(r.read_json(self.dest / r.STATE)['status'], 'verified')
        self.assertEqual(path.read_bytes(), b'new edit')

    def test_bad_relocation_original_backup_rejected(self):
        r.restore(self.repo, self.dest, self.archives)
        relocated = b'moved'
        (self.dest / 'workspace/a.mp4').write_bytes(relocated)
        backup = self.dest / '.relocation/originals/workspace/a.mp4'
        backup.parent.mkdir(parents=True); backup.write_bytes(b'not original')
        journal = {'runs': [{'changes': [{'path': 'workspace/a.mp4', 'before_sha256': self.sha,
                                       'after_sha256': hashlib.sha256(relocated).hexdigest()}]}]}
        (self.dest / '.relocation/relocation_log.json').write_text(json.dumps(journal))
        with self.assertRaisesRegex(ValueError, 'modified file'):
            r.restore(self.repo, self.dest, self.archives)

    def test_nested_destination_rejected_before_writes(self):
        with self.assertRaisesRegex(ValueError, 'non-nested'):
            r.restore(self.repo, self.repo / 'nested', self.archives)
        self.assertFalse((self.repo / 'nested').exists())

    def test_interrupted_duplicate_copy_resumes_without_partial_target(self):
        def interrupted_copy(source, output, length):
            output.write(source.read(2))
            raise OSError('simulated interrupted write')
        with patch.object(r.shutil, 'copyfileobj', interrupted_copy):
            with self.assertRaisesRegex(OSError, 'simulated'):
                r.restore(self.repo, self.dest, self.archives)
        self.assertTrue((self.dest / 'workspace/a.mp4').is_file())
        self.assertFalse((self.dest / 'workspace/b.mp4').exists())
        self.assertEqual(list((self.dest / 'workspace').glob('.restore-*')), [])
        self.assertTrue(r.restore(self.repo, self.dest, self.archives)['all_files_sha256_verified'])


    def transport_parts(self, subfolder='', chunk_size=47):
        asset = self.index['assets'][0]
        original = (self.archives / asset['name']).read_bytes()
        directory = self.archives / subfolder
        directory.mkdir(parents=True, exist_ok=True)
        parts, contents = [], {}
        for position, offset in enumerate(range(0, len(original), chunk_size), 1):
            data = original[offset:offset + chunk_size]
            name = f'transfer-snapshot-core-001-{position:03d}.bin'
            (directory / name).write_bytes(data)
            parts.append({'name': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
            contents[name] = data
        asset['parts'] = parts
        self.save()
        return original, contents

    def test_local_parts_reassemble_exact_bytes_and_restore_without_network(self):
        original, contents = self.transport_parts()
        asset = self.index['assets'][0]
        (self.archives / asset['name']).unlink()
        with patch.object(r.subprocess, 'run') as network:
            report = r.restore(self.repo, self.dest, self.archives)
        network.assert_not_called()
        self.assertTrue(report['all_files_sha256_verified'])
        self.assertEqual((self.archives / asset['name']).read_bytes(), original)
        for name, data in contents.items():
            self.assertEqual((self.archives / name).read_bytes(), data)
        self.assertFalse((self.repo / '.downloads').exists())

    def test_local_transport_subfolder_is_supported_and_never_deleted(self):
        original, contents = self.transport_parts('transport')
        asset = self.index['assets'][0]
        (self.archives / asset['name']).unlink()
        with patch.object(r.subprocess, 'run') as network:
            result = r.prepare_archives(self.repo, self.index, self.archives)
        network.assert_not_called()
        self.assertEqual(result, self.archives.resolve())
        self.assertEqual((result / asset['name']).read_bytes(), original)
        for name, data in contents.items():
            self.assertEqual((self.archives / 'transport' / name).read_bytes(), data)

    def test_complete_local_zip_wins_even_when_parts_are_unavailable(self):
        original, contents = self.transport_parts()
        for name in contents:
            (self.archives / name).unlink()
        path = self.archives / self.index['assets'][0]['name']
        before = path.stat().st_mtime_ns
        with patch.object(r, 'local_parts') as parts, patch.object(r.subprocess, 'run') as network:
            r.prepare_archives(self.repo, self.index, self.archives)
        parts.assert_not_called()
        network.assert_not_called()
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(path.stat().st_mtime_ns, before)

    def test_corrupt_local_part_rejected_without_network_or_mutation(self):
        _, contents = self.transport_parts()
        asset = self.index['assets'][0]
        (self.archives / asset['name']).unlink()
        name = next(iter(contents))
        bad = b'X' * len(contents[name])
        (self.archives / name).write_bytes(bad)
        with patch.object(r.subprocess, 'run') as network:
            with self.assertRaisesRegex(ValueError, 'verified local transport part'):
                r.prepare_archives(self.repo, self.index, self.archives)
        network.assert_not_called()
        self.assertFalse((self.archives / asset['name']).exists())
        self.assertEqual((self.archives / name).read_bytes(), bad)
        self.assertEqual(list(self.archives.glob('.assemble-*')), [])

    def test_wrong_part_order_fails_parent_hash_without_partial_zip(self):
        _, contents = self.transport_parts()
        asset = self.index['assets'][0]
        (self.archives / asset['name']).unlink()
        asset['parts'].reverse()
        with self.assertRaisesRegex(ValueError, 'Reassembled archive SHA256'):
            r.prepare_archives(self.repo, self.index, self.archives)
        self.assertFalse((self.archives / asset['name']).exists())
        self.assertEqual(list(self.archives.glob('.assemble-*')), [])
        for name, data in contents.items():
            self.assertEqual((self.archives / name).read_bytes(), data)

    def test_transport_metadata_rejects_traversal_non_ascii_and_invalid_sizes(self):
        self.transport_parts()
        original = copy.deepcopy(self.index)
        for name in ('../escape.bin', '/escape.bin', 'C:/escape.bin', 'a\\b.bin',
                     'part?.bin', '中.bin', 'CON.bin', 'part.bin ', '.hidden.bin'):
            with self.subTest(name=name):
                index = copy.deepcopy(original)
                index['assets'][0]['parts'][0]['name'] = name
                with self.assertRaises(ValueError):
                    r.validate_manifest(self.m, index)
                with self.assertRaises(ValueError):
                    r.prepare_archives(self.repo, index, None)
        for size in (0, -1, True, '47', r.MAX_PART_BYTES + 1):
            with self.subTest(size=size):
                index = copy.deepcopy(original)
                index['assets'][0]['parts'][0]['size'] = size
                with self.assertRaises(ValueError):
                    r.validate_manifest(self.m, index)
        index = copy.deepcopy(original)
        index['assets'][0]['parts'][0]['sha256'] = 'bad'
        with self.assertRaises(ValueError):
            r.validate_manifest(self.m, index)
        index = copy.deepcopy(original)
        index['assets'][0]['parts'][0]['size'] += 1
        with self.assertRaisesRegex(ValueError, 'sum'):
            r.validate_manifest(self.m, index)
        index = copy.deepcopy(original)
        index['assets'][0]['parts'][1]['name'] = index['assets'][0]['parts'][0]['name'].upper()
        with self.assertRaisesRegex(ValueError, 'colliding'):
            r.validate_manifest(self.m, index)
        self.assertFalse((self.repo / '.downloads').exists())

    def test_remote_parts_retry_three_attempts_cache_resume_and_precise_cleanup(self):
        original, contents = self.transport_parts()
        asset = self.index['assets'][0]
        cache = self.repo / '.downloads/.parts' / asset['name']
        cache.mkdir(parents=True)
        first, retry = list(contents)[:2]
        (cache / first).write_bytes(contents[first])
        (cache / 'unrelated.keep').write_bytes(b'leave this exact file alone')
        counts, active, maximum = {}, 0, 0
        lock = threading.Lock()

        def download(arguments, **kwargs):
            nonlocal active, maximum
            name = arguments[arguments.index('--pattern') + 1]
            temporary = Path(arguments[arguments.index('--output') + 1])
            with lock:
                counts[name] = counts.get(name, 0) + 1
                attempt = counts[name]
                active += 1
                maximum = max(maximum, active)
            try:
                threading.Event().wait(0.01)
                self.assertIn('--clobber', arguments)
                self.assertTrue(kwargs['capture_output'])
                if name == retry and attempt < 3:
                    temporary.write_bytes(b'partial')
                    raise subprocess.CalledProcessError(1, arguments, stderr=b'private authentication diagnostic')
                temporary.write_bytes(contents[name])
            finally:
                with lock:
                    active -= 1

        output = io.StringIO()
        with patch.object(r.shutil, 'which', return_value='gh'), \
             patch.object(r.subprocess, 'run', side_effect=download), \
             patch.object(r.time, 'sleep'), contextlib.redirect_stdout(output):
            folder = r.prepare_archives(self.repo, self.index, None)
        self.assertEqual((folder / asset['name']).read_bytes(), original)
        self.assertNotIn(first, counts)
        self.assertEqual(counts[retry], 3)
        self.assertLessEqual(maximum, 3)
        self.assertGreaterEqual(maximum, 2)
        self.assertNotIn('private authentication diagnostic', output.getvalue())
        self.assertEqual((cache / 'unrelated.keep').read_bytes(), b'leave this exact file alone')
        for name in contents:
            self.assertFalse((cache / name).exists())
        self.assertEqual(list(cache.glob('.download-*')), [])

    def test_remote_part_failure_keeps_only_verified_cache_and_stops_after_three(self):
        _, contents = self.transport_parts()
        part = self.index['assets'][0]['parts'][0]
        cache = self.repo / '.downloads/.parts/cache'
        cache.mkdir(parents=True)
        attempts = []

        def fail(arguments, **kwargs):
            temporary = Path(arguments[arguments.index('--output') + 1])
            attempts.append(temporary)
            temporary.write_bytes(b'partial')
            raise subprocess.CalledProcessError(1, arguments, stderr=b'do not expose credential details')

        with patch.object(r.shutil, 'which', return_value='gh'), \
             patch.object(r.subprocess, 'run', side_effect=fail), patch.object(r.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'after 3 attempts') as failure:
                r.download_verified(self.index, part, cache, {})
        self.assertEqual(len(attempts), 3)
        self.assertEqual(len(set(attempts)), 3)
        self.assertNotIn('credential', str(failure.exception))
        self.assertFalse((cache / part['name']).exists())
        self.assertEqual(list(cache.iterdir()), [])

    def test_wrong_downloaded_part_hash_is_retried_before_atomic_commit(self):
        _, contents = self.transport_parts()
        part = self.index['assets'][0]['parts'][0]
        cache = self.repo / '.downloads/.parts/cache'
        cache.mkdir(parents=True)
        (cache / part['name']).write_bytes(b'X' * part['size'])
        calls = []

        def download(arguments, **kwargs):
            calls.append(arguments)
            temporary = Path(arguments[arguments.index('--output') + 1])
            temporary.write_bytes(b'X' * part['size'] if len(calls) == 1 else contents[part['name']])

        with patch.object(r.shutil, 'which', return_value='gh'), \
             patch.object(r.subprocess, 'run', side_effect=download), patch.object(r.time, 'sleep'):
            result = r.download_verified(self.index, part, cache, {})
        self.assertEqual(len(calls), 2)
        self.assertEqual(result.read_bytes(), contents[part['name']])
        self.assertEqual(list(cache.glob('.download-*')), [])

    def test_failed_parent_hash_preserves_remote_parts_for_offline_resume(self):
        original, contents = self.transport_parts()
        asset = self.index['assets'][0]
        ordered = copy.deepcopy(asset['parts'])
        asset['parts'].reverse()
        cache = self.repo / '.downloads/.parts' / asset['name']
        cache.mkdir(parents=True)
        for name, data in contents.items():
            (cache / name).write_bytes(data)
        with patch.object(r.subprocess, 'run') as network:
            with self.assertRaisesRegex(ValueError, 'Reassembled archive SHA256'):
                r.prepare_archives(self.repo, self.index, None)
        network.assert_not_called()
        for name, data in contents.items():
            self.assertEqual((cache / name).read_bytes(), data)
        self.assertFalse((self.repo / '.downloads' / asset['name']).exists())
        asset['parts'] = ordered
        with patch.object(r.subprocess, 'run') as network:
            folder = r.prepare_archives(self.repo, self.index, None)
        network.assert_not_called()
        self.assertEqual((folder / asset['name']).read_bytes(), original)
        self.assertTrue(all(not (cache / name).exists() for name in contents))

    def test_explicit_proxy_environment_takes_precedence_over_static_windows_proxy(self):
        explicit = {'https_proxy': 'http://explicit.example:1234', 'HTTP_PROXY': '', 'NO_PROXY': 'localhost'}
        static = {'http': 'http://static.example:5678', 'https': 'http://static.example:5678', 'no': 'static-bypass'}
        with patch.dict(os.environ, explicit, clear=True), patch.object(r.urllib.request, 'getproxies', return_value=static):
            result = r.download_environment()
        self.assertEqual({key.casefold(): value for key, value in result.items()},
                         {key.casefold(): value for key, value in explicit.items()})
        with patch.dict(os.environ, {}, clear=True), patch.object(r.urllib.request, 'getproxies', return_value=static):
            result = r.download_environment()
        self.assertEqual(result['HTTP_PROXY'], static['http'])
        self.assertEqual(result['HTTPS_PROXY'], static['https'])
        self.assertEqual(result['NO_PROXY'], static['no'])



if __name__ == '__main__':
    unittest.main()
