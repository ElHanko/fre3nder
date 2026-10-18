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

    def test_system_details_require_root_or_a_paired_web_peer(self):
        path = "/fre3nder/api/v1/system/details"
        private = {"platform": {"hostname": "printer.test"}, "network": {"interfaces": []}}
        with patch.object(self.daemon, "mutation_uids", return_value={0}), \
                patch.object(self.daemon, "web_uids", return_value={41000}), \
                patch.object(self.daemon.system_info, "snapshot", return_value=private) as snapshot:
            with patch.object(self.daemon.Handler, "peer_uid", return_value=41001):
                status, _ = self.request("GET", path)
                self.assertEqual(status, 403)
            with patch.object(self.daemon.Handler, "peer_uid", return_value=41000):
                status, _ = self.request("GET", path)
                self.assertEqual(status, 401)
            snapshot.assert_not_called()
            with patch.object(self.daemon.Handler, "peer_uid", return_value=0):
                status, body = self.request("GET", path)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["system"], private)
            self.daemon.set_maintenance(True)
            token = self.daemon.create_web_session()
            headers = {"Cookie": f"fre3nder_admin={token}"}
            with patch.object(self.daemon.Handler, "peer_uid", return_value=41001):
                status, _, _ = self.request_full("GET", path, headers=headers)
                self.assertEqual(status, 403, "a session must not authorize another local UID")
            with patch.object(self.daemon.Handler, "peer_uid", return_value=41000):
                status, body, _ = self.request_full("GET", path, headers=headers)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["operation"], "system-details")
                self.daemon._sessions[token]["last_seen"] -= self.daemon.SESSION_IDLE_SECONDS + 1
                status, _, _ = self.request_full("GET", path, headers=headers)
                self.assertEqual(status, 401)
                token = self.daemon.create_web_session()
                self.daemon.set_maintenance(False)
                status, _, _ = self.request_full("GET", path, headers={"Cookie": f"fre3nder_admin={token}"})
                self.assertEqual(status, 401)

    def test_system_details_do_not_expand_public_status_or_mutate(self):
        with patch.object(self.daemon.system_info, "snapshot", return_value={"platform": {}}), \
                patch.object(self.daemon, "refresh_web") as refresh, \
                patch.object(self.daemon, "set_maintenance") as set_maintenance, \
                patch.object(self.daemon.apps, "overview") as apps, \
                patch.object(self.daemon, "ota_status") as ota:
            status, body = self.request("GET", "/fre3nder/api/v1/system/details")
            self.assertEqual(status, 200, body)
            self.assertFalse(self.daemon.MAINTENANCE_STATE.exists())
            for action in (refresh, set_maintenance, apps, ota):
                action.assert_not_called()
            status, body = self.request("GET", "/fre3nder/api/v1/system")
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["system"], {"version": "2026.5.a", "root_status": "active"})
            status, _ = self.request("POST", "/fre3nder/api/v1/system/details")
            self.assertEqual(status, 404)

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

    def test_repeated_enable_does_not_refresh_active_web(self):
        status, _body = self.request(
            "POST",
            "/fre3nder/api/v1/maintenance/enable",
        )
        self.assertEqual(status, 200)

        with patch.object(
            self.daemon, "refresh_web", wraps=self.daemon.refresh_web,
        ) as refresh:
            status, body = self.request(
                "POST",
                "/fre3nder/api/v1/maintenance/enable",
            )
            refresh.assert_not_called()

        self.assertEqual(status, 200)
        self.assertEqual(
            json.loads(body)["maintenance"],
            {"enabled": True, "web_status": "active"},
        )

    def test_enable_refreshes_web_unless_already_enabled_and_active(self):
        for enabled, web_status in (
            (False, "active"),
            (True, "stopped"),
            (True, "unknown"),
        ):
            with self.subTest(enabled=enabled, web_status=web_status):
                self.daemon.set_maintenance(enabled)
                self.web_status.write_text(web_status + "\n")
                with patch.object(
                    self.daemon, "refresh_web", wraps=self.daemon.refresh_web,
                ) as refresh:
                    status, _body = self.request(
                        "POST",
                        "/fre3nder/api/v1/maintenance/enable",
                    )
                    refresh.assert_called_once_with()
                self.assertEqual(status, 200)
                self.assertEqual(self.web_status.read_text(), "active\n")

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
        self.daemon.OTA_UPLOAD_BUFFER = self.root / "home/.tmp/fre3nder/lighttpd"
        self.daemon.OTA_UPLOAD_BUFFER.mkdir(parents=True, mode=0o700)
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

    def setup_apps(self):
        headers = self.setup_ota()
        apps = self.daemon.apps
        apps.STAGING = self.root / "home/.tmp/fre3nder/uploads"
        apps.STAGING.parent.chmod(0o700)
        apps.EXECUTION_FILE = self.runtime / "apps-execution.json"
        self.app_calls = []
        self.block_app = None
        self.app_identity = {"name": "sample", "version": "2.0", "publisher": "trusted",
                             "storage": "home",
                             "release_serial": 2, "fingerprint": "a" * 64,
                             "web_frontend": False, "display_frontend": False, "display_api": None}

        def core(operation, *args):
            self.app_calls.append((operation, args))
            if operation in apps.OPERATIONS and self.block_app:
                self.block_app.wait(5)
            result = {"api_version": 1, "ok": True, "operation": operation}
            if operation == "verify":
                result["package"] = dict(self.app_identity)
            elif operation == "list":
                result["apps"] = [dict(self.app_identity)]
            elif operation == "display-list":
                result.update(active=None, apps=[])
            elif operation == "frontend-status":
                result["frontend"] = {"active": None}
            elif operation == "status":
                result["app"] = {**self.app_identity, "running": True}
            elif operation == "storage-status":
                result["storage"] = {"sys": {"available_bytes": 100}, "home": {"available_bytes": 200}}
            return result

        mocked = patch.object(apps, "run_core", side_effect=core)
        mocked.start()
        self.addCleanup(mocked.stop)
        return headers

    def app_request(self, operation, payload, headers):
        return self.request_full("POST", "/fre3nder/api/v1/apps/" + operation,
                                 body=json.dumps(payload),
                                 headers={**headers, "Content-Type": "application/json"})

    def app_upload(self, headers, extra=None):
        return self.request_full("POST", "/fre3nder/api/v1/apps/upload", body=b"fixture",
                                 headers={**headers, "Content-Type": "application/octet-stream",
                                          "X-Fre3nder-Filename": "fixture.fre3app", **(extra or {})})

    def wait_app_execution(self):
        deadline = time.monotonic() + 3
        while self.daemon.apps.running() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertFalse(self.daemon.apps.running(), "App fixture did not finish")
        return self.daemon.apps._execution

    def test_apps_mutations_require_session_csrf_origin_and_web_peer(self):
        headers = self.setup_apps()
        operations = ("verify", "install", "update", "remove", "display/select",
                      "display/disable", "discard", "acknowledge", "upload")
        for operation in operations:
            for extra, expected in [
                ({"Cookie": ""}, 401), ({"Cookie": "fre3nder_admin=invalid"}, 401),
                ({"X-Fre3nder-CSRF": ""}, 403), ({"X-Fre3nder-CSRF": "wrong"}, 403),
                ({"Origin": ""}, 403), ({"Origin": "http://printer.test"}, 403),
                ({"Origin": "http://other.test:8081"}, 403), ({"Host": "other.test:8081"}, 403),
            ]:
                with self.subTest(operation=operation, extra=extra):
                    status, body, _ = self.request_full("POST", "/fre3nder/api/v1/apps/" + operation,
                                                      headers={**headers, **extra})
                    self.assertEqual(status, expected, body)
            with patch.object(self.daemon, "web_uids", return_value=set()):
                status, body, _ = self.request_full("POST", "/fre3nder/api/v1/apps/" + operation,
                                                  headers=headers)
                self.assertEqual(status, 403, body)
        self.assertEqual(self.app_calls, [])
        self.assertFalse(self.daemon.apps.STAGING.exists())

    def test_apps_reads_require_session_and_web_peer(self):
        headers = self.setup_apps()
        for suffix in ("status", "detail?name=sample"):
            path = "/fre3nder/api/v1/apps/" + suffix
            status, _, _ = self.request_full("GET", path)
            self.assertEqual(status, 401)
            with patch.object(self.daemon, "web_uids", return_value=set()):
                status, _, _ = self.request_full("GET", path, headers=headers)
                self.assertEqual(status, 403)
            status, body, _ = self.request_full("GET", path, headers=headers)
            self.assertEqual(status, 200, body)
            self.assertTrue(json.loads(body)["ok"])
        self.daemon.clear_web_auth()
        status, _, _ = self.app_upload(headers)
        self.assertEqual(status, 401)
        self.assertFalse(any(op in self.daemon.apps.OPERATIONS for op, _ in self.app_calls))

    def test_apps_http_upload_update_identity_and_explicit_mutations(self):
        headers = self.setup_apps()
        status, body, _ = self.app_upload(headers)
        self.assertEqual(status, 202, body)
        package_id = json.loads(body)["execution"]["package_id"]
        self.assertEqual(self.wait_app_execution()["state"], "succeeded")
        self.assertEqual([op for op, _ in self.app_calls], ["verify"])
        status, body, _ = self.request_full("GET", "/fre3nder/api/v1/apps/status", headers=headers)
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)["apps"]["verified_packages"], [package_id])
        status, body, _ = self.app_request("update", {"package_id": package_id, "name": "other"}, headers)
        self.assertEqual(status, 409, body)
        self.assertEqual(json.loads(body)["error"]["code"], "identity-mismatch")
        self.assertFalse(any(op == "update" for op, _ in self.app_calls))
        for operation, payload in [
            ("verify", {"package_id": package_id}),
            ("update", {"package_id": package_id, "name": "sample"}),
            ("remove", {"name": "sample"}), ("display/select", {"name": "sample"}),
            ("display/disable", {}),
        ]:
            status, body, _ = self.app_request(operation, payload, headers)
            self.assertEqual(status, 202, body)
            self.assertEqual(self.wait_app_execution()["state"], "succeeded")
        self.assertFalse(list(self.daemon.apps.STAGING.glob("*.fre3app")))

    def test_apps_http_install_discard_and_acknowledgement(self):
        headers = self.setup_apps()
        for operation in ("install", "discard"):
            status, body, _ = self.app_upload(headers)
            self.assertEqual(status, 202, body)
            package_id = json.loads(body)["execution"]["package_id"]
            self.wait_app_execution()
            status, body, _ = self.app_request(operation, {"package_id": package_id}, headers)
            self.assertEqual(status, 202 if operation == "install" else 200, body)
            self.wait_app_execution()
            self.assertFalse(list(self.daemon.apps.STAGING.glob("*.fre3app")))
        self.daemon.apps.store_execution({"id": "b" * 32, "operation": "remove", "state": "unknown"})
        status, _, _ = self.app_request("remove", {"name": "sample"}, headers)
        self.assertEqual(status, 409)
        status, body, _ = self.app_request("acknowledge", {}, headers)
        self.assertEqual(status, 200, body)
        self.assertFalse(self.daemon.apps.running())

    def test_apps_http_rejects_paths_extra_fields_and_inactive_runtime(self):
        headers = self.setup_apps()
        for operation, payload in [
            ("remove", {"name": "../etc/passwd"}), ("verify", {"package_id": "../file"}),
            ("install", {"package_id": "a" * 32, "path": "/tmp/fixture"}),
            ("update", {"package_id": "a" * 32, "name": "sample", "allow_downgrade": True}),
            ("display/disable", {"name": "sample"}), ("discard", {}),
            ("acknowledge", {"command": "true"}),
        ]:
            status, body, _ = self.app_request(operation, payload, headers)
            self.assertEqual(status, 400, body)
        for extra, expected in [
            ({"Content-Type": "multipart/form-data"}, 415),
            ({"X-Fre3nder-Filename": "..%2Ffile.fre3app"}, 400),
            ({"Content-Length": str(256 * 1024 * 1024 + 1)}, 413),
        ]:
            status, body, _ = self.app_upload(headers, extra)
            self.assertEqual(status, expected, body)
        self.root_status.write_text("inactive\n")
        status, body, _ = self.app_request("remove", {"name": "sample"}, headers)
        self.assertEqual(status, 409, body)
        self.assertEqual(self.app_calls, [])

    def test_display_start_failure_is_exposed_in_failed_http_receipt(self):
        headers = self.setup_apps()
        apps = self.daemon.apps
        original = apps.run_core.side_effect
        message = ('Display frontend "doom" failed to start (status: startup-failed; service status not confirmed). '
                   'Previous display "fre3nderscreen" restored.')

        def core(operation, *args):
            if operation == "display-select":
                raise apps.AppError(409, "package-rejected", message)
            if operation == "display-list":
                return {"active": "fre3nderscreen", "apps": []}
            return original(operation, *args)

        with patch.object(apps, "run_core", side_effect=core):
            status, body, _ = self.app_request("display/select", {"name": "doom"}, headers)
            self.assertEqual(status, 202, body)
            job = json.loads(body)["execution"]
            self.assertEqual(self.wait_app_execution()["state"], "failed")
            status, body, _ = self.request_full("GET", "/fre3nder/api/v1/apps/status", headers=headers)
        self.assertEqual(status, 200, body)
        state = json.loads(body)["apps"]
        self.assertEqual(state["execution"]["id"], job["id"])
        self.assertEqual(state["execution"]["state"], "failed")
        self.assertEqual(state["execution"]["error"]["message"], message)
        self.assertEqual(state["display"]["active"], "fre3nderscreen")

    def test_apps_and_ota_http_operations_exclude_each_other(self):
        headers = self.setup_apps()
        self.block_app = threading.Event()
        self.addCleanup(self.block_app.set)
        status, body, _ = self.app_request("remove", {"name": "sample"}, headers)
        self.assertEqual(status, 202, body)
        status, body, _ = self.ota_request("verify", {"package_id": "a" * 32}, headers)
        self.assertEqual(status, 409, body)
        self.assertEqual(json.loads(body)["error"]["code"], "apps-busy")
        status, _, _ = self.request_full("GET", "/fre3nder/api/v1/apps/status", headers=headers)
        self.assertEqual(status, 200)
        self.block_app.set()
        self.wait_app_execution()
        self.block_core = threading.Event()
        self.addCleanup(self.block_core.set)
        path = self.daemon.OTA_PACKAGES / ("a" * 32 + ".ota")
        path.write_bytes(b"fixture")
        path.chmod(0o600)
        status, body, _ = self.ota_request("verify", {"package_id": "a" * 32}, headers)
        self.assertEqual(status, 202, body)
        for operation in ("remove", "upload"):
            status, body, _ = self.app_request(operation, {"name": "sample"}, headers)
            self.assertEqual(status, 409, body)
            self.assertEqual(json.loads(body)["error"]["code"], "ota-busy")
        self.block_core.set()
        self.assertEqual(self.wait_execution()["state"], "succeeded")

    def test_apps_http_storage_selection_and_status(self):
        headers = self.setup_apps()
        for role in (None, "sys", "home"):
            status, body, _ = self.app_upload(headers)
            self.assertEqual(status, 202, body)
            package_id = json.loads(body)["execution"]["package_id"]
            self.wait_app_execution()
            payload = {"package_id": package_id}
            if role is not None:
                payload["storage"] = role
            status, body, _ = self.app_request("install", payload, headers)
            self.assertEqual(status, 202, body)
            self.wait_app_execution()
            self.assertEqual(self.app_calls[-1][1][-2:], ("--storage", role or "sys"))
        for suffix in ("status", "detail?name=sample"):
            status, body, _ = self.request_full("GET", "/fre3nder/api/v1/apps/" + suffix, headers=headers)
            self.assertEqual(status, 200, body)
            result = json.loads(body)
            app = result["apps"]["installed"][0] if suffix == "status" else result["app"]
            self.assertEqual(app["storage"], "home")
        for role in ("/tmp", "HOME", None, []):
            status, body, _ = self.app_request("install", {"package_id": "a" * 32, "storage": role}, headers)
            self.assertEqual(status, 400, body)
        status, _, _ = self.app_request("update", {"package_id": "a" * 32, "name": "sample", "storage": "sys"}, headers)
        self.assertEqual(status, 400)

    def test_ota_upload_checks_home_proxy_and_sys_staging_separately(self):
        self.setup_ota()
        directory = self.daemon.OTA_PACKAGES
        proxy = self.daemon.OTA_UPLOAD_BUFFER
        original_stat = pathlib.Path.stat

        def separate_devices(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            if path == proxy:
                values = list(result)
                values[2] += 1
                return os.stat_result(values)
            return result

        reserve = self.daemon.OTA_SPACE_RESERVE
        for lacking in (directory, proxy):
            def available(path):
                return types.SimpleNamespace(f_bavail=reserve + (9 if path == lacking else 100), f_frsize=1)
            with (patch.object(pathlib.Path, "stat", separate_devices),
                  patch.object(self.daemon.os, "statvfs", side_effect=available)):
                with self.assertRaises(self.daemon.ManagementError) as exc:
                    self.daemon.upload_space(10)
                self.assertEqual(exc.exception.status, 507)
        with (patch.object(pathlib.Path, "stat", separate_devices),
              patch.object(self.daemon.os, "statvfs", return_value=types.SimpleNamespace(f_bavail=reserve + 10, f_frsize=1))):
            self.assertEqual(self.daemon.upload_space(10)["max_package_bytes"], 96 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
