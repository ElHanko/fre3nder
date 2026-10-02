#!/usr/bin/env python3
# Non-building fixtures for the dedicated Maintenance listener.

import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "configs/x2000/rootfs-overlay"
SERVICE = OVERLAY / "etc/init.d/S62fre3nder-maintenance-web"
BASE_CONFIG = OVERLAY / "etc/lighttpd/fre3nder-maintenance.conf"


class MaintenanceWebServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runtime = self.root / "run/maintenance-web"
        self.root_state = self.root / "run/root"
        self.state = self.root / "home/.fre3nder/maintenance/enabled"
        self.web_root = self.root / "usr/share/fre3nder/web-root/maintenance"
        self.management_socket = self.root / "run/management/api.sock"
        self.daemon = self.root / "bin/lighttpd"
        self.calls = self.root / "calls"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("FRE3NDER_")}
        self.env.update({
            "FRE3NDER_MAINTENANCE_WEB_RUNTIME": str(self.runtime),
            "FRE3NDER_ROOT_STATE": str(self.root_state),
            "FRE3NDER_MAINTENANCE_STATE": str(self.state),
            "FRE3NDER_MAINTENANCE_ROOT": str(self.web_root),
            "FRE3NDER_MANAGEMENT_SOCKET": str(self.management_socket),
            "FRE3NDER_MAINTENANCE_WEB_BASE_CONFIG": str(BASE_CONFIG),
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
        result = subprocess.run(
            ["sh", str(SERVICE), action],
            env=self.env,
            capture_output=True,
            text=True,
        )
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        if expected:
            self.assertEqual((self.runtime / "status").read_text().strip(), expected)
        return result

    def setup_enabled(self):
        self.write(self.root_state / "status", "active\n")
        self.write(self.state, "enabled\n")
        self.state.chmod(0o644)
        self.write(self.web_root / "index.html", "fixture maintenance")
        self.management_socket.parent.mkdir(parents=True, exist_ok=True)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(self.management_socket))
        listener.listen(1)
        self.addCleanup(listener.close)

    def test_disabled_by_default(self):
        self.write(self.root_state / "status", "active\n")
        self.run_service(expected="disabled")
        self.assertFalse(self.calls.exists())
        self.assertFalse((self.runtime / "lighttpd.pid").exists())

    def test_enabled_serves_root_on_dedicated_origin(self):
        self.setup_enabled()
        self.run_service(expected="active")
        generated = (self.runtime / "lighttpd.conf").read_text()
        self.assertIn(f'server.document-root = "{self.web_root}"', generated)
        self.assertIn(f'include "{BASE_CONFIG}"', generated)
        self.assertIn(str(self.management_socket), generated)
        self.assertIn(
            '^/fre3nder/api/v1/(system|maintenance|auth/(session|unlock|lock))$',
            generated,
        )
        self.assertNotIn('/maintenance/', generated)

        self.state.unlink()
        self.run_service("restart", expected="disabled")
        self.assertFalse((self.runtime / "lighttpd.pid").exists())

    def test_invalid_state_and_missing_management_fail_closed(self):
        self.write(self.root_state / "status", "active\n")
        self.write(self.state, "maybe\n")
        self.state.chmod(0o644)
        self.run_service(expected="state-invalid")
        self.assertFalse(self.calls.exists())

        self.state.write_text("enabled\n")
        self.write(self.web_root / "index.html", "fixture maintenance")
        self.run_service("restart", expected="management-unavailable")
        self.assertFalse(self.calls.exists())

    def test_stale_pid_does_not_kill_unrelated_process(self):
        self.setup_enabled()
        innocent = subprocess.Popen(["sleep", "60"])
        self.addCleanup(innocent.wait)
        self.addCleanup(innocent.terminate)
        self.write(self.runtime / "lighttpd.pid", str(innocent.pid))
        self.run_service(expected="stale-pid")
        self.run_service("stop", expected="stopped")
        self.assertIsNone(innocent.poll())


class MaintenanceWebConfigurationTests(unittest.TestCase):
    def test_dedicated_port_and_privilege_boundary(self):
        config = BASE_CONFIG.read_text()
        self.assertIn('server.bind = "0.0.0.0"', config)
        self.assertIn('server.port = 8081', config)
        self.assertIn('server.username = "nobody"', config)
        self.assertIn('server.groupname = "fre3nder-management"', config)
        self.assertNotIn('server.document-root', config)
        self.assertNotIn('/maintenance/', config)
        modules = re.search(r'server.modules = \( (.+) \)', config).group(1)
        self.assertEqual(
            re.findall(r'"([^"]+)"', modules),
            ["mod_indexfile", "mod_setenv", "mod_proxy", "mod_staticfile"],
        )
        self.assertIn(
            '''"Content-Security-Policy" => "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"''',
            config,
        )
        self.assertIn('"X-Frame-Options" => "DENY"', config)
        self.assertIn('"X-Content-Type-Options" => "nosniff"', config)
        self.assertIn('"Referrer-Policy" => "no-referrer"', config)


if __name__ == "__main__":
    unittest.main()
