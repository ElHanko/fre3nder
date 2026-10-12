#!/usr/bin/env python3
"""Host-side tests for the Fre3nder management API."""

import grp
import errno
import http.client
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import socket
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
DAEMON = (
    ROOT
    / "configs/x2000/rootfs-overlay/usr/libexec/fre3nder/managementd"
)


def load_daemon():
    loader = importlib.machinery.SourceFileLoader(
        "fre3nder_managementd_test",
        str(DAEMON),
    )
    spec = importlib.util.spec_from_loader(
        "fre3nder_managementd_test",
        loader,
    )
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path):
        super().__init__("localhost", timeout=2)
        self.socket_path = str(socket_path)

    def connect(self):
        self.sock = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
        )
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


class ManagementApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir(mode=0o700)
        self.runtime = self.root / "run-management"
        self.runtime.mkdir(mode=0o700)
        self.root_status = self.root / "root-status"
        self.root_status.write_text("active\n")
        self.version = self.root / "VERSION"
        self.version.write_text("2026.5.a\n")
        self.web_status = self.root / "web-status"
        self.web_status.write_text("stopped\n")
        self.web_service = self.root / "web-service"
        self.web_service.write_text(
            "#!/bin/sh\n"
            "printf 'active\\n' > \"$FRE3NDER_TEST_WEB_STATUS\"\n"
        )
        self.web_service.chmod(0o755)
        os.environ["FRE3NDER_TEST_WEB_STATUS"] = str(
            self.web_status
        )
        self.addCleanup(
            os.environ.pop,
            "FRE3NDER_TEST_WEB_STATUS",
            None,
        )

        self.daemon = load_daemon()
        self.daemon.SOCKET_PATH = self.runtime / "api.sock"
        self.daemon.MAINTENANCE_STATE = (
            self.home / ".fre3nder/maintenance/enabled"
        )
        self.daemon.VERSION_FILE = self.version
        self.daemon.ROOT_STATUS = self.root_status
        self.daemon.WEB_STATUS = self.web_status
        self.daemon.WEB_SERVICE = self.web_service
        self.daemon.MANAGEMENT_GROUP = grp.getgrgid(
            os.getegid()
        ).gr_name
        self.daemon.ADMIN_UID_OVERRIDE = str(os.getuid())
        self.daemon.WEB_UID_OVERRIDE = str(os.getuid())
        self.daemon.clear_web_auth()

        self.daemon.prepare_socket()
        self.server = self.daemon.Server(
            str(self.daemon.SOCKET_PATH),
            self.daemon.Handler,
        )
        group = grp.getgrgid(os.getegid())
        os.chown(self.daemon.SOCKET_PATH, os.geteuid(), group.gr_gid)
        os.chmod(self.daemon.SOCKET_PATH, 0o660)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.daemon.SOCKET_PATH.unlink(missing_ok=True)

    def request_full(self, method, path, body=None, headers=None):
        connection = UnixHTTPConnection(self.daemon.SOCKET_PATH)
        connection.request(
            method,
            path,
            body=body,
            headers=headers or {},
        )
        response = connection.getresponse()
        response_body = response.read().decode("utf-8")
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, response_body, response_headers

    def request(self, method, path):
        status, body, _headers = self.request_full(method, path)
        return status, body

    def browser_headers(self, extra=None):
        headers = {
            "Host": "printer.test:8081",
            "Origin": "http://printer.test:8081",
        }
        headers.update(extra or {})
        return headers

    def test_system_and_default_maintenance_status(self):
        status, body = self.request(
            "GET",
            "/fre3nder/api/v1/system",
        )
        self.assertEqual(status, 200)
        self.assertIn('"version":"2026.5.a"', body)
        self.assertIn('"root_status":"active"', body)

        status, body = self.request(
            "GET",
            "/fre3nder/api/v1/maintenance",
        )
        self.assertEqual(status, 200)
        self.assertIn('"enabled":false', body)

    def test_enable_disable_is_persistent_and_refreshes_web(self):
        status, body = self.request(
            "POST",
            "/fre3nder/api/v1/maintenance/enable",
        )
        self.assertEqual(status, 200)
        self.assertIn('"enabled":true', body)
        self.assertEqual(
            self.daemon.MAINTENANCE_STATE.read_text(),
            "enabled\n",
        )
        self.assertEqual(self.web_status.read_text(), "active\n")

        status, body = self.request(
            "POST",
            "/fre3nder/api/v1/maintenance/disable",
        )
        self.assertEqual(status, 200)
        self.assertIn('"enabled":false', body)
        self.assertFalse(self.daemon.MAINTENANCE_STATE.exists())

    def test_invalid_state_fails_closed(self):
        self.daemon.MAINTENANCE_STATE.parent.mkdir(
            parents=True,
        )
        self.daemon.MAINTENANCE_STATE.write_text("maybe\n")
        self.daemon.MAINTENANCE_STATE.chmod(0o644)
        status, body = self.request(
            "GET",
            "/fre3nder/api/v1/maintenance",
        )
        self.assertEqual(status, 500)
        self.assertIn('"code":"internal-error"', body)
        self.assertNotIn(str(self.daemon.MAINTENANCE_STATE), body)

    def test_unsafe_state_mode_fails_closed(self):
        self.daemon.MAINTENANCE_STATE.parent.mkdir(
            parents=True,
        )
        self.daemon.MAINTENANCE_STATE.write_text("enabled\n")
        self.daemon.MAINTENANCE_STATE.chmod(0o666)
        status, body = self.request(
            "GET",
            "/fre3nder/api/v1/maintenance",
        )
        self.assertEqual(status, 500)
        self.assertIn('"code":"internal-error"', body)

    def test_mutation_rejects_non_admin_peer(self):
        handler = object.__new__(
            self.daemon.Handler
        )
        handler.peer_uid = lambda: os.getuid() + 10000
        with self.assertRaises(self.daemon.ManagementError) as raised:
            handler.require_admin()
        self.assertEqual(raised.exception.status, 403)
        self.assertEqual(raised.exception.code, "forbidden")

    def enable_maintenance_and_pair(self):
        status, _body = self.request(
            "POST",
            "/fre3nder/api/v1/maintenance/enable",
        )
        self.assertEqual(status, 200)

        status, body = self.request(
            "POST",
            "/fre3nder/api/v1/maintenance/unlock",
        )
        self.assertEqual(status, 200)
        code = json.loads(body)["auth"]["pairing_code"]
        self.assertRegex(code, r"^\d{6}$")

        payload = json.dumps({"code": code}).encode("utf-8")
        status, body, headers = self.request_full(
            "POST",
            "/fre3nder/api/v1/auth/unlock",
            body=payload,
            headers=self.browser_headers(
                {"Content-Type": "application/json"}
            ),
        )
        self.assertEqual(status, 200, body)
        auth = json.loads(body)["auth"]
        self.assertTrue(auth["authenticated"])
        csrf = auth["csrf_token"]
        self.assertIsInstance(csrf, str)
        self.assertTrue(csrf)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        return cookie, csrf

    def test_browser_pairing_session_and_browser_lock(self):
        status, body, _headers = self.request_full(
            "GET",
            "/fre3nder/api/v1/auth/session",
        )
        self.assertEqual(status, 200)
        self.assertIn('"authenticated":false', body)

        cookie, csrf = self.enable_maintenance_and_pair()

        status, body, _headers = self.request_full(
            "GET",
            "/fre3nder/api/v1/auth/session",
            headers={"Cookie": cookie},
        )
        self.assertEqual(status, 200)
        self.assertIn('"authenticated":true', body)

        status, body, headers = self.request_full(
            "POST",
            "/fre3nder/api/v1/auth/lock",
            headers=self.browser_headers({
                "Cookie": cookie,
                "X-Fre3nder-CSRF": csrf,
            }),
        )
        self.assertEqual(status, 200)
        self.assertIn('"authenticated":false', body)
        self.assertIn("Max-Age=0", headers["Set-Cookie"])

        status, body, _headers = self.request_full(
            "GET",
            "/fre3nder/api/v1/auth/session",
            headers={"Cookie": cookie},
        )
        self.assertEqual(status, 200)
        self.assertIn('"authenticated":false', body)

    def test_pairing_is_one_time_and_has_bounded_attempts(self):
        status, _body = self.request(
            "POST",
            "/fre3nder/api/v1/maintenance/enable",
        )
        self.assertEqual(status, 200)

        status, body = self.request(
            "POST",
            "/fre3nder/api/v1/maintenance/unlock",
        )
        self.assertEqual(status, 200)
        code = json.loads(body)["auth"]["pairing_code"]

        wrong = b'{"code":"000000"}'
        if code == "000000":
            wrong = b'{"code":"999999"}'

        for _ in range(self.daemon.PAIRING_MAX_ATTEMPTS):
            status, _body, _headers = self.request_full(
                "POST",
                "/fre3nder/api/v1/auth/unlock",
                body=wrong,
                headers=self.browser_headers({"Content-Type": "application/json"}),
            )
            self.assertEqual(status, 401)

        payload = json.dumps({"code": code}).encode("utf-8")
        status, _body, _headers = self.request_full(
            "POST",
            "/fre3nder/api/v1/auth/unlock",
            body=payload,
            headers=self.browser_headers({"Content-Type": "application/json"}),
        )
        self.assertEqual(status, 401)

    def test_root_lock_and_maintenance_disable_revoke_sessions(self):
        cookie, csrf = self.enable_maintenance_and_pair()

        status, _body = self.request(
            "POST",
            "/fre3nder/api/v1/maintenance/lock",
        )
        self.assertEqual(status, 200)

        status, body, _headers = self.request_full(
            "GET",
            "/fre3nder/api/v1/auth/session",
            headers={"Cookie": cookie},
        )
        self.assertEqual(status, 200)
        self.assertIn('"authenticated":false', body)

        cookie, csrf = self.enable_maintenance_and_pair()
        status, _body = self.request(
            "POST",
            "/fre3nder/api/v1/maintenance/disable",
        )
        self.assertEqual(status, 200)

        status, body, _headers = self.request_full(
            "GET",
            "/fre3nder/api/v1/auth/session",
            headers={"Cookie": cookie},
        )
        self.assertEqual(status, 200)
        self.assertIn('"authenticated":false', body)

    def test_unlock_requires_enabled_maintenance(self):
        status, body = self.request(
            "POST",
            "/fre3nder/api/v1/maintenance/unlock",
        )
        self.assertEqual(status, 409)
        self.assertIn('"code":"maintenance-disabled"', body)

    def test_browser_unlock_rejects_port80_origin(self):
        status, _body = self.request(
            "POST",
            "/fre3nder/api/v1/maintenance/enable",
        )
        self.assertEqual(status, 200)
        status, body = self.request(
            "POST",
            "/fre3nder/api/v1/maintenance/unlock",
        )
        self.assertEqual(status, 200)
        code = json.loads(body)["auth"]["pairing_code"]
        payload = json.dumps({"code": code}).encode("utf-8")

        status, body, _headers = self.request_full(
            "POST",
            "/fre3nder/api/v1/auth/unlock",
            body=payload,
            headers={
                "Host": "printer.test:8081",
                "Origin": "http://printer.test",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(status, 403)
        self.assertIn('"code":"origin-invalid"', body)

    def test_browser_lock_requires_csrf(self):
        cookie, csrf = self.enable_maintenance_and_pair()

        status, body, _headers = self.request_full(
            "POST",
            "/fre3nder/api/v1/auth/lock",
            headers=self.browser_headers({"Cookie": cookie}),
        )
        self.assertEqual(status, 403)
        self.assertIn('"code":"csrf-invalid"', body)

        status, body, _headers = self.request_full(
            "POST",
            "/fre3nder/api/v1/auth/lock",
            headers=self.browser_headers({
                "Cookie": cookie,
                "X-Fre3nder-CSRF": csrf,
            }),
        )
        self.assertEqual(status, 200)
        self.assertIn('"authenticated":false', body)

    def test_pairing_and_sessions_expire(self):
        status, _body = self.request(
            "POST",
            "/fre3nder/api/v1/maintenance/enable",
        )
        self.assertEqual(status, 200)
        status, body = self.request(
            "POST",
            "/fre3nder/api/v1/maintenance/unlock",
        )
        self.assertEqual(status, 200)
        code = json.loads(body)["auth"]["pairing_code"]
        self.daemon._pairing["expires"] = 0
        payload = json.dumps({"code": code}).encode("utf-8")
        status, _body, _headers = self.request_full(
            "POST",
            "/fre3nder/api/v1/auth/unlock",
            body=payload,
            headers=self.browser_headers({"Content-Type": "application/json"}),
        )
        self.assertEqual(status, 401)

        cookie, _csrf = self.enable_maintenance_and_pair()
        token = cookie.split("=", 1)[1]
        self.daemon._sessions[token]["last_seen"] -= (
            self.daemon.SESSION_IDLE_SECONDS + 1
        )
        status, body, _headers = self.request_full(
            "GET",
            "/fre3nder/api/v1/auth/session",
            headers={"Cookie": cookie},
        )
        self.assertEqual(status, 200)
        self.assertIn('"authenticated":false', body)

        cookie, _csrf = self.enable_maintenance_and_pair()
        token = cookie.split("=", 1)[1]
        self.daemon._sessions[token]["created"] -= (
            self.daemon.SESSION_MAX_SECONDS + 1
        )
        status, body, _headers = self.request_full(
            "GET",
            "/fre3nder/api/v1/auth/session",
            headers={"Cookie": cookie},
        )
        self.assertEqual(status, 200)
        self.assertIn('"authenticated":false', body)

    def test_unknown_endpoint_is_rejected(self):
        status, body = self.request(
            "GET",
            "/fre3nder/api/v1/nope",
        )
        self.assertEqual(status, 404)
        self.assertIn('"code":"not-found"', body)

    def setup_ota(self):
        self.daemon.OTA_PACKAGES = self.root / "ota/packages"
        self.daemon.OTA_PACKAGES.mkdir(parents=True, mode=0o755)
        self.daemon.OTA_EXECUTION = self.runtime / "ota-execution.json"
        self.core_state = {"transaction": None, "activation": None, "known_good": None, "busy": False}
        self.core_calls = []
        self.block_core = None

        def core(operation, arguments=()):
            if operation == "status":
                return {"api_version": 1, "ok": True, "operation": operation, **self.core_state}
            self.core_calls.append((operation, arguments))
            if self.block_core:
                self.block_core.wait(5)
            return {"api_version": 1, "ok": True, "operation": operation, "package": {"version": "fixture"}}

        mocked = patch.object(self.daemon, "run_ota_core", side_effect=core)
        self.addCleanup(mocked.stop)
        mocked.start()
        cookie, csrf = self.enable_maintenance_and_pair()
        return self.browser_headers({"Cookie": cookie, "X-Fre3nder-CSRF": csrf})

    def ota_request(self, operation, payload=None, headers=None):
        return self.request_full(
            "POST", "/fre3nder/api/v1/ota/" + operation,
            body=json.dumps(payload or {}).encode(),
            headers={**(headers or {}), "Content-Type": "application/json"},
        )

    def upload(self, body, headers, extra=None):
        return self.request_full(
            "POST", "/fre3nder/api/v1/ota/upload", body=body,
            headers={**headers, "Content-Type": "application/octet-stream", "X-Fre3nder-Filename": "fixture.ota", **(extra or {})},
        )

    def wait_execution(self):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with self.daemon._ota_lock:
                state = self.daemon._execution
            if state and state["state"] not in ("running", "uploading"):
                return state
            time.sleep(0.01)
        self.fail("Core operation did not complete")

    def test_streaming_upload_publishes_atomically_and_verifies(self):
        headers = self.setup_ota()
        self.block_core = threading.Event()
        self.addCleanup(self.block_core.set)
        body = b"package fixture" * 20000
        status, response, _ = self.upload(body, headers)
        self.assertEqual(status, 202, response)
        accepted = json.loads(response)["execution"]
        path = self.daemon.package_path(accepted["package_id"])
        self.assertEqual(path.read_bytes(), body)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertFalse(list(path.parent.glob("*.part")))
        self.assertEqual(accepted["operation"], "verify")
        status, response, _ = self.request_full("GET", "/fre3nder/api/v1/ota/status", headers=headers)
        self.assertEqual(status, 200)
        state = json.loads(response)["ota"]
        self.assertEqual(state["execution"]["id"], accepted["id"])
        self.assertEqual(state["execution"]["state"], "running")
        self.assertEqual(state["packages"][0]["id"], accepted["package_id"])
        # A reload fetches the same session/CSRF and execution, without repeating it.
        status, auth, _ = self.request_full("GET", "/fre3nder/api/v1/auth/session", headers=headers)
        self.assertEqual(json.loads(auth)["auth"]["csrf_token"], headers["X-Fre3nder-CSRF"])
        self.block_core.set()
        self.assertEqual(self.wait_execution()["state"], "succeeded")
        self.assertEqual(self.core_calls, [("verify", [str(path)])])

    def test_upload_signed_package_runs_real_verifier(self):
        headers = self.setup_ota()
        loader = importlib.machinery.SourceFileLoader("ota_upload_fixture", str(ROOT / "tests/test-x2000-ota-verify"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        fixture = importlib.util.module_from_spec(spec)
        loader.exec_module(fixture)
        private_key, public_key = fixture.generate_keys(self.root)
        source = self.root / "signed.ota"
        fixture.make_package(source, private_key, public_key)
        fallback = self.daemon.run_ota_core

        def core(operation, arguments=()):
            if operation == "verify":
                return fixture.module.verify_response(arguments[0], public_key)
            return fallback(operation, arguments)

        with patch.object(self.daemon, "run_ota_core", side_effect=core):
            status, body, _ = self.upload(source.read_bytes(), headers)
            self.assertEqual(status, 202, body)
            completed = self.wait_execution()
            self.assertEqual(completed["state"], "succeeded")
            self.assertEqual(completed["result"]["package"]["status"], "valid")

    def test_failed_core_is_reported_without_automatic_retry(self):
        headers = self.setup_ota()
        package_id = "a" * 32
        path = self.daemon.OTA_PACKAGES / (package_id + ".ota")
        path.write_bytes(b"fixture")
        path.chmod(0o600)
        fallback = self.daemon.run_ota_core

        def core(operation, arguments=()):
            if operation == "preflight":
                raise self.daemon.ManagementError(409, "ota-operation-failed", "fixture preflight failure")
            return fallback(operation, arguments)

        with patch.object(self.daemon, "run_ota_core", side_effect=core) as mocked:
            status, _, _ = self.ota_request("preflight", {"package_id": package_id}, headers)
            self.assertEqual(status, 202)
            completed = self.wait_execution()
            self.assertEqual(completed["state"], "failed")
            self.assertEqual(completed["error"]["message"], "fixture preflight failure")
            for _ in range(2):
                status, body, _ = self.request_full("GET", "/fre3nder/api/v1/ota/status", headers=headers)
                self.assertEqual(json.loads(body)["ota"]["execution"]["state"], "failed")
            self.assertEqual(sum(call.args[0] == "preflight" for call in mocked.call_args_list), 1)

    def test_upload_limits_types_space_and_paths(self):
        headers = self.setup_ota()
        cases = [
            ({"Content-Length": str(96 * 1024 * 1024 + 1)}, 413),
            ({"Content-Length": "0"}, 413),
            ({"Content-Type": "multipart/form-data"}, 415),
            ({"X-Fre3nder-Filename": "file.fre3app"}, 400),
            ({"X-Fre3nder-Filename": "..%2Ffile.ota"}, 400),
            ({"Transfer-Encoding": "chunked"}, 400),
        ]
        for extra, expected in cases:
            with self.subTest(extra=extra):
                status, body, _ = self.upload(b"x", headers, extra)
                self.assertEqual(status, expected, body)
        with patch.object(self.daemon.os, "statvfs", return_value=types.SimpleNamespace(f_bavail=1, f_frsize=4096)):
            status, _, _ = self.upload(b"x", headers)
            self.assertEqual(status, 507)
        self.assertFalse(list(self.daemon.OTA_PACKAGES.iterdir()))
        self.assertFalse(self.core_calls)

    def test_upload_early_eof_cleans_staging(self):
        headers = self.setup_ota()
        connection = UnixHTTPConnection(self.daemon.SOCKET_PATH)
        connection.connect()
        connection.putrequest("POST", "/fre3nder/api/v1/ota/upload", skip_host=True)
        for key, value in {**headers, "Content-Type": "application/octet-stream", "X-Fre3nder-Filename": "fixture.ota", "Content-Length": "10000"}.items():
            connection.putheader(key, value)
        connection.endheaders(b"partial")
        connection.sock.shutdown(socket.SHUT_WR)
        response = connection.getresponse()
        self.assertEqual(response.status, 400, response.read())
        connection.close()
        self.assertFalse(list(self.daemon.OTA_PACKAGES.iterdir()))
        self.assertFalse(self.core_calls)

    def test_upload_enospc_collision_and_symlinks(self):
        headers = self.setup_ota()
        with patch.object(self.daemon.os, "fsync", side_effect=[None, OSError(errno.ENOSPC, "fixture full"), None]):
            status, body, _ = self.upload(b"body", headers)
            self.assertEqual(status, 507, body)
        self.assertFalse(list(self.daemon.OTA_PACKAGES.iterdir()))
        package_id = "a" * 32
        path = self.daemon.OTA_PACKAGES / (package_id + ".ota")
        path.write_bytes(b"original")
        with patch.object(self.daemon.secrets, "token_hex", return_value=package_id):
            status, body, _ = self.upload(b"replacement", headers)
            self.assertEqual(status, 400, body)
        self.assertEqual(path.read_bytes(), b"original")
        path.unlink()
        path.symlink_to(self.version)
        status, _, _ = self.ota_request("verify", {"package_id": package_id}, headers)
        self.assertNotEqual(status, 202)
        path.unlink()
        self.daemon.OTA_PACKAGES.rmdir()
        self.daemon.OTA_PACKAGES.symlink_to(self.home, target_is_directory=True)
        status, _, _ = self.upload(b"body", headers)
        self.assertEqual(status, 409)

    def test_ota_requires_paired_session_csrf_origin_and_web_peer(self):
        headers = self.setup_ota()
        for extra, expected in [
            ({"Cookie": ""}, 401), ({"X-Fre3nder-CSRF": "bad"}, 403),
            ({"Origin": "http://printer.test"}, 403),
            ({"Host": "other.test:8081"}, 403),
        ]:
            status, body, _ = self.upload(b"body", {**headers, **extra})
            self.assertEqual(status, expected, body)
        with patch.object(self.daemon, "web_uids", return_value=set()):
            status, _, _ = self.upload(b"body", headers)
            self.assertEqual(status, 403)
        status, _, _ = self.request_full("GET", "/fre3nder/api/v1/ota/status")
        self.assertEqual(status, 401)
        self.daemon.clear_web_auth()
        status, _, _ = self.upload(b"body", headers)
        self.assertEqual(status, 401)
        self.assertFalse(self.core_calls)

    def test_fixed_arguments_transaction_and_conflicts(self):
        headers = self.setup_ota()
        package_id = "a" * 32
        transaction_id = "b" * 32
        path = self.daemon.OTA_PACKAGES / (package_id + ".ota")
        path.write_bytes(b"fixture")
        path.chmod(0o600)
        self.block_core = threading.Event()
        self.addCleanup(self.block_core.set)
        status, body, _ = self.ota_request("write", {"package_id": package_id, "transaction_id": transaction_id}, headers)
        self.assertEqual(status, 202, body)
        status, _, _ = self.ota_request("write", {"package_id": package_id, "transaction_id": transaction_id}, headers)
        self.assertEqual(status, 409)
        status, _, _ = self.upload(b"body", headers)
        self.assertEqual(status, 409)
        self.block_core.set()
        self.wait_execution()
        self.assertEqual(self.core_calls, [("write", [str(path), transaction_id])])
        status, _, _ = self.ota_request("backup-plan", {"package_id": package_id, "home": "home", "sys": "usb"}, headers)
        self.assertEqual(status, 400)
        status, _, _ = self.ota_request("verify", {"package_id": package_id, "path": "/dev/fixture"}, headers)
        self.assertEqual(status, 400)
        self.core_state["busy"] = True
        status, _, _ = self.ota_request("verify", {"package_id": package_id}, headers)
        self.assertEqual(status, 409)

    def test_lost_browser_response_does_not_stop_core(self):
        headers = self.setup_ota()
        self.block_core = threading.Event()
        self.addCleanup(self.block_core.set)
        package_id = "a" * 32
        path = self.daemon.OTA_PACKAGES / (package_id + ".ota")
        path.write_bytes(b"fixture")
        path.chmod(0o600)
        connection = UnixHTTPConnection(self.daemon.SOCKET_PATH)
        connection.request("POST", "/fre3nder/api/v1/ota/verify", body=json.dumps({"package_id": package_id}), headers={**headers, "Content-Type": "application/json"})
        connection.close()
        self.block_core.set()
        self.assertEqual(self.wait_execution()["state"], "succeeded")
        self.assertEqual(len(self.core_calls), 1)

    def test_core_adapter_response_validation_and_errors(self):
        # Test the real process adapter without invoking an OTA operation.
        for stdout, code, expected in [
            ("not json", 0, "ota-core-unavailable"),
            ('{"api_version":2,"ok":true,"operation":"write"}', 0, "ota-core-invalid"),
            ('{"api_version":1,"ok":false,"operation":"write","error":"fixture failure"}', 1, "ota-operation-failed"),
        ]:
            with patch.object(self.daemon.subprocess, "run", return_value=types.SimpleNamespace(stdout=stdout, returncode=code)):
                with self.assertRaises(self.daemon.ManagementError) as raised:
                    self.daemon.run_ota_core("write", ["fixture.ota", "opaque-id"])
                self.assertEqual(raised.exception.code, expected)

    def test_restart_reports_unknown_and_removes_incomplete_upload(self):
        self.setup_ota()
        self.daemon.store_execution({"id": "a" * 32, "state": "running", "operation": "write"})
        staging = self.daemon.OTA_PACKAGES / ".upload-fixture.part"
        staging.write_bytes(b"incomplete")
        self.daemon._execution = None
        self.daemon.restore_execution()
        self.assertEqual(self.daemon._execution["state"], "unknown")
        self.assertFalse(staging.exists())
        with self.assertRaises(self.daemon.ManagementError):
            self.daemon.require_ota_idle()


if __name__ == "__main__":
    unittest.main()
