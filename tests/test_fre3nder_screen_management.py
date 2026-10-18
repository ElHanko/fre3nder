#!/usr/bin/env python3
"""Focused host-side tests: Fre3nderScreen Management UNIX credential boundary."""
import importlib.machinery
import importlib.util
import os
import pathlib
import tempfile
import types
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIBEXEC = ROOT / "configs/x2000/rootfs-overlay/usr/libexec/fre3nder"


def load(path, name):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class ManagementScreenCredentialTests(unittest.TestCase):
    def test_exact_primary_group_and_user_are_required(self):
        daemon = load(LIBEXEC / "managementd", "fre3nder_management_screen_test")
        peer = types.SimpleNamespace(peer_credentials=lambda: (123, 1000, 1003))
        with mock.patch.object(daemon.pwd, "getpwnam", return_value=types.SimpleNamespace(pw_uid=1000)), \
                mock.patch.object(daemon.grp, "getgrnam", return_value=types.SimpleNamespace(gr_gid=1003)):
            self.assertTrue(daemon.Handler.is_screen_peer(peer))
            peer.peer_credentials = lambda: (123, 1000, 1000)
            self.assertFalse(daemon.Handler.is_screen_peer(peer))
            peer.peer_credentials = lambda: (123, 1001, 1003)
            self.assertFalse(daemon.Handler.is_screen_peer(peer))

    def test_browser_checks_still_apply_to_unprivileged_client(self):
        daemon = load(LIBEXEC / "managementd", "fre3nder_management_browser_test")
        calls = []
        peer = types.SimpleNamespace(is_screen_peer=lambda: False,
                                     require_web_admin=lambda: calls.append("web"))
        daemon.Handler.require_screen_or_web_admin(peer)
        self.assertEqual(calls, ["web"])
        peer.is_screen_peer = lambda: True
        daemon.Handler.require_screen_or_web_admin(peer)
        self.assertEqual(calls, ["web"])


class ProtectedScreenPackageTests(unittest.TestCase):
    def setUp(self):
        self.core = load(LIBEXEC / "package-core", "fre3nder_screen_package_test")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.keydir = self.root / "keys"
        self.keydir.mkdir()
        (self.keydir / "fre3nder-official.pem").write_text("fixture\n")
        (self.keydir / "fre3nder-official.pem").chmod(0o644)
        self.core.BUILTIN_KEYS = self.keydir
        self.metadata = {
            "name": "fre3nderscreen", "publisher": "fre3nder-official",
            "display_frontend": True, "display_api": 1,
            "fingerprint": "a" * 64,
        }

    def test_official_key_and_display_capability_required(self):
        with mock.patch.object(self.core, "fingerprint", return_value="a" * 64):
            self.assertTrue(self.core.official_screen(self.metadata))
            for field, value in (("name", "arbitrary"), ("publisher", "untrusted"),
                                 ("display_frontend", False), ("display_api", None),
                                 ("fingerprint", "b" * 64)):
                with self.subTest(field=field):
                    self.assertFalse(self.core.official_screen({**self.metadata, field: value}))

    def test_writable_or_linked_runtime_does_not_receive_privileges(self):
        runtime = self.root / "runtime"
        runtime.mkdir(mode=0o755)
        runtime.chmod(0o755)
        script = runtime / "service"
        script.write_text("#!/bin/sh\n")
        script.chmod(0o755)
        self.assertTrue(self.core.protected_screen_runtime(runtime))
        script.chmod(0o775)
        self.assertFalse(self.core.protected_screen_runtime(runtime))
        script.chmod(0o755)
        (runtime / "alias").symlink_to(script)
        self.assertFalse(self.core.protected_screen_runtime(runtime))

    def test_privileged_screen_preserves_base_display_group(self):
        runtime = self.root / "runtime-service"
        runtime.mkdir()
        (runtime / "service").write_text("#!/bin/sh\n")
        (runtime / "service").chmod(0o755)
        base_gid, management_gid = 1000, 31000
        recorded = {}

        def fake_run(*args, **kwargs):
            kwargs["preexec_fn"]()
            return types.SimpleNamespace(returncode=0)

        with (mock.patch.object(self.core, "app_user", return_value=(1000, base_gid)),
              mock.patch.object(self.core, "installed", return_value=True),
              mock.patch.object(self.core, "active_display", return_value="fre3nderscreen"),
              mock.patch.object(self.core, "read_metadata", return_value=self.metadata),
              mock.patch.object(self.core, "official_screen", return_value=True),
              mock.patch.object(self.core, "protected_screen_runtime", return_value=True),
              mock.patch.object(self.core.grp, "getgrnam", return_value=types.SimpleNamespace(gr_gid=management_gid)),
              mock.patch.object(self.core, "DATA_ROOT", self.root / "data"),
              mock.patch.object(self.core.os, "chown"),
              mock.patch.object(self.core.os, "setgroups", side_effect=lambda gs: recorded.update(groups=gs)),
              mock.patch.object(self.core.os, "setgid", side_effect=lambda g: recorded.update(gid=g)),
              mock.patch.object(self.core.os, "setuid", side_effect=lambda u: recorded.update(uid=u)),
              mock.patch.object(self.core.subprocess, "run", side_effect=fake_run)):
            result = self.core.service_action(
                "fre3nderscreen", "start", runtime, supplementary_groups=(44, 45, 46)
            )
        self.assertEqual(result, 0)
        self.assertEqual(recorded["uid"], 1000)
        self.assertEqual(recorded["gid"], management_gid)
        self.assertEqual(set(recorded["groups"]), {base_gid, 44, 45, 46})


if __name__ == "__main__":
    unittest.main()
