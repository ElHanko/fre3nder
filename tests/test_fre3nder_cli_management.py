#!/usr/bin/env python3
"""Host-side tests for the Fre3nder maintenance CLI."""

import json
import os
import pathlib
import socket
import socketserver
import subprocess
import tempfile
import threading
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI = ROOT / "configs/x2000/rootfs-overlay/usr/bin/fre3nder"


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        request_line = self.rfile.readline().decode("ascii").strip()
        method, path, _version = request_line.split(" ", 2)
        while self.rfile.readline() not in (b"\r\n", b"\n", b""):
            pass

        if path == "/fre3nder/api/v1/maintenance":
            operation = "maintenance-status"
            enabled = False
        elif path == "/fre3nder/api/v1/maintenance/enable":
            operation = "maintenance-enable"
            enabled = True
        elif path == "/fre3nder/api/v1/maintenance/disable":
            operation = "maintenance-disable"
            enabled = False
        else:
            payload = {
                "api_version": 1,
                "ok": False,
                "error": {
                    "code": "not-found",
                    "message": "not found",
                },
            }
            self.send(404, payload)
            return

        expected_method = "GET" if operation == "maintenance-status" else "POST"
        if method != expected_method:
            self.send(
                405,
                {
                    "api_version": 1,
                    "ok": False,
                    "error": {
                        "code": "method-not-allowed",
                        "message": "wrong method",
                    },
                },
            )
            return

        self.send(
            200,
            {
                "api_version": 1,
                "ok": True,
                "operation": operation,
                "maintenance": {
                    "enabled": enabled,
                    "web_status": "active" if enabled else "stopped",
                },
            },
        )

    def send(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        reason = "OK" if status == 200 else "Error"
        self.wfile.write(
            f"HTTP/1.0 {status} {reason}\r\n".encode("ascii")
        )
        self.wfile.write(b"Content-Type: application/json\r\n")
        self.wfile.write(
            f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
        )
        self.wfile.write(data)


class Server(socketserver.UnixStreamServer):
    pass


class Fre3nderMaintenanceCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.socket_path = pathlib.Path(self.tmp.name) / "management.sock"
        self.server = Server(str(self.socket_path), Handler)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.env = os.environ.copy()
        self.env["FRE3NDER_MANAGEMENT_SOCKET"] = str(self.socket_path)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.socket_path.unlink(missing_ok=True)

    def run_cli(self, *arguments):
        return subprocess.run(
            [str(CLI), *arguments],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_status_enable_disable(self):
        result = self.run_cli("maintenance", "status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Maintenance: disabled", result.stdout)
        self.assertIn("Web:         stopped", result.stdout)

        result = self.run_cli("maintenance", "enable")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Maintenance: enabled", result.stdout)
        self.assertIn("Web:         active", result.stdout)

        result = self.run_cli("maintenance", "disable")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Maintenance: disabled", result.stdout)

    def test_invalid_action_is_rejected_without_api_call(self):
        result = self.run_cli("maintenance", "toggle")
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            "fre3nder maintenance {status|enable|disable}",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
