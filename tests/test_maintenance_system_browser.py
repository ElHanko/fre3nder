#!/usr/bin/env python3
"""Non-building Chromium/JavaScript fixtures for the System information page."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "configs/x2000/rootfs-overlay/usr/share/fre3nder/web-root/maintenance"
CHROMIUM = shutil.which("chromium") or shutil.which("chromium-browser")


def system_fixture():
    mib = 1024 ** 2
    return {
        "platform": {"version": "2026.5.a", "hardware_model": "Fixture board", "cpu_model": "Fixture CPU",
                     "architecture": "mips", "kernel_version": "6.6.fixture", "hostname": "printer.test"},
        "runtime": {"uptime_seconds": 90061, "system_time": "2026-01-01T12:00:00+00:00", "load_average": [0.1, 0.2, 0.3]},
        "memory": {"total_bytes": 256 * mib, "available_bytes": 192 * mib, "used_bytes": 64 * mib,
                   "swap_total_bytes": 0, "swap_free_bytes": 0, "swap_used_bytes": 0},
        "storage": [{"role": role, "device": f"/dev/fixture-{role.lower()}", "filesystem": "ext4",
                     "mountpoint": mountpoint, "total_bytes": 4 * 1024 * mib, "used_bytes": 1024 * mib,
                     "available_bytes": 3 * 1024 * mib} for role, mountpoint in (("SYS", "/run/fre3nder-root/system"), ("HOME", "/home"))],
        "boot": {"active_slot": "B", "active_rootfs": "/dev/mmcblk0p8", "root_status": "active"},
        # RFC 5737 fixture addresses; no individual device observations.
        "network": {"interfaces": [{"name": "eth0", "kind": "ethernet", "state": "up", "carrier": True, "addresses": ["192.0.2.7"]}],
                    "default_ipv4_route": {"interface": "eth0", "gateway": "192.0.2.1", "metric": 10}, "default_ipv4_routes": []},
        "usb": [{"port": f"1-1.{index}", "parent": "1-1", "product": "Fixture camera " + "long-model-name-" * 10,
                 "manufacturer": "Fixture", "vendor_id": "1234", "product_id": "5678", "driver": "usb",
                 "interfaces": [{"interface": f"1-1.{index}:1.0", "driver": "uvcvideo"}]} for index in range(2, 15)],
        "services": [{"name": "Klipper", "status": "active", "process_running": True},
                     {"name": "Camera", "status": "startup-failed", "process_running": False}],
        "applications": {"installed_count": 2, "web_frontend": {"status": "selected", "name": "fixture-web"},
                         "display_frontend": {"status": "selected", "name": "fixture-screen"}, "display_runtime_status": "active"},
        "maintenance": {"enabled": True, "web_status": "active", "execution": None,
                        "ota": {"busy": False, "transaction": None, "activation": None, "known_good": None}},
    }


FIXTURE = r'''
fixture.requests = []; fixture.errors = [];
window.addEventListener("error", (event) => fixture.errors.push(event.message));
window.addEventListener("unhandledrejection", (event) => fixture.errors.push(String(event.reason)));
window.fetch = async (path, options = {}) => {
  fixture.requests.push({path, method: options.method || "GET"});
  const reply = (value, status = 200) => ({ok: status < 400, status, json: async () => ({api_version: 1, ok: status < 400, ...value})});
  if (path.endsWith("/system/details")) {
    if (fixture.hold) await new Promise((resolve) => { fixture.release = () => { fixture.hold = false; fixture.release = null; resolve(); }; });
    if (fixture.fail) return reply({error: {code: "fixture-error", message: "fixture unavailable"}}, fixture.fail);
    return reply({system: JSON.parse(JSON.stringify(fixture.data))});
  }
  if (path.endsWith("/system")) return reply({system: {version: "2026.5.a", root_status: "active"}});
  if (path.endsWith("/maintenance")) return reply({maintenance: {enabled: true, web_status: "active"}});
  if (path.endsWith("/auth/session")) return reply({auth: {authenticated: fixture.authenticated, csrf_token: "fixture-csrf"}});
  if (path.endsWith("/apps/status")) return reply({apps: {installed: [], web: {active: null}, display: {active: null, apps: []},
    packages: [], verified_packages: [], execution: null, storage: {available_bytes: 1024, max_package_bytes: 1024}}});
  if (path.endsWith("/ota/status")) return reply({ota: {core: {transaction: null, activation: null, known_good: null, busy: false},
    execution: null, packages: [], storage: {available_bytes: 1024}}});
  throw new Error("Unexpected API request: " + path);
};
'''


@unittest.skipUnless(CHROMIUM, "Chromium is required for the JavaScript/DOM regression")
class MaintenanceSystemBrowserTests(unittest.TestCase):
    def test_javascript_formatting_and_untrusted_text(self):
        self.run_browser("format")

    def test_system_navigation_refresh_and_responsive_layout(self):
        for size in ("1100,800", "360,640"):
            with self.subTest(window_size=size):
                self.run_browser("page", size)

    def test_locked_missing_data_and_expired_session(self):
        self.run_browser("access", authenticated=False)

    def run_browser(self, mode, window_size="1100,800", authenticated=True):
        with tempfile.TemporaryDirectory(prefix="fre3nder-system-browser-") as tmp:
            root = Path(tmp)
            for name in ("maintenance.js", "apps.js", "system.js", "maintenance.css"):
                shutil.copyfile(WEB / name, root / name)
            shutil.copyfile(ROOT / "tests/test_maintenance_system_ui.js", root / "tests.js")
            state = {"mode": mode, "authenticated": authenticated, "data": system_fixture()}
            (root / "fixture.js").write_text("const fixture = " + json.dumps(state) + ";\n" + FIXTURE)
            html = (WEB / "index.html").read_text().replace(
                '<script src="maintenance.js"></script>', '<script src="fixture.js"></script><script src="maintenance.js"></script>'
            ).replace("</body>", '<pre id="browser-result">PENDING</pre><script src="tests.js"></script></body>')
            (root / "index.html").write_text(html)
            result = subprocess.run([
                CHROMIUM, "--headless", "--no-sandbox", "--disable-gpu", "--disable-background-networking",
                f"--window-size={window_size}", f"--user-data-dir={root / 'profile'}",
                "--virtual-time-budget=5000", "--dump-dom", (root / "index.html").as_uri() + "#system",
            ], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('<pre id="browser-result">PASS</pre>', result.stdout, result.stdout[-6000:] + result.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
