#!/usr/bin/env python3
"""Offline CLI and bootstrap fixtures; no printer or network access."""

import contextlib
import hashlib
import importlib.util
from importlib.machinery import SourceFileLoader
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = ROOT / "configs/x2000/rootfs-overlay/usr/bin/fre3nder"
SERVICE = ROOT / "apps/fluidd/service"
INFO = {"project_name": "fluidd", "project_owner": "fluidd-core", "version": "v0.0.0-fixture"}
sys.dont_write_bytecode = True


class AppFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home/fre3nder"
        self.apps = self.root / "opt/apps"
        self.handler = self.apps / "fluidd/service"
        self.web = self.root / "opt/web"
        self.payload = self.web / "fluidd"
        self.marker = self.home / ".fre3nder/services/fluidd/installed"
        self.active = self.home / ".fre3nder/frontend/active"
        self.config = self.home / "printer_data/config/fre3nder/fluidd.conf"
        self.moonraker = self.home / "printer_data/config/moonraker.conf"
        self.source = self.root / "source"
        self.fixtures = self.root / "fixtures"
        self.fixtures.mkdir()
        self.ref = self.root / "APP_REF"
        self.ref.write_text("a" * 40 + "\n")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("FRE3NDER_")}
        self.env.update({
            "FRE3NDER_HOME_DIR": str(self.home),
            "FRE3NDER_APPS_DIR": str(self.apps),
            "FRE3NDER_WEB_DIR": str(self.web),
            "FRE3NDER_APP_SOURCE_DIR": str(self.source),
            "FRE3NDER_APP_REF_FILE": str(self.ref),
            "FRE3NDER_FLUIDD_FIXTURE_DIR": str(self.fixtures),
            "FRE3NDER_PYTHON": sys.executable,
        })

    def run_cli(self, *args, ok=True, handler=False):
        command = ["sh", str(SERVICE)] if handler else [sys.executable, str(DISPATCHER)]
        result = subprocess.run(command + list(args), env=self.env, capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def write(self, path, data="", executable=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)
        if executable:
            path.chmod(0o755)

    def desired(self):
        self.write(self.marker)

    def include(self):
        self.write(self.moonraker, "# user configuration\n[include fre3nder/*.conf]\n")

    def valid_payload(self):
        self.write(self.payload / "index.html", "old user payload")
        self.write(self.payload / "release_info.json", json.dumps(INFO))

    def state(self):
        return dict(line.split("=", 1) for line in self.run_cli("status", handler=True).stdout.splitlines())

    def release(self, entries=None, digest=True):
        entries = entries if entries is not None else {
            "index.html": "fixture index", "release_info.json": json.dumps(INFO),
            "assets/app.js": "fixture script",
        }
        archive = self.fixtures / "fluidd.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
            for name, content in entries.items():
                zipped.writestr(name, content)
        asset = {
            "name": "fluidd.zip", "state": "uploaded", "size": archive.stat().st_size,
            "browser_download_url": "https://github.com/fluidd-core/fluidd/releases/download/v0.0.0-fixture/fluidd.zip",
        }
        if digest:
            asset["digest"] = "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest()
        release = {
            "draft": False, "prerelease": False, "tag_name": "v0.0.0-fixture",
            "html_url": "https://github.com/fluidd-core/fluidd/releases/tag/v0.0.0-fixture",
            "assets": [asset],
        }
        self.write(self.fixtures / "release.json", json.dumps(release))
        return release

    def fluidd_functions(self):
        # Exercise the Python body with the same environment as the shell entry.
        body = SERVICE.read_text().split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
        namespace = {}
        with patch.dict(os.environ, self.env, clear=True), patch.object(sys, "argv", ["service", "status"]), contextlib.redirect_stdout(io.StringIO()):
            exec(compile(body, str(SERVICE), "exec"), namespace)
        return namespace


class DispatcherTests(AppFixtures):
    def test_invalid_invocations(self):
        for args in ((), ("install",), ("install", "test", "extra"), ("update", "test")):
            with self.subTest(args=args):
                self.assertIn("usage:", self.run_cli(*args, ok=False).stderr)
        for name in ("", "../fluidd", "/tmp/service", "a/b", "a..b", ".", "-x", "Upper", "a b", "a\nb", "a" * 65):
            with self.subTest(name=name):
                self.assertIn("invalid app name", self.run_cli("install", name, ok=False).stderr)
        self.assertFalse(self.apps.exists())

    def test_local_handler_and_exit_code(self):
        del self.env["FRE3NDER_APP_SOURCE_DIR"]
        self.ref.write_text("unpublished\n")
        app = self.apps / "sample_1-app/service"
        self.write(app, '#!/bin/sh\nprintf "%s\\n" "$1"\nexit 23\n', executable=True)
        for action in ("install", "uninstall", "status", "restore"):
            result = self.run_cli(action, "sample_1-app", ok=False)
            self.assertEqual(result.returncode, 23)
            self.assertEqual(result.stdout, action + "\n")

    def test_reconstruct_and_reuse_handler(self):
        source = self.source / "apps/sample/service"
        self.write(source, '#!/bin/sh\nprintf "%s\\n" "$1"\n', executable=True)
        for action in ("install", "restore", "status", "uninstall"):
            target = self.apps / "sample/service"
            target.unlink(missing_ok=True)
            self.assertEqual(self.run_cli(action, "sample").stdout, action + "\n")
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o755)
        shutil.rmtree(self.source)
        del self.env["FRE3NDER_APP_SOURCE_DIR"]
        self.ref.write_text("unpublished\n")
        self.run_cli("status", "sample")

    def test_missing_and_invalid_source(self):
        self.run_cli("install", "sample", ok=False)
        target = self.apps / "sample/service"
        self.assertFalse(target.exists())
        source = self.source / "apps/sample/service"
        self.write(source, "not a handler", executable=True)
        self.run_cli("install", "sample", ok=False)
        self.assertFalse(target.exists())
        source.unlink()
        source.symlink_to(SERVICE)
        self.run_cli("install", "sample", ok=False)

    def test_invalid_local_handler_never_replaced_or_executed(self):
        self.handler.parent.mkdir(parents=True)
        for kind in ("symlink", "directory", "nonexecutable", "fifo"):
            with self.subTest(kind=kind):
                if kind == "symlink":
                    self.handler.symlink_to(SERVICE)
                elif kind == "directory":
                    self.handler.mkdir()
                elif kind == "fifo":
                    os.mkfifo(self.handler)
                else:
                    self.handler.write_text("#!/bin/sh\nexit 0\n")
                self.run_cli("install", "fluidd", ok=False)
                if kind == "directory":
                    self.handler.rmdir()
                else:
                    self.handler.unlink()
        self.handler.parent.rmdir()
        self.handler.parent.symlink_to(self.source)
        self.run_cli("install", "fluidd", ok=False)

    def test_no_specific_app_in_rootfs(self):
        self.assertNotIn("fluidd", DISPATCHER.read_text().lower())
        overlay = ROOT / "configs/x2000/rootfs-overlay"
        self.assertFalse(list(overlay.rglob("*fluidd*")))
        self.assertFalse((overlay / "opt/fre3nder/apps").exists())
        self.assertFalse((overlay / "etc/init.d/S62fre3nder-services").exists())

    def test_pinned_remote_source_and_dirty_ref(self):
        spec = importlib.util.spec_from_loader("dispatcher", SourceFileLoader("dispatcher", str(DISPATCHER)))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        env = dict(self.env)
        del env["FRE3NDER_APP_SOURCE_DIR"]
        url = "https://raw.githubusercontent.com/ElHanko/fre3nder/" + "a" * 40 + "/apps/sample/service"
        response = io.BytesIO(b"#!/bin/sh\nexit 0\n")
        response.geturl = lambda: url
        target = self.apps / "sample/service"
        with patch.dict(os.environ, env, clear=True), patch.object(module.urllib.request, "urlopen", return_value=response) as fetch:
            module.load_handler("sample", target)
            fetch.assert_called_once_with(url, timeout=60)
        for ref in ("main", "2026.2.a", "unpublished", "../../bad", ""):
            self.ref.write_text(ref)
            with patch.dict(os.environ, env, clear=True), patch.object(module.urllib.request, "urlopen") as fetch:
                with self.assertRaises(ValueError):
                    module.load_handler("sample", target)
                fetch.assert_not_called()

    def test_build_ref_for_clean_and_dirty_worktrees(self):
        source = (ROOT / "build/x2000/entrypoint.sh").read_text()
        block = source.split("\t# A dirty tree has no remotely reconstructible app-definition revision.\n", 1)[1].split("\tif [", 1)[0]
        overlay = self.root / "overlay"
        (overlay / "usr/share/fre3nder").mkdir(parents=True)
        for status, expected in (("clean", "a" * 40), ("dirty", "unpublished")):
            env = dict(self.env, klipper_overlay=str(overlay), project_commit="a" * 40, project_worktree_status=status)
            subprocess.run(["sh", "-eu", "-c", block], env=env, check=True)
            self.assertEqual((overlay / "usr/share/fre3nder/APP_REF").read_text(), expected + "\n")

    def dispatcher(self):
        spec = importlib.util.spec_from_loader("dispatcher", SourceFileLoader("dispatcher", str(DISPATCHER)))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_cache_binding_for_all_actions(self):
        del self.env["FRE3NDER_APP_SOURCE_DIR"]
        module = self.dispatcher()
        target = self.apps / "sample/service"
        cached_ref = target.parent / "APP_REF"
        old = b"#!/bin/sh\nexit 23\n"
        new = b"#!/bin/sh\nexit 24\n"
        url = "https://raw.githubusercontent.com/ElHanko/fre3nder/" + "a" * 40 + "/apps/sample/service"
        for action in ("install", "uninstall", "status", "restore"):
            for provenance in ("a" * 40, "b" * 40, None, "bad-ref"):
                with self.subTest(action=action, provenance=provenance):
                    self.write(target, old.decode(), executable=True)
                    cached_ref.unlink(missing_ok=True)
                    if provenance is not None:
                        cached_ref.write_text(provenance + "\n")
                    response = io.BytesIO(new)
                    response.geturl = lambda: url
                    with patch.dict(os.environ, self.env, clear=True), patch.object(sys, "argv", ["fre3nder", action, "sample"]), patch("urllib.request.urlopen", return_value=response) as fetch, patch("os.execv") as execute:
                        module.main()
                    execute.assert_called_once_with(str(target), [str(target), action])
                    if provenance == "a" * 40:
                        fetch.assert_not_called()
                        self.assertEqual(target.read_bytes(), old)
                    else:
                        fetch.assert_called_once_with(url, timeout=60)
                        self.assertEqual(target.read_bytes(), new)
                    self.assertEqual(cached_ref.read_text(), "a" * 40 + "\n")

    def test_failed_fetch_and_activation_keep_cache_pair(self):
        del self.env["FRE3NDER_APP_SOURCE_DIR"]
        module = self.dispatcher()
        target = self.apps / "sample/service"
        self.write(target, "#!/bin/sh\nexit 23\n", executable=True)
        provenance = target.parent / "APP_REF"
        provenance.write_text("b" * 40 + "\n")
        original = target.read_bytes()
        with patch.dict(os.environ, self.env, clear=True), patch("urllib.request.urlopen", side_effect=OSError("fixture fetch failed")):
            with self.assertRaisesRegex(OSError, "fixture fetch failed"):
                module.ensure_handler("sample", target)
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(provenance.read_text(), "b" * 40 + "\n")
        replace = os.replace
        def fail_activation(source, destination):
            if source.name == "new":
                raise OSError("fixture activation failed")
            replace(source, destination)
        response = io.BytesIO(b"#!/bin/sh\nexit 24\n")
        response.geturl = lambda: "https://raw.githubusercontent.com/ElHanko/fre3nder/" + "a" * 40 + "/apps/sample/service"
        with patch.dict(os.environ, self.env, clear=True), patch("urllib.request.urlopen", return_value=response), patch("os.replace", side_effect=fail_activation):
            with self.assertRaisesRegex(OSError, "fixture activation failed"):
                module.ensure_handler("sample", target)
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(provenance.read_text(), "b" * 40 + "\n")

    def test_source_override_always_replaces_cache_without_provenance(self):
        source = self.source / "apps/sample/service"
        target = self.apps / "sample/service"
        self.write(target, "#!/bin/sh\nexit 23\n", executable=True)
        self.write(target.parent / "APP_REF", "a" * 40 + "\n")
        for message in ("first", "changed"):
            self.write(source, f"#!/bin/sh\necho {message}\n", executable=True)
            result = self.run_cli("status", "sample")
            self.assertEqual(result.stdout, message + "\n")
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertFalse((target.parent / "APP_REF").exists())

    def test_unpublished_without_handler_fails_without_fetch(self):
        del self.env["FRE3NDER_APP_SOURCE_DIR"]
        self.ref.write_text("unpublished\n")
        module = self.dispatcher()
        with patch.dict(os.environ, self.env, clear=True), patch("urllib.request.urlopen") as fetch:
            with self.assertRaisesRegex(ValueError, "unpublished"):
                module.ensure_handler("sample", self.apps / "sample/service")
        fetch.assert_not_called()

    def test_published_ref_repairs_invalid_handler_safely(self):
        del self.env["FRE3NDER_APP_SOURCE_DIR"]
        module = self.dispatcher()
        target = self.apps / "sample/service"
        outside = self.root / "outside"
        self.write(outside, "keep")
        target.parent.mkdir(parents=True)
        for kind in ("nonexecutable", "symlink", "directory"):
            if kind == "symlink":
                target.symlink_to(outside)
            elif kind == "directory":
                target.mkdir()
            else:
                target.write_text("#!/bin/sh\nexit 23\n")
            response = io.BytesIO(b"#!/bin/sh\nexit 0\n")
            response.geturl = lambda: "https://raw.githubusercontent.com/ElHanko/fre3nder/" + "a" * 40 + "/apps/sample/service"
            with patch.dict(os.environ, self.env, clear=True), patch("urllib.request.urlopen", return_value=response):
                module.ensure_handler("sample", target)
            self.assertTrue(module.handler_present(target))
            self.assertEqual(outside.read_text(), "keep")
            target.unlink()


