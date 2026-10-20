#!/usr/bin/env python3
"""Regression tests for protected, image-pinned system fre3apps."""
from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "configs/x2000/rootfs-overlay/usr/libexec/fre3nder/package-core"


def core_module():
    loader = importlib.machinery.SourceFileLoader("fre3nder_system_app_core", str(PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class SystemAppPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.core = core_module()
        self.core.SYSTEM_APP_DIR = self.root / "system-apps"
        self.core.SYSTEM_APP_DIR.mkdir(mode=0o755)
        self.core.STATE_ROOT = self.root / "packages"
        self.core.STATE_ROOT.mkdir()
        self.seeds = {
            "moonraker": {"name": "moonraker", "version": "1.1", "release_serial": 2,
                          "publisher": "fre3nder-official", "fingerprint": "a" * 64,
                          "display_frontend": False},
            "other": {"name": "other", "version": "2.0", "release_serial": 3,
                      "publisher": "fre3nder-official", "fingerprint": "a" * 64,
                      "display_frontend": False},
        }
        for name in self.seeds:
            (self.core.SYSTEM_APP_DIR / (name + ".fre3app")).write_bytes(b"fixture")
        self.key = self.root / "official.pem"
        self.key.write_text("fixture")
        self.core.BUILTIN_KEYS = self.root
        official_key = self.root / "fre3nder-official.pem"
        official_key.write_text("fixture")
        official_key.chmod(0o644)

    def test_image_requires_official_identity_and_exact_filenames(self):
        with (mock.patch.object(self.core, "fingerprint", return_value="a" * 64),
              mock.patch.object(self.core, "verify_package", side_effect=lambda path: self.seeds[path.stem])):
            self.assertEqual(len(self.core.image_system_apps()), 2)
            self.seeds["other"]["publisher"] = "other-publisher"
            with self.assertRaisesRegex(ValueError, "invalid image system-app identity"):
                self.core.image_system_apps()

    def test_reconcile_installs_only_missing_and_upgrades_newer(self):
        current = {"moonraker": {"publisher": "fre3nder-official", "fingerprint": "a" * 64,
                                 "release_serial": 1, "version": "1.0", "system_app": True}}
        ops = []
        def activate(path, operation, **kwargs):
            ops.append((path.stem, operation, kwargs))
        with (mock.patch.object(self.core, "image_system_app_seeds", return_value=[
                   self.core.SYSTEM_APP_DIR / (name + ".fre3app")
                   for name in self.seeds]),
              mock.patch.object(self.core, "verify_image_system_app",
                                side_effect=lambda path: self.seeds[path.stem]),
              mock.patch.object(self.core, "installed", side_effect=lambda name: name in current),
              mock.patch.object(self.core, "read_metadata", side_effect=lambda name: current[name]),
              mock.patch.object(self.core, "activate_package", side_effect=activate)):
            self.assertEqual(self.core.reconcile_system_apps(), 0)
        self.assertEqual([(name, op) for name, op, _ in ops],
                         [("moonraker", "update"), ("other", "install")])
        self.assertTrue(all(not kw["start_service"] and kw["system_app"] for _, _, kw in ops))

    def test_reconcile_preserves_newer_and_promotes_system_role(self):
        installed = {"publisher": "fre3nder-official", "fingerprint": "a" * 64,
                     "release_serial": 5, "version": "2.1", "system_app": False}
        with (mock.patch.object(self.core, "image_system_app_seeds", return_value=[
                  self.core.SYSTEM_APP_DIR / "moonraker.fre3app"]),
              mock.patch.object(self.core, "verify_image_system_app",
                                return_value=self.seeds["moonraker"]),
              mock.patch.object(self.core, "installed", return_value=True),
              mock.patch.object(self.core, "read_metadata", return_value=installed),
              mock.patch.object(self.core, "activate_package") as activate,
              mock.patch.object(self.core, "promote_system_app") as promote):
            self.assertEqual(self.core.reconcile_system_apps(), 0)
            activate.assert_not_called()
            promote.assert_called_once_with("moonraker")

    def test_reconcile_continues_after_conflict(self):
        with (mock.patch.object(self.core, "image_system_app_seeds", return_value=[
                  self.core.SYSTEM_APP_DIR / (n + ".fre3app") for n in self.seeds]),
              mock.patch.object(self.core, "verify_image_system_app",
                                side_effect=lambda path: self.seeds[path.stem]),
              mock.patch.object(self.core, "installed", side_effect=lambda name: name == "moonraker"),
              mock.patch.object(self.core, "read_metadata", return_value={
                  "publisher": "untrusted", "fingerprint": "b" * 64, "release_serial": 1}),
              mock.patch.object(self.core, "activate_package") as activate):
            self.assertEqual(self.core.reconcile_system_apps(), 1)
            activate.assert_called_once()
            self.assertEqual(activate.call_args.args[1], "install")

    def test_invalid_seed_does_not_block_other_system_apps(self):
        def verify(path):
            if path.stem == "moonraker":
                raise ValueError("bad signature")
            return self.seeds[path.stem]
        with (mock.patch.object(self.core, "image_system_app_seeds", return_value=[
                  self.core.SYSTEM_APP_DIR / (n + ".fre3app") for n in self.seeds]),
              mock.patch.object(self.core, "verify_image_system_app", side_effect=verify),
              mock.patch.object(self.core, "installed", return_value=False),
              mock.patch.object(self.core, "activate_package") as activate):
            self.assertEqual(self.core.reconcile_system_apps(), 1)
            activate.assert_called_once()
            self.assertEqual(activate.call_args.args[0].stem, "other")

    def test_remove_rejects_protected_installed_app(self):
        with (mock.patch.object(self.core, "installed", return_value=True),
              mock.patch.object(self.core, "read_metadata", return_value={"system_app": True}),
              mock.patch.object(self.core, "image_system_app") as scan):
            with self.assertRaisesRegex(ValueError, "system app cannot be removed"):
                self.core.remove_package("moonraker")
            scan.assert_not_called()


if __name__ == "__main__":
    unittest.main()
