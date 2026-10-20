#!/usr/bin/env python3
"""Host-side trust-contract tests for fre3nder-package-core."""

import hashlib
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE = ROOT / "configs/x2000/rootfs-overlay/usr/libexec/fre3nder/package-core"


def load_core_module():
    loader = importlib.machinery.SourceFileLoader(
        "fre3nder_package_core_test",
        str(CORE),
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class Fre3AppExecutablePayloadTests(unittest.TestCase):
    def test_extract_keeps_payload_bin_executable(self):
        core = load_core_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            package = root / "fixture.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("service", "#!/bin/sh\n")
                archive.writestr("payload/bin/fre3nderscreen", b"binary")
                archive.writestr("payload/themes/blue.json", b"{}")
            with mock.patch.object(core, "app_user", return_value=(os.getuid(), os.getgid())):
                core.extract_runtime(package, {}, root / "runtime")
            runtime = root / "runtime"
            self.assertEqual((runtime / "service").stat().st_mode & 0o777, 0o755)
            self.assertEqual(
                (runtime / "payload/bin/fre3nderscreen").stat().st_mode & 0o777,
                0o755,
            )
            self.assertEqual(
                (runtime / "payload/themes/blue.json").stat().st_mode & 0o777,
                0o644,
            )


class Fre3AppDevelopmentPolicyTests(unittest.TestCase):
    def test_manifest_accepts_zero_and_rejects_negative_serial(self):
        core = load_core_module()
        with tempfile.TemporaryDirectory() as tmp:
            package = pathlib.Path(tmp) / "fixture.zip"

            def verify(serial):
                manifest = f'''format = 1
[app]
name = "dummy"
version = "1.0.0-fre3nder.0.test"
release_serial = {serial}
[publisher]
id = "test-publisher"
key_fingerprint = "{"a" * 64}"
[target]
platform = "fre3nder-x2000"
arch = "mipsel"
[runtime]
service = "service"
autostart = false
[signature]
algorithm = "Ed25519"
file = "SHA256SUMS.sig"
signed_file = "SHA256SUMS"
'''.encode()
                members = {"manifest.toml": manifest, "service": b"#!/bin/sh\n"}
                sums = "".join(
                    f"{hashlib.sha256(data).hexdigest()}  {name}\n"
                    for name, data in sorted(members.items())
                ).encode()
                members.update({"SHA256SUMS": sums, "SHA256SUMS.sig": b"fixture"})
                with zipfile.ZipFile(package, "w") as archive:
                    for name, data in sorted(members.items()):
                        archive.writestr(name, data)
                with (mock.patch.object(core, "key_path", return_value=pathlib.Path(tmp) / "key"),
                      mock.patch.object(core, "fingerprint", return_value="a" * 64),
                      mock.patch.object(core, "verify_signature")):
                    return core.verify_package(package)

            self.assertEqual(verify(0)["release_serial"], 0)
            with self.assertRaisesRegex(ValueError, "manifest release_serial is invalid"):
                verify(-1)

    def test_update_serial_transitions(self):
        cases = (
            (0, "dev-a", 0, "dev-a", False, "same development package is already installed"),
            (0, "dev-a", 0, "dev-b", False, None),
            (0, "dev-a", 1, "release-a", False, None),
            (1, "release-a", 0, "dev-a", False, "package downgrade requires --allow-downgrade"),
            (1, "release-a", 0, "dev-a", True, None),
            (1, "release-a", 1, "release-b", False, "same package release is already installed"),
            (2, "release-b", 1, "release-a", False, "package downgrade requires --allow-downgrade"),
            (1, "release-a", 2, "release-b", False, None),
            (-1, "invalid", 0, "dev-a", False, "installed release_serial is invalid"),
        )
        for old_serial, old_version, new_serial, new_version, allow, error in cases:
            with self.subTest(old_serial=old_serial, new_serial=new_serial, allow=allow, error=error):
                core = load_core_module()
                with tempfile.TemporaryDirectory() as tmp:
                    root = pathlib.Path(tmp)
                    core.RUNTIME_ROOT = root / "runtime"
                    core.RECOVERY_ROOT = root / "recovery"
                    verified = {
                        "name": "dummy", "version": new_version, "release_serial": new_serial,
                        "publisher": "publisher", "fingerprint": "a" * 64,
                        "autostart": False, "web_frontend": False,
                        "display_frontend": False, "display_api": None,
                    }
                    old = {
                        "version": old_version, "release_serial": old_serial,
                        "publisher": "publisher", "fingerprint": "a" * 64,
                        "web_frontend": False, "display_frontend": False,
                        "display_api": None,
                    }
                    with (mock.patch.object(core, "verify_package", return_value=verified),
                          mock.patch.object(core, "installed", return_value=True),
                          mock.patch.object(core, "read_metadata", return_value=old),
                          mock.patch.object(core, "extract_runtime", side_effect=lambda _p, _v, target: target.mkdir()),
                          mock.patch.object(core, "service_action", return_value=0),
                          mock.patch.object(core, "check_install_space"),
                          mock.patch.object(core, "write_state") as write_state):
                        if error:
                            with self.assertRaisesRegex(ValueError, error):
                                core.activate_package(root / "fixture.zip", "update", allow)
                            write_state.assert_not_called()
                        else:
                            self.assertEqual(
                                core.activate_package(root / "fixture.zip", "update", allow),
                                verified,
                            )
                            write_state.assert_called_once()


class Fre3AppTrustTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.private = self.root / "private.pem"
        self.public = self.root / "public.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", self.private], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["openssl", "pkey", "-in", self.private, "-pubout", "-out", self.public], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        der = subprocess.run(["openssl", "pkey", "-pubin", "-in", self.public, "-outform", "DER"], check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout
        self.fingerprint = hashlib.sha256(der).hexdigest()
        self.env = os.environ.copy()
        self.env["FRE3NDER_HOME_DIR"] = str(self.home)
        self.env["FRE3NDER_PACKAGE_STATE_ROOT"] = str(self.root / "manager-state")
        previous_umask = os.umask(0o002)
        try:
            self.run_core("key-add", "test-publisher", str(self.public), check=True)
        finally:
            os.umask(previous_umask)

    def tearDown(self):
        self.temp.cleanup()

    def run_core(self, *args, check=False):
        return subprocess.run([str(CORE), *args], env=self.env, text=True, capture_output=True, check=check)

    def make_package(
        self,
        name="dummy.fre3app",
        extra_unsigned=False,
        duplicate=False,
        traversal=False,
        noncanonical=False,
    ):
        src = self.root / (name + ".src")
        src.mkdir()
        (src / "manifest.toml").write_text(f'''format = 1\n\n[app]\nname = "dummy"\nversion = "1.0.0-fre3nder.1"\nrelease_serial = 1\n\n[publisher]\nid = "test-publisher"\nkey_fingerprint = "{self.fingerprint}"\n\n[target]\nplatform = "fre3nder-x2000"\narch = "mipsel"\n\n[runtime]\nservice = "service"\nautostart = true\n\n[signature]\nalgorithm = "Ed25519"\nfile = "SHA256SUMS.sig"\nsigned_file = "SHA256SUMS"\n''')
        (src / "service").write_text("#!/bin/sh\nexit 0\n")
        payload = src / "payload"
        payload.mkdir()
        (payload / "data.txt").write_text("payload\n")
        files = sorted(p for p in src.rglob("*") if p.is_file())
        sums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(src).as_posix()}\n" for p in files)
        (src / "SHA256SUMS").write_text(sums)
        subprocess.run(["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", self.private, "-in", src / "SHA256SUMS", "-out", src / "SHA256SUMS.sig"], check=True)
        package = self.root / name
        with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
            for p in sorted(src.rglob("*")):
                if p.is_file():
                    archive.write(p, p.relative_to(src).as_posix())
            if extra_unsigned:
                archive.writestr("payload/unsigned.txt", "unsigned\n")
            if duplicate:
                archive.writestr("payload/data.txt", "duplicate\n")
            if traversal:
                archive.writestr("../escape", "bad\n")
            if noncanonical:
                archive.writestr("payload//alias.txt", "bad\n")
        return package

    def test_valid_package(self):
        result = self.run_core("verify", str(self.make_package()))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_unsigned_extra_member_is_refused(self):
        result = self.run_core("verify", str(self.make_package(extra_unsigned=True)))
        self.assertNotEqual(result.returncode, 0)

    def test_duplicate_member_is_refused(self):
        result = self.run_core("verify", str(self.make_package(duplicate=True)))
        self.assertNotEqual(result.returncode, 0)

    def test_traversal_member_is_refused(self):
        result = self.run_core("verify", str(self.make_package(traversal=True)))
        self.assertNotEqual(result.returncode, 0)

    def test_noncanonical_member_is_refused(self):
        result = self.run_core("verify", str(self.make_package(noncanonical=True)))
        self.assertNotEqual(result.returncode, 0)


