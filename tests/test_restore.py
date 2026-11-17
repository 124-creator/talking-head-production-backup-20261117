from pathlib import Path
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


if __name__ == '__main__':
    unittest.main()
