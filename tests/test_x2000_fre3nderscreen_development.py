#!/usr/bin/env python3
"""Development orchestration fixtures; no builds, packages, signing or keys."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FAKE_COMMAND = f"#!{sys.executable}\n" + '''
import json
import os
from pathlib import Path
import sys

command = Path(sys.argv[0]).name
with Path(os.environ["FIXTURE_LOG"]).open("a") as log:
    log.write(json.dumps({"command": command, "args": sys.argv[1:],
        "seed": os.environ.get("FRE3NDER_FACTORY_FRE3NDERSCREEN_APP"),
        "mode": os.environ.get("FRE3NDER_FACTORY_FRE3NDERSCREEN_MODE")}) + "\\n")
if command == "build-x2000-fre3nderscreen":
    assert sys.argv[1:] == ["--develop"]
    sys.exit(int(os.environ.get("FIXTURE_CROSS_RC", "0")))
if command == "build-fre3nderscreen-development":
    assert sys.argv[1:] == ["--artifact", os.environ["FIXTURE_ARTIFACT"],
                           "--key", os.environ["FIXTURE_KEY"]]
    rc = int(os.environ.get("FIXTURE_PACKAGE_RC", "0"))
    if rc:
        sys.exit(rc)
    package = Path(os.environ["FIXTURE_PACKAGE"])
    package.parent.mkdir(parents=True, exist_ok=True)
    kind = os.environ.get("FIXTURE_PACKAGE_KIND", "file")
    if kind == "file":
        package.write_bytes(b"mock output, not a package")
    elif kind == "symlink":
        package.symlink_to(os.environ["FIXTURE_SEED"])
    elif kind == "directory":
        package.mkdir()
    receipt = os.environ.get("FIXTURE_RECEIPT", "normal")
    header = "=== Fre3nderScreen development package: PASS ==="
    if receipt != "missing-pass":
        print(header)
    if receipt == "duplicate-pass":
        print(header)
    if receipt != "missing-package":
        print("Package:  " + ("relative.fixture" if receipt == "relative" else str(package)))
    if receipt == "duplicate-package":
        print("Package:  " + str(package))
'''

FAKE_GIT = f"#!{sys.executable}\n" + '''
import os
import sys

args = sys.argv[3:]
if args == ["check-ignore", "-q", "local/production"]:
    sys.exit(0)
assert args in (["diff", "--quiet", "--"], ["diff", "--cached", "--quiet", "--"])
state = "staged" if "--cached" in args else "unstaged"
sys.exit(1 if os.environ.get("FIXTURE_DIRTY") == state else 0)
'''


def executable(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


class DevelopmentOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "fre3nder"
        self.apps = self.root / "fre3nder-apps"
        self.wrapper = self.repo / "scripts/build-x2000"
        self.wrapper.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "scripts/build-x2000", self.wrapper)
        self.wrapper.chmod(0o755)
        (self.repo / "configs/x2000/rootfs-overlay").mkdir(parents=True)
        for command in ("build-x2000-kernel", "build-x2000-moonraker",
                        "build-x2000-buildroot", "build-x2000-fre3nderscreen", "build-f005"):
            executable(self.repo / "scripts" / command, FAKE_COMMAND)
        self.package_builder = self.apps / "scripts/build-fre3nderscreen-development"
        executable(self.package_builder, FAKE_COMMAND)
        self.seed = self.repo / "local/production/factory-apps/fre3nderscreen.fre3app"
        self.seed.parent.mkdir(parents=True)
        self.seed.write_bytes(b"canonical release seed untouched")
        self.package = self.apps / "dist/development output.fixture"
        self.log = self.root / "calls.jsonl"
        self.bin = self.root / "bin"
        # Only the final composition uses this fake Python; component fakes use
        # an absolute interpreter. No OTA archive or signature is produced.
        executable(self.bin / "python3", '#!/bin/sh\ncat >/dev/null\nexit 0\n')
        executable(self.bin / "git", FAKE_GIT)
        executable(self.bin / "openssl", f"#!{sys.executable}\n" + '''
from pathlib import Path
import sys
args = sys.argv[1:]
if "-pubout" in args:
    Path(args[args.index("-out") + 1]).write_text("mock key placeholder")
else:
    print("ED25519 Public-Key:" if "-pubin" in args else "ED25519 Private-Key:")
''')
        keys = self.repo / "local/production/keys/ota"
        keys.mkdir(parents=True)
        for name in ("private.pem", "public.pem"):
            (keys / name).write_text("mock key placeholder")
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        FIXTURE_LOG=str(self.log), FIXTURE_PACKAGE=str(self.package),
                        FIXTURE_SEED=str(self.seed),
                        FIXTURE_ARTIFACT=str(self.repo / "local/production/artifacts/x2000/fre3nderscreen/app"),
                        FIXTURE_KEY=str(self.repo / "local/production/keys/apps/private.pem"))
        for name in ("FRE3NDER_FACTORY_FRE3NDERSCREEN_APP", "FRE3NDER_FACTORY_FRE3NDERSCREEN_MODE"):
            self.env.pop(name, None)

    def run_wrapper(self, args, **env):
        return subprocess.run([str(self.wrapper), *args], cwd=self.root,
                              env=dict(self.env, **env), capture_output=True, text=True)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_default_and_plain_development_keep_release_seed(self):
        for args in ([], ["--develop"]):
            with self.subTest(args=args):
                self.log.unlink(missing_ok=True)
                result = self.run_wrapper(args)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = self.calls()
                self.assertEqual([c["command"] for c in calls], ["build-x2000-kernel",
                    "build-x2000-moonraker", "build-x2000-buildroot", "build-x2000-buildroot"])
                self.assertEqual(calls[-1]["seed"], str(self.seed))
                self.assertEqual(calls[-1]["mode"], "release")

    def test_development_app_full_and_rootfs_scopes_preserve_seed(self):
        for scope in ([], ["--rootfs-only"], ["--rootfs-only", "--f005-build"], ["--f005-build"]):
            with self.subTest(scope=scope):
                self.log.unlink(missing_ok=True)
                result = self.run_wrapper([*scope, "--develop", "--fre3nderscreen-app"])
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = self.calls()
                commands = [c["command"] for c in calls]
                expected = ["build-x2000-fre3nderscreen", "build-fre3nderscreen-development"]
                if "--rootfs-only" not in scope:
                    expected.append("build-x2000-kernel")
                if "--f005-build" in scope:
                    expected.append("build-f005")
                expected += ["build-x2000-moonraker", "build-x2000-buildroot", "build-x2000-buildroot"]
                self.assertEqual(commands, expected)
                self.assertEqual(calls[-2]["args"], ["--toolchain", "--develop"])
                self.assertEqual(calls[-1]["args"], ["--assemble", "--develop"])
                self.assertEqual(calls[-1]["seed"], str(self.package))
                self.assertEqual(calls[-1]["mode"], "development")
                self.assertEqual(self.seed.read_bytes(), b"canonical release seed untouched")

    def test_invalid_cli_stops_before_any_builder(self):
        for args in (["--fre3nderscreen-app"],
                     ["--kernel-only", "--develop", "--fre3nderscreen-app"],
                     ["--compose-only", "--fre3nderscreen-app"],
                     ["--compose-only", "--develop", "--fre3nderscreen-app"]):
            with self.subTest(args=args):
                result = self.run_wrapper(args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self.calls(), [])

    def test_component_failures_stop_without_fallback(self):
        for env, rc, commands in (({"FIXTURE_CROSS_RC": "17"}, 17, ["build-x2000-fre3nderscreen"]),
                                 ({"FIXTURE_PACKAGE_RC": "23"}, 23, ["build-x2000-fre3nderscreen", "build-fre3nderscreen-development"])):
            with self.subTest(env=env):
                self.log.unlink(missing_ok=True)
                result = self.run_wrapper(["--rootfs-only", "--develop", "--fre3nderscreen-app"], **env)
                self.assertEqual(result.returncode, rc)
                self.assertEqual([c["command"] for c in self.calls()], commands)
                self.assertEqual(self.seed.read_bytes(), b"canonical release seed untouched")

    def test_invalid_receipts_and_package_files_stop_before_rootfs(self):
        for env in ([{"FIXTURE_RECEIPT": mode} for mode in
                     ("missing-pass", "duplicate-pass", "missing-package", "duplicate-package", "relative")]
                    + [{"FIXTURE_PACKAGE_KIND": kind} for kind in ("missing", "symlink", "directory")]):
            with self.subTest(env=env):
                self.log.unlink(missing_ok=True)
                if self.package.is_dir() and not self.package.is_symlink():
                    self.package.rmdir()
                else:
                    self.package.unlink(missing_ok=True)
                result = self.run_wrapper(["--rootfs-only", "--develop", "--fre3nderscreen-app"], **env)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len(self.calls()), 2)
                self.assertEqual(self.seed.read_bytes(), b"canonical release seed untouched")

    def test_missing_apps_or_wrapper_stops_before_cross_build(self):
        self.package_builder.unlink()
        result = self.run_wrapper(["--rootfs-only", "--develop", "--fre3nderscreen-app"])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])
        shutil.rmtree(self.apps)
        result = self.run_wrapper(["--rootfs-only", "--develop", "--fre3nderscreen-app"])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_tracked_dirty_stops_before_cross_build(self):
        for state in ("staged", "unstaged"):
            with self.subTest(state=state):
                result = self.run_wrapper(["--rootfs-only", "--develop", "--fre3nderscreen-app"], FIXTURE_DIRTY=state)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("tracked worktree changes", result.stderr)
                self.assertEqual(self.calls(), [])


class FactoryModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.wrapper = self.root / "scripts/build-x2000-buildroot"
        # Run the actual shell mode checks and Python package gate, stopping
        # immediately afterwards. Docker and the package verifier are fakes.
        source = (ROOT / "scripts/build-x2000-buildroot").read_text()
        executable(self.wrapper, source.split("\nPY\n", 1)[0] + "\nPY\nexit 0\n")
        (self.root / "VERSION").write_text("fixture")
        (self.root / "configs/x2000/rootfs-overlay").mkdir(parents=True)
        core = self.root / "configs/x2000/rootfs-overlay/usr/libexec/fre3nder/package-core"
        core.parent.mkdir(parents=True)
        core.write_text('import json\ndef verify_package(seed):\n    return json.loads(seed.read_text())\n')
        self.seed = self.root / "seed.fixture"
        self.bin = self.root / "bin"
        executable(self.bin / "git", FAKE_GIT)
        self.log = self.root / "docker.log"
        executable(self.bin / "docker", '#!/bin/sh\nprintf called >> "$FIXTURE_DOCKER_LOG"\n')
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        X2000_BUILD_DOCKER=str(self.bin / "docker"), FIXTURE_DOCKER_LOG=str(self.log),
                        FRE3NDER_FACTORY_FRE3NDERSCREEN_APP=str(self.seed), PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("FRE3NDER_FACTORY_FRE3NDERSCREEN_MODE", None)

    def run_gate(self, serial, mode=None, develop=True):
        self.seed.write_text(json.dumps(dict(name="fre3nderscreen", publisher="fre3nder-official",
                            display_frontend=True, display_api=1, autostart=False, release_serial=serial)))
        env = dict(self.env)
        if mode is not None:
            env["FRE3NDER_FACTORY_FRE3NDERSCREEN_MODE"] = mode
        return subprocess.run([str(self.wrapper), "--assemble", *(["--develop"] if develop else [])],
                              env=env, capture_output=True, text=True)

    def test_app_mode_and_serial_are_independent_of_platform_development(self):
        for mode, serial, success in (("release", 0, False), ("release", 1, True),
                                     ("release", 2, True), ("development", 0, True),
                                     ("development", 1, False), (None, 2, True), (None, 0, False)):
            with self.subTest(mode=mode, serial=serial):
                result = self.run_gate(serial, mode)
                self.assertEqual(result.returncode == 0, success, result.stderr)
                if not success:
                    self.assertIn("does not match expected app mode", result.stderr)

    def test_invalid_mode_and_release_platform_with_development_app_stop_before_docker(self):
        for mode, develop in (("invalid", True), ("", True), ("development", False)):
            with self.subTest(mode=mode, develop=develop):
                result = self.run_gate(0, mode, develop)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
