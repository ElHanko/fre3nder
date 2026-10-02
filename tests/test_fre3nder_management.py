#!/usr/bin/env python3
"""Host-side tests for the Fre3nder management API."""

import grp
import http.client
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import socket
import tempfile
import threading
import unittest


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


if __name__ == "__main__":
    unittest.main()
