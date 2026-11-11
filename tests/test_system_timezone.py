"""Non-building timezone/init fixtures; never change host time or /etc files."""

import datetime
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "configs/x2000/rootfs-overlay/usr/libexec/fre3nder/system_timezone.py"
INIT = ROOT / "configs/x2000/rootfs-overlay/etc/init.d/S45fre3nder-time"


def fixture(module, root):
    module.HOME = root / "home"
    module.ZONEINFO = root / "usr/share/zoneinfo"
    module.LOCALTIME = root / "etc/localtime"
    module.TIMEZONE = root / "etc/timezone"
    module.HOME.mkdir(mode=0o755, exist_ok=True)
    module.LOCALTIME.parent.mkdir(parents=True, exist_ok=True)
    # Match Buildroot: top-level regions point into posix/.
    for name in ("Etc/UTC", "Europe/Berlin", "America/Indiana/Indianapolis"):
        source = Path("/usr/share/zoneinfo") / name
        if not source.is_file():
            raise unittest.SkipTest("Host IANA fixture data unavailable: " + name)
        target = module.ZONEINFO / "posix" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        region = module.ZONEINFO / name.split("/")[0]
        if not region.is_symlink():
            region.symlink_to("posix/" + region.name)
    return module.available()


class TimezoneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        spec = importlib.util.spec_from_file_location("timezone_fixture", SOURCE)
        self.tz = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tz)
        self.zones = fixture(self.tz, self.root)
        self.runtime = self.root / "run/time"
        self.runtime.mkdir(parents=True, mode=0o700)

    def config(self, data):
        path = self.tz.HOME / ".fre3nder/system/timezone"
        (self.tz.HOME / ".fre3nder").mkdir(mode=0o700, exist_ok=True)
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o600)
        return path

    def test_catalog_contains_only_installed_data_and_multilevel_names(self):
        self.assertEqual(self.zones, ["America/Indiana/Indianapolis", "Etc/UTC", "Europe/Berlin"])
        (self.tz.ZONEINFO / "Europe/Fake").write_text("not TZif")
        (self.tz.ZONEINFO / "Europe/Escape").symlink_to("/usr/share/zoneinfo/Europe/London")
        (self.tz.ZONEINFO / "Europe/Loop").symlink_to(".")
        self.assertEqual(self.tz.available(), self.zones)

    def test_missing_configuration_activates_utc_offline(self):
        self.tz.activate(self.runtime)
        self.assertEqual(self.tz.active(self.zones), "Etc/UTC")
        self.assertFalse(self.tz.status()["reboot_required"])

    def test_saved_configuration_pending_until_next_boot(self):
        self.tz.activate(self.runtime)
        self.tz.save("America/Indiana/Indianapolis", self.zones)
        self.assertEqual(self.tz.status(), {"active": "Etc/UTC", "configured": "America/Indiana/Indianapolis", "reboot_required": True})
        self.tz.activate(self.runtime)
        self.assertEqual(self.tz.active(self.zones), "Etc/UTC")
        (self.runtime / "timezone").unlink()  # Only the fixture simulates a new boot.
        self.tz.activate(self.runtime)
        self.assertEqual(self.tz.active(self.zones), "America/Indiana/Indianapolis")
        self.assertFalse(self.tz.status()["reboot_required"])
        self.assertEqual(self.tz.TIMEZONE.read_text(), "America/Indiana/Indianapolis\n")

    def test_corrupt_configuration_falls_back_without_aborting_boot(self):
        for data in (b"", b"Europe/Unknown\n", b"Europe/Berlin", b"Europe/Berlin\n\n",
                     b"../Europe/Berlin\n", b"Europe/Berlin\x00\n", b"\xff\n", b"x" * 1000):
            with self.subTest(data=data[:30]):
                self.config(data)
                (self.runtime / "timezone").unlink(missing_ok=True)
                self.tz.activate(self.runtime)
                self.assertEqual(self.tz.active(self.zones), "Etc/UTC")

    def test_unknown_paths_and_tz_strings_rejected(self):
        for name in ("Europe/Missing", "../Europe/Berlin", "/etc/passwd", "Europe/../Etc/UTC",
                     "posix/Europe/Berlin", "UTC0", "Europe/Berlin\n", "Europe//Berlin", {}, None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.tz.save(name, self.zones)

    def test_symlink_components_are_rejected_and_boot_uses_utc(self):
        self.config(b"Europe/Berlin\n")
        for name in (".fre3nder/system/timezone", ".fre3nder/system", ".fre3nder", "."):
            path = self.tz.HOME / name
            if name == ".":
                path = self.tz.HOME
            moved = path.with_name(path.name + ".original")
            path.rename(moved)
            path.symlink_to(moved)
            try:
                self.assertEqual(self.tz.configured(self.zones), "Etc/UTC")
                (self.runtime / "timezone").unlink(missing_ok=True)
                self.tz.activate(self.runtime)
                self.assertEqual(self.tz.active(self.zones), "Etc/UTC")
                with self.assertRaises((OSError, ValueError)):
                    self.tz.save("Etc/UTC", self.zones)
            finally:
                path.unlink()
                moved.rename(path)
        self.assertEqual((self.tz.HOME / ".fre3nder/system/timezone").read_text(), "Europe/Berlin\n")

    def test_unsafe_file_directory_and_nonregular_config(self):
        path = self.config(b"Europe/Berlin\n")
        for unsafe in (path, path.parent):
            original = unsafe.stat().st_mode & 0o777
            unsafe.chmod(0o777)
            self.assertEqual(self.tz.configured(self.zones), "Etc/UTC")
            with self.assertRaises(ValueError):
                self.tz.save("Etc/UTC", self.zones)
            unsafe.chmod(original)
        path.unlink()
        os.mkfifo(path)
        self.assertEqual(self.tz.configured(self.zones), "Etc/UTC")
        with self.assertRaises(ValueError):
            self.tz.save("Etc/UTC", self.zones)

    def test_atomic_save_preserves_old_value_on_replace_failure(self):
        path = self.config(b"Europe/Berlin\n")
        with patch.object(self.tz.os, "replace", side_effect=OSError("fixture failure")):
            with self.assertRaises(OSError):
                self.tz.save("Etc/UTC", self.zones)
        self.assertEqual(path.read_text(), "Europe/Berlin\n")
        self.assertEqual(list(path.parent.iterdir()), [path])
        self.tz.save("Etc/UTC", self.zones)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_installed_iana_rules_handle_summer_winter_and_transition(self):
        with (self.tz.ZONEINFO / "Europe/Berlin").open("rb") as data:
            berlin = ZoneInfo.from_file(data)
        for stamp, offset in (("2024-01-15T12:00:00+00:00", 1), ("2024-07-15T12:00:00+00:00", 2),
                              ("2024-03-31T00:59:00+00:00", 1), ("2024-03-31T01:00:00+00:00", 2),
                              ("2024-10-27T00:59:00+00:00", 2), ("2024-10-27T01:00:00+00:00", 1)):
            result = datetime.datetime.fromisoformat(stamp).astimezone(berlin)
            self.assertEqual(result.utcoffset(), datetime.timedelta(hours=offset))

    def test_init_preserves_ntp_lease_wait_idempotence_and_stop(self):
        helper = self.root / "timezone-helper.py"
        helper.write_text(f"import importlib.util\nfrom pathlib import Path\nimport sys\n"
                          f"s = importlib.util.spec_from_file_location('tz', {str(SOURCE)!r})\n"
                          "m = importlib.util.module_from_spec(s)\ns.loader.exec_module(m)\n"
                          + "\n".join(f"m.{key} = Path({str(getattr(self.tz, key))!r})" for key in ("HOME", "ZONEINFO", "LOCALTIME", "TIMEZONE"))
                          + "\nm.activate(Path(sys.argv[1]))\n")
        ntpd = self.root / "ntpd-fixture"
        calls = self.root / "ntp-calls"
        ntpd.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> '{calls}'\nexec sleep 60\n")
        ntpd.chmod(0o755)
        proc = self.root / "proc"
        state = self.root / "run/fre3nder"
        env = {**os.environ, "FRE3NDER_STATE": str(state), "FRE3NDER_NTPD": str(ntpd),
               "FRE3NDER_TIMEZONE_HELPER": str(helper), "FRE3NDER_PROC_ROOT": str(proc)}
        def run(action):
            subprocess.run(["sh", str(INIT), action], env=env, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True, timeout=5)
        def stop_process():
            pidfile = state / "time/ntpd.pid"
            if pidfile.exists():
                pid = int(pidfile.read_text())
                try:
                    os.kill(pid, 15)
                except ProcessLookupError:
                    pass
        self.addCleanup(stop_process)
        run("start")
        self.assertEqual(self.tz.active(self.zones), "Etc/UTC")
        self.assertFalse(calls.exists())
        pidfile = state / "time/ntpd.pid"
        pid = pidfile.read_text().strip()
        command = proc / pid / "cmdline"
        command.parent.mkdir(parents=True)
        command.write_bytes(b"ntpd\0")
        run("start")
        self.assertEqual(pidfile.read_text().strip(), pid)
        lease = state / "network/lease"
        lease.parent.mkdir()
        lease.write_text("fixture\n")
        for _ in range(150):
            if calls.exists():
                break
            time.sleep(0.02)
        self.assertEqual(calls.read_text(), "-n -p pool.ntp.org\n")
        self.tz.save("Europe/Berlin", self.zones)
        run("stop")
        self.assertEqual(self.tz.active(self.zones), "Etc/UTC")
        self.assertFalse(pidfile.exists())
        self.assertEqual((state / "time/timezone").read_text(), "Etc/UTC\n")


if __name__ == "__main__":
    unittest.main()