class Fre3AppLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.core = load_core_module()
        self.core.RUNTIME_ROOT = self.root / "runtime"
        self.core.RECOVERY_ROOT = self.root / "recovery"
        self.core.STATE_ROOT = self.root / "state"

    def tearDown(self):
        self.temp.cleanup()

    def verified(self, publisher="publisher-a", fingerprint="a" * 64, serial=2):
        return {
            "name": "dummy",
            "version": f"1.0.{serial}-fre3nder.1",
            "release_serial": serial,
            "publisher": publisher,
            "fingerprint": fingerprint,
            "autostart": True,
            "web_frontend": False,
            "display_frontend": False,
            "display_api": None,
        }

    def test_update_cannot_change_publisher(self):
        package = self.root / "dummy.fre3app"
        package.touch()
        with (
            mock.patch.object(self.core, "verify_package", return_value=self.verified()),
            mock.patch.object(self.core, "installed", return_value=True),
            mock.patch.object(
                self.core,
                "read_metadata",
                return_value={
                    "name": "dummy",
                    "version": "1.0.1-fre3nder.1",
                    "release_serial": 1,
                    "publisher": "publisher-b",
                    "fingerprint": "b" * 64,
                    "autostart": True,
                    "web_frontend": False,
                },
            ),
        ):
            with self.assertRaisesRegex(ValueError, "publisher differs"):
                self.core.activate_package(package, "update")

    def test_failed_start_does_not_commit_new_state(self):
        package = self.root / "dummy.fre3app"
        package.touch()
        current = self.core.RUNTIME_ROOT / "dummy"
        current.mkdir(parents=True)
        current.parent.chmod(0o755)
        (current / "old").write_text("old\n")

        def extract_runtime(_package, _verified, target):
            target.mkdir(parents=True)
            (target / "service").write_text("#!/bin/sh\n")

        def service_action(_name, action, runtime=None):
            if action == "status":
                return 0
            if action == "start" and runtime == current:
                return 1
            return 0

        state_writer = mock.Mock()
        with (
            mock.patch.object(self.core, "verify_package", return_value=self.verified()),
            mock.patch.object(self.core, "installed", return_value=True),
            mock.patch.object(
                self.core,
                "read_metadata",
                return_value={
                    "name": "dummy",
                    "version": "1.0.1-fre3nder.1",
                    "release_serial": 1,
                    "publisher": "publisher-a",
                    "fingerprint": "a" * 64,
                    "autostart": True,
                    "web_frontend": False,
                },
            ),
            mock.patch.object(self.core, "extract_runtime", side_effect=extract_runtime),
            mock.patch.object(self.core, "service_action", side_effect=service_action),
            mock.patch.object(self.core, "check_install_space"),
            mock.patch.object(self.core, "write_state", state_writer),
        ):
            with self.assertRaisesRegex(ValueError, "start failed"):
                self.core.activate_package(package, "update")

        state_writer.assert_not_called()
        self.assertTrue((current / "old").is_file())


