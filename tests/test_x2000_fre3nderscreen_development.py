#!/usr/bin/env python3
"""Development orchestration fixtures; no builds, packages, signing or keys."""

import hashlib
import json
import os
import runpy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


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
        for command in ("build-x2000-kernel",
                        "build-x2000-buildroot", "build-x2000-fre3nderscreen", "build-f005"):
            executable(self.repo / "scripts" / command, FAKE_COMMAND)
        self.package_builder = self.apps / "apps/fre3nderscreen/scripts/build-fre3nderscreen-development"
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
                    "build-x2000-buildroot", "build-x2000-buildroot"])
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
                expected += ["build-x2000-buildroot", "build-x2000-buildroot"]
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

    def test_pending_apps_recipe_can_reach_development_wrapper(self):
        result = self.run_wrapper(["--rootfs-only", "--develop", "--fre3nderscreen-app"], FIXTURE_DIRTY="unstaged")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[0]["command"], "build-x2000-fre3nderscreen")


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


class LocalScreenSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "fre3nderscreen"
        self.source.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("remote", "add", "origin", "https://example.invalid/screen.git")
        (self.source / "main.cpp").write_text("old source")
        (self.source / "deleted.cpp").write_text("remove me")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture baseline")
        (self.source / "main.cpp").write_text("pending source")
        (self.source / "new.cpp").write_text("new VT source")
        (self.source / "deleted.cpp").unlink()
        self.git("add", "deleted.cpp")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.source), *args], stderr=subprocess.DEVNULL)

    def add_submodule(self, name="module", files=None):
        module = self.root / name
        module.mkdir()
        subprocess.run(["git", "init", "-q", str(module)], check=True)
        for relative, data in (files or {"source.h": b"/* module fixture */\n"}).items():
            path = module / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        subprocess.run(["git", "-C", str(module), "add", "."], check=True)
        subprocess.run(["git", "-C", str(module), "-c", "user.name=Fixture", "-c",
                        "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)
        self.git("-c", "protocol.file.allow=always", "submodule", "add", str(module), name)
        self.git("commit", "-qam", "module baseline")
        return module

    def test_snapshot_preserves_pending_sources_and_leaves_checkout_untouched(self):
        snapshot = runpy.run_path(str(ROOT / "build/x2000/snapshot-fre3nderscreen.py"))["snapshot"]
        before = self.git("status", "--porcelain=v1")
        destination = self.root / "work/source"
        snapshot(self.source, destination)
        self.assertEqual((destination / "main.cpp").read_text(), "pending source")
        self.assertEqual((destination / "new.cpp").read_text(), "new VT source")
        self.assertFalse((destination / "deleted.cpp").exists())
        self.assertEqual(self.git("status", "--porcelain=v1"), before)
        record = json.loads(destination.with_suffix(".snapshot.json").read_text())
        self.assertEqual(record["origin"], "local-worktree")
        self.assertEqual(record["worktree_status"], "dirty")
        (self.source / "new.cpp").write_text("different VT source")
        snapshot(self.source, destination)
        changed = json.loads(destination.with_suffix(".snapshot.json").read_text())
        self.assertNotEqual(record["worktree_sha256"], changed["worktree_sha256"])

    def test_snapshot_preserves_pending_submodule_removal(self):
        snapshot = runpy.run_path(str(ROOT / "build/x2000/snapshot-fre3nderscreen.py"))["snapshot"]
        self.add_submodule()
        self.git("rm", "module")
        before = self.git("status", "--porcelain=v1")
        destination = self.root / "work/source"
        snapshot(self.source, destination)
        self.assertFalse((destination / "module").exists())
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(destination), "submodule", "status"]), b"")
        self.assertEqual(self.git("status", "--porcelain=v1"), before)

    def test_cross_builder_refuses_remote_main_when_local_sources_would_be_lost(self):
        repo = self.root / "fre3nder"
        wrapper = repo / "scripts/build-x2000-fre3nderscreen"
        source = (ROOT / "scripts/build-x2000-fre3nderscreen").read_text()
        executable(wrapper, source.split('"$docker_cmd" build', 1)[0] + '\nprintf "%s\\n" "$@"\n')
        (repo / "VERSION").write_text("fixture")
        env = dict(os.environ)
        env.pop("FRE3NDER_FRE3NDERSCREEN_SOURCE", None)
        result = subprocess.run([str(wrapper), "--develop"], env=env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local Screen changes exist", result.stderr)
        env["FRE3NDER_FRE3NDERSCREEN_SOURCE"] = str(self.source)
        result = subprocess.run([str(wrapper)], env=env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires --develop", result.stderr)

    def test_snapshot_excludes_local_configuration_and_old_history(self):
        snapshot = runpy.run_path(str(ROOT / "build/x2000/snapshot-fre3nderscreen.py"))["snapshot"]
        old_commit = self.git("rev-parse", "HEAD").decode().strip()
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-qam", "new baseline")
        self.git("config", "credential.helper", "fixture-local-secret")
        (self.source / ".git/hooks/local-secret").write_text("fixture hook")
        (self.source / ".env").write_text("fixture untracked secret")
        destination = self.root / "work/source"
        snapshot(self.source, destination)
        self.assertFalse((destination / ".env").exists())
        self.assertFalse((destination / ".git/hooks/local-secret").exists())
        self.assertNotIn("fixture-local-secret", (destination / ".git/config").read_text())
        absent = subprocess.run(["git", "-C", str(destination), "cat-file", "-e", old_commit],
                                capture_output=True)
        self.assertNotEqual(absent.returncode, 0)

    def test_snapshot_rejects_symlinks_private_keys_and_credential_urls(self):
        snapshot = runpy.run_path(str(ROOT / "build/x2000/snapshot-fre3nderscreen.py"))["snapshot"]
        destination = self.root / "work/source"
        pending = self.source / "new.cpp"
        pending.unlink()
        pending.symlink_to(self.source / "main.cpp")
        with self.assertRaisesRegex(ValueError, "symlink"):
            snapshot(self.source, destination)
        pending.unlink()
        pending.write_bytes(b"-----BEGIN " + b"PRIVATE KEY-----\nfixture, not a key\n")
        with self.assertRaisesRegex(ValueError, "private key"):
            snapshot(self.source, destination)
        pending.unlink()
        self.git("remote", "set-url", "origin", "https://fixture:secret@example.invalid/screen.git")
        with self.assertRaisesRegex(ValueError, "credential-bearing"):
            snapshot(self.source, destination)
        self.assertFalse(destination.exists())

    def test_snapshot_keeps_selected_submodule_without_local_metadata(self):
        snapshot = runpy.run_path(str(ROOT / "build/x2000/snapshot-fre3nderscreen.py"))["snapshot"]
        module = self.add_submodule()
        local_config = self.source / ".git/modules/module/config"
        with local_config.open("a") as config:
            config.write("\n[fixture]\n\tsecret = local-only\n")
        destination = self.root / "work/source"
        snapshot(self.source, destination)
        self.assertEqual((destination / "module/source.h").read_bytes(), (module / "source.h").read_bytes())
        self.assertNotIn("local-only", (destination / "module/.git/config").read_text())
        status = subprocess.check_output(["git", "-C", str(destination), "submodule", "status"], text=True)
        self.assertTrue(status.startswith(" "), status)

    def test_public_test_key_exception_requires_exact_bytes_path_and_submodule(self):
        checked_source = runpy.run_path(str(ROOT / "build/x2000/snapshot-fre3nderscreen.py"))["checked_source"]
        key = b"-----BEGIN " + b"PRIVATE KEY-----\nfixture, not a key\n"
        path = self.source / "cert/server.key"
        path.parent.mkdir()
        path.write_bytes(key)
        with mock.patch.dict(checked_source.__globals__, LIBHV_TEST_KEY_SHA256=hashlib.sha256(key).hexdigest()):
            checked_source(self.source, "cert/server.key", submodule="libhv")
            for submodule in (None, "other", "nested/libhv"):
                with self.subTest(submodule=submodule), self.assertRaisesRegex(ValueError, "private key"):
                    checked_source(self.source, "cert/server.key", submodule=submodule)
            other = path.with_name("other.key")
            other.write_bytes(key)
            with self.assertRaisesRegex(ValueError, "private key"):
                checked_source(self.source, "cert/other.key", submodule="libhv")
            path.write_bytes(key + b"changed\n")
            with self.assertRaisesRegex(ValueError, "private key"):
                checked_source(self.source, "cert/server.key", submodule="libhv")
            path.unlink()
            path.symlink_to(other)
            with self.assertRaisesRegex(ValueError, "symlink"):
                checked_source(self.source, "cert/server.key", submodule="libhv")

    def test_snapshot_keeps_public_test_fixture_and_provenance_without_ignored_keys(self):
        snapshot = runpy.run_path(str(ROOT / "build/x2000/snapshot-fre3nderscreen.py"))["snapshot"]
        key = b"-----BEGIN " + b"PRIVATE KEY-----\nfixture, not a key\n"
        self.add_submodule("libhv", {"cert/server.key": key, "source.h": b"/* module */\n",
                                     ".gitignore": b"ignored.key\n"})
        (self.source / "libhv/ignored.key").write_bytes(key + b"local secret sentinel\n")
        (self.source / "main.cpp").write_text("pending edit")
        (self.source / "added.h").write_text("staged header")
        self.git("add", "added.h")
        before = self.git("status", "--porcelain=v1")
        commit = self.git("-C", "libhv", "rev-parse", "HEAD")
        destination = self.root / "work/source"
        with mock.patch.dict(snapshot.__globals__, LIBHV_TEST_KEY_SHA256=hashlib.sha256(key).hexdigest()):
            snapshot(self.source, destination)
            record = json.loads(destination.with_suffix(".snapshot.json").read_text())
            self.assertEqual(set(record), {"origin", "worktree_status", "worktree_sha256"})
            self.assertEqual(record["origin"], "local-worktree")
            self.assertEqual(record["worktree_status"], "dirty")
            self.assertEqual((destination / "main.cpp").read_text(), "pending edit")
            self.assertEqual((destination / "new.cpp").read_text(), "new VT source")
            self.assertEqual((destination / "added.h").read_text(), "staged header")
            self.assertFalse((destination / "deleted.cpp").exists())
            self.assertEqual((destination / "libhv/cert/server.key").read_bytes(), key)
            self.assertFalse((destination / "libhv/ignored.key").exists())
            self.assertEqual(subprocess.check_output(["git", "-C", str(destination / "libhv"),
                                                     "rev-parse", "HEAD"]), commit)
            self.assertEqual(self.git("status", "--porcelain=v1"), before)
            (self.source / "new.cpp").write_text("different pending source")
            snapshot(self.source, destination)
            changed = json.loads(destination.with_suffix(".snapshot.json").read_text())
            self.assertNotEqual(record["worktree_sha256"], changed["worktree_sha256"])

    def test_snapshot_rejects_unrecognized_key_even_in_clean_libhv(self):
        snapshot = runpy.run_path(str(ROOT / "build/x2000/snapshot-fre3nderscreen.py"))["snapshot"]
        self.add_submodule("libhv", {"cert/server.key": b"-----BEGIN " + b"PRIVATE KEY-----\nnot upstream\n"})
        destination = self.root / "work/source"
        with self.assertRaisesRegex(ValueError, "private key"):
            snapshot(self.source, destination)
        self.assertFalse(destination.exists())

    def test_snapshot_rejects_private_keys_in_pending_staged_and_committed_sources(self):
        snapshot = runpy.run_path(str(ROOT / "build/x2000/snapshot-fre3nderscreen.py"))["snapshot"]
        (self.source / "new.cpp").write_bytes(b"-----BEGIN " + b"PRIVATE KEY-----\nnot a key\n")
        destination = self.root / "work/source"
        for state in ("pending", "staged", "committed"):
            if state == "staged":
                self.git("add", "new.cpp")
            elif state == "committed":
                self.git("commit", "-qm", "fixture with rejected key")
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, "private key"):
                snapshot(self.source, destination)
            self.assertFalse(destination.exists())

    def test_snapshot_rejects_dirty_or_unrecorded_submodules(self):
        snapshot = runpy.run_path(str(ROOT / "build/x2000/snapshot-fre3nderscreen.py"))["snapshot"]
        self.add_submodule("libhv")
        (self.source / "libhv/source.h").write_text("pending module edit")
        destination = self.root / "work/source"
        with self.assertRaisesRegex(ValueError, "submodule changes are unsupported"):
            snapshot(self.source, destination)
        self.assertEqual((self.source / "libhv/source.h").read_text(), "pending module edit")
        self.git("-C", "libhv", "add", "source.h")
        self.git("-C", "libhv", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "new module revision")
        with self.assertRaisesRegex(ValueError, "submodules must be initialized at their recorded commits"):
            snapshot(self.source, destination)
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
