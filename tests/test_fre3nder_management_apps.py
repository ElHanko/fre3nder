#!/usr/bin/env python3
"""Non-building, non-device tests for the Maintenance Apps adapter."""
import importlib.util
import contextlib
import fcntl
import io
import os
import runpy
from pathlib import Path
import tempfile
import subprocess
import sys
import threading
import time
import types
import json
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "configs/x2000/rootfs-overlay/usr/libexec/fre3nder/management_apps.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fre3nder_apps_fixture", ADAPTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


IDENTITY = {"name": "sample", "version": "1.2.0", "release_serial": 2,
            "publisher": "trusted", "fingerprint": "a" * 64,
            "web_frontend": False, "display_frontend": False, "display_api": None}


class AppsAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.mod = load_module()
        self.mod.STAGING = root / "home/.tmp/fre3nder/uploads"
        self.mod.EXECUTION_FILE = root / "run/apps-execution.json"
        self.mod.STAGING.parent.mkdir(mode=0o700, parents=True)
        self.mod.EXECUTION_FILE.parent.mkdir(mode=0o700, parents=True)
        self.calls = []

        def fake_core(operation, *args):
            self.calls.append((operation, args))
            if operation == "verify":
                return {"api_version": 1, "operation": "verify", "ok": True, "package": dict(IDENTITY)}
            if operation == "list":
                return {"apps": []}
            if operation == "display-list":
                return {"active": None, "apps": []}
            if operation == "frontend-status":
                return {"frontend": {"active": None}}
            if operation == "storage-status":
                return {"storage": {"sys": {"available_bytes": 100}, "home": {"available_bytes": 200}}}
            return {"api_version": 1, "operation": operation, "ok": True}

        self.patcher = patch.object(self.mod, "run_core", side_effect=fake_core)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def wait(self):
        for _ in range(100):
            if self.mod._execution and self.mod._execution["state"] not in ("running", "uploading"):
                return self.mod._execution
            time.sleep(.01)
        self.fail("Asynchronous fixture operation did not complete")

    def test_upload_requires_whole_body_and_never_publishes_partial(self):
        with self.assertRaises(self.mod.AppError) as exc:
            self.mod.upload(io.BytesIO(b"abc"), 5, "file.fre3app")
        self.assertEqual(exc.exception.code, "upload-incomplete")
        self.assertFalse(list(self.mod.stage_dir().glob("*.fre3app")))
        self.assertFalse(list(self.mod.stage_dir().glob("*.part")))
        self.assertEqual(self.mod._execution["state"], "failed")

    def test_upload_only_verifies_without_installing(self):
        job = self.mod.upload(io.BytesIO(b"fixture"), 7, "file.fre3app")
        self.wait()
        path = self.mod.staged(job["package_id"])
        self.assertEqual(path.read_bytes(), b"fixture")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.mod._execution["state"], "succeeded")
        self.assertEqual(self.calls[0][0], "verify")
        self.assertFalse(any(op == "install" for op, _ in self.calls))

    def test_install_requires_explicit_verified_stage(self):
        package_id = "f" * 32
        path = self.mod.stage_dir() / (package_id + ".fre3app")
        path.write_bytes(b"fixture")
        path.chmod(0o600)
        with self.assertRaises(self.mod.AppError) as exc:
            self.mod.start("install", {"package_id": package_id})
        self.assertEqual(exc.exception.code, "verification-required")

    def test_update_identity_bound_to_package(self):
        job = self.mod.upload(io.BytesIO(b"fixture"), 7, "file.fre3app")
        self.wait()
        with self.assertRaises(self.mod.AppError) as exc:
            self.mod.start("update", {"package_id": job["package_id"], "name": "other"})
        self.assertEqual(exc.exception.code, "identity-mismatch")
        self.assertFalse(any(op == "update" for op, _ in self.calls))

    def test_update_invokes_only_existing_package_core(self):
        job = self.mod.upload(io.BytesIO(b"fixture"), 7, "file.fre3app")
        self.wait()
        self.mod.start("update", {"package_id": job["package_id"], "name": "sample"})
        self.wait()
        self.assertIn("update", [op for op, _ in self.calls])
        self.assertEqual(self.mod._execution["state"], "succeeded")
        self.assertFalse(list(self.mod.stage_dir().glob("*.fre3app")))

    def test_install_storage_is_validated_and_only_forwarded_to_core(self):
        for role in ("sys", "home"):
            job = self.mod.upload(io.BytesIO(b"fixture"), 7, "file.fre3app")
            self.wait()
            self.mod.start("install", {"package_id": job["package_id"], "storage": role})
            self.wait()
            self.assertEqual(self.calls[-1], ("install", (str(self.mod.STAGING / (job["package_id"] + ".fre3app")), "--storage", role)))
        for role in ("/tmp", "HOME", None, {}, ""):
            with self.assertRaises(self.mod.AppError) as exc:
                self.mod.start("install", {"package_id": "a" * 32, "storage": role})
            self.assertEqual(exc.exception.code, "invalid-storage")
        with self.assertRaises(self.mod.AppError):
            self.mod.start("update", {"package_id": "a" * 32, "name": "sample", "storage": "home"})

    def test_home_upload_capacity_reserves_proxy_staging_and_cache_together(self):
        directory = self.mod.stage_dir()
        for free, accepted in ((self.mod.RESERVE + 29, False), (self.mod.RESERVE + 30, True)):
            with patch.object(self.mod.os, "statvfs", return_value=types.SimpleNamespace(f_bavail=free, f_frsize=1)) as capacity:
                if accepted:
                    self.assertEqual(self.mod.storage(10, 10)["available_bytes"], free)
                else:
                    with self.assertRaises(self.mod.AppError) as exc:
                        self.mod.upload(io.BytesIO(b"x" * 10), 10, "file.fre3app")
                    self.assertEqual(exc.exception.code, "insufficient-space")
                    self.assertFalse(list(directory.glob("*.fre3app")))
                capacity.assert_called_with(directory)

    def test_overview_reports_core_storage_capacity(self):
        result = self.mod.overview()
        self.assertEqual(result["storage"]["sys"]["available_bytes"], 100)
        self.assertEqual(result["storage"]["home"]["available_bytes"], 200)

    def test_overview_does_not_pair_completed_removal_with_older_installed_list(self):
        job = {"id": "a" * 32, "operation": "remove", "name": "sample", "state": "running"}
        self.mod.store_execution(job)
        original = self.mod.run_core.side_effect

        def finish_after_list(operation, *args):
            if operation == "list":
                # The Core read began before the worker published completion.
                self.mod.store_execution({**job, "state": "succeeded"})
                return {"apps": [dict(IDENTITY)]}
            return original(operation, *args)

        self.mod.run_core.side_effect = finish_after_list
        first = self.mod.overview()
        self.assertEqual(first["execution"], job)
        self.assertEqual(first["installed"], [IDENTITY])
        self.mod.run_core.side_effect = original
        second = self.mod.overview()
        self.assertEqual(second["execution"]["state"], "succeeded")
        self.assertEqual(second["installed"], [])

    def test_install_receipt_names_verified_app_even_on_failure(self):
        job = self.mod.upload(io.BytesIO(b"fixture"), 7, "file.fre3app")
        self.wait()
        with patch.object(self.mod, "run_core", side_effect=self.mod.AppError(409, "package-rejected", "service failed")):
            accepted = self.mod.start("install", {"package_id": job["package_id"]})
            receipt = self.wait()
        self.assertEqual(accepted["name"], "sample")
        self.assertEqual(receipt["name"], "sample")
        self.assertEqual(receipt["state"], "failed")

    def test_app_name_and_stage_id_cannot_inject_paths(self):
        for name in ("../etc/shadow", "APP", "app/test", "sample\n"):
            with self.assertRaises(self.mod.AppError):
                self.mod.start("remove", {"name": name})
        with self.assertRaises(self.mod.AppError):
            self.mod.staged("../tmp/other")
        self.assertEqual(self.calls, [])

    def test_unknown_receipt_after_daemon_restart(self):
        self.mod.store_execution({"id": "a" * 32, "operation": "remove", "state": "running", "name": "sample"})
        self.mod._execution = None
        self.mod.restore()
        self.assertEqual(self.mod._execution["state"], "unknown")
        self.assertTrue(self.mod.running())
        with self.assertRaises(self.mod.AppError) as exc:
            self.mod.start("remove", {"name": "sample"})
        self.assertEqual(exc.exception.code, "apps-busy")
        self.mod.acknowledge()
        self.assertFalse(self.mod.running())
        self.assertEqual(self.calls[-1][0], "list")

    def test_staged_symlink_rejected(self):
        directory = self.mod.stage_dir()
        (directory / ("a" * 32 + ".fre3app")).symlink_to("/etc/passwd")
        with self.assertRaises(self.mod.AppError) as exc:
            self.mod.staged("a" * 32)
        self.assertEqual(exc.exception.code, "storage-unsafe")

    def test_display_select_delegates_without_marker_write(self):
        self.mod.start("display-select", {"name": "sample"})
        self.wait()
        self.assertIn(("display-select", ("sample",)), self.calls)

    def test_service_stdout_does_not_replace_final_core_json(self):
        self.patcher.stop()
        try:
            def fake_run(command, **kwargs):
                kwargs["stdout"].write(b"untrusted service log\n{\"ok\":true}\n")
                kwargs["stdout"].write(json.dumps({"api_version": 1, "operation": "list", "ok": True, "apps": []}).encode() + b"\n")
                return types.SimpleNamespace(returncode=0)
            with patch.object(self.mod.subprocess, "run", side_effect=fake_run):
                result = self.mod.run_core("list")
            self.assertEqual(result["apps"], [])
        finally:
            self.patcher.start()

    def test_untrusted_publisher_does_not_start_install(self):
        def reject(operation, *args):
            if operation == "verify":
                raise self.mod.AppError(409, "package-rejected", "publisher is not trusted")
            self.fail("Untrusted package reached an unexpected operation")
        with patch.object(self.mod, "run_core", side_effect=reject):
            self.mod.upload(io.BytesIO(b"untrusted"), 9, "untrusted.fre3app")
            receipt = self.wait()
        self.assertEqual(receipt["state"], "failed")
        self.assertEqual(receipt["error"]["code"], "package-rejected")
        self.assertFalse(self.mod._verified)


