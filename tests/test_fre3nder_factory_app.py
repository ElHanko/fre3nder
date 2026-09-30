#!/usr/bin/env python3
"""Fixture checks for the once-only factory app bootstrap."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "configs/x2000/rootfs-overlay/etc/init.d/S63fre3nder-factory-app"

FAKE_CORE = '''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

state_path = Path(os.environ["FAKE_STATE"])
state = json.loads(state_path.read_text())
operation = sys.argv[1]
marker = Path(os.environ["FRE3NDER_FACTORY_MARKER"])
with Path(os.environ["FAKE_LOG"]).open("a") as stream:
    stream.write(json.dumps({"operation": operation,
                             "marker": marker.read_text() if marker.exists() else None}) + "\\n")
if state.get("fail") == operation:
    print(json.dumps({"api_version": 1, "operation": operation, "ok": False,
                      "error": "fixture failure"}))
    sys.exit(1)
apps = []
if state.get("screen"):
    apps.append({"name": "fre3nderscreen", "display_frontend": True})
if state.get("other"):
    apps.append({"name": "other", "display_frontend": True})
result = {}
if operation == "display-list":
    result = {"active": state.get("active"), "apps": apps}
elif operation == "list":
    result = {"apps": apps}
elif operation == "verify":
    result = {"package": {"name": "fre3nderscreen", "publisher": "fre3nder-official",
                          "display_frontend": True, "display_api": 1}}
elif operation == "install":
    state["screen"] = True
elif operation == "display-select":
    if not state.get("screen"):
        sys.exit(1)
    state["active"] = "fre3nderscreen"
else:
    sys.exit(2)
state_path.write_text(json.dumps(state))
print(json.dumps({"api_version": 1, "operation": operation, "ok": True, **result}))
'''


class FactoryAppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state_root = self.root / "package-state"
        self.state_root.mkdir(mode=0o700)
        self.marker = self.state_root / "factory-apps/fre3nderscreen"
        self.root_state = self.root / "root-state"
        self.root_state.mkdir()
        (self.root_state / "status").write_text("active\n")
        self.seed = self.root / "seed.fixture"
        self.seed.write_bytes(b"signed package fixture")
        self.core = self.root / "fake-package-core"
        self.core.write_text(FAKE_CORE)
        self.core.chmod(0o755)
        self.state_file = self.root / "fake-state.json"
        self.state_file.write_text("{}\n")
        self.log = self.root / "calls.jsonl"
        self.env = dict(
            os.environ,
            FRE3NDER_PACKAGE_CORE=str(self.core),
            FRE3NDER_FACTORY_FRE3NDERSCREEN_APP=str(self.seed),
            FRE3NDER_PACKAGE_STATE_ROOT=str(self.state_root),
            FRE3NDER_FACTORY_MARKER=str(self.marker),
            FRE3NDER_ROOT_STATE=str(self.root_state),
            FAKE_STATE=str(self.state_file),
            FAKE_LOG=str(self.log),
        )

    def run_boot(self):
        return subprocess.run(
            [sys.executable, str(BOOTSTRAP), "start"], env=self.env,
            capture_output=True, text=True,
        )

    def set_state(self, **fields):
        state = json.loads(self.state_file.read_text())
        state.update(fields)
        self.state_file.write_text(json.dumps(state))

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def set_marker(self, value):
        self.marker.parent.mkdir(mode=0o700)
        self.marker.write_text(value + "\n")

    def test_fresh_install_selects_then_completes(self):
        self.assertEqual(self.run_boot().returncode, 0)
        self.assertEqual(self.marker.read_text(), "complete\n")
        self.assertEqual([call["operation"] for call in self.calls()],
                         ["display-list", "list", "verify", "install", "display-select"])
        self.assertEqual(self.calls()[3]["marker"], "pending\n")

    def test_pending_installed_app_only_selects(self):
        self.set_marker("pending")
        self.set_state(screen=True)
        self.seed.unlink()
        self.assertEqual(self.run_boot().returncode, 0)
        self.assertEqual(self.marker.read_text(), "complete\n")
        self.assertNotIn("install", [call["operation"] for call in self.calls()])
        self.assertNotIn("verify", [call["operation"] for call in self.calls()])
        self.assertEqual(self.calls()[-1]["operation"], "display-select")

    def test_complete_does_nothing(self):
        self.set_marker("complete")
        self.assertEqual(self.run_boot().returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_existing_display_decision_is_preserved(self):
        self.set_state(other=True, active="other")
        self.assertEqual(self.run_boot().returncode, 0)
        self.assertEqual(self.marker.read_text(), "complete\n")
        self.assertEqual([call["operation"] for call in self.calls()], ["display-list"])
        self.assertEqual(json.loads(self.state_file.read_text())["active"], "other")

    def test_invalid_marker_fails_closed(self):
        self.set_marker("unexpected")
        result = self.run_boot()
        self.assertEqual(result.returncode, 0)
        self.assertIn("DEGRADED", result.stderr)
        self.assertEqual(self.marker.read_text(), "unexpected\n")
        self.assertEqual(self.calls(), [])

    def test_marker_symlink_fails_closed(self):
        target = self.root / "marker-target"
        target.write_text("pending\n")
        self.marker.parent.mkdir(mode=0o700)
        self.marker.symlink_to(target)
        result = self.run_boot()
        self.assertEqual(result.returncode, 0)
        self.assertIn("DEGRADED", result.stderr)
        self.assertEqual(target.read_text(), "pending\n")
        self.assertEqual(self.calls(), [])

    def test_failed_install_keeps_pending(self):
        self.set_state(fail="install")
        result = self.run_boot()
        self.assertEqual(result.returncode, 0)
        self.assertIn("DEGRADED", result.stderr)
        self.assertEqual(self.marker.read_text(), "pending\n")

    def test_failed_selection_keeps_pending(self):
        self.set_state(fail="display-select")
        result = self.run_boot()
        self.assertEqual(result.returncode, 0)
        self.assertIn("DEGRADED", result.stderr)
        self.assertEqual(self.marker.read_text(), "pending\n")

    def test_missing_or_invalid_seed_never_completes(self):
        self.seed.unlink()
        self.assertIn("DEGRADED", self.run_boot().stderr)
        self.assertEqual(self.marker.read_text(), "pending\n")
        self.seed.write_bytes(b"invalid fixture")
        self.set_state(fail="verify")
        self.assertIn("DEGRADED", self.run_boot().stderr)
        self.assertEqual(self.marker.read_text(), "pending\n")

    def test_invalid_active_selection_fails_closed(self):
        self.set_state(active="missing")
        result = self.run_boot()
        self.assertEqual(result.returncode, 0)
        self.assertIn("DEGRADED", result.stderr)
        self.assertFalse(self.marker.exists())

    def test_ambiguous_package_state_fails_closed(self):
        (self.state_root / "packages").mkdir(mode=0o700)
        orphan = self.state_root / "packages/orphan"
        orphan.mkdir()
        result = self.run_boot()
        self.assertEqual(result.returncode, 0)
        self.assertIn("ambiguous installed package state", result.stderr)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
