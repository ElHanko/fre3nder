#!/usr/bin/env python3
"""Non-building, non-device tests for the Maintenance Apps adapter."""
import importlib.util
import contextlib
import fcntl
import hashlib
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
REPOSITORY_CLIENT = {"name": "fre3nder-app-update"}
OFFER = {"name": "sample", "version": "1.3.0", "release_serial": 3,
         "publisher": {"id": "trusted", "key_fingerprint": "a" * 64},
         "channel": "stable", "target": {"platform": "fre3nder-x2000", "arch": "mipsel"},
         "sha256": "b" * 64, "size": 1024,
         "path": "packages/sample/sample-1.3.0-" + "b" * 12 + ".fre3app"}


class AppsAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.mod = load_module()
        self.mod.STAGING = root / "home/.tmp/fre3nder/uploads"
        self.mod.EXECUTION_FILE = root / "run/apps-execution.json"
        self.mod.REPOSITORY_STATUS = root / "home/fre3nder/.local/share/fre3nder-app-update/status.json"
        self.mod.APP_OTA_LOCK = root / "run/ota/write.lock"
        self.mod.STAGING.parent.mkdir(mode=0o700, parents=True)
        self.mod.EXECUTION_FILE.parent.mkdir(mode=0o700, parents=True)
        self.calls = []
        self.installed_apps = []

        def fake_core(operation, *args):
            self.calls.append((operation, args))
            if operation == "verify":
                return {"api_version": 1, "operation": "verify", "ok": True, "package": dict(IDENTITY)}
            if operation == "list":
                return {"apps": self.installed_apps}
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

    def write_repository(self, offers=None, **changes):
        value = {"schema": 1, "configuration": "configured", "check": "ok", "error": None,
                 "repository": {"name": "Fixture repository", "key_fingerprint": "c" * 64,
                                "base_url": "https://repository.example.invalid/"},
                 "revision": 7, "last_attempt": "2026-10-20T10:00:00+00:00",
                 "last_success": "2026-10-20T10:00:00+00:00",
                 "packages": [dict(OFFER)] if offers is None else offers, **changes}
        path = self.mod.REPOSITORY_STATUS
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return value

    def test_repository_selects_highest_matching_release_and_preserves_channel(self):
        self.installed_apps = [dict(IDENTITY), dict(REPOSITORY_CLIENT)]
        value = self.write_repository([
            {**OFFER, "version": "9.0", "release_serial": 3},
            {**OFFER, "version": "0.1", "release_serial": 5, "channel": "testing"},
            {**OFFER, "version": "10.0", "release_serial": 4},
            {**OFFER, "name": "not-installed", "release_serial": 99},
            {**OFFER, "release_serial": 100, "publisher": {**OFFER["publisher"], "id": "other"}}])
        result = self.mod.overview()
        repository = result["repository"]
        self.assertEqual(repository, {
            "client_installed": True, "configuration": "configured", "check": "ok",
            "availability": "checked", "identity": value["repository"], "revision": 7,
            "last_attempt": value["last_attempt"], "last_success": value["last_success"],
            "error": None, "updates": [{
                "name": "sample", "publisher": OFFER["publisher"],
                "installed": {"version": "1.2.0", "release_serial": 2},
                "offered": {"version": "0.1", "release_serial": 5, "channel": "testing"}}]})
        self.assertEqual(result["installed"], self.installed_apps)
        self.assertEqual([op for op, _ in self.calls], ["list", "display-list", "frontend-status", "storage-status"])
        self.assertEqual(self.mod._verified, {})

    def test_repository_equal_or_lower_serial_is_not_an_update(self):
        self.installed_apps = [dict(IDENTITY), dict(REPOSITORY_CLIENT)]
        for serial in (1, 2):
            with self.subTest(serial=serial):
                self.write_repository([{**OFFER, "version": "999.0", "release_serial": serial}])
                repository = self.mod.overview()["repository"]
                self.assertEqual(repository["availability"], "checked")
                self.assertEqual(repository["updates"], [])

    def test_repository_requires_exact_name_publisher_and_fingerprint(self):
        self.installed_apps = [dict(IDENTITY), dict(REPOSITORY_CLIENT)]
        for change in ({"name": "other"}, {"publisher": {**OFFER["publisher"], "id": "other"}},
                       {"publisher": {**OFFER["publisher"], "key_fingerprint": "d" * 64}}):
            with self.subTest(change=change):
                self.write_repository([{**OFFER, **change}])
                self.assertEqual(self.mod.overview()["repository"]["updates"], [])

    def test_repository_development_has_no_version_order(self):
        cases = ((2, 0, "testing", False), (0, 0, "testing", False),
                 (0, 3, "stable", True), (0, 3, "testing", True), (2, 3, "stable", True))
        for installed_serial, offered_serial, channel, expected in cases:
            with self.subTest(installed=installed_serial, offered=offered_serial, channel=channel):
                self.installed_apps = [{**IDENTITY, "version": "1.0-dev-old", "release_serial": installed_serial},
                                       dict(REPOSITORY_CLIENT)]
                self.write_repository([{**OFFER, "version": "999.0-dev-new", "release_serial": offered_serial,
                                        "channel": channel}])
                updates = self.mod.overview()["repository"]["updates"]
                self.assertEqual(bool(updates), expected)
                if expected:
                    self.assertEqual(updates[0]["offered"]["channel"], channel)

    def test_repository_does_not_guess_missing_or_invalid_core_serial(self):
        for serial in (None, "2", True, -1):
            with self.subTest(serial=serial):
                self.installed_apps = [{**IDENTITY, "release_serial": serial}, dict(REPOSITORY_CLIENT)]
                self.write_repository()
                self.assertEqual(self.mod.overview()["repository"]["updates"], [])

    def test_repository_client_not_installed_does_not_read_retained_status(self):
        self.installed_apps = [dict(IDENTITY)]
        self.write_repository()
        with patch.object(self.mod, "read_repository_status", side_effect=AssertionError("must not read")):
            repository = self.mod.overview()["repository"]
        self.assertFalse(repository["client_installed"])
        self.assertEqual(repository["availability"], "unavailable")
        self.assertEqual(repository["check"], "unavailable")
        self.assertEqual(repository["error"]["code"], "client-not-installed")
        self.assertEqual(repository["updates"], [])

    def test_repository_missing_status_keeps_installed_apps_available(self):
        self.installed_apps = [dict(IDENTITY), dict(REPOSITORY_CLIENT)]
        result = self.mod.overview()
        self.assertEqual(result["installed"], self.installed_apps)
        self.assertEqual(result["repository"]["availability"], "unavailable")
        self.assertEqual(result["repository"]["error"]["code"], "status-missing")

    def test_repository_invalid_status_keeps_apps_available(self):
        self.installed_apps = [dict(IDENTITY), dict(REPOSITORY_CLIENT)]
        valid = self.write_repository()
        invalid = [b"{", b"\xff", b"[]", json.dumps({**valid, "schema": 2}).encode(),
                   json.dumps({**valid, "schema": True}).encode(),
                   json.dumps({**valid, "packages": {}}).encode(),
                   json.dumps({**valid, "last_success": None}).encode(),
                   json.dumps({**valid, "repository": {}}).encode(),
                   json.dumps({**valid, "packages": [{**OFFER, "release_serial": True}]}).encode(),
                   json.dumps({**valid, "packages": [{**OFFER, "channel": "other"}]}).encode(),
                   json.dumps({**valid, "packages": [{**OFFER, "target": {"arch": "other"}}]}).encode()]
        for raw in invalid:
            with self.subTest(raw=raw[:80]):
                self.mod.REPOSITORY_STATUS.write_bytes(raw)
                result = self.mod.overview()
                self.assertEqual(result["installed"], self.installed_apps)
                self.assertEqual(result["repository"]["availability"], "unavailable")
                self.assertEqual(result["repository"]["error"]["code"], "status-invalid")
                self.assertEqual(result["repository"]["updates"], [])

    def test_repository_disabled_and_invalid_configuration_offer_no_updates(self):
        self.installed_apps = [dict(IDENTITY), dict(REPOSITORY_CLIENT)]
        for configuration, check, error in (("unconfigured", "disabled", None),
                                             ("invalid", "error", "Invalid repository URL")):
            with self.subTest(configuration=configuration):
                self.write_repository([], configuration=configuration, check=check, error=error,
                                      repository=None, revision=None, last_attempt=None, last_success=None)
                repository = self.mod.overview()["repository"]
                self.assertEqual(repository["configuration"], configuration)
                self.assertEqual(repository["check"], check)
                self.assertEqual(repository["availability"], "unavailable")
                self.assertEqual(repository["updates"], [])
                self.assertEqual(repository["error"]["message"] if repository["error"] else None, error)

    def test_repository_network_error_preserves_cache_without_claiming_success(self):
        self.installed_apps = [dict(IDENTITY), dict(REPOSITORY_CLIENT)]
        for offers in ([dict(OFFER)], []):
            with self.subTest(offers=bool(offers)):
                self.write_repository(offers, check="error", error="Network unreachable",
                                      last_attempt="2026-10-21T10:00:00+00:00")
                repository = self.mod.overview()["repository"]
                self.assertEqual(repository["check"], "error")
                self.assertEqual(repository["availability"], "cached")
                self.assertEqual(repository["last_success"], "2026-10-20T10:00:00+00:00")
                self.assertEqual(repository["last_attempt"], "2026-10-21T10:00:00+00:00")
                self.assertEqual(repository["error"], {"code": "repository-check-failed", "message": "Network unreachable"})
                self.assertEqual(bool(repository["updates"]), bool(offers))
        self.write_repository([], check="error", error="Network unreachable", revision=None, last_success=None)
        repository = self.mod.overview()["repository"]
        self.assertEqual(repository["availability"], "unavailable")
        self.assertEqual(repository["updates"], [])

    def test_repository_read_rejects_symlinks_including_parent_directories(self):
        self.installed_apps = [dict(IDENTITY), dict(REPOSITORY_CLIENT)]
        self.write_repository()
        path = self.mod.REPOSITORY_STATUS
        real_file = path.with_name("real.json")
        path.rename(real_file)
        path.symlink_to(real_file)
        self.assertEqual(self.mod.overview()["repository"]["error"]["code"], "status-unavailable")
        path.unlink()
        real_file.rename(path)
        directory = path.parent
        real_directory = directory.with_name("real-client")
        directory.rename(real_directory)
        directory.symlink_to(real_directory, target_is_directory=True)
        self.assertEqual(self.mod.overview()["repository"]["error"]["code"], "status-unavailable")

    def test_repository_read_is_bounded_and_does_not_block_on_fifo(self):
        self.installed_apps = [dict(IDENTITY), dict(REPOSITORY_CLIENT)]
        self.write_repository()
        path = self.mod.REPOSITORY_STATUS
        path.write_bytes(b" " * (self.mod.REPOSITORY_STATUS_LIMIT + 1))
        self.assertEqual(self.mod.overview()["repository"]["error"]["code"], "status-invalid")
        # Enforce the actual read limit even if the file grows after fstat.
        with patch.object(self.mod.os, "fstat", return_value=types.SimpleNamespace(st_mode=0o100600, st_size=0)):
            self.assertEqual(self.mod.overview()["repository"]["error"]["code"], "status-invalid")
        path.unlink()
        os.mkfifo(path)
        self.assertEqual(self.mod.overview()["repository"]["error"]["code"], "status-invalid")

    def test_overview_without_repository_preserves_all_existing_fields(self):
        self.installed_apps = [dict(IDENTITY)]
        capacity = {"available_bytes": 500, "max_package_bytes": self.mod.LIMIT,
                    "reserve_bytes": self.mod.RESERVE, "proxy_copy_reserved": True, "cache_copy_reserved": True}
        with patch.object(self.mod, "storage", return_value=capacity):
            result = self.mod.overview()
        repository = result.pop("repository")
        self.assertEqual(result, {
            "installed": [IDENTITY], "web": {"active": None}, "display": {"active": None, "apps": []},
            "packages": [], "verified_packages": [], "execution": None,
            "storage": {**capacity, "sys": {"available_bytes": 100}, "home": {"available_bytes": 200}}})
        self.assertEqual(repository["availability"], "unavailable")

    def prepare_download(self):
        self.installed_apps = [dict(IDENTITY), {**REPOSITORY_CLIENT, "storage": "home"}]
        self.download_bytes = b"fre3app-fixture" * 6000
        self.download_metadata = {**OFFER, "size": len(self.download_bytes),
                                  "sha256": hashlib.sha256(self.download_bytes).hexdigest()}
        self.download_exit = 0
        self.download_pause = 0
        self.previous_stages = set()
        self.verify_error = None
        self.verify_identity = {**IDENTITY, "version": OFFER["version"], "release_serial": OFFER["release_serial"]}
        self.write_repository([self.download_metadata])
        original_core = self.mod.run_core.side_effect

        def core(operation, *args):
            result = original_core(operation, *args)
            if operation == "verify":
                path = Path(args[0])
                self.assertEqual(path.parent, self.mod.STAGING)
                self.assertTrue(path.name.startswith(".download-"))
                self.assertEqual(path.read_bytes(), self.download_bytes)
                self.assertEqual(set(self.mod.STAGING.glob("*.fre3app")), self.previous_stages)
                if self.verify_error:
                    raise self.mod.AppError(409, "package-rejected", self.verify_error)
                result["package"] = dict(self.verify_identity)
            return result

        self.mod.run_core.side_effect = core
        patcher = patch.object(self.mod.pwd, "getpwnam", return_value=types.SimpleNamespace(pw_uid=12345, pw_gid=12346))
        patcher.start()
        self.addCleanup(patcher.stop)
        real_popen = subprocess.Popen

        def popen(command, **kwargs):
            self.assertEqual((kwargs.pop("user"), kwargs.pop("group"), kwargs.pop("extra_groups")), (12345, 12346, ()))
            self.assertEqual(command[:4], ["/usr/bin/python3", "-I",
                                          str(self.mod.CLIENT_RUNTIMES["home"] / "fre3nder-app-update/payload/client.py"), "--data"])
            self.assertEqual(command[command.index("--download") + 1], "sample")
            self.assertEqual(command[command.index("--release-serial") + 1], "3")
            self.assertEqual(kwargs["env"], {"PATH": "/usr/bin:/bin", "HOME": "/home/fre3nder",
                                            "USER": "fre3nder", "LOGNAME": "fre3nder"})
            metadata_fd = command[-1]
            code = ("import os, sys, time\n"
                    f"os.write({metadata_fd}, {json.dumps(self.download_metadata).encode()!r} + b'\\n')\n"
                    f"time.sleep({self.download_pause})\n"
                    f"sys.stdout.buffer.write({self.download_bytes!r})\n"
                    "sys.stdout.buffer.flush()\n"
                    "sys.stderr.write('fixture transfer interrupted' if " + str(self.download_exit) + " else '')\n"
                    f"sys.exit({self.download_exit})\n")
            return real_popen([sys.executable, "-c", code], **kwargs)

        patcher = patch.object(self.mod.subprocess, "Popen", side_effect=popen)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_repository_download_streams_verifies_and_becomes_normal_staged_update(self):
        self.prepare_download()
        job = self.mod.start_download({"name": "sample", "release_serial": 3})
        receipt = self.wait()
        self.assertEqual(receipt["state"], "succeeded", receipt)
        path = self.mod.staged(job["package_id"])
        self.assertEqual(path.read_bytes(), self.download_bytes)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.mod._verified[job["package_id"]], self.verify_identity)
        self.assertEqual(receipt["result"]["package_id"], job["package_id"])
        self.assertFalse(list(path.parent.glob("*.part")))
        self.assertFalse(any(op in ("install", "update") for op, _ in self.calls))
        self.mod.start("update", {"package_id": job["package_id"], "name": "sample"})
        self.assertEqual(self.wait()["state"], "succeeded")
        self.assertIn(("update", (str(path),)), self.calls)

    def test_repository_download_integrity_and_core_failures_clean_staging(self):
        self.prepare_download()
        original_metadata = dict(self.download_metadata)
        retained = self.mod.stage_dir() / ("f" * 32 + ".fre3app")
        retained.write_bytes(b"already verified package")
        retained.chmod(0o600)
        self.previous_stages = {retained}
        for failure in ("sha256", "size", "oversized", "process", "verify", "identity", "metadata"):
            with self.subTest(failure=failure):
                self.download_metadata = dict(original_metadata)
                self.download_exit = 1 if failure == "process" else 0
                self.verify_error = "fixture publisher not trusted" if failure == "verify" else None
                self.verify_identity["version"] = "other" if failure == "identity" else OFFER["version"]
                if failure == "sha256":
                    self.download_metadata["sha256"] = "0" * 64
                if failure == "size":
                    self.download_metadata["size"] += 1
                if failure == "oversized":
                    self.download_metadata["size"] -= 1
                if failure == "metadata":
                    self.download_metadata["version"] = "other"
                self.mod._verified["f" * 32] = dict(IDENTITY)
                self.mod.start_download({"name": "sample", "release_serial": 3})
                receipt = self.wait()
                self.assertEqual(receipt["state"], "failed", receipt)
                self.assertEqual(list(self.mod.stage_dir().iterdir()), [retained])
                self.assertEqual(retained.read_bytes(), b"already verified package")
                self.assertEqual(self.mod._verified, {"f" * 32: IDENTITY})
        self.assertFalse(any(op in ("install", "update") for op, _ in self.calls))

    def test_repository_download_timeout_kills_client_and_removes_partial_file(self):
        self.prepare_download()
        self.download_pause = 2
        self.mod.DOWNLOAD_TIMEOUT = 0.1
        self.mod.start_download({"name": "sample", "release_serial": 3})
        receipt = self.wait()
        self.assertEqual(receipt["state"], "failed", receipt)
        self.assertEqual(list(self.mod.stage_dir().iterdir()), [])
        self.assertEqual(self.mod._verified, {})

    def test_repository_download_rejects_parameters_and_unoffered_or_missing_client(self):
        for payload in ({}, {"name": "../sample", "release_serial": 3},
                        {"name": "sample", "release_serial": 0}, {"name": "sample", "release_serial": True},
                        {"name": "sample", "release_serial": "3"},
                        {"name": "sample", "release_serial": 3, "url": "https://example.invalid/"}):
            with self.subTest(payload=payload), self.assertRaises(self.mod.AppError):
                self.mod.start_download(payload)
        self.installed_apps = [dict(IDENTITY)]
        self.mod.start_download({"name": "sample", "release_serial": 3})
        self.assertEqual(self.wait()["error"]["code"], "update-not-offered")
        self.prepare_download()
        for serial in (2, 4):
            self.mod.start_download({"name": "sample", "release_serial": serial})
            self.assertEqual(self.wait()["error"]["code"], "update-not-offered")

    def test_repository_download_capacity_omits_only_proxy_buffer(self):
        self.prepare_download()
        size = len(self.download_bytes)
        directory = self.mod.stage_dir()
        for free, accepted in ((self.mod.RESERVE + 2 * size - 1, False), (self.mod.RESERVE + 2 * size, True)):
            with patch.object(self.mod.os, "statvfs", return_value=types.SimpleNamespace(f_bavail=free, f_frsize=1)):
                if accepted:
                    self.assertFalse(self.mod.storage(size, size, proxy_copy=False)["proxy_copy_reserved"])
                    with self.assertRaises(self.mod.AppError):
                        self.mod.storage(size, size)
                self.mod.start_download({"name": "sample", "release_serial": 3})
                receipt = self.wait()
                self.assertEqual(receipt["state"], "succeeded" if accepted else "failed", receipt)
                if not accepted:
                    self.assertEqual(receipt["error"]["code"], "insufficient-space")
                    self.assertEqual(list(directory.iterdir()), [])

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
        self.mod.APP_OTA_LOCK = self.state / "ota/write.lock"

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

    def test_repository_download_and_cli_share_existing_ota_app_lock(self):
        with self.active_cli():
            self.mod.start_download({"name": "sample", "release_serial": 3})
            receipt = self.wait_apps()
            self.assertEqual(receipt["state"], "failed", receipt)
            self.assertEqual(receipt["error"]["code"], "apps-busy")
        entered, release = threading.Event(), threading.Event()
        identity = {**IDENTITY, "version": OFFER["version"], "release_serial": 3}

        def stream(job, *args):
            entered.set()
            release.wait(3)
            return {"package": identity, "package_id": job["package_id"]}

        with patch.object(self.mod, "installed", return_value=[IDENTITY, REPOSITORY_CLIENT]), \
                patch.object(self.mod, "repository_status", return_value={"error": None,
                    "updates": self.mod.repository_updates([IDENTITY], [OFFER])}), \
                patch.object(self.mod.pwd, "getpwnam", return_value=types.SimpleNamespace(pw_uid=12345, pw_gid=12346)), \
                patch.object(self.mod, "stream_download", side_effect=stream):
            self.mod.start_download({"name": "sample", "release_serial": 3})
            try:
                self.assertTrue(entered.wait(1))
                result = self.cli_run("display-disable")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("another OTA/app operation is active", result.stdout)
                self.assertTrue(self.ota_status()["busy"])
            finally:
                release.set()
                receipt = self.wait_apps()
        self.assertEqual(receipt["state"], "succeeded", receipt)
        self.assertFalse(self.ota_status()["busy"])

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
