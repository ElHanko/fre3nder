#!/usr/bin/env python3
"""Host-side trust-contract tests for fre3nder-package-core."""

import hashlib
import importlib.machinery
import importlib.util
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE = ROOT / "configs/x2000/rootfs-overlay/usr/libexec/fre3nder-package-core"


def load_core_module():
    loader = importlib.machinery.SourceFileLoader(
        "fre3nder_package_core_test",
        str(CORE),
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


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
                },
            ),
            mock.patch.object(self.core, "extract_runtime", side_effect=extract_runtime),
            mock.patch.object(self.core, "service_action", side_effect=service_action),
            mock.patch.object(self.core, "write_state", state_writer),
        ):
            with self.assertRaisesRegex(ValueError, "start failed"):
                self.core.activate_package(package, "update")

        state_writer.assert_not_called()
        self.assertTrue((current / "old").is_file())


if __name__ == "__main__":
    unittest.main()