class Fre3AppWebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.core = load_core_module()
        self.core.PACKAGE_STATE_ROOT = self.root / "manager"
        self.core.STATE_ROOT = self.core.PACKAGE_STATE_ROOT / "packages"
        self.core.FRONTEND_ROOT = self.core.PACKAGE_STATE_ROOT / "frontend"
        self.core.ACTIVE_FRONTEND = self.core.FRONTEND_ROOT / "active"
        self.core.RUNTIME_ROOT = self.root / "runtime"
        self.core.RECOVERY_ROOT = self.root / "recovery"
        self.core.DATA_ROOT = self.root / "data"
        self.calls = self.root / "web-calls"
        self.core.WEB_SERVICE = self.root / "web-service"
        self.core.WEB_SERVICE.write_text(
            f"#!/bin/sh\nprintf '%s\\n' \"$1\" >> '{self.calls}'\n"
        )
        self.core.WEB_SERVICE.chmod(0o755)

    def package(self, web=None, index=b"<html></html>"):
        # Build only an in-memory verification fixture, never a signed app artifact.
        lines = [
            'format = 1',
            '[app]', 'name = "fluidd"', 'version = "1.37.6-fre3nder.1"', 'release_serial = 1',
            '[publisher]', 'id = "fre3nder-official"', f'key_fingerprint = "{"a" * 64}"',
            '[target]', 'platform = "fre3nder-x2000"', 'arch = "mipsel"',
            '[runtime]', 'service = "service"', 'autostart = false',
        ]
        if web is not None:
            lines.extend(['[web]', f'frontend = {web}'])
        lines.extend(['[signature]', 'algorithm = "Ed25519"', 'file = "SHA256SUMS.sig"', 'signed_file = "SHA256SUMS"'])
        files = {"manifest.toml": ("\n".join(lines) + "\n").encode(), "service": b"#!/bin/sh\n"}
        if index is not None:
            files["payload/index.html"] = index
        sums = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())).encode()
        files["SHA256SUMS"] = sums
        files["SHA256SUMS.sig"] = b"s" * 64
        package = self.root / "fixture.zip"
        with zipfile.ZipFile(package, "w") as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        return package

    def verify(self, package):
        with (mock.patch.object(self.core, "key_path", return_value=self.root / "key"),
              mock.patch.object(self.core, "fingerprint", return_value="a" * 64),
              mock.patch.object(self.core, "verify_signature")):
            return self.core.verify_package(package)

    def test_web_manifest_validation(self):
        self.assertIs(self.verify(self.package())["web_frontend"], False)
        self.assertIs(self.verify(self.package("true"))["web_frontend"], True)
        for web, index in (("1", b"valid"), ("true", None), ("true", b"")):
            with self.subTest(web=web, index=index):
                with self.assertRaises(ValueError):
                    self.verify(self.package(web, index))

    def test_verify_response_reports_web_capability(self):
        package = self.package("true")
        output = io.StringIO()
        with (contextlib.redirect_stdout(output),
              mock.patch.object(self.core, "verify_package", return_value=self.verify(package)),
              mock.patch.object(sys, "argv", [str(CORE), "verify", str(package)])):
            self.core.main()
        self.assertIs(json.loads(output.getvalue())["package"]["web_frontend"], True)

    def verified(self, name="fluidd", serial=1, web=True):
        return {
            "name": name, "version": f"1.37.6-fre3nder.{serial}",
            "release_serial": serial, "publisher": "fre3nder-official",
            "fingerprint": "a" * 64, "autostart": False,
            "web_frontend": web, "display_frontend": False,
            "display_api": None,
        }

    def extract(self, _package, _verified, target):
        target.mkdir(parents=True)
        (target / "service").write_text("#!/bin/sh\n")

    def activate(self, verified, operation="install"):
        package = self.root / "source.zip"
        package.write_bytes(b"fixture")
        with (mock.patch.object(self.core, "verify_package", return_value=verified),
              mock.patch.object(self.core, "check_install_space"),
              mock.patch.object(self.core, "extract_runtime", side_effect=self.extract),
              mock.patch.object(self.core, "service_action", return_value=0)):
            return self.core.activate_package(package, operation)

    def test_selection_metadata_and_refresh(self):
        self.activate(self.verified())
        self.assertEqual(self.core.ACTIVE_FRONTEND.read_text(), "fluidd\n")
        self.assertEqual(self.core.read_metadata("fluidd")["web_frontend"], True)
        self.assertEqual(self.calls.read_text(), "restart\n")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), mock.patch.object(self.core, "service_action", return_value=0), mock.patch.object(sys, "argv", [str(CORE), "status", "fluidd"]):
            self.core.main()
        self.assertIs(json.loads(output.getvalue())["app"]["web_frontend"], True)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), mock.patch.object(sys, "argv", [str(CORE), "list"]):
            self.core.main()
        self.assertIs(json.loads(output.getvalue())["apps"][0]["web_frontend"], True)
        self.activate(self.verified(serial=2), "update")
        self.assertEqual(self.calls.read_text(), "restart\nrestart\n")
        with mock.patch.object(self.core, "service_action", return_value=0):
            self.core.remove_package("fluidd")
        self.assertFalse(self.core.ACTIVE_FRONTEND.exists())
        self.assertEqual(self.calls.read_text(), "restart\nrestart\nrestart\n")

    def test_other_selection_is_preserved_and_capability_cannot_change(self):
        self.core.PACKAGE_STATE_ROOT.mkdir(mode=0o700)
        self.core.FRONTEND_ROOT.mkdir(mode=0o700)
        self.core.ACTIVE_FRONTEND.write_text("another-ui\n")
        self.core.ACTIVE_FRONTEND.chmod(0o644)
        self.activate(self.verified())
        self.assertEqual(self.core.ACTIVE_FRONTEND.read_text(), "another-ui\n")
        self.assertFalse(self.calls.exists())
        with self.assertRaisesRegex(ValueError, "capability differs"):
            self.activate(self.verified(serial=2, web=False), "update")
        with mock.patch.object(self.core, "service_action", return_value=0):
            self.core.remove_package("fluidd")
        self.assertEqual(self.core.ACTIVE_FRONTEND.read_text(), "another-ui\n")
        self.assertFalse(self.calls.exists())

    def test_boot_restore_never_refreshes_web(self):
        self.activate(self.verified())
        self.calls.unlink()
        shutil.rmtree(self.core.runtime_dir("fluidd"))
        (self.core.RECOVERY_ROOT / "fluidd/restored").unlink()
        with (mock.patch.object(self.core, "verify_package", return_value=self.verified()),
              mock.patch.object(self.core, "check_install_space"),
              mock.patch.object(self.core, "extract_runtime", side_effect=self.extract),
              mock.patch.object(self.core, "service_action", return_value=0)):
            self.assertEqual(self.core.restore_installed(), 0)
        self.assertFalse(self.calls.exists())
        self.assertEqual(self.core.ACTIVE_FRONTEND.read_text(), "fluidd\n")

    def test_restore_pre_web_metadata_and_cached_package(self):
        package = self.package()
        verified = self.verify(package)
        self.assertIs(verified["web_frontend"], False)
        with (mock.patch.object(self.core, "key_path", return_value=self.root / "key"),
              mock.patch.object(self.core, "fingerprint", return_value="a" * 64),
              mock.patch.object(self.core, "verify_signature")):
            self.core.write_state(package, verified)
        metadata = self.core.metadata_path("fluidd")
        value = json.loads(metadata.read_text())
        del value["web_frontend"]
        metadata.write_text(json.dumps(value) + "\n")
        self.assertNotIn("web_frontend", json.loads(metadata.read_text()))
        cached = self.core.state_dir("fluidd") / "package.fre3app"
        with zipfile.ZipFile(cached) as archive:
            self.assertNotIn(b"[web]", archive.read("manifest.toml"))

        with (mock.patch.object(self.core, "key_path", return_value=self.root / "key"),
              mock.patch.object(self.core, "fingerprint", return_value="a" * 64),
              mock.patch.object(self.core, "verify_signature"),
              mock.patch.object(self.core, "extract_runtime", side_effect=self.extract),
              mock.patch.object(self.core, "service_action", return_value=0),
              mock.patch.object(sys, "argv", [str(CORE), "restore-installed"])):
            self.assertEqual(self.core.main(), 0)

        self.assertIs(self.core.read_metadata("fluidd")["web_frontend"], False)
        self.assertTrue((self.core.runtime_dir("fluidd") / "service").is_file())
        self.assertTrue((self.core.RECOVERY_ROOT / "fluidd/restored").is_file())
        self.assertFalse(self.core.ACTIVE_FRONTEND.exists())

    def test_restore_rejects_changed_web_metadata(self):
        self.activate(self.verified())
        self.calls.unlink()
        shutil.rmtree(self.core.runtime_dir("fluidd"))
        (self.core.RECOVERY_ROOT / "fluidd/restored").unlink()
        metadata = self.core.metadata_path("fluidd")
        value = json.loads(metadata.read_text())
        value["web_frontend"] = False
        metadata.write_text(json.dumps(value))
        with mock.patch.object(self.core, "verify_package", return_value=self.verified()):
            self.assertEqual(self.core.restore_installed(), 1)
        self.assertFalse(self.calls.exists())

    def test_web_refresh_failure_does_not_undo_install(self):
        self.core.WEB_SERVICE.write_text("#!/bin/sh\nexit 23\n")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.activate(self.verified())
        self.assertIn("web refresh failed", stderr.getvalue())
        self.assertTrue(self.core.installed("fluidd"))
        self.assertEqual(self.core.ACTIVE_FRONTEND.read_text(), "fluidd\n")

    def test_corrupt_cached_copy_does_not_replace_existing_state(self):
        package = self.package("true")
        verified = self.verify(package)
        with (mock.patch.object(self.core, "key_path", return_value=self.root / "key"),
              mock.patch.object(self.core, "fingerprint", return_value="a" * 64),
              mock.patch.object(self.core, "verify_signature")):
            self.core.write_state(package, verified)
            current = self.core.state_dir("fluidd")
            old_package = (current / "package.fre3app").read_bytes()
            old_metadata = (current / "metadata.json").read_bytes()

            real_copy = shutil.copyfile

            def corrupt_copy(source, target):
                real_copy(source, target)
                with zipfile.ZipFile(target) as archive:
                    info = archive.getinfo("payload/index.html")
                    offset = (info.header_offset + 30
                              + len(info.filename.encode("utf-8")) + len(info.extra))
                with open(target, "r+b") as stream:
                    stream.seek(offset)
                    before = stream.read(1)
                    stream.seek(offset)
                    stream.write(bytes([before[0] ^ 1]))

            with mock.patch.object(self.core.shutil, "copyfile", side_effect=corrupt_copy):
                with self.assertRaises(zipfile.BadZipFile):
                    self.core.write_state(package, verified)

        self.assertEqual((current / "package.fre3app").read_bytes(), old_package)
        self.assertEqual((current / "metadata.json").read_bytes(), old_metadata)
        self.assertEqual([p.name for p in self.core.STATE_ROOT.iterdir()], ["fluidd"])

    def test_cache_fsync_failure_does_not_publish_state(self):
        package = self.package("true")
        verified = self.verify(package)
        with mock.patch.object(self.core.os, "fsync", side_effect=OSError("writeback failed")):
            with self.assertRaisesRegex(OSError, "writeback failed"):
                self.core.write_state(package, verified)
        self.assertFalse(self.core.installed("fluidd"))

    def test_s58_only_calls_package_core_and_never_blocks_boot(self):
        service = self.root / "package-core"
        service.write_text("#!/bin/sh\nexit 23\n")
        service.chmod(0o755)
        script = ROOT / "configs/x2000/rootfs-overlay/etc/init.d/S58fre3nder-app-restore"
        env = dict(os.environ, FRE3NDER_PACKAGE_CORE=str(service))
        result = subprocess.run(["sh", str(script), "start"], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("DEGRADED", result.stderr)


class Fre3AppDisplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.core = load_core_module()
        self.core.PACKAGE_STATE_ROOT = self.root / "manager"
        self.core.STATE_ROOT = self.core.PACKAGE_STATE_ROOT / "packages"
        self.core.FRONTEND_ROOT = self.core.PACKAGE_STATE_ROOT / "frontend"
        self.core.ACTIVE_FRONTEND = self.core.FRONTEND_ROOT / "active"
        self.core.DISPLAY_ROOT = self.core.PACKAGE_STATE_ROOT / "display"
        self.core.ACTIVE_DISPLAY = self.core.DISPLAY_ROOT / "active"
        self.core.RUNTIME_ROOT = self.root / "runtime"
        self.core.RECOVERY_ROOT = self.root / "recovery"
        self.core.DATA_ROOT = self.root / "data"
        self.core.DISPLAY_SERVICE = self.root / "display-service"
        self.core.DISPLAY_STATUS = self.root / "display-status"
        self.core.DISPLAY_SERVICE.write_text(
            "#!/bin/sh\n"
            f"case $1 in start) echo active > '{self.core.DISPLAY_STATUS}';;\n"
            f"stop) echo stopped > '{self.core.DISPLAY_STATUS}';; esac\n"
            "exit 0\n"
        )
        self.core.DISPLAY_SERVICE.chmod(0o755)

    def package(self, display=None, api=None, autostart=False):
        lines = [
            'format = 1',
            '[app]', 'name = "screen"', 'version = "1.0.0"', 'release_serial = 1',
            '[publisher]', 'id = "fre3nder-official"', f'key_fingerprint = "{"a" * 64}"',
            '[target]', 'platform = "fre3nder-x2000"', 'arch = "mipsel"',
            '[runtime]', 'service = "service"',
            f'autostart = {"true" if autostart else "false"}',
        ]
        if display is not None:
            lines.extend(['[display]', f'frontend = {display}'])
            if api is not None:
                lines.append(f'api = {api}')
        lines.extend([
            '[signature]', 'algorithm = "Ed25519"',
            'file = "SHA256SUMS.sig"', 'signed_file = "SHA256SUMS"',
        ])
        files = {
            "manifest.toml": ("\n".join(lines) + "\n").encode(),
            "service": b"#!/bin/sh\nexit 0\n",
        }
        sums = "".join(
            f"{hashlib.sha256(data).hexdigest()}  {name}\n"
            for name, data in sorted(files.items())
        ).encode()
        files["SHA256SUMS"] = sums
        files["SHA256SUMS.sig"] = b"s" * 64
        package = self.root / "fixture.fre3app"
        with zipfile.ZipFile(package, "w") as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        return package

    def verify(self, package):
        with (
            mock.patch.object(self.core, "key_path", return_value=self.root / "key"),
            mock.patch.object(self.core, "fingerprint", return_value="a" * 64),
            mock.patch.object(self.core, "verify_signature"),
        ):
            return self.core.verify_package(package)

    def verified(self, serial=1, display=True, api=1):
        return {
            "name": "screen",
            "version": f"1.0.{serial}",
            "release_serial": serial,
            "publisher": "fre3nder-official",
            "fingerprint": "a" * 64,
            "autostart": False,
            "web_frontend": False,
            "display_frontend": display,
            "display_api": api if display else None,
        }

    def extract(self, _package, _verified, target):
        target.mkdir(parents=True)
        (target / "service").write_text("#!/bin/sh\nexit 0\n")

    def activate(self, verified, operation="install"):
        package = self.root / "source.fre3app"
        package.write_bytes(b"fixture")
        with (
            mock.patch.object(self.core, "verify_package", return_value=verified),
            mock.patch.object(self.core, "check_install_space"),
            mock.patch.object(self.core, "extract_runtime", side_effect=self.extract),
            mock.patch.object(self.core, "service_action", return_value=0),
        ):
            return self.core.activate_package(package, operation)

    def test_display_manifest_validation(self):
        plain = self.verify(self.package())
        self.assertIs(plain["display_frontend"], False)
        self.assertIsNone(plain["display_api"])

        display = self.verify(self.package("true", 1))
        self.assertIs(display["display_frontend"], True)
        self.assertEqual(display["display_api"], 1)

        for frontend, api, autostart in (
            ("1", 1, False),
            ("true", None, False),
            ("true", 2, False),
            ("true", 1, True),
            ("false", 1, False),
        ):
            with self.subTest(frontend=frontend, api=api, autostart=autostart):
                with self.assertRaises(ValueError):
                    self.verify(self.package(frontend, api, autostart))

    def test_verify_list_and_status_report_display_capability(self):
        package = self.package("true", 1)
        verified = self.verify(package)

        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            mock.patch.object(self.core, "verify_package", return_value=verified),
            mock.patch.object(sys, "argv", [str(CORE), "verify", str(package)]),
        ):
            self.assertEqual(self.core.main(), 0)
        package_result = json.loads(output.getvalue())["package"]
        self.assertIs(package_result["display_frontend"], True)
        self.assertEqual(package_result["display_api"], 1)

        self.activate(self.verified())

        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            mock.patch.object(sys, "argv", [str(CORE), "list"]),
        ):
            self.assertEqual(self.core.main(), 0)
        listed = json.loads(output.getvalue())["apps"][0]
        self.assertIs(listed["display_frontend"], True)
        self.assertEqual(listed["display_api"], 1)

        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            mock.patch.object(self.core, "service_action", return_value=0),
            mock.patch.object(sys, "argv", [str(CORE), "status", "screen"]),
        ):
            self.assertEqual(self.core.main(), 0)
        status = json.loads(output.getvalue())["app"]
        self.assertIs(status["display_frontend"], True)
        self.assertEqual(status["display_api"], 1)

    def test_install_does_not_select_display_and_selection_is_explicit(self):
        self.activate(self.verified())
        self.assertFalse(self.core.ACTIVE_DISPLAY.exists())
        self.assertTrue(self.core.read_metadata("screen")["display_frontend"])

        self.core.select_display("screen")
        self.assertEqual(self.core.active_display(), "screen")
        self.assertEqual(self.core.ACTIVE_DISPLAY.read_text(), "screen\n")

        self.activate(self.verified(serial=2), "update")
        self.assertEqual(self.core.active_display(), "screen")

        with mock.patch.object(self.core, "service_action", return_value=0):
            self.core.remove_package("screen")
        self.assertFalse(self.core.ACTIVE_DISPLAY.exists())

    def test_select_requires_installed_display_frontend(self):
        with self.assertRaisesRegex(ValueError, "not installed"):
            self.core.select_display("missing")

        self.activate(self.verified(display=False, api=None))
        with self.assertRaisesRegex(ValueError, "not a display frontend"):
            self.core.select_display("screen")

    def test_update_cannot_change_display_capability(self):
        self.activate(self.verified())
        with self.assertRaisesRegex(ValueError, "display frontend capability differs"):
            self.activate(self.verified(serial=2, display=False, api=None), "update")

    def test_display_core_operations_report_selection(self):
        self.activate(self.verified())

        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            mock.patch.object(sys, "argv", [str(CORE), "display-list"]),
        ):
            self.assertEqual(self.core.main(), 0)
        result = json.loads(output.getvalue())
        self.assertIsNone(result["active"])
        self.assertEqual(result["apps"][0]["name"], "screen")
        self.assertIs(result["apps"][0]["active"], False)

        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            mock.patch.object(
                sys,
                "argv",
                [str(CORE), "display-select", "screen"],
            ),
        ):
            self.assertEqual(self.core.main(), 0)
        self.assertEqual(json.loads(output.getvalue())["display"]["active"], "screen")

        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            mock.patch.object(sys, "argv", [str(CORE), "display-status"]),
        ):
            self.assertEqual(self.core.main(), 0)
        self.assertEqual(json.loads(output.getvalue())["display"]["active"], "screen")

        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            mock.patch.object(sys, "argv", [str(CORE), "display-disable"]),
        ):
            self.assertEqual(self.core.main(), 0)
        self.assertIsNone(json.loads(output.getvalue())["display"]["active"])
        self.assertFalse(self.core.ACTIVE_DISPLAY.exists())

    def test_pre_display_metadata_defaults_to_no_capability(self):
        package = self.package()
        verified = self.verify(package)
        with (mock.patch.object(self.core, "key_path", return_value=self.root / "key"),
              mock.patch.object(self.core, "fingerprint", return_value="a" * 64),
              mock.patch.object(self.core, "verify_signature")):
            self.core.write_state(package, verified)
        metadata = self.core.metadata_path("screen")
        value = json.loads(metadata.read_text())
        del value["display_frontend"]
        del value["display_api"]
        metadata.write_text(json.dumps(value) + "\n")

        restored = self.core.read_metadata("screen")
        self.assertIs(restored["display_frontend"], False)
        self.assertIsNone(restored["display_api"])


