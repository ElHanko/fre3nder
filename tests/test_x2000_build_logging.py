"""Offline orchestration fixtures; all builders, signing and OTA work are stubbed."""

import os
from pathlib import Path
import re
import select
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DevelopmentLoggingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="fre3nder-logging-test-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.project = self.directory / "project"
        self.scripts = self.project / "scripts"
        self.scripts.mkdir(parents=True)
        shutil.copyfile(ROOT / "scripts/build-x2000", self.scripts / "build-x2000")
        (self.project / "configs/x2000/rootfs-overlay").mkdir(parents=True)
        keys = self.project / "local/production/keys/ota"
        keys.mkdir(parents=True)
        (keys / "private.pem").write_text("fixture private\n")
        (keys / "public.pem").write_text("fixture public\n")
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        FIXTURE_DIR=str(self.directory))
        self.logs = set()
        self.addCleanup(lambda: [p.unlink(missing_ok=True) for p in self.logs])
        self.write(self.directory / "functions", r'''
simulate() {
    printf '%s\n' "$1" >> "$FIXTURE_DIR/events"
    printf '%s stdout\n' "$1"
    printf '%s stderr\n' "$1" >&2
    if [ "${READ_STDIN:-}" = "$1" ]; then
        IFS= read -r line
        printf 'stdin: %s\n' "$line"
    fi
    if [ "${WAIT_PHASE:-}" = "$1" ]; then
        : > "$FIXTURE_DIR/ready"
        while :; do sleep 1; done
    fi
    [ "${FAIL_PHASE:-}" != "$1" ] || exit "${FAIL_CODE:-37}"
}
''')
        self.write(self.scripts / "build-x2000-kernel", r'''
. "$FIXTURE_DIR/functions"
if [ "${1:-}" = --develop ]; then
    printf '[fre3nder-toolchain] START %s\n' "$(date +%s)"
    simulate EmbeddedToolchain
    printf '[fre3nder-toolchain] END %s\n' "$(date +%s)"
fi
simulate Kernel
rm -f "$FIXTURE_DIR/mode-test"
: > "$FIXTURE_DIR/mode-test"
''')
        self.write(self.scripts / "build-x2000-buildroot", r'''
. "$FIXTURE_DIR/functions"
case "$1" in
--toolchain) simulate Toolchain ;;
--assemble) simulate RootFS ;;
*) exit 99 ;;
esac
''')
        self.write(self.scripts / "build-f005", '. "$FIXTURE_DIR/functions"\nsimulate F005\n')
        self.write(self.scripts / "build-x2000-fre3nderscreen",
                   '. "$FIXTURE_DIR/functions"\nsimulate Fre3nderScreen\n')
        self.write(self.bin / "python3", '. "$FIXTURE_DIR/functions"\nsimulate OTA\n')
        self.write(self.bin / "openssl", r'''
case " $* " in
*' -pubout '*)
    while [ "$1" != -out ]; do shift; done
    printf 'fixture public\n' > "$2"
    ;;
*' -pubin '*) printf 'ED25519 Public-Key:\n' ;;
*) printf 'ED25519 Private-Key:\n' ;;
esac
''')
        # A fixed filename timestamp exercises mktemp's collision protection.
        # A deterministic advancing clock makes duration assertions instant.
        self.write(self.bin / "date", r'''
case "$1" in
+%s)
    value=1000000000
    [ ! -f "$FIXTURE_DIR/clock" ] || value=$(cat "$FIXTURE_DIR/clock")
    value=$((value + 2))
    printf '%s\n' "$value" > "$FIXTURE_DIR/clock"
    printf '%s\n' "$value"
    ;;
+%Y%m%d-%H%M%S) printf '20261103-181800\n' ;;
*) exit 99 ;;
esac
''')
        app_builder = self.directory / (
            "fre3nder-apps/apps/fre3nderscreen/scripts/build-fre3nderscreen-development")
        self.write(app_builder, r'''
. "$FIXTURE_DIR/functions"
simulate ScreenPackage
printf '=== Fre3nderScreen development package: PASS ===\n'
printf 'Package:  %s/factory.fre3app\n' "$FIXTURE_DIR"
''')
        (self.directory / "factory.fre3app").write_text("fixture package\n")

    def write(self, path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\nset -eu\n" + body)
        path.chmod(0o755)

    def log_paths(self, output):
        paths = {Path(p) for p in re.findall(r"^Log: (/tmp/fre3nder-build-\S+\.log)$",
                                           output, re.M)}
        self.logs.update(paths)
        return paths

    def run_build(self, *args, input=None, **environment):
        result = subprocess.run(["sh", str(self.scripts / "build-x2000"), *args],
                                env=dict(self.env, **environment), input=input,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=10, start_new_session=True)
        self.log_paths(result.stdout)
        return result

    def assert_log(self, result):
        paths = self.log_paths(result.stdout)
        self.assertEqual(len(paths), 1, result.stdout)
        path = paths.pop()
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(path.read_text(), result.stdout)
        self.assertEqual(result.stdout.count(f"Log: {path}"), 2)
        return path

    def row(self, output, phase):
        match = re.search(rf"^{phase}\s+(\d+:\d{{2}}:\d{{2}}|--:--:--)\s+(\w+)$",
                          output, re.M)
        self.assertIsNotNone(match, output)
        return match.groups()

    def assert_phase_summary(self, output, phase):
        elapsed, status = self.row(output, phase)
        block = ("\n========================================\n"
                 f"  {phase}: {status} ({elapsed})\n"
                 "========================================\n")
        self.assertEqual(status, "PASS")
        self.assertEqual(output.count(block), 1, output)
        return output.index(block)

    def test_full_success_and_exclusive_toolchain_time(self):
        result = self.run_build("--develop")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assert_log(result)
        for phase in ("Kernel", "Toolchain", "RootFS", "OTA"):
            self.assertIn(f"{phase} stdout", result.stdout)
            self.assertIn(f"{phase} stderr", result.stdout)
        self.assertEqual(self.row(result.stdout, "Kernel"), ("00:00:04", "PASS"))
        self.assertEqual(self.row(result.stdout, "Toolchain"), ("00:00:04", "PASS"))
        self.assertEqual(self.row(result.stdout, "Gesamt"), ("00:00:22", "PASS"))
        phases = ("Kernel", "Toolchain", "RootFS", "OTA")
        for index, phase in enumerate(phases):
            position = self.assert_phase_summary(result.stdout, phase)
            self.assertLess(result.stdout.index(f"\n{phase} stderr\n"), position)
            if index + 1 < len(phases):
                self.assertLess(position, result.stdout.index(f"\n{phases[index + 1]} stdout\n"))
        self.assertIn("  Device Tree: ender3-v3-ke.dtb\n", result.stdout)
        self.assertIn("  Manifest und Integrität: OK\n", result.stdout)
        self.assertTrue(result.stdout.endswith(
            "Phase               Dauer    Status\n"
            "Kernel           00:00:04    PASS\n"
            "Toolchain        00:00:04    PASS\n"
            "RootFS           00:00:02    PASS\n"
            "OTA              00:00:02    PASS\n"
            "------------------------------------\n"
            "Gesamt           00:00:22    PASS\n"), result.stdout)

    def test_scopes_and_optional_components(self):
        for scope, passed, skipped in (
            ("--kernel-only", ("Kernel", "Toolchain"), ("RootFS", "OTA")),
            ("--rootfs-only", ("Toolchain", "RootFS"), ("Kernel", "OTA")),
        ):
            with self.subTest(scope=scope):
                result = self.run_build("--develop", scope)
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assert_log(result)
                for phase in passed:
                    self.assertEqual(self.row(result.stdout, phase)[1], "PASS")
                    self.assert_phase_summary(result.stdout, phase)
                for phase in skipped:
                    self.assertEqual(self.row(result.stdout, phase), ("--:--:--", "SKIP"))
                    self.assertNotIn(f"  {phase}:", result.stdout)
        result = self.run_build("--develop", "--rootfs-only", "--f005-build",
                                "--fre3nderscreen-app")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assert_log(result)
        for phase in ("F005", "Fre3nderScreen"):
            self.assertEqual(self.row(result.stdout, phase), ("00:00:02", "PASS"))
            self.assert_phase_summary(result.stdout, phase)
        self.assertIn(f"  Package: {self.directory}/factory.fre3app\n", result.stdout)
        self.assertIn("ScreenPackage stdout", result.stdout)
        self.assertIn("ScreenPackage stderr", result.stdout)
        result = self.run_build("--develop", "--f005-build", "--fre3nderscreen-app")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assert_log(result)
        for phase in ("Kernel", "Toolchain", "RootFS", "OTA", "F005", "Fre3nderScreen"):
            self.assertEqual(self.row(result.stdout, phase)[1], "PASS")
            self.assert_phase_summary(result.stdout, phase)

    def test_phase_failure_keeps_exit_code_log_and_completed_times(self):
        result = self.run_build("--develop", FAIL_PHASE="RootFS", FAIL_CODE="37")
        self.assertEqual(result.returncode, 37, result.stdout)
        self.assert_log(result)
        for phase in ("Kernel", "Toolchain"):
            self.assertEqual(self.row(result.stdout, phase), ("00:00:04", "PASS"))
            self.assert_phase_summary(result.stdout, phase)
        self.assertEqual(self.row(result.stdout, "RootFS"), ("00:00:02", "FAIL"))
        self.assertEqual(self.row(result.stdout, "OTA")[1], "SKIP")
        self.assertNotIn("OTA", (self.directory / "events").read_text())
        self.assertEqual(self.row(result.stdout, "Gesamt")[1], "FAIL")
        self.assertNotIn("  RootFS:", result.stdout)
        self.assertNotIn("  OTA:", result.stdout)

    def test_embedded_toolchain_failure_is_identified(self):
        result = self.run_build("--develop", "--kernel-only",
                                FAIL_PHASE="EmbeddedToolchain", FAIL_CODE="43")
        self.assertEqual(result.returncode, 43, result.stdout)
        self.assert_log(result)
        self.assertEqual(self.row(result.stdout, "Toolchain")[1], "FAIL")
        self.assertEqual(self.row(result.stdout, "Kernel")[1], "ABORT")
        self.assertEqual(self.row(result.stdout, "RootFS")[1], "SKIP")
        self.assertNotIn("========================================", result.stdout)

    def test_early_abort_before_any_phase(self):
        (self.project / "local/production/keys/ota/private.pem").unlink()
        result = self.run_build("--develop")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assert_log(result)
        self.assertIn("missing OTA signing key", result.stdout)
        for phase in ("Kernel", "Toolchain", "RootFS", "OTA"):
            self.assertEqual(self.row(result.stdout, phase)[1], "SKIP")
        self.assertEqual(self.row(result.stdout, "Gesamt")[1], "FAIL")

    def test_other_phase_failures_are_not_hidden_by_tee(self):
        for phase in ("Kernel", "Toolchain", "OTA", "F005", "Fre3nderScreen", "ScreenPackage"):
            with self.subTest(phase=phase):
                result = self.run_build("--develop", "--f005-build", "--fre3nderscreen-app",
                                        FAIL_PHASE=phase, FAIL_CODE="53")
                self.assertEqual(result.returncode, 53, result.stdout)
                self.assert_log(result)
                self.assertEqual(self.row(result.stdout, "Fre3nderScreen" if phase == "ScreenPackage" else phase)[1], "FAIL")
                self.assertEqual(self.row(result.stdout, "Gesamt")[1], "FAIL")

    def test_unique_private_logs_and_unchanged_release_mode(self):
        release = self.run_build("--kernel-only")
        self.assertEqual(release.returncode, 0, release.stdout)
        self.assertFalse(self.log_paths(release.stdout))
        self.assertNotIn("Development Build", release.stdout)
        self.assertNotIn("========================================", release.stdout)
        release_mode = stat.S_IMODE((self.directory / "mode-test").stat().st_mode)
        first = self.run_build("--develop", "--kernel-only")
        second = self.run_build("--develop", "--kernel-only")
        self.assertNotEqual(self.assert_log(first), self.assert_log(second))
        self.assertEqual(stat.S_IMODE((self.directory / "mode-test").stat().st_mode), release_mode)
        failure = self.run_build("--kernel-only", FAIL_PHASE="Kernel", FAIL_CODE="29")
        self.assertEqual(failure.returncode, 29)
        self.assertFalse(self.log_paths(failure.stdout))
        self.assertEqual(failure.stdout, "Kernel stdout\nKernel stderr\n")

    def test_stdin_is_preserved(self):
        result = self.run_build("--develop", "--rootfs-only", input="fixture stdin\n",
                                READ_STDIN="Toolchain")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("stdin: fixture stdin", result.stdout)
        self.assert_log(result)

    def test_interrupts_write_a_report_and_stop_later_phases(self):
        for phase, sig, expected in (("RootFS", signal.SIGINT, 130),
                                     ("RootFS", signal.SIGTERM, 143),
                                     ("ScreenPackage", signal.SIGINT, 130),
                                     ("ScreenPackage", signal.SIGTERM, 143)):
            with self.subTest(phase=phase, signal=sig):
                ready = self.directory / "ready"
                ready.unlink(missing_ok=True)
                args = ["--develop"]
                if phase == "ScreenPackage":
                    args.append("--fre3nderscreen-app")
                process = subprocess.Popen(
                    ["sh", str(self.scripts / "build-x2000"), *args],
                    env=dict(self.env, WAIT_PHASE=phase), stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, start_new_session=True)
                try:
                    deadline = time.monotonic() + 5
                    while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.01)
                    self.assertTrue(ready.exists(), f"fixture did not reach {phase}")
                    os.killpg(process.pid, sig)
                    output, _ = process.communicate(timeout=5)
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.communicate()
                self.assertEqual(process.returncode, expected, output)
                self.assert_log(subprocess.CompletedProcess([], process.returncode, output))
                failed_phase = "Fre3nderScreen" if phase == "ScreenPackage" else phase
                self.assertEqual(self.row(output, failed_phase)[1], "FAIL")
                self.assertEqual(self.row(output, "OTA")[1], "SKIP")
                self.assertEqual(self.row(output, "Gesamt")[1], "FAIL")

    def test_output_is_live_before_the_build_finishes(self):
        process = subprocess.Popen(
            ["sh", str(self.scripts / "build-x2000"), "--develop", "--rootfs-only"],
            env=dict(self.env, WAIT_PHASE="RootFS"), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, start_new_session=True)
        captured = b""
        try:
            deadline = time.monotonic() + 5
            while b"RootFS stderr\n" not in captured and time.monotonic() < deadline:
                if select.select([process.stdout], [], [], 0.1)[0]:
                    chunk = os.read(process.stdout.fileno(), 4096)
                    if not chunk:
                        break
                    captured += chunk
            self.assertIsNone(process.poll())
            self.assertIn(b"RootFS stdout\n", captured)
            self.assertIn(b"RootFS stderr\n", captured)
            self.assertIn(b"  Toolchain: PASS (00:00:02)\n", captured)
            path = self.log_paths(captured.decode()).pop()
            self.assertIn("RootFS stderr", path.read_text())
            os.killpg(process.pid, signal.SIGTERM)
            remainder, _ = process.communicate(timeout=5)
            output = (captured + remainder).decode()
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
        self.assertEqual(process.returncode, 143, output)
        self.assert_log(subprocess.CompletedProcess([], process.returncode, output))

    def test_container_markers_are_development_only(self):
        source = (ROOT / "build/x2000/entrypoint.sh").read_text()
        prefix = source.split("build_kernel_only() {\n", 1)[1].split(
            '\tmake -C "$buildroot" O="$brout" -j"$jobs" linux-firmware', 1)[0]
        stubs = "prepare_buildroot() { :; }\nconfigure_buildroot() { :; }\n"
        stubs += "make() { :; }\nwrite_buildroot_toolchain_fingerprint() { :; }\n"
        for mode in ("release", "development"):
            result = subprocess.run(["sh", "-eu"], input=stubs + prefix,
                                    env=dict(self.env, artifact_mode=mode, work=str(self.directory),
                                             buildroot="fixture"), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.count("[fre3nder-toolchain]"),
                             2 if mode == "development" else 0)


if __name__ == "__main__":
    unittest.main()
