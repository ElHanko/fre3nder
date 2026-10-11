#!/usr/bin/env python3

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import stat
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE = ROOT / "configs/x2000/rootfs-overlay/usr/libexec/fre3nder/package-core"


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
            "FRE3NDER_DISPLAY_VT": "/dev/tty7",
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


class LocalConsoleTests(unittest.TestCase):
    def setUp(self):
        loader = importlib.machinery.SourceFileLoader("local_console_test", str(CORE.with_name("console")))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.console = importlib.util.module_from_spec(spec)
        loader.exec_module(self.console)

    def authorization(self, *, enabled=True, mode=0o600, uid=0, gid=0, kind=stat.S_IFREG,
                      status="active", links=1, parent_mode=0o755, parent_uid=0,
                      parent_gid=0, etc_gid=0, parent_kind=stat.S_IFDIR,
                      status_uid=0, status_gid=0, status_mode=0o644,
                      status_kind=stat.S_IFREG):
        console = self.console
        def info(path):
            if path == console.ROOT_STATUS:
                return types.SimpleNamespace(
                    st_uid=status_uid, st_gid=status_gid,
                    st_mode=status_kind | status_mode, st_nlink=1,
                )
            is_parent = path in (pathlib.Path('/etc'), console.ENABLE.parent)
            return types.SimpleNamespace(
                st_uid=parent_uid if is_parent else uid,
                st_gid=etc_gid if path == pathlib.Path('/etc') else (parent_gid if is_parent else gid),
                st_mode=(parent_kind | parent_mode) if is_parent else (kind | mode),
                st_nlink=links,
            )
        def lstat(path):
            if path == console.ENABLE and not enabled:
                raise FileNotFoundError(path)
            return info(path)
        with (mock.patch.object(pathlib.Path, "lstat", lstat),
              mock.patch.object(pathlib.Path, "read_text", return_value=status)):
            return console.shell_enabled()

    def test_local_root_shell_requires_explicit_rootfs_authorization(self):
        self.assertTrue(self.authorization())
        for invalid in ({"enabled": False}, {"mode": 0o644}, {"mode": 0o666},
                        {"uid": 1000}, {"kind": stat.S_IFLNK}, {"kind": stat.S_IFDIR},
                        {"kind": stat.S_IFIFO}, {"links": 2}, {"status": "degraded"},
                        {"status": ""}, {"parent_mode": 0o777}, {"parent_uid": 1000},
                        {"parent_mode": 0o775}, {"parent_mode": 0o757},
                        {"parent_kind": stat.S_IFLNK}, {"parent_kind": stat.S_IFREG}):
            with self.subTest(invalid=invalid):
                self.assertFalse(self.authorization(**invalid))

    def test_console_opt_in_and_parents_require_root_group(self):
        self.assertTrue(self.authorization(gid=0, etc_gid=0, parent_gid=0))
        for invalid in ({"etc_gid": 1000}, {"parent_gid": 1000}, {"gid": 1000}):
            with self.subTest(invalid=invalid):
                self.assertFalse(self.authorization(**invalid))

    def test_root_status_keeps_uid_only_ownership_contract(self):
        for mode in (0o644, 0o640):
            with self.subTest(mode=mode):
                self.assertTrue(self.authorization(status_gid=1000, status_mode=mode))
        for invalid in ({"status_uid": 1000}, {"status_mode": 0o664},
                        {"status_mode": 0o646}, {"status_kind": stat.S_IFLNK},
                        {"status_kind": stat.S_IFDIR}):
            with self.subTest(invalid=invalid):
                self.assertFalse(self.authorization(**invalid))

    def test_disabled_console_never_executes_a_shell(self):
        with (mock.patch.object(sys, "argv", ["console", "shell"]),
              mock.patch.object(self.console.os, "geteuid", return_value=0),
              mock.patch.object(self.console, "shell_enabled", return_value=False),
              mock.patch.object(self.console.os, "execv") as execute,
              contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(self.console.main(), 1)
        execute.assert_not_called()

    def test_console_init_follows_pivot_and_does_not_gate_printer_services(self):
        inittab = (ROOT / "configs/x2000/rootfs-overlay/etc/inittab").read_text()
        self.assertLess(inittab.index("fre3nder-root start"), inittab.index("console services"))
        self.assertNotIn("console boot", inittab)
        self.assertIn("tty1::askfirst:/usr/libexec/fre3nder/console shell", inittab)
        self.assertFalse((ROOT / "configs/x2000/rootfs-overlay/etc/fre3nder/console.enabled").exists())

    def test_prepare_only_changes_tty7_and_is_repeatable(self):
        with (mock.patch.object(sys, 'argv', ['console', 'prepare']),
              mock.patch.object(self.console.os, 'geteuid', return_value=0),
              mock.patch.object(self.console.pwd, 'getpwnam', return_value=types.SimpleNamespace(pw_uid=1000, pw_gid=1000)),
              mock.patch.object(self.console, 'open_vt', return_value=123) as open_vt,
              mock.patch.object(self.console, 'text_console') as text,
              mock.patch.object(self.console.fcntl, 'ioctl') as ioctl,
              mock.patch.object(self.console.os, 'fchown') as owner,
              mock.patch.object(self.console.os, 'fchmod'),
              mock.patch.object(self.console.os, 'close'),
              mock.patch.object(self.console.os, 'write') as write):
            for _ in range(2):
                self.assertEqual(self.console.main(), 0)
            self.assertEqual(open_vt.call_args_list, [mock.call(self.console.TTY7)] * 2)
            self.assertEqual(owner.call_args_list, [mock.call(123, 1000, 1000)] * 2)
            self.assertEqual([call.args[1] for call in ioctl.call_args_list],
                             [self.console.VT_SETMODE, self.console.KDSETMODE] * 2)
            text.assert_not_called()
            write.assert_not_called()

    def test_background_binds_before_rotation_without_output_or_vt_switch(self):
        events = []
        with (mock.patch.object(self.console, 'check_display', side_effect=lambda: events.append('check')),
              mock.patch.object(self.console.os, 'open', return_value=123),
              mock.patch.object(self.console.os, 'fstat', return_value=types.SimpleNamespace(
                  st_mode=stat.S_IFCHR, st_rdev=os.makedev(29, 0))),
              mock.patch.object(self.console.fcntl, 'ioctl', side_effect=lambda fd, op, arg: events.append((op, arg))),
              mock.patch.object(pathlib.Path, 'write_text', side_effect=lambda value: events.append(value)),
              mock.patch.object(self.console.os, 'close'),
              mock.patch.object(self.console, 'open_vt') as open_vt,
              mock.patch.object(self.console.os, 'write') as write):
            for _ in range(2):
                self.console.background_console()
        self.assertEqual(events, ['check', (self.console.FBIOPUT_CON2FBMAP,
                                           self.console.struct.pack('@II', 1, 0)), '3\n'] * 2)
        open_vt.assert_not_called()
        write.assert_not_called()

    def test_background_rejects_missing_graphics_ownership_before_framebuffer_access(self):
        with (mock.patch.object(self.console, 'check_display', side_effect=ValueError('not ready')),
              mock.patch.object(self.console.os, 'open') as open_fb):
            with self.assertRaisesRegex(ValueError, 'not ready'):
                self.console.background_console()
        open_fb.assert_not_called()

    def test_services_preserve_serial_and_logs_then_prepare_diagnostics(self):
        for state in ('active', 'startup-failed', 'stop-failed', None):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                console = self.console
                console.BOOT_LOG = pathlib.Path(directory) / 'boot.log'
                console.DISPLAY_STATUS = pathlib.Path(directory) / 'status'
                if state:
                    console.DISPLAY_STATUS.write_text(state)
                serial = types.SimpleNamespace(buffer=io.BytesIO())
                events = []
                def run(command, *, stdout, stderr, check):
                    self.assertEqual(command, ['/etc/init.d/rcS'])
                    self.assertIs(stdout, stderr)
                    self.assertEqual(events, [])  # No early console access.
                    stdout.write(b'network ready\nprinter ready\n')
                    return types.SimpleNamespace(returncode=0)
                with (mock.patch.object(sys, 'argv', ['console', 'services']),
                      mock.patch.object(sys, 'stdout', serial),
                      mock.patch.object(console.os, 'geteuid', return_value=0),
                      mock.patch.object(console.subprocess, 'run', side_effect=run),
                      mock.patch.object(console, 'background_console', side_effect=lambda: events.append('background')),
                      mock.patch.object(console, 'text_console', side_effect=lambda: events.append('text')),
                      mock.patch.object(console, 'diagnostics', side_effect=lambda: events.append('logs')),
                      mock.patch.object(console, 'open_vt', return_value=123),
                      mock.patch.object(console.fcntl, 'ioctl', side_effect=lambda *args: events.append('activate')),
                      mock.patch.object(console.os, 'close'),
                      contextlib.redirect_stderr(io.StringIO()) as errors):
                    self.assertEqual(console.main(), 0)
                self.assertEqual(serial.buffer.getvalue(), console.BOOT_LOG.read_bytes())
                if state == 'stop-failed':
                    self.assertEqual(events, [])
                    self.assertIn('retaining VT ownership', errors.getvalue())
                else:
                    self.assertEqual(events, ['background', 'logs'] if state == 'active'
                                     else ['text', 'activate', 'logs'])

    def test_console_failure_after_services_does_not_change_rcs_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            self.console.BOOT_LOG = pathlib.Path(directory) / 'boot.log'
            self.console.DISPLAY_STATUS = pathlib.Path(directory) / 'missing'
            with (mock.patch.object(sys, 'argv', ['console', 'services']),
                  mock.patch.object(sys, 'stdout', types.SimpleNamespace(buffer=io.BytesIO())),
                  mock.patch.object(self.console.os, 'geteuid', return_value=0),
                  mock.patch.object(self.console.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0)),
                  mock.patch.object(self.console, 'text_console', side_effect=OSError('missing tty1')),
                  contextlib.redirect_stderr(io.StringIO()) as errors):
                self.assertEqual(self.console.main(), 0)
            self.assertIn('missing tty1', errors.getvalue())

    def test_diagnostics_replay_kernel_and_boot_log_with_failure_state(self):
        with tempfile.TemporaryDirectory() as directory:
            console = self.console
            console.BOOT_LOG = pathlib.Path(directory) / 'boot.log'
            console.BOOT_LOG.write_bytes(b'frontend startup timed out\n')
            console.DISPLAY_STATUS = pathlib.Path(directory) / 'status'
            console.DISPLAY_STATUS.write_text('startup-failed\n')
            display = pathlib.Path(directory) / 'tty1'
            def dmesg(command, *, stdout, stderr, check):
                self.assertEqual(command, ['dmesg'])
                stdout.write(b'kernel ring buffer\n')
            with (mock.patch.object(console, 'open_vt', side_effect=lambda path: os.open(display, os.O_CREAT | os.O_WRONLY, 0o600)),
                  mock.patch.object(console.subprocess, 'run', side_effect=dmesg)):
                console.diagnostics()
            self.assertEqual(display.read_bytes(), b'kernel ring buffer\nfrontend startup timed out\n'
                             b'\r\nFre3nder display: startup-failed\r\n')

    def test_rotation_waits_for_deferred_takeover_and_missing_fbcon_fails(self):
        console = self.console
        entry = pathlib.Path('/sys/class/vtconsole/vtcon1')
        for bindings, success in ((['0', '1'], True), (['0'] * 20, False)):
            reads = iter(bindings)
            def read(path):
                return '(M) frame buffer device' if path.name == 'name' else next(reads)
            with (mock.patch.object(console, 'open_vt', return_value=123),
                  mock.patch.object(console.fcntl, 'ioctl'),
                  mock.patch.object(console.os, 'write'),
                  mock.patch.object(console.os, 'close'),
                  mock.patch.object(pathlib.Path, 'glob', return_value=[entry]),
                  mock.patch.object(pathlib.Path, 'read_text', read),
                  mock.patch.object(pathlib.Path, 'write_text') as rotate,
                  mock.patch.object(console.time, 'sleep') as sleep):
                if success:
                    console.text_console()
                    rotate.assert_called_once_with('3\n')
                    sleep.assert_called_once_with(0.05)
                else:
                    with self.assertRaisesRegex(ValueError, 'not bound'):
                        console.text_console()
                    rotate.assert_not_called()

    def test_release_restores_text_and_does_not_switch_away_from_another_vt(self):
        for current in (1, 7):
            calls = []
            def ioctl(_fd, operation, arg, *extra):
                calls.append((operation, arg))
                if operation == self.console.VT_GETSTATE:
                    arg[:] = self.console.struct.pack('@HHH', current, 0, 0)
            with (mock.patch.object(sys, "argv", ["console", "release"]),
                  mock.patch.object(self.console.os, "geteuid", return_value=0),
                  mock.patch.object(self.console, "open_vt", return_value=123),
                  mock.patch.object(self.console.fcntl, "ioctl", side_effect=ioctl),
                  mock.patch.object(self.console.os, "fchown") as owner,
                  mock.patch.object(self.console.os, "fchmod") as permissions,
                  mock.patch.object(self.console.os, "close")):
                self.assertEqual(self.console.main(), 0)
            self.assertIn((self.console.KDSETMODE, 0), calls)
            self.assertIn((self.console.VT_SETMODE, self.console.struct.pack('@BBhhh', 0, 0, 0, 0, 0)), calls)
            self.assertEqual((self.console.VT_ACTIVATE, 1) in calls, current == 7)
            owner.assert_called_once_with(123, 0, 0)
            permissions.assert_called_once_with(123, 0o600)

    def test_check_requires_both_vt_process_and_graphics_without_mutating_vt(self):
        for vt_mode, graphics in ((0, 0), (1, 0), (0, 1), (1, 1)):
            with self.subTest(vt_mode=vt_mode, graphics=graphics):
                calls = []
                def ioctl(_fd, operation, arg, *extra):
                    calls.append(operation)
                    if operation == self.console.VT_GETMODE:
                        arg[:] = self.console.struct.pack('@BBhhh', vt_mode, 0, 0, 0, 0)
                    elif operation == self.console.KDGETMODE:
                        arg[:] = self.console.struct.pack('@i', graphics)
                with (mock.patch.object(sys, 'argv', ['console', 'check']),
                      mock.patch.object(self.console.os, 'geteuid', return_value=0),
                      mock.patch.object(self.console, 'open_vt', return_value=123) as open_vt,
                      mock.patch.object(self.console.fcntl, 'ioctl', side_effect=ioctl),
                      mock.patch.object(self.console.os, 'close') as close):
                    if (vt_mode, graphics) == (1, 1):
                        self.assertEqual(self.console.main(), 0)
                    else:
                        with self.assertRaisesRegex(ValueError, 'has not acquired tty7'):
                            self.console.main()
                open_vt.assert_called_once_with(self.console.TTY7)
                close.assert_called_once_with(123)
                self.assertEqual(calls, [self.console.VT_GETMODE, self.console.KDGETMODE])


if __name__ == "__main__":
    unittest.main()
