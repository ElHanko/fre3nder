#!/usr/bin/env python3
"""Fixture-only checks for read-only Management system information."""

import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "configs/x2000/rootfs-overlay/usr/libexec/fre3nder/management_system.py"


class SystemInformationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        spec = importlib.util.spec_from_file_location("system_fixture", SOURCE)
        self.info = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.info)
        self.info.ROOT = self.root
        self.info.PROC = self.root / "proc"
        self.info.SYS = self.root / "sys"
        self.version = self.write("usr/share/fre3nder/VERSION", "2026.5.a\n")
        self.root_status = self.write("run/fre3nder-root/status", "active\n")

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
        path.chmod(0o644)
        return path

    def test_platform_runtime_and_linux_memory_semantics(self):
        self.write("sys/firmware/devicetree/base/model", "Fixture board\0")
        self.write("proc/cpuinfo", "system type\t: Fixture SoC\ncpu model\t: Fixture CPU\n")
        self.write("proc/sys/kernel/osrelease", "6.6.fixture\n")
        self.write("proc/sys/kernel/hostname", "printer.test\n")
        self.write("proc/uptime", "90061.50 12345.00\n")
        self.write("proc/loadavg", "0.10 0.20 0.30 1/40 123\n")
        self.write("proc/meminfo", "MemTotal: 262144 kB\nMemFree: 16384 kB\n"
                   "MemAvailable: 196608 kB\nCached: 180224 kB\nSwapTotal: 32768 kB\nSwapFree: 24576 kB\n")
        platform = self.info.platform(self.version)
        self.assertEqual(platform["hardware_model"], "Fixture board")
        self.assertEqual(platform["cpu_model"], "Fixture CPU")
        self.assertEqual(platform["hostname"], "printer.test")
        self.assertEqual(platform["kernel_version"], "6.6.fixture")
        self.assertTrue(platform["architecture"])
        runtime = self.info.runtime()
        self.assertEqual(runtime["uptime_seconds"], 90061.5)
        self.assertEqual(runtime["load_average"], [0.1, 0.2, 0.3])
        self.assertTrue(runtime["system_time"].endswith("+00:00"))
        memory = self.info.memory()
        self.assertEqual(memory["total_bytes"], 256 * 1024 ** 2)
        self.assertEqual(memory["available_bytes"], 192 * 1024 ** 2)
        self.assertEqual(memory["used_bytes"], 64 * 1024 ** 2)
        self.assertEqual(memory["swap_used_bytes"], 8 * 1024 ** 2)

    def test_missing_and_invalid_observations_are_unavailable(self):
        self.assertIsNone(self.info.platform(self.version)["cpu_model"])
        self.assertIsNone(self.info.runtime()["uptime_seconds"])
        self.assertIsNone(self.info.memory()["used_bytes"])
        self.write("proc/meminfo", "MemTotal: 100 kB\nMemFree: 20 kB\nCached: 80 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB\n")
        self.assertIsNone(self.info.memory()["used_bytes"], "MemFree is not a MemAvailable substitute")
        self.assertEqual(self.info.memory()["swap_used_bytes"], 0)
        self.write("proc/meminfo", "MemTotal: 100 kB\nMemAvailable: 200 kB\n")
        self.assertIsNone(self.info.memory()["used_bytes"])
        self.write("proc/uptime", "nan 0\n")
        self.write("proc/loadavg", "bad 0.2\n")
        self.assertIsNone(self.info.runtime()["uptime_seconds"])
        self.assertIsNone(self.info.runtime()["load_average"])
        with patch.object(Path, "read_text", side_effect=PermissionError):
            self.assertIsNone(self.info.text(self.version))

    def test_sys_home_use_exact_observed_mounts_and_available_blocks(self):
        self.write("proc/mounts", "/dev/root /rom squashfs ro 0 0\n"
                   "/dev/fixture-sys /run/fre3nder-root/system ext4 rw 0 0\n"
                   "/dev/fixture-home /home ext4 rw 0 0\n")
        usage = types.SimpleNamespace(f_blocks=100, f_bfree=40, f_bavail=35, f_frsize=4096)
        with patch.object(self.info.os, "statvfs", return_value=usage) as statvfs:
            system, home = self.info.storage()
        self.assertEqual(system["device"], "/dev/fixture-sys")
        self.assertEqual(home["device"], "/dev/fixture-home")
        self.assertEqual(home["filesystem"], "ext4")
        self.assertEqual(home["used_bytes"], 60 * 4096)
        self.assertEqual(home["available_bytes"], 35 * 4096)
        self.assertEqual([call.args[0] for call in statvfs.call_args_list], [
            self.root / "run/fre3nder-root/system", self.root / "home"])
        self.write("proc/mounts", "/dev/root / squashfs ro 0 0\n")
        with patch.object(self.info.os, "statvfs") as statvfs:
            self.assertTrue(all(item["total_bytes"] is None for item in self.info.storage()))
            statvfs.assert_not_called()
        self.write("proc/mounts", "/dev/a /home ext4 rw 0 0\n/dev/b /home ext4 rw 0 0\n")
        self.assertIsNone(self.info.storage()[1]["device"], "ambiguous mount must not be guessed")

    def test_boot_uses_core_slot_mapping_not_selector_history(self):
        self.write("proc/cmdline", "console=ttyS2 root=/dev/mmcblk0p8 ro\n")
        with patch.object(self.info.ota, "discover_active_slot", wraps=self.info.ota.discover_active_slot) as discover:
            self.assertEqual(self.info.boot(self.root_status), {
                "active_slot": "B", "active_rootfs": "/dev/mmcblk0p8", "root_status": "active"})
            discover.assert_called_once()
        for cmdline in ("root=/dev/unknown", "root=/dev/mmcblk0p7 root=/dev/mmcblk0p8", ""):
            self.write("proc/cmdline", cmdline)
            self.assertIsNone(self.info.boot(self.root_status)["active_slot"])

    def test_network_links_addresses_and_unambiguous_default_route(self):
        for name, state in (("eth0", "up"), ("wlan0", "down")):
            self.write(f"sys/class/net/{name}/type", "1\n")
            self.write(f"sys/class/net/{name}/operstate", state + "\n")
            self.write(f"sys/class/net/{name}/carrier", "1\n" if state == "up" else "0\n")
        (self.root / "sys/class/net/wlan0/wireless").mkdir()
        self.write("sys/class/net/lo/type", "772\n")
        # RFC 5737 addresses, never observations from an individual device.
        ifconfig = "eth0      Link encap:Ethernet\n          inet addr:192.0.2.7  Mask:255.255.255.0\n\n" \
                   "wlan0: flags=4099<UP,BROADCAST>\n        inet6 2001:db8::7 prefixlen 64\n"
        self.write("proc/net/route", "Iface Destination Gateway Flags RefCnt Use Metric Mask\n"
                   "eth0 00000000 010200C0 0003 0 0 10 00000000\n"
                   "wlan0 00000000 010200C0 0003 0 0 20 00000000\n")
        with patch.object(self.info.subprocess, "run", return_value=types.SimpleNamespace(returncode=0, stdout=ifconfig)) as run:
            network = self.info.network()
        self.assertEqual(run.call_args.args[0], ["/sbin/ifconfig", "-a"])
        self.assertEqual(network["default_ipv4_route"]["interface"], "eth0")
        self.assertEqual(network["default_ipv4_route"]["gateway"], "192.0.2.1")
        self.assertEqual(network["interfaces"][0]["addresses"], ["192.0.2.7"])
        self.assertEqual(network["interfaces"][1]["kind"], "wlan")
        self.assertEqual(network["interfaces"][1]["addresses"], ["2001:db8::7"])
        self.assertFalse(network["interfaces"][1]["carrier"])
        route = self.root / "proc/net/route"
        route.write_text(route.read_text().replace("0 0 20", "0 0 10"))
        with patch.object(self.info.subprocess, "run", side_effect=FileNotFoundError):
            network = self.info.network()
        self.assertIsNone(network["default_ipv4_route"], "equal routes do not identify one active interface")
        self.assertIsNone(network["interfaces"][0]["addresses"])

    def test_usb_topology_and_interface_driver_without_serials(self):
        self.write("sys/bus/usb/devices/usb1/product", "Fixture USB bus\n")
        self.write("sys/bus/usb/devices/1-1.2/product", "Fixture camera\n")
        self.write("sys/bus/usb/devices/1-1.2/idVendor", "1234\n")
        self.write("sys/bus/usb/devices/1-1.2/serial", "must-not-be-returned\n")
        interface = self.root / "sys/bus/usb/devices/1-1.2:1.0"
        interface.mkdir()
        target = self.root / "sys/bus/usb/drivers/uvcvideo"
        target.mkdir(parents=True)
        (interface / "driver").symlink_to(target, target_is_directory=True)
        devices = self.info.usb()
        self.assertEqual(len(devices), 2)
        camera = next(item for item in devices if item["port"] == "1-1.2")
        self.assertEqual(camera["parent"], "1-1")
        self.assertEqual(camera["interfaces"], [{"interface": "1-1.2:1.0", "driver": "uvcvideo"}])
        self.assertNotIn("must-not-be-returned", json.dumps(devices))

    def test_service_active_marker_needs_matching_live_process(self):
        pid = self.write("run/fre3nder-klipper/klippy.pid", "42\n")
        self.write("run/fre3nder-klipper/status", "active\n")
        command = self.write("proc/42/cmdline", "/usr/bin/python3\0/usr/share/klipper/klippy/klippy.py\0")
        self.assertEqual(self.info.services()[0]["status"], "active")
        command.write_text("unrelated-process\0")
        self.assertEqual(self.info.services()[0]["status"], "not-running")
        command.unlink()
        self.assertFalse(self.info.services()[0]["process_running"])
        pid.unlink()
        self.assertEqual(self.info.services()[0]["status"], "unconfirmed")
        self.write("run/fre3nder-display/status", "startup-failed\n")
        self.assertEqual(self.info.services()[-1]["status"], "startup-failed")

    def test_moonraker_status_uses_app_pid_and_signed_runtime(self):
        self.write("run/fre3nder-moonraker/status", "active\n")
        pid = self.write("home/fre3nder/.local/share/moonraker/moonraker.pid", "42\n")
        command = self.write("proc/42/cmdline", "/usr/bin/python3\0"
                             "/opt/fre3nder/apps-v2/moonraker/payload/source/moonraker/moonraker.py\0")
        self.assertEqual(self.info.services()[1]["status"], "active")
        command.write_text("unrelated-process\0")
        self.assertEqual(self.info.services()[1]["status"], "not-running")
        pid.unlink()
        self.assertEqual(self.info.services()[1]["status"], "unconfirmed")

    def test_snapshot_only_reads_and_keeps_partial_results(self):
        self.write("home/.fre3nder/frontend/active", "fixture-web\n")
        self.write("home/.fre3nder/display/active", "fixture-screen\n")
        self.write("run/fre3nder-display/status", "startup-failed\n")
        calls = []

        def run(arguments, **kwargs):
            calls.append(arguments)
            if arguments == ["/sbin/ifconfig", "-a"]:
                raise FileNotFoundError
            self.assertEqual(arguments, [str(self.info.PACKAGE_CORE), "list"])
            self.assertFalse(any(key.startswith("FRE3NDER_") for key in kwargs["env"]))
            return types.SimpleNamespace(returncode=0, stdout=json.dumps({"api_version": 1, "ok": True, "apps": [{}, {}]}))

        before = {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        with patch.object(self.info.subprocess, "run", side_effect=run), \
                patch.object(self.info.ota, "status_response", side_effect=ValueError("invalid record")), \
                patch.object(Path, "write_text", side_effect=AssertionError("write forbidden")), \
                patch.object(Path, "mkdir", side_effect=AssertionError("mkdir forbidden")):
            snapshot = self.info.snapshot(self.version, self.root_status, lambda: True, self.root / "missing-web-status", None)
        after = {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(len(calls), 2)
        self.assertEqual(snapshot["applications"]["installed_count"], 2)
        self.assertEqual(snapshot["applications"]["web_frontend"]["name"], "fixture-web")
        self.assertEqual(snapshot["applications"]["display_runtime_status"], "startup-failed")
        self.assertIsNone(snapshot["maintenance"]["ota"])
        self.assertIsNone(snapshot["maintenance"]["web_status"])
        self.assertIsNone(snapshot["usb"])
        self.assertEqual(snapshot["platform"]["version"], "2026.5.a")

    def test_app_count_and_selections_distinguish_unavailable_from_absent(self):
        self.assertEqual(self.info.selection("display"), {"status": "none", "name": None})
        selected = self.write("home/.fre3nder/display/active", "invalid app name\n")
        self.assertEqual(self.info.selection("display")["status"], "unavailable")
        selected.unlink()
        selected.symlink_to(self.version)
        self.assertEqual(self.info.selection("display")["status"], "unavailable")
        for output in ("[]", "{broken}", '{"api_version":1,"ok":false,"apps":[]}'):
            with self.subTest(output=output), patch.object(self.info.subprocess, "run", return_value=types.SimpleNamespace(returncode=0, stdout=output)):
                self.assertIsNone(self.info.applications()["installed_count"])


if __name__ == "__main__":
    unittest.main()
