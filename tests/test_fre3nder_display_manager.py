#!/usr/bin/env python3

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE = ROOT / "configs/x2000/rootfs-overlay/usr/libexec/fre3nder-package-core"


def load_core_module():
    loader = importlib.machinery.SourceFileLoader(
        "fre3nder_package_core_display_test",
        str(CORE),
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class Fre3nderDisplayManagerCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.core = load_core_module()

        self.core.PACKAGE_STATE_ROOT = self.root / "manager"
        self.core.PACKAGE_STATE_ROOT.mkdir(mode=0o700)
        self.core.STATE_ROOT = self.core.PACKAGE_STATE_ROOT / "packages"
        self.core.DISPLAY_ROOT = self.core.PACKAGE_STATE_ROOT / "display"
        self.core.ACTIVE_DISPLAY = self.core.DISPLAY_ROOT / "active"
        self.core.RUNTIME_ROOT = self.root / "runtime"
        self.core.RECOVERY_ROOT = self.root / "recovery"
        self.core.DATA_ROOT = self.root / "data"

        self.display_calls = self.root / "display-calls"
        self.core.DISPLAY_SERVICE = self.root / "display-service"
        self.core.DISPLAY_SERVICE.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$1\" >> '{self.display_calls}'\n"
            "exit 0\n"
        )
        self.core.DISPLAY_SERVICE.chmod(0o755)

    def metadata(self, name="screen", serial=1, display=True):
        return {
            "name": name,
            "version": f"1.0.{serial}",
            "release_serial": serial,
            "publisher": "fre3nder-official",
            "fingerprint": "a" * 64,
            "autostart": False,
            "web_frontend": False,
            "display_frontend": display,
            "display_api": 1 if display else None,
        }

    def install_state(self, name="screen"):
        state = self.core.state_dir(name)
        state.mkdir(parents=True)
        (state / "installed").touch()
        (state / "metadata.json").write_text(
            json.dumps(self.metadata(name=name), sort_keys=True) + "\n"
        )
        runtime = self.core.runtime_dir(name)
        runtime.mkdir(parents=True)
        service = runtime / "service"
        service.write_text("#!/bin/sh\nexit 0\n")
        service.chmod(0o755)
        self.core.select_display(name)

    def test_display_service_action_supplies_api_and_functional_groups(self):
        self.install_state()
        environment = {
            "FRE3NDER_DISPLAY_API": "1",
            "FRE3NDER_DISPLAY_FRAMEBUFFER": "/dev/fb0",
            "FRE3NDER_DISPLAY_INPUT": "/run/fre3nder-display/input",
            "FRE3NDER_DISPLAY_BACKLIGHT_POWER": "",
            "FRE3NDER_DISPLAY_BEEPER": "",
        }

        gids = {"video": 28, "input": 1001, "beep": 1002}
        with (
            mock.patch.dict(os.environ, environment, clear=False),
            mock.patch.object(
                self.core.grp,
                "getgrnam",
                side_effect=lambda name: types.SimpleNamespace(gr_gid=gids[name]),
            ),
            mock.patch.object(self.core, "service_action", return_value=0) as action,
        ):
            self.assertEqual(self.core.display_service_action("start"), 0)

        action.assert_called_once_with(
            "screen",
            "start",
            extra_env=environment,
            supplementary_groups=(28, 1001, 1002),
        )

    def test_service_action_defaults_to_no_supplementary_groups(self):
        runtime = self.core.RUNTIME_ROOT / "plain"
        runtime.mkdir(parents=True)
        service = runtime / "service"
        service.write_text("#!/bin/sh\nexit 0\n")
        service.chmod(0o755)

        result = types.SimpleNamespace(returncode=0)
        with (
            mock.patch.object(self.core, "app_user", return_value=(1000, 1000)),
            mock.patch.object(self.core.os, "chown"),
            mock.patch.object(self.core.subprocess, "run", return_value=result) as run,
        ):
            self.assertEqual(self.core.service_action("plain", "status", runtime), 0)

        preexec = run.call_args.kwargs["preexec_fn"]
        with (
            mock.patch.object(self.core.os, "setgroups") as setgroups,
            mock.patch.object(self.core.os, "setgid") as setgid,
            mock.patch.object(self.core.os, "setuid") as setuid,
        ):
            preexec()

        setgroups.assert_called_once_with([])
        setgid.assert_called_once_with(1000)
        setuid.assert_called_once_with(1000)

    def test_selected_display_update_and_remove_use_display_manager(self):
        package = self.root / "screen.fre3app"
        package.write_bytes(b"fixture")

        def extract(_package, _verified, target):
            target.mkdir(parents=True)
            service = target / "service"
            service.write_text("#!/bin/sh\nexit 0\n")
            service.chmod(0o755)

        with (
            mock.patch.object(
                self.core,
                "verify_package",
                return_value=self.metadata(serial=1),
            ),
            mock.patch.object(self.core, "extract_runtime", side_effect=extract),
            mock.patch.object(self.core, "service_action", return_value=0),
        ):
            self.core.activate_package(package, "install")

        self.core.select_display("screen")
        self.display_calls.unlink(missing_ok=True)

        with (
            mock.patch.object(
                self.core,
                "verify_package",
                return_value=self.metadata(serial=2),
            ),
            mock.patch.object(self.core, "extract_runtime", side_effect=extract),
            mock.patch.object(self.core, "service_action", return_value=0),
        ):
            self.core.activate_package(package, "update")

        self.assertEqual(
            self.display_calls.read_text().splitlines(),
            ["stop", "start"],
        )

        self.display_calls.unlink()
        with mock.patch.object(self.core, "service_action", return_value=0):
            self.core.remove_package("screen")

        self.assertEqual(self.display_calls.read_text().splitlines(), ["stop"])
        self.assertFalse(self.core.ACTIVE_DISPLAY.exists())

    def test_fresh_install_ignores_stale_display_selection(self):
        self.core.DISPLAY_ROOT.mkdir(mode=0o700)
        self.core.ACTIVE_DISPLAY.write_text("screen\n")
        self.core.ACTIVE_DISPLAY.chmod(0o644)
        package = self.root / "screen.fre3app"
        package.write_bytes(b"fixture")

        def extract(_package, _verified, target):
            target.mkdir(parents=True)
            (target / "service").write_text("#!/bin/sh\nexit 0\n")

        with (
            mock.patch.object(self.core, "verify_package", return_value=self.metadata()),
            mock.patch.object(self.core, "extract_runtime", side_effect=extract),
            mock.patch.object(self.core, "service_action", return_value=0),
            mock.patch.object(self.core, "run_display_manager") as display_manager,
        ):
            self.core.activate_package(package, "install")

        self.assertTrue(self.core.installed("screen"))
        self.assertEqual(self.core.active_display(), "screen")
        display_manager.assert_not_called()

    def test_disable_keeps_selection_when_display_stop_fails(self):
        self.install_state()
        self.core.DISPLAY_SERVICE.write_text(
            "#!/bin/sh\n"
            "[ \"$1\" != stop ] || exit 23\n"
            "exit 0\n"
        )
        self.core.DISPLAY_SERVICE.chmod(0o755)

        with mock.patch.object(
            sys,
            "argv",
            [str(CORE), "display-disable"],
        ):
            with self.assertRaisesRegex(ValueError, "display manager stop failed"):
                self.core.main()

        self.assertEqual(self.core.active_display(), "screen")

    def test_generic_runtime_skips_display_frontends(self):
        self.install_state()
        marker = self.core.state_dir("screen") / "autostart"
        marker.touch()

        with mock.patch.object(self.core, "service_action") as action:
            self.assertEqual(self.core.start_installed(), 0)
            self.assertEqual(self.core.stop_installed(), 0)

        action.assert_not_called()


if __name__ == "__main__":
    unittest.main()
