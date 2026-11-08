"""Asynchronous backup receipts and protected downloads for Management."""

import importlib.machinery
import importlib.util
import json
import os
import pathlib
import re
import secrets
import sys
import tempfile
import threading


_loader = importlib.machinery.SourceFileLoader(
    "fre3nder_management_backup_core", str(pathlib.Path(__file__).with_name("backup-core")))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
core = importlib.util.module_from_spec(_spec)
_loader.exec_module(core)

EXECUTION_FILE = pathlib.Path("/run/fre3nder-management/backup-execution.json")
_lock = threading.RLock()
_execution = None
_downloads = {}


class BackupError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def store(execution, downloads):
    global _execution, _downloads
    core.require_directory(EXECUTION_FILE.parent, "management runtime directory")
    if EXECUTION_FILE.is_symlink():
        raise ValueError("unsafe backup receipt")
    with tempfile.NamedTemporaryFile(mode="w", dir=EXECUTION_FILE.parent,
            prefix=".backup-execution-", delete=False) as output:
        temporary = pathlib.Path(output.name)
        try:
            json.dump({"execution": execution, "downloads": downloads}, output)
            output.flush()
            os.fsync(output.fileno())
            temporary.replace(EXECUTION_FILE)
        finally:
            temporary.unlink(missing_ok=True)
    _execution, _downloads = execution, downloads


def restore():
    global _execution, _downloads
    if not EXECUTION_FILE.exists():
        return
    info = core.require_regular_file(EXECUTION_FILE, "backup receipt")
    if info.st_uid != os.geteuid() or info.st_mode & 0o077 or info.st_size > 1024 * 1024:
        raise ValueError("unsafe backup receipt")
    saved = json.loads(EXECUTION_FILE.read_text())
    _execution, _downloads = saved["execution"], saved["downloads"]
    if _execution and _execution["state"] == "running":
        _execution = {**_execution, "state": "failed", "error": {
            "code": "backup-interrupted", "message": "Management restarted during backup; completion was not confirmed"}}


def running():
    with _lock:
        return bool(_execution and _execution["state"] == "running")


def status():
    with _lock:
        execution, downloads = _execution, dict(_downloads)
    offer = core.backup_offer_response()
    return {"backup_offer": offer["backup_offer"], "runtime_usb": offer["runtime_usb"],
            "execution": execution,
            "downloads": [{"id": key, **value} for key, value in downloads.items()]}


def start(payload):
    if set(payload) != {"role", "target"}:
        raise BackupError(400, "invalid-request", "Expected role and target")
    role, target = payload["role"], payload["target"]
    if (role not in ("home", "sys") or not isinstance(target, str)
            or target not in (("download", "usb") if role == "home" else ("download", "usb", "home"))):
        raise BackupError(400, "invalid-selection", "Invalid backup role or target")
    arguments = (["--home", target, "--no-sys"] if role == "home" else
                 ["--no-home", "--sys", target])
    try:
        planned = core.backup_plan_response(arguments)
    except (OSError, ValueError) as exc:
        raise BackupError(409, "backup-unavailable", str(exc)) from exc
    with _lock:
        if running():
            raise BackupError(409, "backup-busy", "A backup is already running")
        job = {"id": secrets.token_hex(16), "state": "running", "operation": "create", **payload}
        store(job, _downloads)
        expected_usb = planned["runtime_usb"] if target == "usb" else None
        threading.Thread(target=execute, args=(job, arguments, expected_usb), daemon=True).start()
        return job


def execute(job, arguments, expected_usb=None):
    try:
        result = core.execute_response(arguments, expected_usb=expected_usb)
        created = result["backup_result"][job["role"]]
        if result["backup_result"]["complete"] is not True or created.get("verified") is not True:
            raise ValueError("Backup completion was not verified")
        completed = {**job, "state": "succeeded", "result": result}
    except (OSError, ValueError) as exc:
        completed = {**job, "state": "failed", "error": {
            "code": "insufficient-space" if getattr(exc, "errno", None) == 28 else "backup-failed",
            "message": str(exc)}}
    except Exception:
        completed = {**job, "state": "failed", "error": {
            "code": "backup-failed", "message": "Backup completion could not be confirmed"}}
    with _lock:
        downloads = dict(_downloads)
        if completed["state"] == "succeeded" and job["target"] == "download":
            downloads[job["id"]] = created
        try:
            store(completed, downloads)
        except (OSError, ValueError):
            global _execution
            _execution = {**job, "state": "failed", "error": {
                "code": "receipt-failed", "message": "Backup result could not be recorded"}}