class FluiddTests(AppFixtures):
    def test_empty_and_desired_status(self):
        self.assertEqual(self.state(), {
            "desired": "absent", "app_handler": "missing", "payload": "missing",
            "moonraker_config": "missing", "moonraker_include": "missing",
        })
        self.desired()
        self.assertEqual(self.state()["desired"], "installed")
        self.handler.parent.mkdir(parents=True)
        self.handler.symlink_to(SERVICE)
        self.assertEqual(self.state()["app_handler"], "invalid")

    def test_include_required_and_user_config_untouched(self):
        for content in ("", "# [include fre3nder/*.conf]\n", " [include fre3nder/*.conf]\n"):
            self.write(self.moonraker, content)
            result = self.run_cli("install", handler=True, ok=False)
            self.assertIn(str(self.moonraker), result.stderr)
            self.assertIn("[include fre3nder/*.conf]", result.stderr)
            self.assertIn("does not automatically modify", result.stderr)
            self.assertEqual(self.moonraker.read_text(), content)
            self.assertFalse(self.marker.exists())
            self.assertFalse(self.payload.exists())
        self.include()
        self.assertEqual(self.state()["moonraker_include"], "present")

    def test_install_bootstrap_and_marker_last(self):
        self.include()
        self.release()
        original = self.moonraker.read_bytes()
        # CLI reconstructs the repository handler before bootstrapping.
        source = self.source / "apps/fluidd/service"
        source.parent.mkdir(parents=True)
        shutil.copy2(SERVICE, source)
        self.run_cli("install", "fluidd")
        self.assertEqual(self.state(), {
            "desired": "installed", "app_handler": "present", "payload": "present",
            "moonraker_config": "present", "moonraker_include": "present",
        })
        self.assertEqual(self.marker.read_bytes(), b"")
        self.assertEqual(self.moonraker.read_bytes(), original)
        self.assertIn(f"path: {self.payload}\n", self.config.read_text())
        self.assertIn("repo: fluidd-core/fluidd\n", self.config.read_text())
        self.assertEqual(list(self.web.glob(".fluidd-*")), [])

    def test_valid_payload_is_never_updated(self):
        self.include()
        self.valid_payload()
        before = (self.payload / "index.html").stat()
        self.run_cli("install", handler=True)  # No release fixture exists.
        self.config.unlink()
        self.run_cli("restore", handler=True)
        self.assertTrue(self.config.is_file())
        self.assertEqual((self.payload / "index.html").read_text(), "old user payload")
        after = (self.payload / "index.html").stat()
        self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))

    def test_restore_without_marker_is_noop(self):
        self.run_cli("restore", handler=True)
        self.assertFalse(self.home.exists())
        self.assertFalse(self.web.exists())
        self.valid_payload()
        self.run_cli("restore", handler=True)
        self.assertEqual((self.payload / "index.html").read_text(), "old user payload")

    def test_overlay_reset_restores_handler_and_payload(self):
        self.include()
        self.desired()
        source = self.source / "apps/fluidd/service"
        source.parent.mkdir(parents=True)
        shutil.copy2(SERVICE, source)
        self.release()
        self.run_cli("restore", "fluidd")
        self.assertTrue(self.config.exists())
        self.assertEqual(self.state()["payload"], "present")
        shutil.rmtree(self.apps)
        shutil.rmtree(self.web)
        self.run_cli("restore", "fluidd")
        self.assertEqual(self.state()["app_handler"], "present")
        self.assertEqual(self.state()["payload"], "present")

    def test_invalid_payload_and_failed_bootstrap(self):
        self.include()
        self.write(self.payload / "index.html", "incomplete")
        self.assertEqual(self.state()["payload"], "invalid")
        self.run_cli("install", handler=True, ok=False)
        self.assertEqual((self.payload / "index.html").read_text(), "incomplete")
        self.assertFalse(self.marker.exists())
        self.release()
        self.run_cli("install", handler=True)
        self.assertEqual(self.state()["payload"], "present")

    def test_failed_verification_preserves_state(self):
        self.include()
        self.write(self.payload / "index.html", "previous")
        for corruption in ("digest", "size", "zip", "metadata", "missing-asset", "prerelease", "repository", "asset-url"):
            with self.subTest(corruption=corruption):
                release = self.release()
                asset = release["assets"][0]
                if corruption == "digest":
                    asset["digest"] = "sha256:" + "0" * 64
                elif corruption == "size":
                    asset["size"] += 1
                elif corruption == "zip":
                    (self.fixtures / "fluidd.zip").write_bytes(b"invalid zip")
                    asset["size"] = 11
                    asset.pop("digest")
                elif corruption == "metadata":
                    release = self.release({"index.html": "bad", "release_info.json": "{}"})
                elif corruption == "missing-asset":
                    release["assets"] = []
                elif corruption == "prerelease":
                    release["prerelease"] = True
                elif corruption == "repository":
                    release["html_url"] = "https://github.com/elsewhere/fluidd/releases/tag/v0.0.0-fixture"
                else:
                    asset["browser_download_url"] = "file:///tmp/fluidd.zip"
                self.write(self.fixtures / "release.json", json.dumps(release))
                self.run_cli("install", handler=True, ok=False)
                self.assertFalse(self.marker.exists())
                self.assertFalse(self.config.exists())
                self.assertEqual((self.payload / "index.html").read_text(), "previous")
                self.assertEqual(list(self.web.glob(".fluidd-*")), [])
        # A previously valid payload bypasses even a broken download source.
        self.valid_payload()
        self.run_cli("install", handler=True)
        self.assertEqual((self.payload / "index.html").read_text(), "old user payload")

    def test_payload_metadata_and_symlinks_are_invalid(self):
        self.valid_payload()
        for data in ({}, [], {**INFO, "project_owner": "other"}, {**INFO, "version": None}, {**INFO, "asset_name": "other.zip"}):
            self.write(self.payload / "release_info.json", json.dumps(data))
            self.assertEqual(self.state()["payload"], "invalid")
        self.valid_payload()
        (self.payload / "link").symlink_to(self.fixtures)
        self.assertEqual(self.state()["payload"], "invalid")

    def test_uninstall_idempotent_and_owned_files_only(self):
        del self.env["FRE3NDER_APP_SOURCE_DIR"]
        self.ref.write_text("unpublished\n")
        self.include()
        self.valid_payload()
        self.run_cli("install", handler=True)
        self.write(self.config.parent / "other.conf", "other config")
        self.write(self.config.parent / "camera.conf", "platform camera config")
        self.write(self.home / "printer_data/database/moonraker-sql.db", "database")
        self.write(self.web / "other/index.html", "other payload")
        self.write(self.handler, SERVICE.read_text(), executable=True)
        original = self.moonraker.read_bytes()
        for _ in range(2):
            self.run_cli("uninstall", "fluidd")
            self.assertFalse(self.payload.exists())
            self.assertFalse(self.marker.exists())
            self.assertFalse(self.config.exists())
            self.assertEqual(self.moonraker.read_bytes(), original)
            self.assertEqual((self.config.parent / "other.conf").read_text(), "other config")
            self.assertEqual((self.config.parent / "camera.conf").read_text(), "platform camera config")
            self.assertEqual((self.home / "printer_data/database/moonraker-sql.db").read_text(), "database")
            self.assertEqual((self.web / "other/index.html").read_text(), "other payload")
            self.assertTrue(self.handler.is_file())

    def test_symlink_paths_refused_before_mutation(self):
        self.include()
        self.release()
        outside = self.root / "outside"
        self.write(outside / "sentinel", "keep")
        for path in (self.payload, self.web, self.marker, self.marker.parent, self.config, self.config.parent, self.moonraker):
            with self.subTest(path=path):
                path.parent.mkdir(parents=True, exist_ok=True)
                saved = path.read_bytes() if path.is_file() else None
                if path.exists():
                    path.unlink() if path.is_file() else path.rmdir()
                path.symlink_to(outside)
                self.run_cli("install", handler=True, ok=False)
                self.assertEqual((outside / "sentinel").read_text(), "keep")
                self.assertEqual(sorted(p.name for p in outside.iterdir()), ["sentinel"])
                path.unlink()
                if saved is not None:
                    path.write_bytes(saved)

    def test_unsafe_zip_paths_never_escape_staging(self):
        self.include()
        for name in ("../escape", "/escape", "a/../../escape", "a\\escape", "a//escape", "./escape"):
            self.release({name: "bad"})
            self.run_cli("install", handler=True, ok=False)
            self.assertFalse(self.marker.exists())
            self.assertFalse(self.payload.exists())
            self.assertEqual(list(self.web.iterdir()), [])
        entry = zipfile.ZipInfo("link")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.release({entry: "../../outside"})
        self.run_cli("install", handler=True, ok=False)
        self.assertEqual(list(self.web.iterdir()), [])

    def test_missing_digest_supported(self):
        self.include()
        self.release(digest=False)
        result = self.run_cli("install", handler=True)
        self.assertIn("no SHA256 digest", result.stderr)
        self.assertEqual(self.state()["payload"], "present")

    def test_real_network_branch_with_mocked_https(self):
        self.include()
        release = self.release()
        functions = self.fluidd_functions()
        functions["fixtures"] = None
        urls = []

        def fetch(request, timeout):
            url = request if isinstance(request, str) else request.full_url
            urls.append(url)
            if url == "https://api.github.com/repos/fluidd-core/fluidd/releases/latest":
                response = io.BytesIO(json.dumps(release).encode())
                response.geturl = lambda: url
            elif url == release["assets"][0]["browser_download_url"]:
                response = io.BytesIO((self.fixtures / "fluidd.zip").read_bytes())
                response.geturl = lambda: "https://release-assets.githubusercontent.com/fixture"
            else:
                self.fail("unexpected network request: " + url)
            self.assertEqual(timeout, 60)
            return response

        with patch("urllib.request.urlopen", side_effect=fetch), patch.object(sys, "argv", ["service", "install"]), contextlib.redirect_stderr(io.StringIO()):
            functions["main"]()
        self.assertEqual(len(urls), 2)
        self.assertTrue(self.marker.is_file())
        self.assertEqual(self.state()["payload"], "present")

    def test_config_and_marker_failure_preserve_valid_payload(self):
        self.include()
        self.valid_payload()
        functions = self.fluidd_functions()
        atomic_file = functions["atomic_file"]
        for failing_path in (self.config, self.marker):
            def fail_write(path, content):
                if path == failing_path:
                    raise OSError("fixture write failure")
                atomic_file(path, content)
            with patch.dict(functions, atomic_file=fail_write), patch.object(sys, "argv", ["service", "install"]), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaisesRegex(OSError, "fixture write failure"):
                    functions["main"]()
            self.assertFalse(self.marker.exists())
            self.assertEqual((self.payload / "index.html").read_text(), "old user payload")
        self.assertTrue(self.config.is_file())

    def test_restore_failure_retains_desired_and_config(self):
        self.include()
        self.desired()
        self.run_cli("restore", handler=True, ok=False)
        self.assertTrue(self.config.is_file())
        self.assertTrue(self.marker.is_file())
        self.assertFalse(self.payload.exists())

    def test_activation_failure_restores_previous_target(self):
        self.include()
        self.write(self.payload / "index.html", "previous incomplete payload")
        self.release()
        functions = self.fluidd_functions()
        replace = os.replace

        def fail_activation(source, destination):
            if source.name == "payload" and destination == self.payload:
                raise OSError("fixture activation failure")
            replace(source, destination)

        with patch("os.replace", side_effect=fail_activation), patch.object(sys, "argv", ["service", "install"]):
            with self.assertRaisesRegex(OSError, "fixture activation failure"):
                functions["main"]()
        self.assertEqual((self.payload / "index.html").read_text(), "previous incomplete payload")
        self.assertFalse(self.marker.exists())
        self.assertEqual(list(self.web.glob(".fluidd-*")), [])

    def test_uninstall_refuses_unsafe_paths(self):
        self.include()
        self.valid_payload()
        self.run_cli("install", handler=True)
        outside = self.root / "outside"
        self.write(outside, "keep")
        self.config.unlink()
        self.config.symlink_to(outside)
        self.run_cli("uninstall", handler=True, ok=False)
        self.assertTrue(self.marker.exists())
        self.assertEqual((self.payload / "index.html").read_text(), "old user payload")
        self.assertEqual(outside.read_text(), "keep")
        self.config.unlink()
        shutil.rmtree(self.payload)
        self.payload.symlink_to(self.fixtures)
        self.run_cli("uninstall", handler=True, ok=False)
        self.assertTrue(self.marker.exists())

    def test_active_selection_and_disabled_webserver(self):
        self.include()
        self.valid_payload()
        self.write(self.home / ".fre3nder/web/disabled")
        self.run_cli("install", handler=True)
        self.assertEqual(self.active.read_text(), "fluidd\n")
        self.assertTrue(self.marker.exists())
        for name in ("fluidd", "another-ui"):
            self.write(self.active, name + "\n")
            before = self.active.stat()
            self.run_cli("install", handler=True)
            self.assertEqual(self.active.stat().st_mtime_ns, before.st_mtime_ns)
            self.run_cli("uninstall", handler=True)
            if name == "fluidd":
                self.assertFalse(self.active.exists())
            else:
                self.assertEqual(self.active.read_text(), name + "\n")
            self.valid_payload()

    def test_invalid_active_selection_fails_before_install(self):
        self.include()
        self.valid_payload()
        for name in ("../bad", "", "two\nnames"):
            self.write(self.active, name)
            self.run_cli("install", handler=True, ok=False)
            self.assertFalse(self.marker.exists())
        self.active.unlink()
        self.active.symlink_to(self.moonraker)
        original = self.moonraker.read_bytes()
        self.run_cli("install", handler=True, ok=False)
        self.assertEqual(self.moonraker.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