class Fre3AppStorageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fre3AppTrustTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        self.env = {**self.fixture.env,
                    "FRE3NDER_PACKAGE_RUNTIME_ROOT": str(self.root / "sys/apps-v2"),
                    "FRE3NDER_PACKAGE_RECOVERY_DIR": str(self.root / "sys/restored")}
        with mock.patch.dict(os.environ, self.env):
            self.core = load_core_module()
        self.user = mock.patch.object(self.core, "app_user", return_value=(os.getuid(), os.getgid()))
        self.user.start()
        self.addCleanup(self.user.stop)
        self.actions = mock.patch.object(self.core, "service_action", return_value=0)
        self.service = self.actions.start()
        self.addCleanup(self.actions.stop)
        self.refresh = mock.patch.object(self.core, "refresh_web")
        self.refresh.start()
        self.addCleanup(self.refresh.stop)

    def package(self, serial=1, name="dummy"):
        manifest = f'''format = 1
[app]
name = "{name}"
version = "1.0.{serial}"
release_serial = {serial}
[publisher]
id = "test-publisher"
key_fingerprint = "{self.fixture.fingerprint}"
[target]
platform = "fre3nder-x2000"
arch = "mipsel"
[runtime]
service = "service"
autostart = false
[web]
frontend = true
'''
        manifest += '[signature]\nalgorithm = "Ed25519"\nfile = "SHA256SUMS.sig"\nsigned_file = "SHA256SUMS"\n'
        files = {"manifest.toml": manifest.encode(), "service": b"#!/bin/sh\nexit 0\n",
                 "payload/index.html": f"release {serial}".encode()}
        sums = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())).encode()
        source = self.root / "checksums"
        signature = self.root / "signature"
        source.write_bytes(sums)
        subprocess.run(["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", self.fixture.private,
                        "-in", source, "-out", signature], check=True)
        files.update({"SHA256SUMS": sums, "SHA256SUMS.sig": signature.read_bytes()})
        package = self.root / f"{name}-{serial}.fre3app"
        with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        return package

    def install(self, role=None, name="dummy"):
        package = self.package(name=name)
        self.core.activate_package(package, "install", storage=role)
        return self.core.runtime_dir(name)

    def test_default_explicit_roles_and_legacy_metadata(self):
        for role in (None, "sys", "home"):
            name = "app-" + (role or "default")
            current = self.install(role, name)
            expected = self.core.RUNTIME_ROOT if role != "home" else self.core.HOME_RUNTIME_ROOT
            self.assertEqual(current, expected / name)
            self.assertEqual(self.core.read_metadata(name)["storage"], role or "sys")
            cached = self.core.state_dir(name) / "package.fre3app"
            self.assertEqual(cached.read_bytes(), (self.root / f"{name}-1.fre3app").read_bytes())
            self.assertNotIn("storage", self.core.verify_package(cached)["manifest"]["app"])
        metadata = self.core.metadata_path("app-default")
        value = json.loads(metadata.read_text())
        del value["storage"]
        metadata.write_text(json.dumps(value))
        self.assertEqual(self.core.read_metadata("app-default")["storage"], "sys")
        self.assertEqual(self.core.runtime_dir("app-default"), self.core.RUNTIME_ROOT / "app-default")

    def test_invalid_storage_and_update_migration_are_rejected(self):
        package = self.package()
        for role in ("/tmp", "../home", "HOME", "", 1, []):
            with self.subTest(role=role), self.assertRaisesRegex(ValueError, "storage"):
                self.core.activate_package(package, "install", storage=role)
        self.install("sys")
        with self.assertRaisesRegex(ValueError, "preserve"):
            self.core.activate_package(self.package(2), "update", storage="home")
        metadata = self.core.metadata_path("dummy")
        data = json.loads(metadata.read_text())
        data["storage"] = "../other"
        metadata.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "storage"):
            self.core.runtime_dir("dummy")

    def test_updates_and_removal_keep_each_runtime_role(self):
        for role in ("sys", "home"):
            name = "app-" + role
            current = self.install(role, name)
            self.service.reset_mock()
            self.core.activate_package(self.package(2, name), "update")
            self.assertEqual([call.args[1] for call in self.service.call_args_list],
                             ["status", "stop", "update", "start"])
            self.assertEqual(self.core.runtime_dir(name), current)
            self.assertEqual((current / "payload/index.html").read_bytes(), b"release 2")
            other = self.core.prepare_runtime_root("home" if role == "sys" else "sys") / name
            other.mkdir()
            (other / "keep").write_text("unrelated")
            self.core.remove_package(name)
            self.assertFalse(current.exists())
            self.assertTrue((other / "keep").is_file())

    def test_core_install_syntax_and_status_report_storage(self):
        for role in (None, "sys", "home"):
            name = "app-" + (role or "default")
            package = self.package(name=name)
            args = [str(CORE), "install", str(package)] + (["--storage", role] if role else [])
            output = io.StringIO()
            with contextlib.redirect_stdout(output), mock.patch.object(sys, "argv", args):
                self.assertEqual(self.core.main(), 0)
            self.assertEqual(json.loads(output.getvalue())["package"]["storage"], role or "sys")
            output = io.StringIO()
            with contextlib.redirect_stdout(output), mock.patch.object(sys, "argv", [str(CORE), "status", name]):
                self.core.main()
            self.assertEqual(json.loads(output.getvalue())["app"]["storage"], role or "sys")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), mock.patch.object(sys, "argv", [str(CORE), "list"]):
            self.core.main()
        self.assertEqual({item["name"]: item["storage"] for item in json.loads(output.getvalue())["apps"]},
                         {"app-default": "sys", "app-sys": "sys", "app-home": "home"})

    def test_update_failure_restores_runtime_metadata_and_cache(self):
        for role in ("sys", "home"):
            name = "app-" + role
            current = self.install(role, name)
            old_state = {path.name: path.read_bytes() for path in self.core.state_dir(name).iterdir()}
            self.service.side_effect = lambda _name, action, *args: 1 if action == "update" else 0
            with self.assertRaisesRegex(ValueError, "update failed"):
                self.core.activate_package(self.package(2, name), "update")
            self.service.side_effect = None
            self.assertEqual((current / "payload/index.html").read_bytes(), b"release 1")
            self.assertEqual(old_state, {path.name: path.read_bytes() for path in self.core.state_dir(name).iterdir()})

    def test_sys_reset_reconstructs_sys_but_reuses_valid_home_runtime(self):
        sys_runtime = self.install("sys", "app-sys")
        home_runtime = self.install("home", "app-home")
        home_inode = (home_runtime / "service").stat().st_ino
        shutil.rmtree(self.core.RUNTIME_ROOT)
        shutil.rmtree(self.core.RECOVERY_ROOT)
        self.service.reset_mock()
        with mock.patch.object(self.core, "extract_runtime", wraps=self.core.extract_runtime) as extract:
            self.assertEqual(self.core.restore_installed(), 0)
        self.assertEqual(extract.call_count, 1)
        self.assertTrue((sys_runtime / "service").is_file())
        self.assertEqual((home_runtime / "service").stat().st_ino, home_inode)
        self.assertIn(mock.call("app-home", "restore", home_runtime), self.service.call_args_list)
        self.service.reset_mock()
        with mock.patch.object(self.core, "extract_runtime", wraps=self.core.extract_runtime) as extract:
            self.assertEqual(self.core.restore_installed(), 0)
            extract.assert_not_called()
        self.service.assert_not_called()

    def test_missing_and_damaged_home_runtime_are_reconstructed(self):
        current = self.install("home")
        for damage in ("missing", "checksum", "symlink"):
            if damage == "missing":
                shutil.rmtree(current)
            elif damage == "checksum":
                (current / "payload/index.html").write_bytes(b"tampered")
            else:
                (current / "payload/index.html").unlink()
                (current / "payload/index.html").symlink_to(self.root / "checksums")
            with mock.patch.object(self.core, "extract_runtime", wraps=self.core.extract_runtime) as extract:
                self.assertEqual(self.core.restore_installed(), 0)
                extract.assert_called_once()
            self.assertEqual((current / "payload/index.html").read_bytes(), b"release 1")

    def test_home_recovery_rechecks_cached_trust_and_preserves_valid_runtime_on_error(self):
        current = self.install("home")
        with mock.patch.object(self.core, "verify_signature", side_effect=ValueError("untrusted cache")):
            self.assertEqual(self.core.restore_installed(), 1)
        self.assertEqual((current / "payload/index.html").read_bytes(), b"release 1")

    def test_capacity_counts_extraction_and_cache_before_service_actions(self):
        package = self.package()
        for role in ("sys", "home"):
            self.service.reset_mock()
            with mock.patch.object(self.core.os, "statvfs", return_value=types.SimpleNamespace(f_bavail=1, f_frsize=4096)):
                with self.assertRaisesRegex(ValueError, "space"):
                    self.core.activate_package(package, "install", storage=role)
            self.service.assert_not_called()
            self.assertFalse(self.core.installed("dummy"))
        target = self.core.prepare_runtime_root("home")
        reserve = 32 * 1024 * 1024
        # Each requirement separately fits; their combined HOME use does not.
        free = reserve + package.stat().st_size
        with mock.patch.object(self.core.os, "statvfs", return_value=types.SimpleNamespace(f_bavail=free, f_frsize=1)):
            with self.assertRaisesRegex(ValueError, "space"):
                self.core.check_install_space(package, target, "home")

    def test_service_and_web_resolution_use_home_metadata(self):
        current = self.install("home")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), mock.patch.object(sys, "argv", [str(CORE), "frontend-status"]):
            self.core.main()
        self.assertEqual(json.loads(output.getvalue())["frontend"]["document_root"], str(current / "payload"))
        self.service.reset_mock()
        for action in ("start", "status", "stop"):
            with contextlib.redirect_stdout(output), mock.patch.object(
                    sys, "argv", [str(CORE), "service-" + action, "dummy"]):
                self.assertEqual(self.core.main(), 0)
        self.assertEqual([call.args[1] for call in self.service.call_args_list],
                         ["start", "status", "stop"])
        self.actions.stop()
        with mock.patch.object(self.core.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)) as execute:
            self.assertEqual(self.core.service_action("dummy", "status"), 0)
        self.actions.start()
        self.assertEqual(execute.call_args.kwargs["cwd"], current)
        self.assertEqual(execute.call_args.kwargs["env"]["FRE3NDER_APP_RUNTIME_DIR"], str(current))

    def test_capacity_failure_does_not_stop_or_replace_installed_runtime(self):
        for role in ("sys", "home"):
            name = "app-" + role
            current = self.install(role, name)
            package = self.package(2, name)
            self.service.reset_mock()
            with mock.patch.object(self.core.os, "statvfs", return_value=types.SimpleNamespace(f_bavail=1, f_frsize=4096)):
                with self.assertRaisesRegex(ValueError, "space"):
                    self.core.activate_package(package, "update")
            self.service.assert_not_called()
            self.assertEqual(self.core.read_metadata(name)["release_serial"], 1)
            self.assertEqual((current / "payload/index.html").read_bytes(), b"release 1")

    def test_sys_extraction_and_home_cache_need_space_on_their_own_filesystems(self):
        package = self.package()
        target = self.core.prepare_runtime_root("sys")
        original_stat = pathlib.Path.stat

        def separate_devices(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            if path == target:
                values = list(result)
                values[2] += 1
                return os.stat_result(values)
            return result

        reserve = 32 * 1024 * 1024
        for lacking in ("sys", "home"):
            def available(path):
                low = path == (target if lacking == "sys" else self.core.PACKAGE_STATE_ROOT)
                return types.SimpleNamespace(f_frsize=4096, f_bavail=reserve // 4096 if low else 1024 * 1024)
            with (mock.patch.object(pathlib.Path, "stat", separate_devices),
                  mock.patch.object(self.core.os, "statvfs", side_effect=available)):
                with self.assertRaisesRegex(ValueError, lacking.upper()):
                    self.core.check_install_space(package, target, "sys")

    def test_symlink_runtime_root_cannot_redirect_installation(self):
        outside = self.root / "outside"
        outside.mkdir()
        self.core.HOME_RUNTIME_ROOT.parent.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "unsafe"):
            self.core.activate_package(self.package(), "install", storage="home")
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
