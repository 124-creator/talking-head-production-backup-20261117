"""All closeout tests use temporary fixtures and fake network/git backends."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location('finalize_release_tested', Path(__file__).resolve().parents[1] / 'tools/finalize_release.py')
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)


class FakeBackend:
    def __init__(self, repository, expected):
        self.repository = repository
        self.base = 'a' * 40
        self.head = self.base
        self.branch, self.clean = 'main', True
        self.commits = self.tags_created = self.published = self.remote_reads = 0
        self.local_tag = self.remote_tag = None
        self.release = {'id': 17, 'tag_name': F.TAG, 'draft': True}
        self.rows = [{'name': name, 'size': row['size'], 'digest': 'sha256:' + row['sha256'],
                      'id': number, 'state': 'uploaded'} for number, (name, row) in enumerate(expected.items(), 1)]
        self.last_documents = None

    def state(self):
        return {'head': self.head, 'branch': self.branch, 'clean': self.clean}

    def live_release(self, release_id):
        self.remote_reads += 1
        return self.release, self.rows

    def documents_match(self, documents):
        return self.last_documents == documents

    def prior_closeout(self, head, validated, documents):
        return self.commits == 1 and head == 'b' * 40 and validated == self.base and self.documents_match(documents)

    def tags(self):
        return self.local_tag, self.remote_tag

    def record_documents(self, documents, expected_head):
        assert self.head == expected_head and self.clean
        if not self.documents_match(documents):
            self.commits += 1
            self.head = 'b' * 40
            self.last_documents = copy.deepcopy(documents)
            for name, content in documents.items():
                F.atomic_write(self.repository / name, content, self.repository)
        return self.head

    def push_refs(self, head):
        if self.local_tag is None:
            self.tags_created += 1
            self.local_tag = {'object': 'c' * 40, 'annotated': True, 'commit': head}
        self.remote_tag = copy.deepcopy(self.local_tag)

    def publish_release(self, release_id):
        if self.release['draft']:
            self.published += 1
            self.release['draft'] = False


class FinalizeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo, self.verification = self.root / 'repository', self.root / 'verification'
        (self.repo / 'manifests').mkdir(parents=True)
        (self.repo / 'environment').mkdir()
        self.verification.mkdir()
        snapshot = {'repo': F.REPO, 'tag': F.TAG, 'snapshot_id': F.SNAPSHOT,
                    'file_count': F.FILE_COUNT, 'files': [{}] * F.FILE_COUNT}
        parts = [{'name': f'transfer-snapshot-core-001-{number:03d}.bin', 'size': number,
                  'sha256': F.sha256(str(number).encode())} for number in range(1, F.PART_COUNT + 1)]
        index = {'repo': F.REPO, 'tag': F.TAG, 'assets': [{'name': 'snapshot-core-001.zip',
                  'size': sum(p['size'] for p in parts), 'sha256': 'd' * 64, 'parts': parts}]}
        self.write(self.repo / 'manifests/snapshot.json', snapshot)
        self.write(self.repo / 'manifests/archives.json', index)
        self.write(self.repo / 'environment/python-bootstrap.json',
                   {'installer': F.INSTALLER, 'sha256': F.INSTALLER_SHA, 'bytes': 28838672})
        self.expected, self.context = F.expected_assets(self.repo)
        self.local = {'status': 'passed', 'snapshot_files_verified': F.FILE_COUNT, 'unit_tests_run': 38,
                      'git_source_blobs_matched': 253, 'system_font_mismatches': 0,
                      'snapshot_manifest_sha256': self.context['snapshot_sha256'],
                      'validated_revision': 'a' * 40, 'note': r'Actual local Windows test at C:\private\name; not another physical PC'}
        self.local.update({field: 'passed' for field in F.LOCAL_PASSES})
        self.local.update({field: True for field in F.LOCAL_TRUE})
        self.report = {'status': 'all_assets_verified', 'repo': F.REPO, 'tag': F.TAG,
                       'release_id': 17, 'asset_count': F.ASSET_COUNT,
                       'total_bytes': sum(row['size'] for row in self.expected.values()),
                       'assets': [{'name': name, 'size': row['size'], 'local_sha256': row['sha256'],
                                   'github_digest': 'sha256:' + row['sha256'], 'asset_id': number,
                                   'state': 'uploaded'} for number, (name, row) in enumerate(self.expected.items(), 1)]}
        self.persist()
        self.backend = FakeBackend(self.repo, self.expected)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def write(path, value):
        path.write_bytes(F.json_bytes(value))

    def persist(self):
        self.write(self.verification / 'local-validation.json', self.local)
        self.write(self.verification / 'remote-release-verification.json', self.report)

    def run_finalizer(self):
        return F.finalize(self.repo, self.verification, backend=self.backend)

    def assert_no_side_effects(self):
        self.assertEqual((self.backend.commits, self.backend.tags_created, self.backend.published), (0, 0, 0))
        self.assertFalse((self.verification / 'final-completion.json').exists())

    def test_expected_asset_count_order_and_windows_checksum_file(self):
        self.assertEqual(len(self.expected), 290)
        self.assertEqual(list(self.expected)[-4:], ['snapshot.json', 'archives.json', F.INSTALLER, 'SHA256SUMS'])
        content = ''.join(f"{row['sha256']}  {name}\r\n" for name, row in list(self.expected.items())[:-1]).encode('ascii')
        self.assertEqual(content.count(b'\r\n'), 289)
        self.assertEqual(self.expected['SHA256SUMS']['sha256'], F.sha256(content))

    def test_all_local_gates_are_mandatory(self):
        for field in (*F.LOCAL_PASSES, *F.LOCAL_TRUE, 'status', 'snapshot_files_verified', 'unit_tests_run',
                      'git_source_blobs_matched', 'system_font_mismatches', 'snapshot_manifest_sha256', 'validated_revision', 'note'):
            with self.subTest(field=field):
                evidence = copy.deepcopy(self.local)
                evidence.pop(field)
                with self.assertRaises(F.GateError):
                    F.validate_local(evidence, self.context)

    def test_truthy_strings_booleans_and_partial_smokes_are_not_passes(self):
        for field, value in [('unit_tests_passed', 'true'), ('unit_tests_run', True),
                             ('system_font_mismatches', False), ('render_smoke', 'diagnostic_passed'),
                             ('unit_tests_run', 37), ('snapshot_files_verified', 12098)]:
            with self.subTest(field=field, value=value):
                evidence = copy.deepcopy(self.local)
                evidence[field] = value
                with self.assertRaises(F.GateError):
                    F.validate_local(evidence, self.context)

    def test_dirty_and_wrong_branch_refuse_before_remote_or_write(self):
        for field, value in [('clean', False), ('branch', 'feature')]:
            with self.subTest(field=field):
                self.backend = FakeBackend(self.repo, self.expected)
                setattr(self.backend, field, value)
                with self.assertRaises(F.GateError):
                    self.run_finalizer()
                self.assertEqual(self.backend.remote_reads, 0)
                self.assert_no_side_effects()

    def test_unvalidated_revision_refused(self):
        self.backend.head = 'e' * 40
        with self.assertRaises(F.GateError):
            self.run_finalizer()
        self.assert_no_side_effects()

    def test_changed_metadata_and_wrong_report_identity_refused(self):
        for field, value in [('repo', 'someone/else'), ('tag', 'wrong'), ('asset_count', 289), ('total_bytes', 1)]:
            with self.subTest(field=field):
                report = copy.deepcopy(self.report)
                report[field] = value
                with self.assertRaises(F.GateError):
                    F.verify_report(report, self.expected)
        report = copy.deepcopy(self.report)
        report['assets'][-3]['local_sha256'] = '0' * 64
        with self.assertRaises(F.GateError):
            F.verify_report(report, self.expected)

    def test_remote_size_digest_state_id_missing_extra_and_duplicate_rejected(self):
        for field, value in [('size', 0), ('digest', 'sha256:' + '0' * 64), ('state', 'starter'), ('id', False)]:
            with self.subTest(field=field):
                rows = copy.deepcopy(self.backend.rows)
                rows[0][field] = value
                with self.assertRaises(F.GateError):
                    F.verify_asset_rows(rows, self.expected, reported=False)
        for rows in (self.backend.rows[:-1], self.backend.rows + [self.backend.rows[0]],
                     self.backend.rows[:-1] + [self.backend.rows[0]]):
            with self.assertRaises(F.GateError):
                F.verify_asset_rows(rows, self.expected, reported=False)

    def test_live_asset_id_change_refused(self):
        self.backend.rows[0]['id'] = 999999
        with self.assertRaises(F.GateError):
            self.run_finalizer()
        self.assert_no_side_effects()

    def test_live_release_identity_refused(self):
        for field, value in [('tag_name', 'elsewhere'), ('id', 18), ('draft', 'false')]:
            with self.subTest(field=field):
                release = copy.deepcopy(self.backend.release)
                release[field] = value
                with self.assertRaises(F.GateError):
                    F.verify_release_identity(release, 17)

    def test_existing_tag_cannot_be_moved_or_replaced(self):
        variants = ({'commit': 'e' * 40, 'object': 'c' * 40, 'annotated': True},
                    {'commit': 'a' * 40, 'object': 'c' * 40, 'annotated': False})
        for tag in variants:
            with self.assertRaises(F.GateError):
                F.check_tags(tag, None, 'a' * 40, documents_match=True)
        tag = {'commit': 'a' * 40, 'object': 'c' * 40, 'annotated': True}
        with self.assertRaises(F.GateError):
            F.check_tags(tag, None, 'a' * 40, documents_match=False)
        different = dict(tag, object='d' * 40)
        with self.assertRaises(F.GateError):
            F.check_tags(tag, different, 'a' * 40, documents_match=True)

    def test_wait_is_bounded_and_does_not_launch_uploader(self):
        pending = self.verification / 'pending.json'
        with self.assertRaises(F.GateError):
            F.wait_remote_report(pending, False)
        sleeps = []
        clock = [0]
        def sleep(seconds):
            sleeps.append(seconds)
            clock[0] += seconds
        with patch('builtins.print'):
            with self.assertRaises(F.GateError):
                F.wait_remote_report(pending, True, sleep=sleep, monotonic=lambda: clock[0])
        self.assertEqual(sum(sleeps), 12 * 60 * 60)
        self.assertTrue(all(seconds <= 60 for seconds in sleeps))

    def test_wait_handles_in_progress_report_then_reads_existing_pass(self):
        pending = self.verification / 'pending.json'
        pending.write_text('{', encoding='utf-8')
        clock = [0]
        def sleep(seconds):
            clock[0] += seconds
            self.write(pending, self.report)
        with patch('builtins.print'):
            value, _ = F.wait_remote_report(pending, True, sleep=sleep, monotonic=lambda: clock[0])
        self.assertEqual(value['status'], 'all_assets_verified')
        self.assertEqual(clock[0], 60)

    def test_repeat_success_does_not_duplicate_commit_tag_or_publication(self):
        first = self.run_finalizer()
        second = self.run_finalizer()
        self.assertEqual(first, second)
        self.assertEqual((self.backend.commits, self.backend.tags_created, self.backend.published), (1, 1, 1))
        self.assertEqual(first['asset_count'], 290)
        for name in F.DOCUMENTS:
            self.assertNotIn(b'C:\\private', (self.repo / name).read_bytes())
        public = json.loads((self.repo / F.DOCUMENTS[0]).read_text(encoding='utf-8'))
        self.assertEqual(public['note'], F.DISCLAIMER)
        self.assertTrue((self.verification / 'final-completion.json').is_file())

    def test_resume_after_commit_and_refs_does_not_duplicate_them(self):
        original = self.backend.publish_release
        self.backend.publish_release = lambda release_id: (_ for _ in ()).throw(F.GateError('transient publication failure'))
        with self.assertRaises(F.GateError):
            self.run_finalizer()
        self.assertFalse((self.verification / 'final-completion.json').exists())
        self.backend.publish_release = original
        result = self.run_finalizer()
        self.assertEqual(result['status'], 'complete')
        self.assertEqual((self.backend.commits, self.backend.tags_created, self.backend.published), (1, 1, 1))

    def test_path_escape_refused(self):
        outside = self.root / 'outside.json'
        with self.assertRaises(F.GateError):
            F.atomic_write(outside, b'x', self.repo)
        self.assertFalse(outside.exists())

    def test_production_backend_mock_read_private_guard_and_pagination(self):
        backend = F.ProductionBackend(self.repo)
        backend.gh_json = lambda *args: {'isPrivate': False, 'nameWithOwner': F.REPO}
        with self.assertRaises(F.GateError):
            backend.live_release(17)
        responses = iter([{'isPrivate': True, 'nameWithOwner': F.REPO}, self.backend.release,
                          [self.backend.rows[:100], self.backend.rows[100:200], self.backend.rows[200:]]])
        calls = []
        def gh_json(*args):
            calls.append(args)
            return next(responses)
        backend.gh_json = gh_json
        _, rows = backend.live_release(17)
        self.assertEqual(len(rows), 290)
        self.assertEqual(calls[-1][-2:], ('--paginate', '--slurp'))

    def test_production_backend_mock_never_edits_already_published_release(self):
        backend = F.ProductionBackend(self.repo)
        backend.gh_json = lambda *args: {'id': 17, 'tag_name': F.TAG, 'draft': False}
        with patch.object(backend, 'gh', side_effect=AssertionError('No live call allowed')):
            backend.publish_release(17)

    def test_production_backend_mock_publication_rechecks_draft_and_uses_latest(self):
        backend = F.ProductionBackend(self.repo)
        responses = iter([{'id': 17, 'tag_name': F.TAG, 'draft': True},
                          {'id': 17, 'tag_name': F.TAG, 'draft': False}])
        backend.gh_json = lambda *args: next(responses)
        with patch.object(backend, 'gh', return_value='') as command:
            backend.publish_release(17)
        arguments = command.call_args.args
        self.assertEqual(arguments[:3], ('release', 'edit', F.TAG))
        self.assertIn('--draft=false', arguments)
        self.assertIn('--latest', arguments)

    def test_production_backend_mock_draft_remains_true_is_failure(self):
        backend = F.ProductionBackend(self.repo)
        backend.gh_json = lambda *args: {'id': 17, 'tag_name': F.TAG, 'draft': True}
        with patch.object(backend, 'gh', return_value=''):
            with self.assertRaises(F.GateError):
                backend.publish_release(17)

    def test_production_backend_mock_absent_tags_is_normal(self):
        backend = F.ProductionBackend(self.repo)
        calls = []
        def git(*args, **kwargs):
            calls.append(args)
            return ''
        backend.git = git
        self.assertEqual(backend.tags(), (None, None))
        self.assertEqual(calls[0][0], 'for-each-ref')
        self.assertEqual(calls[1][0], 'ls-remote')


if __name__ == '__main__':
    unittest.main()
