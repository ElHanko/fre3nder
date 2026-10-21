#!/usr/bin/env python3
"""Offline Quick Start orchestration tests; all target builds are stubbed."""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/quick-start"


class QuickStartTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / "fre3nder"
        self.apps = self.base / "fre3nder-apps"
        for repo in (self.root, self.apps):
            repo.mkdir()
            (repo / "scripts").mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / ".gitignore").write_text("/local/\n/dist/\n")
            (repo / "tracked").write_text("fixture\n")
        shutil.copy2(SCRIPT, self.root / "scripts/quick-start")
        (self.root / "VERSION").write_text("2026.5.a\n")
        self.log = self.base / "calls"
        self.firmware = self.base / "qualified-f005.bin"
        self.firmware.write_bytes(b"qualified")
        self.write(self.root, "build/x2000/f005_firmware.py", """#!/usr/bin/env python3
import pathlib, sys
args = sys.argv
path = pathlib.Path(args[args.index('--firmware') + 1])
if path.read_bytes() != b'qualified':
    sys.exit('invalid F005 firmware')
print('F005 verified')
""")
        self.write(self.root, "configs/x2000/rootfs-overlay/usr/libexec/fre3nder/package-core", """#!/usr/bin/env python3
from pathlib import Path
import os
def verify_package(path):
    assert Path(path).is_file()
    if os.environ.get('QUICK_START_TEST_BAD_PACKAGE') and 'fluidd-' in path.name:
        raise ValueError('Ed25519 signature verification failed')
    name = 'fluidd' if 'fluidd-' in path.name else 'moonraker' if 'moonraker' in path.name else 'fre3nderscreen'
    return dict(name=name, publisher='fre3nder-official', release_serial=1,
                display_frontend=name=='fre3nderscreen', display_api=1,
                web_frontend=name=='fluidd', autostart=False, version='test')
""")
        self.write(self.root, "scripts/generate-app-keypair", """#!/bin/sh
set -eu
printf 'app-key\\n' >> "$QUICK_START_TEST_LOG"
mkdir -p "$QUICK_START_TEST_ROOT/local/production/keys/apps"
touch "$QUICK_START_TEST_ROOT/local/production/keys/apps/private.pem"
""")
        self.write(self.root, "scripts/generate-ota-keypair", """#!/bin/sh
set -eu
printf 'ota-key\\n' >> "$QUICK_START_TEST_LOG"
mkdir -p "$QUICK_START_TEST_ROOT/local/production/keys/ota"
touch "$QUICK_START_TEST_ROOT/local/production/keys/ota/private.pem"
touch "$QUICK_START_TEST_ROOT/local/production/keys/ota/public.pem"
""")
        self.write(self.root, "scripts/build-x2000-buildroot", """#!/bin/sh
set -eu
printf 'buildroot:%s\\n' "$*" >> "$QUICK_START_TEST_LOG"
""")
        self.write(self.root, "scripts/build-x2000-fre3nderscreen-release", """#!/bin/sh
set -eu
printf 'screen\\n' >> "$QUICK_START_TEST_LOG"
mkdir -p "$QUICK_START_TEST_ROOT/local/production/factory-apps"
touch "$QUICK_START_TEST_ROOT/local/production/factory-apps/fre3nderscreen.fre3app"
""")
        self.write(self.root, "scripts/build-x2000", """#!/bin/sh
set -eu
printf 'platform:%s\\n' "$FRE3NDER_F005_FIRMWARE" >> "$QUICK_START_TEST_LOG"
out="$QUICK_START_TEST_ROOT/local/production/artifacts/x2000/full"
mkdir -p "$out"
printf 'ota' > "$out/fre3nder-2026.5.a-ender3-v3-ke.ota"
(cd "$out" && sha256sum fre3nder-2026.5.a-ender3-v3-ke.ota > SHA256SUMS)
""")
        self.write(self.apps, "scripts/fetch-moonraker-inputs", """#!/bin/sh
printf 'fetch-moonraker\\n' >> "$QUICK_START_TEST_LOG"
""")
        self.write(self.apps, "scripts/prepare-moonraker", """#!/bin/sh
printf 'prepare-moonraker:%s\\n' "$*" >> "$QUICK_START_TEST_LOG"
""")
        self.write(self.apps, "scripts/prepare-fluidd", """#!/bin/sh
printf 'prepare-fluidd\\n' >> "$QUICK_START_TEST_LOG"
""")
        self.write(self.apps, "scripts/build-fre3app", """#!/bin/sh
set -eu
printf 'package:%s\\n' "$*" >> "$QUICK_START_TEST_LOG"
if [ "$1" = apps/fluidd ]; then
    mkdir -p dist
    touch dist/fluidd-test-x2000.fre3app
    printf 'dist/fluidd-test-x2000.fre3app\\n'
else
    while [ "$#" -gt 0 ]; do
        if [ "$1" = --output ]; then mkdir -p "$(dirname "$2")"; touch "$2"; break; fi
        shift
    done
fi
""")
        self.write(self.base, "docker", "#!/bin/sh\nexit 0\n")
        for repo in (self.root, self.apps):
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=Fixture",
                            "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)

    @staticmethod
    def write(root, name, content):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o755)

    def run_quickstart(self, *args, extra_env=None):
        env = dict(os.environ, QUICK_START_TEST_LOG=str(self.log),
                   QUICK_START_TEST_ROOT=str(self.root),
                   PATH=f"{self.base}:{os.environ['PATH']}")
        env.update(extra_env or {})
        return subprocess.run([str(self.root / "scripts/quick-start"), *args],
                              cwd=self.base, env=env, text=True, capture_output=True)

    def test_check_requires_firmware_and_does_not_build(self):
        fail = self.run_quickstart("--check")
        self.assertNotEqual(fail.returncode, 0)
        self.assertIn("missing qualified F005 firmware", fail.stderr)
        success = self.run_quickstart("--check", "--firmware", str(self.firmware))
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertIn("Preflight PASS", success.stdout)
        self.assertFalse(self.log.exists())
        self.assertFalse((self.root / "local").exists())

    def test_orchestrates_existing_scripts_in_order(self):
        done = self.run_quickstart("--firmware", str(self.firmware))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Quick Start: PASS", done.stdout)
        self.assertEqual(self.log.read_text().splitlines(), [
            "app-key", "ota-key", "fetch-moonraker",
            "prepare-moonraker:--source local/moonraker/source --wheels local/moonraker/wheels",
            f"package:apps/moonraker --key {self.root}/local/production/keys/apps/private.pem --output {self.root}/local/production/system-apps/moonraker.fre3app",
            "prepare-fluidd", f"package:apps/fluidd --key {self.root}/local/production/keys/apps/private.pem",
            "buildroot:--toolchain", "screen", f"platform:{self.firmware}",
        ])
        self.log.unlink()
        second = self.run_quickstart("--firmware", str(self.firmware))
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotIn("ota-key", self.log.read_text())

    def test_dirty_repository_stops_before_keys_or_build(self):
        (self.apps / "tracked").write_text("changed")
        result = self.run_quickstart("--firmware", str(self.firmware))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dirty repository", result.stderr)
        self.assertFalse(self.log.exists())

    def test_mismatched_firmware_stops_before_keys_or_build(self):
        self.firmware.write_bytes(b"wrong")
        result = self.run_quickstart("--firmware", str(self.firmware))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid F005 firmware", result.stderr)
        self.assertFalse(self.log.exists())

    def test_package_verification_failure_rejects_build_result(self):
        result = self.run_quickstart("--firmware", str(self.firmware),
                                     extra_env={"QUICK_START_TEST_BAD_PACKAGE": "1"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Ed25519 signature verification failed", result.stderr)
        self.assertNotIn("Quick Start: PASS", result.stdout)

    def test_incomplete_ota_keys_are_not_replaced(self):
        directory = self.root / "local/production/keys/ota"
        directory.mkdir(parents=True)
        (directory / "private.pem").write_text("old")
        result = self.run_quickstart("--firmware", str(self.firmware))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("incomplete or unsafe OTA signing keypair", result.stderr)
        self.assertEqual((directory / "private.pem").read_text(), "old")
        self.assertEqual(self.log.read_text().splitlines(), ["app-key"])


if __name__ == "__main__":
    unittest.main()
