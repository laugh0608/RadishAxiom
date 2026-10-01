#!/usr/bin/env python3
"""Synthetic declaration and recorded-request tampering checks; no network."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('m', HERE / 'inspect-linux-headers-git-metadata.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MetadataTests(unittest.TestCase):
    def inputs(self):
        ref = {'ref': 'refs/tags/v4.19.88', 'object': {'type': 'commit', 'sha': m.route.candidate.COMMIT}}
        commit = {'sha': m.route.candidate.COMMIT, 'tree': {'sha': 'a' * 40}, 'parents': [{'sha': 'b' * 40}],
                  'message': 'synthetic', 'author': {'date': 'synthetic'}, 'committer': {'date': 'synthetic'},
                  'verification': {'verified': False, 'reason': 'unsigned', 'signature': None,
                                   'payload': None, 'verified_at': None}}
        return ref, commit

    def test_unsigned_is_not_acceptance(self):
        result = m.declarations(*self.inputs())
        self.assertFalse(result['signature_verified'])
        self.assertFalse(result['original_git_objects_reconstructed'])
        self.assertEqual(result['source_acceptance'], 'not-assessed')

    def test_changed_ref_or_annotated_tag_rejected(self):
        for key, value in [('type', 'tag'), ('sha', '0' * 40)]:
            ref, commit = self.inputs()
            ref['object'][key] = value
            with self.assertRaises(ValueError):
                m.declarations(ref, commit)

    def test_changed_commit_rejected(self):
        ref, commit = self.inputs()
        commit['sha'] = '0' * 40
        with self.assertRaises(ValueError):
            m.declarations(ref, commit)

    def test_verified_claim_cannot_silently_change_observation(self):
        for key, value in [('verified', True), ('signature', 'synthetic'), ('payload', 'synthetic')]:
            ref, commit = self.inputs()
            commit['verification'][key] = value
            with self.assertRaises(ValueError):
                m.declarations(ref, commit)

    def test_parent_and_tree_profile(self):
        ref, commit = self.inputs()
        commit['parents'] = []
        with self.assertRaises(ValueError):
            m.declarations(ref, commit)
        ref, commit = self.inputs()
        commit['tree']['sha'] = '../outside'
        with self.assertRaises(ValueError):
            m.declarations(ref, commit)

    def test_plan_drift_rejected_before_logs(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve()
            (folder / 'fetch-plan.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'plan drift'):
                m.inspect(folder)

    def test_stream_tampering_rejected(self):
        # Synthetic first-attempt log reaches the stream binding without any real input store.
        name, target = next(iter(m.route.TARGETS.items()))
        filename = name + '-attempt-1.' + target['suffix']
        argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--proto', '=https',
                '--tlsv1.2', '--max-time', '60', '--max-filesize', str(target['limit']), '--output',
                str(m.route.DIRECTORY / filename), '--write-out', '%{http_code}\n', target['url']]
        row = {'argv': argv, 'target': name, 'attempt': 1, 'url': target['url'],
               'method': m.route.plan()['method'], 'body': {'file': filename, **m.identity(b'original')},
               'parent_timeout': False}
        with patch.object(m, 'read', side_effect=[json.dumps(m.route.plan()).encode(),
                          json.dumps(row).encode(), b'tampered']), self.assertRaisesRegex(ValueError, 'identity'):
            m.inspect()


if __name__ == '__main__':
    unittest.main()