class AppCoreLockTests(unittest.TestCase):
    """Real CLI/Core processes and flock, using only temporary fixture state."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / "manager"
        self.state.mkdir(mode=0o700)
        self.core = ADAPTER.with_name("package-core")
        self.cli = ADAPTER.parents[2] / "bin/fre3nder"
        self.ota = runpy.run_path(str(ADAPTER.with_name("ota-core")))
        self.pending = self.state / "ota/pending.json"
        self.ready = self.root / "ready"
        self.release = self.root / "release"
        self.failure = self.root / "fail"
        self.service = self.root / "display-service"
        self.service.write_text(
            f"#!{sys.executable}\nimport pathlib, sys, time\n"
            f"pathlib.Path({str(self.ready)!r}).touch()\n"
            "deadline = time.monotonic() + 5\n"
            f"while not pathlib.Path({str(self.release)!r}).exists():\n"
            "    if time.monotonic() > deadline: sys.exit(2)\n"
            "    time.sleep(.01)\n"
            f"sys.exit(int(pathlib.Path({str(self.failure)!r}).exists()))\n"
        )
        self.service.chmod(0o755)
        self.env = {"FRE3NDER_PACKAGE_STATE_ROOT": str(self.state),
                    "FRE3NDER_HOME_DIR": str(self.root / "home"),
                    "FRE3NDER_PACKAGE_RUNTIME_ROOT": str(self.root / "apps"),
                    "FRE3NDER_PACKAGE_RECOVERY_DIR": str(self.root / "recovery"),
                    "FRE3NDER_DISPLAY_SERVICE": str(self.service),
                    "FRE3NDER_DISPLAY_RUNTIME": str(self.root / "display-runtime"),
                    "FRE3NDER_WEB_SERVICE": str(self.root / "unused-web-service")}
        # Production strips FRE3NDER_* before invoking Core. This fixture executable
        # supplies its own isolated paths, then execs the unchanged real Core.
        wrapper = self.root / "fixture-core"
        wrapper.write_text(f"#!{sys.executable}\nimport os, sys\n"
                           f"os.environ.update({self.env!r})\n"
                           f"os.execv({str(self.core)!r}, [{str(self.core)!r}, *sys.argv[1:]])\n")
        wrapper.chmod(0o755)
        self.mod = load_module()
        self.mod.PACKAGE_CORE = wrapper
        self.mod.STAGING = self.root / "home/.tmp/fre3nder/uploads"
        self.mod.STAGING.parent.mkdir(mode=0o700, parents=True)
        self.mod.EXECUTION_FILE = self.root / "apps-execution.json"

    def cli_run(self, *args):
        return subprocess.run([str(self.core), *args], env={**os.environ, **self.env},
                              capture_output=True, text=True, timeout=3)

    def prepare_display(self):
        directory = self.state / "display"
        directory.mkdir(mode=0o700, exist_ok=True)
        (directory / "active").write_text("sample\n")
        (directory / "active").chmod(0o644)
        self.ready.unlink(missing_ok=True)
        self.release.unlink(missing_ok=True)

    def wait_ready(self):
        deadline = time.monotonic() + 3
        while not self.ready.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(self.ready.exists(), "Fixture service was not reached")

    @contextlib.contextmanager
    def active_cli(self):
        self.prepare_display()
        process = subprocess.Popen(
            [sys.executable, str(self.cli), "app", "display", "disable"],
            env={**os.environ, **self.env, "FRE3NDER_PACKAGE_CORE": str(self.core)},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            self.wait_ready()
            yield process
        finally:
            self.release.touch()
            stdout, stderr = process.communicate(timeout=3)
        self.assertEqual(process.returncode, int(self.failure.exists()), stdout + stderr)

    def wait_apps(self):
        deadline = time.monotonic() + 3
        while self.mod.running() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertFalse(self.mod.running(), "App Core deadlocked")
        return self.mod._execution

    def ota_status(self):
        return self.ota["status_response"](
            pending_transaction_path=self.pending,
            activation_record_path=self.root / "activation.json",
            known_good_path=self.root / "known-good.json")

    def test_cli_mutations_reject_active_ota_and_keep_reads_available(self):
        entered, release = threading.Event(), threading.Event()

        @self.ota["transaction_operation"]
        def transition(**kwargs):
            entered.set()
            release.wait(5)

        thread = threading.Thread(target=transition, kwargs={"pending_transaction_path": self.pending})
        thread.start()
        try:
            self.assertTrue(entered.wait(3))
            for operation in ("install", "update", "remove", "display-select", "display-disable",
                              "restore-installed", "start-installed", "stop-installed", "key-add", "key-remove"):
                with self.subTest(operation=operation):
                    result = self.cli_run(operation)
                    self.assertEqual(result.returncode, 1, result.stdout)
                    self.assertIn("another OTA/app operation is active", result.stdout)
            self.assertEqual(self.cli_run("list").returncode, 0)
            self.assertEqual(self.cli_run("display-list").returncode, 0)
            result = self.cli_run("verify", str(self.root / "missing.fre3app"))
            self.assertNotIn("operation is active", result.stdout)
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.cli_run("display-disable").returncode, 0)

    def test_cli_blocks_all_ota_transitions_but_not_status(self):
        with self.active_cli():
            self.assertTrue(self.ota_status()["busy"])
            result = self.cli_run("display-disable")
            self.assertEqual(result.returncode, 1)
            self.assertIn("operation is active", result.stdout)
            for operation in ("backup", "confirm", "write", "readback", "prepare_activation"):
                with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, "another OTA operation is active"):
                    self.ota[operation + "_response"](
                        "missing.ota", ["a" * 32], pending_transaction_path=self.pending)
            with self.assertRaisesRegex(ValueError, "another OTA operation is active"):
                self.ota["reboot_response"](["a" * 32], pending_transaction_path=self.pending)
            self.assertEqual(self.cli_run("list").returncode, 0)
        self.assertFalse(self.ota_status()["busy"])

    def test_maintenance_and_cli_exclude_each_other_without_self_deadlock(self):
        with self.active_cli():
            self.mod.start("display-disable", {})
            receipt = self.wait_apps()
            self.assertEqual(receipt["state"], "failed")
            self.assertIn("operation is active", receipt["error"]["message"])
        self.prepare_display()
        self.mod.start("display-disable", {})
        try:
            self.wait_ready()
            result = self.cli_run("display-disable")
            self.assertEqual(result.returncode, 1)
            self.assertIn("operation is active", result.stdout)
            self.assertTrue(self.ota_status()["busy"])
        finally:
            self.release.touch()
            receipt = self.wait_apps()
        self.assertEqual(receipt["state"], "succeeded", receipt)
        self.assertFalse(self.ota_status()["busy"])

    def test_core_and_service_errors_release_both_locks(self):
        self.failure.touch()
        with self.active_cli():
            pass
        self.failure.unlink()
        self.assertFalse(self.ota_status()["busy"])
        self.mod.start("remove", {"name": "missing"})
        self.assertEqual(self.wait_apps()["state"], "failed")
        self.mod.start("display-disable", {})
        self.assertEqual(self.wait_apps()["state"], "succeeded")
        self.assertEqual(self.cli_run("display-disable").returncode, 0)

    def test_real_core_failed_display_start_produces_failed_receipt_after_recovery(self):
        selection = self.state / "display/active"
        selection.parent.mkdir(mode=0o700)
        status = self.root / "display-runtime/status"
        status.parent.mkdir()
        for name in ("fre3nderscreen", "doom"):
            directory = self.state / "packages" / name
            directory.mkdir(parents=True)
            (directory / "installed").touch()
            (directory / "metadata.json").write_text(json.dumps({
                **IDENTITY, "name": name, "display_frontend": True, "display_api": 1,
                "autostart": False, "storage": "home" if name == "doom" else "sys",
            }))
        # Start remains boot-safe (exit zero), while runtime status reports the
        # failure. Hold the first start so the running receipt can be inspected.
        self.service.write_text(
            f"#!{sys.executable}\nimport pathlib, sys, time\n"
            f"status = pathlib.Path({str(status)!r})\n"
            f"name = pathlib.Path({str(selection)!r}).read_text().strip()\n"
            "action = sys.argv[1]\n"
            "if action == 'start':\n"
            "    if name == 'doom':\n"
            f"        pathlib.Path({str(self.ready)!r}).touch()\n"
            "        deadline = time.monotonic() + 5\n"
            f"        while not pathlib.Path({str(self.release)!r}).exists():\n"
            "            if time.monotonic() > deadline: sys.exit(2)\n"
            "            time.sleep(.01)\n"
            f"    failed = name == 'doom' or pathlib.Path({str(self.failure)!r}).exists()\n"
            "    status.write_text('startup-failed' if failed else 'active')\n"
            "elif action == 'stop': status.write_text('stopped')\n"
            "elif action == 'status': sys.exit(0 if status.read_text() == 'active' else 1)\n"
        )
        for restoration_fails in (False, True):
            with self.subTest(restoration_fails=restoration_fails):
                selection.write_text("fre3nderscreen\n")
                selection.chmod(0o644)
                status.write_text("active")
                self.ready.unlink(missing_ok=True)
                self.release.unlink(missing_ok=True)
                if restoration_fails:
                    self.failure.touch()
                job = self.mod.start("display-select", {"name": "doom"})
                try:
                    self.wait_ready()
                    running = self.mod.overview()["execution"]
                    self.assertEqual(running["id"], job["id"])
                    self.assertEqual(running["state"], "running")
                finally:
                    self.release.touch()
                    receipt = self.wait_apps()
                self.assertEqual(receipt["state"], "failed", receipt)
                self.assertEqual(receipt["error"]["code"], "package-rejected")
                self.assertIn('Display frontend "doom" failed to start', receipt["error"]["message"])
                self.assertIn("startup-failed", receipt["error"]["message"])
                self.assertIn('Recovery failed' if restoration_fails else 'Previous display "fre3nderscreen" restored.',
                              receipt["error"]["message"])
                self.assertEqual(self.mod.overview()["display"]["active"], "fre3nderscreen")
                self.assertEqual(status.read_text().strip(), "startup-failed" if restoration_fails else "active")

    def test_package_lock_conflict_releases_acquired_ota_lock(self):
        with (self.state / ".package-operation.lock").open("w") as lock:
            os.fchmod(lock.fileno(), 0o600)
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.cli_run("display-disable")
            self.assertEqual(result.returncode, 1)
            self.assertIn("another package operation is active", result.stdout)
            self.assertFalse(self.ota_status()["busy"])
        self.assertEqual(self.cli_run("display-disable").returncode, 0)


if __name__ == "__main__":
    unittest.main()
