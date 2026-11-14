"""Regression checks for the protected local P5 rerun on the reviewed Darwin host."""

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_darwin_release as guard  # noqa: E402


class ProtectedRerunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.provenance, cls.binary, cls.rule = guard.reviewed_candidate()

    def setUp(self):
        work = self.enterContext(tempfile.TemporaryDirectory(prefix="radishaxiom-p5-test-"))
        self.work = Path(work).resolve()

    def stage(self):
        directory = self.work / "launch"
        directory.mkdir(mode=0o700)
        return guard.ProtectedLaunch(directory, self.manifest, self.binary)

    def test_manifest_drift(self):
        manifest = self.work / "manifest.jcs"
        manifest.write_bytes(self.provenance + b" ")
        with patch.object(guard, "CANDIDATE", manifest):
            with self.assertRaisesRegex(ValueError, "manifest digest mismatch"):
                guard.reviewed_candidate()

    def test_retained_binary_drift(self):
        binary = self.work / self.manifest["artifact_path"]
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"\0" + self.binary[1:])
        with patch.object(guard, "ROOT", self.work):
            with self.assertRaisesRegex(ValueError, "candidate bytes differ"):
                guard.reviewed_candidate()

    def test_staged_replacement_even_with_identical_bytes(self):
        launch = self.stage()
        replacement = self.work / "replacement"
        shutil.copy(launch.executable, replacement)
        replacement.replace(launch.executable)
        with patch.object(guard.subprocess, "run") as spawn:
            with self.assertRaisesRegex(ValueError, "staging inode changed"):
                launch([str(launch.executable), self.manifest["artifact"]["content_digest"]])
            spawn.assert_not_called()

    def test_refuses_unreviewed_argument_path(self):
        launch = self.stage()
        with patch.object(guard.subprocess, "run") as spawn:
            with self.assertRaisesRegex(ValueError, "unreviewed candidate launch path"):
                launch([str(self.work / "wrong"), self.manifest["artifact"]["content_digest"]])
            spawn.assert_not_called()

    def test_refuses_different_actual_launch_path(self):
        launch = self.stage()
        alternate = self.work / "alternate"
        shutil.copy(launch.executable, alternate)
        run = subprocess.run

        def substitute(argv, **kwargs):
            return run([str(alternate), *argv[1:]], **kwargs)

        with patch.object(guard.subprocess, "run", side_effect=substitute):
            with self.assertRaisesRegex(ValueError, "dyld launch path or image mismatch"):
                launch([str(launch.executable), self.manifest["artifact"]["content_digest"]])

    def test_refuses_missing_dyld_observation(self):
        launch = self.stage()
        with patch.object(guard.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"forged", b"")):
            with self.assertRaisesRegex(ValueError, "missing dyld observation"):
                launch([str(launch.executable), self.manifest["artifact"]["content_digest"]])

    def test_staged_bytes_changed_after_spawn(self):
        launch = self.stage()
        run = subprocess.run

        def replace_bytes(argv, **kwargs):
            result = run(argv, **kwargs)
            launch.executable.chmod(0o700)
            launch.executable.write_bytes(b"\0" + self.binary[1:])
            launch.executable.chmod(0o500)
            return result

        with patch.object(guard.subprocess, "run", side_effect=replace_bytes):
            with self.assertRaisesRegex(ValueError, "staged candidate identity or bytes changed"):
                launch([str(launch.executable), self.manifest["artifact"]["content_digest"]])

    def test_host_cache_drift(self):
        with patch.object(guard, "SHARED_CACHE", None):
            with self.assertRaisesRegex(ValueError, "shared cache UUID differs"):
                guard.check_host(self.manifest)

    def test_config_missing_or_wrong_digest_blocks_before_spawn(self):
        config = self.work / "acceptance.sha256"
        record = self.work / "draft.jcs"
        record.write_bytes(guard.acceptance_bytes(self.binary, self.rule, self.provenance))
        with patch.object(guard, "trust_config_path", return_value=config), patch.object(guard, "check_host") as host:
            with self.assertRaisesRegex(ValueError, "configuration missing"):
                guard.main(False, record)
            config.write_text("sha256:" + "0" * 64 + "\n")
            config.chmod(0o600)
            with self.assertRaisesRegex(ValueError, "record digest mismatch"):
                guard.main(False, record)
            host.assert_not_called()

    def test_config_rejects_public_mode_and_symlink(self):
        config = self.work / "acceptance.sha256"
        config.write_text("sha256:" + "0" * 64 + "\n")
        config.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "private, single-link"):
            guard.read_trusted_pin(config)
        config.chmod(0o600)
        link = self.work / "link"
        link.symlink_to(config)
        with self.assertRaisesRegex(ValueError, "canonical path"):
            guard.read_trusted_pin(link)

    def test_synthetic_approval_through_guard_and_independent_verifier(self):
        launch = self.stage()
        provenance = b"synthetic protected launcher regression; no production provenance"
        expected = guard.acceptance_bytes(self.binary, self.rule, provenance)
        record, config = self.work / "synthetic.jcs", self.work / "synthetic.sha256"
        record.write_bytes(expected)
        config.write_text(guard.raw_digest(expected) + "\n")
        config.chmod(0o600)
        approval = guard.load_approval(record, config, expected, provenance)
        with contextlib.redirect_stdout(io.StringIO()) as report:
            guard.verify_receipts(launch.executable, guard.SCHEMA, False, invoke=launch,
                                  approval=approval, scratch=launch.directory)
        self.assertEqual(len(report.getvalue().splitlines()), 8)
        self.assertNotEqual(json.loads(expected)["provenance"], guard.MANIFEST_PIN)


if __name__ == "__main__":
    unittest.main()