def download_entry(job_id, allow_missing=False):
    if not isinstance(job_id, str) or re.fullmatch(r"[0-9a-f]{32}", job_id) is None:
        raise BackupError(400, "invalid-id", "Invalid backup job ID")
    value = _downloads.get(job_id)
    if value is None:
        raise BackupError(404, "backup-unavailable", "No downloadable backup exists for this job")
    path = pathlib.Path(value["archive"])
    if path.parent.parent != core.STAGING_DIRECTORY or not path.parent.name.startswith("job-"):
        raise BackupError(409, "storage-unsafe", "Backup is outside staging")
    for directory in (path.parent, core.STAGING_DIRECTORY, core.STAGING_DIRECTORY.parent):
        try:
            info = core.require_directory(directory, "backup staging directory")
        except (OSError, ValueError) as exc:
            if allow_missing and isinstance(exc.__cause__, FileNotFoundError):
                continue
            raise BackupError(409, "storage-unsafe", "Backup staging is unavailable or unsafe") from exc
        if info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise BackupError(409, "storage-unsafe", "Backup staging is not root-controlled")
    return value, path


def open_download(job_id):
    stream = None
    try:
        with _lock:
            value, path = download_entry(job_id)
            value = dict(value)
            info = core.require_regular_file(path, "download archive")
            if info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise ValueError("unsafe download archive permissions")
            stream = os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb")
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
                    info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns):
                raise ValueError("download archive changed during verification")
        # An open descriptor survives discard. Status and new jobs must not
        # wait for a complete SHA-256 pass over a potentially large archive.
        core.verify_backup_archive(path, value["size"], value["sha256"], stream=stream)
        stream.seek(0)
        return stream, path.name, value["size"]
    except (OSError, ValueError) as exc:
        if stream is not None:
            stream.close()
        raise BackupError(409, "backup-invalid", "Download archive failed verification") from exc


def discard(payload):
    global _execution, _downloads
    if set(payload) != {"id"}:
        raise BackupError(400, "invalid-request", "Expected a backup job ID")
    with _lock:
        value, path = download_entry(payload["id"], allow_missing=True)
        try:
            core.require_regular_file(path, "download archive")
        except (OSError, ValueError) as exc:
            if not isinstance(exc.__cause__, FileNotFoundError):
                raise BackupError(409, "storage-unsafe", "Download archive cannot be discarded safely") from exc
        previous_execution, previous_downloads = _execution, _downloads
        downloads = dict(_downloads)
        del downloads[payload["id"]]
        execution = _execution
        if execution and execution["id"] == payload["id"]:
            execution = {**execution, "state": "discarded"}
            execution.pop("result", None)
        try:
            # Persist removal before deleting data: a receipt write failure
            # leaves the original downloadable archive available for retry.
            store(execution, downloads)
        except (OSError, ValueError) as exc:
            raise BackupError(503, "receipt-failed", "Backup status could not be recorded; archive was not removed") from exc
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            try:
                store(previous_execution, previous_downloads)
            except (OSError, ValueError):
                # Keep the live receipt consistent even if status storage also
                # failed; the archive itself was not removed.
                _execution, _downloads = previous_execution, previous_downloads
            raise BackupError(409, "discard-failed", "Temporary archive could not be removed; retry discard") from exc
        try:
            path.parent.rmdir()
        except FileNotFoundError:
            pass
        except OSError:
            # The archive is gone and its receipt is committed. A leftover
            # empty job directory is harmless and covered by boot cleanup.
            print("fre3nder backup: discarded archive; job directory cleanup deferred to boot", file=sys.stderr)
