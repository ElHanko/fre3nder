#!/usr/bin/env python3
"""Non-building web-service fixtures. The fake daemon binds no network socket."""

import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "configs/x2000/rootfs-overlay"
SERVICE = OVERLAY / "etc/init.d/S62fre3nder-web"
BASE_CONFIG = OVERLAY / "etc/lighttpd/fre3nder.conf"


class WebServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runtime = self.root / "run/web"
        self.root_state = self.root / "run/root"
        self.home = self.root / "home/fre3nder"
        self.active = self.home / ".fre3nder/frontend/active"
        self.disabled = self.home / ".fre3nder/web/disabled"
        self.web = self.root / "opt/web"
        self.payload = self.web / "sample-ui"
        self.daemon = self.root / "bin/lighttpd"
        self.calls = self.root / "calls"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("FRE3NDER_")}
        self.env.update({
            "FRE3NDER_WEB_RUNTIME": str(self.runtime),
            "FRE3NDER_ROOT_STATE": str(self.root_state),
            "FRE3NDER_HOME_DIR": str(self.home),
            "FRE3NDER_WEB_DIR": str(self.web),
            "FRE3NDER_WEB_BASE_CONFIG": str(BASE_CONFIG),
            "FRE3NDER_LIGHTTPD": str(self.daemon),
            "FRE3NDER_PYTHON": sys.executable,
            "FIXTURE_LIGHTTPD_CALLS": str(self.calls),
        })
        self.write(self.daemon, '''#!/usr/bin/env python3
import os
from pathlib import Path
import sys
import time

with Path(os.environ["FIXTURE_LIGHTTPD_CALLS"]).open("a") as output:
    output.write(" ".join(sys.argv[1:]) + "\\n")
assert sys.argv[2] == "-f"
assert Path(sys.argv[3]).is_file()
if "-tt" in sys.argv:
    sys.exit(int(os.environ.get("FIXTURE_CONFIG_FAILURE", "0")))
if os.environ.get("FIXTURE_START_FAILURE"):
    sys.exit(1)
while True:
    time.sleep(0.1)
''')
        self.daemon.chmod(0o755)
        self.addCleanup(self.stop_fixture)

    def write(self, path, content=""):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def stop_fixture(self):
        subprocess.run(["sh", str(SERVICE), "stop"], env=self.env, capture_output=True)

    def run_service(self, action="start", expected=None, ok=True):
        result = subprocess.run(["sh", str(SERVICE), action], env=self.env, capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        if expected:
            self.assertEqual((self.runtime / "status").read_text().strip(), expected, result.stderr)
        return result

    def setup_frontend(self):
        self.write(self.root_state / "status", "active\n")
        self.write(self.active, "sample-ui\n")
        self.write(self.payload / "index.html", "fixture frontend")

    def test_no_persistent_root(self):
        self.run_service(expected="degraded-root")
        self.assertFalse(self.calls.exists())
        self.assertFalse(self.home.exists())

    def test_disabled_and_disabled_restart(self):
        self.setup_frontend()
        self.write(self.disabled)
        self.run_service(expected="disabled")
        self.run_service("restart", expected="disabled")
        self.assertFalse(self.calls.exists())
        self.assertFalse((self.runtime / "lighttpd.conf").exists())

    def test_invalid_disabled_state(self):
        self.setup_frontend()
        self.disabled.parent.mkdir(parents=True)
        for kind in ("symlink", "directory"):
            if kind == "symlink":
                self.disabled.symlink_to(self.active)
            else:
                self.disabled.mkdir()
            self.run_service(expected="state-invalid")
            self.assertFalse(self.calls.exists())
            self.disabled.unlink() if kind == "symlink" else self.disabled.rmdir()

    def test_missing_or_invalid_frontend(self):
        self.setup_frontend()
        self.active.unlink()
        self.run_service(expected="no-frontend")
        for name in ("../escape", "/tmp", "", "two\nnames", "a" * 65, "A"):
            self.write(self.active, name)
            self.run_service(expected="frontend-invalid")
        self.active.unlink()
        self.active.symlink_to(self.payload / "index.html")
        self.run_service(expected="state-invalid")
        self.assertFalse(self.calls.exists())

    def test_missing_invalid_and_symlink_payload(self):
        self.setup_frontend()
        (self.payload / "index.html").unlink()
        self.run_service(expected="payload-invalid")
        self.payload.rmdir()
        self.run_service(expected="payload-unavailable")
        self.payload.symlink_to(self.home)
        self.run_service(expected="state-invalid")
        self.assertFalse(self.calls.exists())

    def test_start_stop_restart_and_runtime_configuration(self):
        self.setup_frontend()
        original_active = self.active.read_bytes()
        original_index = (self.payload / "index.html").read_bytes()
        # No Moonraker readiness state exists; Lighttpd can start independently.
        self.run_service(expected="active")
        generated = (self.runtime / "lighttpd.conf").read_text()
        self.assertEqual(generated, f'server.document-root = "{self.payload}"\ninclude "{BASE_CONFIG}"\n')
        pid = (self.runtime / "lighttpd.pid").read_text()
        self.run_service(expected="active")
        self.assertEqual((self.runtime / "lighttpd.pid").read_text(), pid)
        self.run_service("restart", expected="active")
        self.assertNotEqual((self.runtime / "lighttpd.pid").read_text(), pid)
        self.write(self.disabled)
        self.run_service("restart", expected="disabled")
        self.assertFalse((self.runtime / "lighttpd.pid").exists())
        self.assertEqual(self.active.read_bytes(), original_active)
        self.assertEqual((self.payload / "index.html").read_bytes(), original_index)
        calls = self.calls.read_text().splitlines()
        self.assertEqual(sum(line.startswith("-D ") for line in calls), 2)
        self.assertEqual(sum(line.startswith("-tt ") for line in calls), 2)
        self.assertEqual(sorted(p.name for p in self.runtime.iterdir()), ["lighttpd.conf", "lighttpd.log", "status"])

    def test_stale_pid_does_not_kill_unrelated_process(self):
        self.setup_frontend()
        innocent = subprocess.Popen(["sleep", "60"])
        self.addCleanup(innocent.wait)
        self.addCleanup(innocent.terminate)
        self.write(self.runtime / "lighttpd.pid", str(innocent.pid))
        self.run_service(expected="stale-pid")
        self.assertFalse(self.calls.exists())
        self.run_service("stop", expected="stopped")
        self.assertIsNone(innocent.poll())

    def test_config_failure_and_early_daemon_exit(self):
        self.setup_frontend()
        self.env["FIXTURE_CONFIG_FAILURE"] = "1"
        self.run_service(expected="config-invalid")
        self.assertFalse((self.runtime / "lighttpd.pid").exists())
        self.env.pop("FIXTURE_CONFIG_FAILURE")
        self.env["FIXTURE_START_FAILURE"] = "1"
        self.run_service(expected="startup-failed")
        self.assertFalse((self.runtime / "lighttpd.pid").exists())

    def test_runtime_symlink_refused(self):
        self.setup_frontend()
        self.runtime.parent.mkdir(parents=True, exist_ok=True)
        self.runtime.symlink_to(self.home)
        self.run_service(ok=False)
        self.assertFalse((self.home / "status").exists())
        self.assertFalse(self.calls.exists())


class WebConfigurationTests(unittest.TestCase):
    def test_routing_and_small_module_set(self):
        config = BASE_CONFIG.read_text()
        self.assertIn('server.port = 80', config)
        self.assertIn('server.bind = "0.0.0.0"', config)
        self.assertIn('"host" => "127.0.0.1", "port" => 17126', config)
        self.assertIn('proxy.header = ( "upgrade" => "enable" )', config)
        self.assertIn('"host" => "127.0.0.1", "port" => 8080', config)
        self.assertIn('proxy.header = ( "map-urlpath" => ( "/webcam/" => "/" ) )', config)
        self.assertNotIn('fluidd', config.lower())
        self.assertNotIn('server.document-root', config)
        self.assertIn('server.username = "nobody"', config)
        self.assertIn('server.groupname = "nobody"', config)
        modules = re.search(r'server.modules = \( (.+) \)', config).group(1)
        self.assertEqual(re.findall(r'"([^"]+)"', modules), ["mod_indexfile", "mod_setenv", "mod_proxy", "mod_staticfile"])
        routes = re.findall(r'\$HTTP\["url"\] =~ "([^"]+)"', config)
        self.assertEqual(len(routes), 2)
        route, webcam_route = routes
        for path in ("/websocket", "/printer/info", "/api/version", "/access/login", "/machine/system_info", "/server/info", "/server/files/gcodes/example.gcode"):
            self.assertRegex(path, route)
        for path in ("/", "/index.html", "/assets/app.js", "/serverevil", "/websocket/other", "/debug"):
            self.assertNotRegex(path, route)
        self.assertRegex("/webcam/?action=snapshot", webcam_route)
        self.assertRegex("/webcam/?action=stream", webcam_route)
        for path in ("/webcam", "/webcamevil/", "/"):
            self.assertNotRegex(path, webcam_route)
        self.assertNotIn('mod_rewrite', config)
        self.assertNotRegex(config, r'server\.(?:bind|port)\s*=\s*(?:"[^"]*"\s*)?8080')
        for header in ("X-Real-IP", "X-Forwarded-For", "X-Forwarded-Proto", "X-Scheme"):
            self.assertIn(f'"{header}" => ""', config)
        moonraker = (OVERLAY / "usr/share/fre3nder/defaults/moonraker.conf").read_text()
        self.assertIn("host: 127.0.0.1\nport: 17126\n", moonraker)
        self.assertIn("[include fre3nder/*.conf]\n", moonraker)
        camera = (OVERLAY / "usr/share/fre3nder/defaults/camera.conf").read_text()
        self.assertEqual(camera, """[webcam fre3nder_camera]
location: printer
service: mjpegstreamer
stream_url: /webcam/?action=stream
snapshot_url: /webcam/?action=snapshot
""")

    def test_build_inputs_and_single_start_path(self):
        fragment = (ROOT / "configs/x2000/buildroot.fragment").read_text()
        self.assertEqual(re.findall(r"^(BR2_PACKAGE_LIGHTTPD\w*)=y$", fragment, re.M), ["BR2_PACKAGE_LIGHTTPD", "BR2_PACKAGE_LIGHTTPD_PCRE"])
        hook = (ROOT / "configs/x2000/rootfs-post-build.sh").read_text()
        self.assertIn('rm -f "$target/etc/init.d/S50lighttpd"', hook)
        self.assertIn('"$target/etc/init.d/S62fre3nder-web"', hook)
        self.assertFalse((OVERLAY / "etc/init.d/S50lighttpd").exists())
        entrypoint = (ROOT / "build/x2000/entrypoint.sh").read_text()
        self.assertIn('[ -f "$target/usr/lib/lighttpd/mod_proxy.so" ]', entrypoint)
        fluidd = (ROOT / "apps/fluidd/service").read_text().lower()
        self.assertNotIn("lighttpd", fluidd)
        self.assertNotIn("webcam", fluidd)
        self.assertNotIn("camera.conf", fluidd)


if __name__ == "__main__":
    unittest.main()
