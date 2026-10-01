#!/usr/bin/env python3
"""Release pipeline fixtures; no real builds, packages, signing, or keys."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts/build-x2000-fre3nderscreen-release"
PACKAGE_BYTES = b"mock package bytes, not a signed archive"

FAKE_COMMAND = '''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

command = Path(sys.argv[0]).name
with Path(os.environ["FIXTURE_LOG"]).open("a") as log:
    log.write(json.dumps({"command": command, "args": sys.argv[1:],
                          "cwd": str(Path.cwd())}) + "\\n")
if command == "build-x2000-fre3nderscreen":
    assert len(sys.argv) == 1
    rc = int(os.environ.get("FIXTURE_CROSS_RC", "0"))
    if rc:
        sys.exit(rc)
    Path(os.environ["FIXTURE_ARTIFACT"]).mkdir(parents=True)
else:
    assert sys.argv[1] == "--artifact" and sys.argv[3] == "--key" and len(sys.argv) == 5
    assert Path(sys.argv[2]).is_dir()
    rc = int(os.environ.get("FIXTURE_APPS_RC", "0"))
    if rc:
        sys.exit(rc)
    package = Path(os.environ["FIXTURE_PACKAGE"])
    package.parent.mkdir(parents=True, exist_ok=True)
    kind = os.environ.get("FIXTURE_PACKAGE_KIND", "file")
    if kind == "file":
        package.write_bytes(b"mock package bytes, not a signed archive")
    elif kind == "symlink":
        package.symlink_to(os.environ["FIXTURE_OUTSIDE"])
    elif kind == "directory":
        package.mkdir()
    mode = os.environ.get("FIXTURE_RECEIPT", "normal")
    if mode != "missing-pass":
        print("=== Fre3nderScreen release package: PASS ===")
    if mode == "duplicate-pass":
        print("=== Fre3nderScreen release package: PASS ===")
    if mode != "missing-package":
        path = "dist/mock.fre3app" if mode == "relative" else str(package)
        print("Package:  " + path)
    if mode == "duplicate-package":
        print("Package:  " + str(package))
'''

FAKE_GIT = '''#!/usr/bin/env python3
import os
from pathlib import Path
import sys

args = sys.argv[1:]
assert args[:1] == ["-C"]
assert Path(args[1]).is_dir()
assert args[2:] in (["diff", "--quiet", "--"], ["diff", "--cached", "--quiet", "--"])
state = "staged" if "--cached" in args else "unstaged"
sys.exit(1 if os.environ.get("FIXTURE_TRACKED_DIRTY") == state else 0)
'''


class ReleasePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "fre3nder"
        self.apps_repo = self.root / "fre3nder-apps"
        scripts = self.repo / "scripts"
        scripts.mkdir(parents=True)
        self.wrapper = scripts / WRAPPER.name
        shutil.copyfile(WRAPPER, self.wrapper)
        self.wrapper.chmod(0o755)
        for command in (scripts / "build-x2000-fre3nderscreen",
                        self.apps_repo / "scripts/build-fre3nderscreen-release"):
            command.parent.mkdir(parents=True, exist_ok=True)
            command.write_text(FAKE_COMMAND)
            command.chmod(0o755)
        self.artifact = self.repo / "local/production/artifacts/x2000/fre3nderscreen/app"
        self.seed = self.repo / "local/production/factory-apps/fre3nderscreen.fre3app"
        self.package = self.apps_repo / "dist/mock package.fre3app"
        self.outside = self.root / "outside.fixture"
        self.outside.write_bytes(b"outside untouched")
        self.caller = self.root / "caller dir"
        self.caller.mkdir()
        self.log = self.root / "calls.jsonl"
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        git = self.fake_bin / "git"
        git.write_text(FAKE_GIT)
        git.chmod(0o755)
        self.env = dict(os.environ, FIXTURE_LOG=str(self.log),
                        FIXTURE_ARTIFACT=str(self.artifact), FIXTURE_PACKAGE=str(self.package),
                        FIXTURE_OUTSIDE=str(self.outside),
                        PATH=str(self.fake_bin) + os.pathsep + os.environ["PATH"])

    def run_wrapper(self, args=(), **env):
        return subprocess.run([str(self.wrapper), *args], cwd=self.caller,
                              env=dict(self.env, **env), capture_output=True, text=True)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def old_seed(self):
        self.seed.parent.mkdir(parents=True)
        self.seed.write_bytes(b"previous seed")
        self.seed.chmod(0o600)

    def assert_old_seed(self):
        self.assertEqual(self.seed.read_bytes(), b"previous seed")
        self.assertEqual(stat.S_IMODE(self.seed.stat().st_mode), 0o600)
        self.assertEqual(list(self.seed.parent.iterdir()), [self.seed])

    def test_default_pipeline_atomic_seed_and_pass(self):
        self.old_seed()
        previous_inode = self.seed.stat().st_ino
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.seed.read_bytes(), PACKAGE_BYTES)
        self.assertEqual(self.package.read_bytes(), self.seed.read_bytes())
        self.assertNotEqual(self.seed.stat().st_ino, previous_inode)
        self.assertEqual(stat.S_IMODE(self.seed.stat().st_mode), 0o644)
        self.assertEqual(list(self.seed.parent.iterdir()), [self.seed])
        digest = hashlib.sha256(PACKAGE_BYTES).hexdigest()
        self.assertIn("=== Fre3nderScreen release pipeline: PASS ===", result.stdout)
        self.assertIn(f"Artifact:     {self.artifact}\n", result.stdout)
        self.assertIn(f"Package:      {self.package}\n", result.stdout)
        self.assertIn(f"Factory seed: {self.seed}\n", result.stdout)
        self.assertIn(f"SHA256:       {digest}\n", result.stdout)
        key = self.repo / "local/production/keys/apps/private.pem"
        self.assertEqual(self.calls(), [
            {"command": "build-x2000-fre3nderscreen", "args": [], "cwd": str(self.repo)},
            {"command": "build-fre3nderscreen-release",
             "args": ["--artifact", str(self.artifact), "--key", str(key)], "cwd": str(self.repo)},
        ])
        self.assertFalse(key.exists())

    def test_relative_overrides(self):
        custom = self.root / "custom apps repo"
        self.apps_repo.rename(custom)
        key = self.root / "existing key path.pem"
        result = self.run_wrapper(
            ["--apps-repo", "../custom apps repo", "--key", "../existing key path.pem"],
            FIXTURE_PACKAGE=str(custom / "dist/custom.fre3app"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(self.calls()[1]["args"][3]).resolve(), key)
        self.assertEqual(self.seed.read_bytes(), PACKAGE_BYTES)
        self.assertIn(f"Package:      {custom}/dist/custom.fre3app\n", result.stdout)
        self.assertFalse(key.exists())

    def test_cross_failure_stops_before_apps_and_preserves_seed(self):
        self.old_seed()
        result = self.run_wrapper(FIXTURE_CROSS_RC="17")
        self.assertEqual(result.returncode, 17)
        self.assertEqual(len(self.calls()), 1)
        self.assert_old_seed()

    def test_tracked_unstaged_changes_stop_before_cross_build(self):
        result = self.run_wrapper(FIXTURE_TRACKED_DIRTY="unstaged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fre3nder-apps has tracked worktree changes", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_tracked_staged_changes_stop_before_cross_build(self):
        result = self.run_wrapper(FIXTURE_TRACKED_DIRTY="staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fre3nder-apps has tracked worktree changes", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_untracked_file_does_not_block_pipeline(self):
        untracked = self.apps_repo / "untracked.fixture"
        untracked.write_text("untracked file")
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(untracked.read_text(), "untracked file")
        self.assertEqual(self.seed.read_bytes(), PACKAGE_BYTES)

    def test_apps_failure_preserves_seed(self):
        self.old_seed()
        result = self.run_wrapper(FIXTURE_APPS_RC="23")
        self.assertEqual(result.returncode, 23)
        self.assertEqual(len(self.calls()), 2)
        self.assert_old_seed()

    def test_invalid_or_ambiguous_receipt_preserves_seed(self):
        self.old_seed()
        for mode in ("missing-pass", "duplicate-pass", "missing-package", "duplicate-package", "relative"):
            with self.subTest(mode=mode):
                # The cross-builder fixture creates a new artifact directory each run.
                if self.artifact.exists():
                    self.artifact.rmdir()
                result = self.run_wrapper(FIXTURE_RECEIPT=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("release pipeline: PASS", result.stdout)
                self.assert_old_seed()

    def test_invalid_package_preserves_seed(self):
        self.old_seed()
        for kind in ("missing", "symlink", "directory"):
            with self.subTest(kind=kind):
                if self.artifact.exists():
                    self.artifact.rmdir()
                result = self.run_wrapper(FIXTURE_PACKAGE_KIND=kind)
                self.assertNotEqual(result.returncode, 0)
                self.assert_old_seed()
                if self.package.is_symlink():
                    self.package.unlink()
                elif self.package.is_dir():
                    self.package.rmdir()
        self.assertEqual(self.outside.read_bytes(), b"outside untouched")

    def test_copy_mismatch_preserves_seed_and_removes_temp(self):
        self.old_seed()
        cp = self.fake_bin / "cp"
        cp.write_text('#!/bin/sh\nprintf corrupted > "$3"\n')
        cp.chmod(0o755)
        result = self.run_wrapper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("staged factory seed differs", result.stderr)
        self.assert_old_seed()

    def test_symlinked_seed_is_not_followed(self):
        self.seed.parent.mkdir(parents=True)
        self.seed.symlink_to(self.outside)
        result = self.run_wrapper()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.seed.is_symlink())
        self.assertEqual(self.outside.read_bytes(), b"outside untouched")

    def test_symlinked_seed_directory_is_not_followed(self):
        self.seed.parent.parent.mkdir(parents=True)
        outside_dir = self.root / "outside dir"
        outside_dir.mkdir()
        self.seed.parent.symlink_to(outside_dir, target_is_directory=True)
        result = self.run_wrapper()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside_dir.iterdir()), [])

    def test_develop_and_missing_option_values_are_rejected(self):
        for args in (["--develop"], ["--key"], ["--apps-repo"]):
            with self.subTest(args=args):
                result = self.run_wrapper(args)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
