#!/usr/bin/env python3
"""Host-side tests for the Fre3nder management API."""

import grp
import http.client
import importlib.machinery
import importlib.util
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

    def request(self, method, path):
        connection = UnixHTTPConnection(self.daemon.SOCKET_PATH)
        connection.request(method, path)
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        connection.close()
        return response.status, body

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

    def test_unknown_endpoint_is_rejected(self):
        status, body = self.request(
            "GET",
            "/fre3nder/api/v1/nope",
        )
        self.assertEqual(status, 404)
        self.assertIn('"code":"not-found"', body)


if __name__ == "__main__":
    unittest.main()
