"""Manual signed .fre3app workflow for the Fre3nder Management daemon.

The package core remains authoritative for trust, lifecycle and selection.
Repository offers from unprivileged app data are informational only.
"""

import json
import os
import pathlib
import re
import secrets
import stat
import subprocess
import tempfile
import threading

PACKAGE_CORE = pathlib.Path(__file__).with_name("package-core")
STAGING = pathlib.Path("/home/.tmp/fre3nder/uploads")
EXECUTION_FILE = pathlib.Path("/run/fre3nder-management/apps-execution.json")
REPOSITORY_STATUS = pathlib.Path("/home/fre3nder/.local/share/fre3nder-app-update/status.json")
REPOSITORY_STATUS_LIMIT = 2 * 1024 * 1024
LIMIT = 256 * 1024 * 1024
RESERVE = 64 * 1024 * 1024
APP_NAME = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
PACKAGE_ID = re.compile(r"[0-9a-f]{32}\Z")
OPERATIONS = {"verify", "install", "update", "remove", "display-select", "display-disable"}

_lock = threading.RLock()
_execution = None
_verified = {}


class AppError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def safe_dir(path, create=False):
    for part in (path, *path.parents):
        if part.is_symlink():
            raise AppError(409, "storage-unsafe", "App storage contains a symbolic link")
    if create and not path.exists():
        path.mkdir(mode=0o700, parents=True)
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise AppError(507, "storage-unavailable", "SYS app staging is unavailable") from exc
    if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o022):
        raise AppError(409, "storage-unsafe", "App storage has unsafe permissions")
    return path


def stage_dir():
    safe_dir(STAGING.parent)
    return safe_dir(STAGING, create=True)


def staged(package_id):
    if not isinstance(package_id, str) or not PACKAGE_ID.fullmatch(package_id):
        raise AppError(400, "invalid-package", "Invalid staged package ID")
    path = stage_dir() / (package_id + ".fre3app")
    try:
        st = path.lstat()
    except FileNotFoundError as exc:
        raise AppError(404, "package-unavailable", "Staged package was not found") from exc
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
            or st.st_mode & 0o077 or st.st_nlink != 1):
        # Atomic staging uses an initial hardlink and removes the temporary name.
        raise AppError(409, "storage-unsafe", "Staged package is not a safe regular file")
    return path


def storage(remaining=0, cache_bytes=0):
    fs = os.statvfs(stage_dir())
    available = fs.f_bavail * fs.f_frsize
    if remaining and available < 2 * remaining + cache_bytes + RESERVE:
        raise AppError(507, "insufficient-space", "Not enough HOME space for upload, proxy buffer and package cache")
    return {"available_bytes": available, "max_package_bytes": LIMIT,
            "reserve_bytes": RESERVE, "proxy_copy_reserved": True, "cache_copy_reserved": True}


def run_core(operation, *args):
    # No browser-controlled executable, environment override, or arbitrary path.
    # The core prints its structured response last; signed service stdout may precede it.
    env = {key: value for key, value in os.environ.items() if not key.startswith("FRE3NDER_")}
    try:
        with tempfile.TemporaryFile(mode="w+b") as output:
            result = subprocess.run([str(PACKAGE_CORE), operation, *map(str, args)],
                                    stdin=subprocess.DEVNULL, stdout=output,
                                    stderr=subprocess.DEVNULL, env=env,
                                    timeout=900 if operation in OPERATIONS else 20,
                                    check=False)
            length = output.tell()
            output.seek(max(0, length - 65536))
            tail = output.read().decode("utf-8", errors="replace")
            lines = tail.splitlines()
            answer = json.loads(lines[-1]) if lines else None
    except subprocess.TimeoutExpired as exc:
        raise AppError(504, "operation-unknown", "Package Core timed out; inspect installed state before retrying") from exc
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise AppError(502, "core-unavailable", "Package Core returned no valid final response") from exc
    if (not isinstance(answer, dict) or answer.get("api_version") != 1
            or answer.get("operation") != operation or type(answer.get("ok")) is not bool):
        raise AppError(502, "core-invalid", "Package Core response has an unexpected format")
    if result.returncode != 0 or not answer["ok"]:
        message = answer.get("error")
        raise AppError(409, "package-rejected", str(message) if isinstance(message, str) else "Package operation failed")
    return answer


def installed():
    result = run_core("list")
    if not isinstance(result.get("apps"), list):
        raise AppError(502, "core-invalid", "Invalid installed applications response")
    for item in result["apps"]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not APP_NAME.fullmatch(item["name"]):
            raise AppError(502, "core-invalid", "Invalid installed app metadata")
    return result["apps"]


def read_repository_status():
    # Pin every directory with openat/O_NOFOLLOW: checking paths before opening
    # would race with the unprivileged app UID replacing a parent with a link.
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    directory = os.open("/", flags | os.O_DIRECTORY)
    try:
        for part in REPOSITORY_STATUS.parts[1:-1]:
            child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(REPOSITORY_STATUS.name, flags | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(fd, "rb") as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > REPOSITORY_STATUS_LIMIT:
            raise ValueError("Repository status must be a bounded regular file")
        raw = source.read(REPOSITORY_STATUS_LIMIT + 1)
    if len(raw) > REPOSITORY_STATUS_LIMIT:
        raise ValueError("Repository status exceeds the read limit")
    value = json.loads(raw.decode("utf-8"))
    validate_repository_status(value)
    return value


def validate_repository_status(value):
    # Validate only the summary contract used here, not signatures or package
    # download paths. Those never become installation authority in Management.
    if (not isinstance(value, dict) or type(value.get("schema")) is not int or value["schema"] != 1
            or (value.get("configuration"), value.get("check")) not in (
                ("unconfigured", "disabled"), ("invalid", "error"),
                ("configured", "ok"), ("configured", "error"))):
        raise ValueError("Unsupported repository status")
    for key in ("last_attempt", "last_success", "error"):
        if value[key] is not None and (not isinstance(value[key], str) or not value[key] or len(value[key]) > 256):
            raise ValueError("Invalid repository status text")
    identity, revision = value["repository"], value["revision"]
    if identity is not None:
        if not isinstance(identity, dict):
            raise ValueError("Invalid repository identity")
        for key in ("name", "key_fingerprint", "base_url"):
            if identity[key] is not None and not isinstance(identity[key], str):
                raise ValueError("Invalid repository identity")
    if revision is not None and (type(revision) is not int or revision < 1):
        raise ValueError("Invalid repository revision")
    packages = value["packages"]
    if not isinstance(packages, list) or len(packages) > 4096:
        raise ValueError("Invalid repository offers")
    if value["last_success"] is not None:
        if (identity is None or not identity["name"] or not identity["key_fingerprint"]
                or revision is None):
            raise ValueError("Incomplete successful repository check")
    elif packages or revision is not None or value["check"] == "ok":
        raise ValueError("Repository offers have no successful check")
    if value["check"] == "ok" and value["error"] is not None:
        raise ValueError("Successful repository check has an error")
    for offer in packages:
        if not isinstance(offer, dict):
            raise ValueError("Invalid repository offer")
        publisher, serial = offer.get("publisher"), offer.get("release_serial")
        if (not isinstance(offer.get("name"), str) or not APP_NAME.fullmatch(offer["name"])
                or not isinstance(offer.get("version"), str) or not 0 < len(offer["version"]) <= 128
                or type(serial) is not int or serial < 0
                or not isinstance(publisher, dict) or not isinstance(publisher.get("id"), str)
                or not publisher["id"] or len(publisher["id"]) > 64
                or not isinstance(publisher.get("key_fingerprint"), str)
                or re.fullmatch(r"[0-9a-f]{64}", publisher["key_fingerprint"]) is None
                or offer.get("channel") not in ("stable", "testing")
                or serial == 0 and offer["channel"] != "testing"
                or offer.get("target") != {"platform": "fre3nder-x2000", "arch": "mipsel"}):
            raise ValueError("Invalid repository offer metadata")


def repository_updates(apps, offers):
    by_name = {app["name"]: app for app in apps}
    selected = {}
    for offer in offers:
        app = by_name.get(offer["name"])
        if (app is None or type(app.get("release_serial")) is not int or app["release_serial"] < 0
                or not isinstance(app.get("version"), str)
                or app.get("publisher") != offer["publisher"]["id"]
                or app.get("fingerprint") != offer["publisher"]["key_fingerprint"]
                or offer["release_serial"] <= app["release_serial"]):
            continue
        # A positive serial also supersedes Development (0); Development offers
        # never supersede anything, regardless of their version text.
        previous = selected.get(app["name"])
        if previous is None or offer["release_serial"] > previous["offered"]["release_serial"]:
            selected[app["name"]] = {
                "name": app["name"], "publisher": dict(offer["publisher"]),
                "installed": {"version": app["version"], "release_serial": app["release_serial"]},
                "offered": {key: offer[key] for key in ("version", "release_serial", "channel")}}
    return [selected[name] for name in sorted(selected)]


def repository_status(apps):
    result = {"client_installed": any(app["name"] == "fre3nder-app-update" for app in apps),
              "configuration": "unknown", "check": "unavailable", "availability": "unavailable",
              "identity": None, "revision": None, "last_attempt": None, "last_success": None,
              "updates": [], "error": None}
    if not result["client_installed"]:
        result["error"] = {"code": "client-not-installed", "message": "Repository client is not installed"}
        return result
    try:
        value = read_repository_status()
    except FileNotFoundError:
        result["error"] = {"code": "status-missing", "message": "Repository status is not available yet"}
        return result
    except OSError:
        result["error"] = {"code": "status-unavailable", "message": "Repository status cannot be read safely"}
        return result
    except (ValueError, KeyError, TypeError, RecursionError):
        result["error"] = {"code": "status-invalid", "message": "Repository status is invalid or unsupported"}
        return result
    for key in ("configuration", "check", "revision", "last_attempt", "last_success"):
        result[key] = value[key]
    identity = value["repository"]
    result["identity"] = {key: identity[key] for key in ("name", "key_fingerprint", "base_url")} if identity else None
    if value["check"] == "error":
        result["error"] = {"code": "repository-check-failed", "message": value["error"] or "Repository check failed"}
    if value["configuration"] == "configured" and value["last_success"] is not None:
        result["availability"] = "checked" if value["check"] == "ok" else "cached"
        result["updates"] = repository_updates(apps, value["packages"])
    return result


def overview():
    # Snapshot the receipt before reading Core state. A worker finishing during
    # those reads must leave this response running so the browser polls again.
    with _lock:
        execution = _execution
        verified_packages = sorted(_verified)
    apps = installed()
    display = run_core("display-list")
    web = run_core("frontend-status")
    capacity = run_core("storage-status")["storage"]
    if not isinstance(display.get("apps"), list) or not isinstance(display.get("active"), (str, type(None))):
        raise AppError(502, "core-invalid", "Invalid display selection response")
    if not isinstance(web.get("frontend"), dict) or not isinstance(web["frontend"].get("active"), (str, type(None))):
        raise AppError(502, "core-invalid", "Invalid web selection response")
    packages = []
    for path in sorted(stage_dir().glob("*.fre3app")):
        if PACKAGE_ID.fullmatch(path.stem):
            packages.append({"id": path.stem, "size": staged(path.stem).stat().st_size})
    return {"installed": apps, "web": web["frontend"],
            "display": {"active": display["active"], "apps": display["apps"]},
            "packages": packages, "verified_packages": verified_packages,
            "execution": execution, "storage": {**storage(), **capacity},
            "repository": repository_status(apps)}


def details(name):
    require_name(name)
    result = run_core("status", name)
    if not isinstance(result.get("app"), dict) or type(result["app"].get("running")) is not bool:
        raise AppError(502, "core-invalid", "Invalid application status response")
    return result["app"]


def require_name(name):
    if not isinstance(name, str) or APP_NAME.fullmatch(name) is None:
        raise AppError(400, "invalid-app", "Invalid application name")
    return name


def running():
    with _lock:
        return _execution is not None and _execution["state"] in ("uploading", "running", "unknown")


def ensure_idle():
    if running():
        raise AppError(409, "apps-busy", "An application operation is active or its outcome is unknown")


def store_execution(value):
    global _execution
    safe_dir(EXECUTION_FILE.parent)
    with tempfile.NamedTemporaryFile("w", dir=EXECUTION_FILE.parent, prefix=".apps-execution.", delete=False) as output:
        tmp = pathlib.Path(output.name)
        try:
            json.dump(value, output, sort_keys=True)
            output.flush()
            os.fsync(output.fileno())
            os.replace(tmp, EXECUTION_FILE)
        finally:
            tmp.unlink(missing_ok=True)
    _execution = value


def restore():
    global _execution
    safe_dir(EXECUTION_FILE.parent)
    if EXECUTION_FILE.exists() or EXECUTION_FILE.is_symlink():
        st = EXECUTION_FILE.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                or st.st_mode & 0o077 or st.st_size > 65536):
            raise AppError(409, "execution-unsafe", "Unsafe application execution receipt")
        value = json.loads(EXECUTION_FILE.read_text())
        if not isinstance(value, dict) or value.get("state") not in ("uploading", "running", "succeeded", "failed", "unknown"):
            raise AppError(409, "execution-invalid", "Invalid application execution receipt")
        if value["state"] in ("uploading", "running"):
            value = {**value, "state": "unknown", "error": {"code": "operation-unknown",
                      "message": "Management restarted during an app operation. Inspect installed state before acknowledging."}}
            store_execution(value)
        else:
            _execution = value
    for part in stage_dir().glob(".upload-*.part"):
        st = part.lstat()
        if stat.S_ISREG(st.st_mode) and st.st_uid == os.geteuid():
            part.unlink()


def execute(job, args):
    global _verified
    try:
        operation = job["operation"]
        # Package Core owns cross-process OTA/app exclusion for CLI and web alike.
        result = run_core(operation, *args)
        if operation == "verify":
            identity = result.get("package")
            if (not isinstance(identity, dict) or not isinstance(identity.get("name"), str)
                    or not APP_NAME.fullmatch(identity["name"]) or not isinstance(identity.get("publisher"), str)
                    or not isinstance(identity.get("version"), str)):
                raise AppError(502, "core-invalid", "Verified package identity is incomplete")
            with _lock:
                _verified[job["package_id"]] = identity
        if operation in ("install", "update"):
            staged(job["package_id"]).unlink()
            with _lock:
                _verified.pop(job["package_id"], None)
        completed = {**job, "state": "succeeded", "result": result}
    except AppError as exc:
        state = "unknown" if exc.code == "operation-unknown" else "failed"
        completed = {**job, "state": state, "error": {"code": exc.code, "message": exc.message}}
    except Exception:
        completed = {**job, "state": "unknown", "error": {"code": "operation-unknown", "message": "Application operation outcome could not be recorded"}}
    with _lock:
        try:
            store_execution(completed)
        except OSError:
            globals()["_execution"] = {**completed, "state": "unknown"}


def start(operation, payload, *, reserved=False):
    if operation not in OPERATIONS:
        raise AppError(404, "not-found", "App operation does not exist")
    fields = {"package_id"} if operation in ("verify", "install", "update") else set()
    if operation in ("update", "remove", "display-select"):
        fields.add("name")
    if operation == "install" and "storage" in payload:
        fields.add("storage")
    if set(payload) != fields:
        raise AppError(400, "invalid-request", "Unexpected application operation arguments")
    if operation == "install":
        role = payload.get("storage", "sys")
        if role not in ("sys", "home"):
            raise AppError(400, "invalid-storage", "App storage must be sys or home")
        payload = {**payload, "storage": role}
    with _lock:
        if not reserved:
            ensure_idle()
        args = []
        if "package_id" in fields:
            path = staged(payload["package_id"])
            args = [str(path)]
            if operation in ("install", "update"):
                identity = _verified.get(payload["package_id"])
                if not identity:
                    raise AppError(409, "verification-required", "Verify this staged package before applying it")
                if operation == "update" and identity["name"] != payload["name"]:
                    raise AppError(409, "identity-mismatch", "Uploaded package does not belong to this app")
                # Core checks extraction, transaction and cache capacity together.
                if operation == "install":
                    args.extend(["--storage", payload["storage"]])
        if "name" in fields:
            require_name(payload["name"])
            if operation not in ("update",):
                args = [payload["name"]]
        job = {"id": secrets.token_hex(16), "state": "running", "operation": operation, **payload}
        if operation == "install":
            job["name"] = identity["name"]
        store_execution(job)
        threading.Thread(target=execute, args=(job, args), daemon=True).start()
        return job


def upload(stream, length, filename):
    if not isinstance(length, int):
        raise AppError(411, "length-required", "Content-Length is required")
    if length <= 0 or length > LIMIT:
        raise AppError(413, "request-too-large", "App upload must be between 1 byte and 256 MiB")
    if (not filename.endswith(".fre3app") or len(filename) > 255
            or any(c in filename for c in "/\\\x00\r\n")):
        raise AppError(400, "invalid-filename", "Choose a local .fre3app file without a path")
    with _lock:
        ensure_idle()
        storage(length, length)
        package_id = secrets.token_hex(16)
        store_execution({"id": secrets.token_hex(16), "state": "uploading",
                         "operation": "upload", "package_id": package_id})
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=stage_dir(), prefix=".upload-", suffix=".part", delete=False) as output:
            temporary = pathlib.Path(output.name)
            remaining = length
            while remaining:
                storage(remaining, length)
                chunk = stream.read(min(65536, remaining))
                if not chunk:
                    raise AppError(400, "upload-incomplete", "App upload ended before Content-Length")
                output.write(chunk)
                remaining -= len(chunk)
            output.flush()
            os.fsync(output.fileno())
        # Hard link prevents replacing a staged package; both names share HOME.
        os.link(temporary, stage_dir() / (package_id + ".fre3app"))
        temporary.unlink()
        temporary = None
        return start("verify", {"package_id": package_id}, reserved=True)
    except (OSError, AppError) as exc:
        issue = exc if isinstance(exc, AppError) else AppError(507 if getattr(exc, "errno", None) == 28 else 400,
                "upload-failed", "Upload could not be completed; no incomplete package was published")
        with _lock:
            store_execution({"id": secrets.token_hex(16), "state": "failed", "operation": "upload",
                             "package_id": package_id, "error": {"code": issue.code, "message": issue.message}})
        raise issue
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def discard(package_id):
    with _lock:
        ensure_idle()
        path = staged(package_id)
        path.unlink()
        _verified.pop(package_id, None)
        return {"package_id": package_id}


def acknowledge():
    with _lock:
        if _execution is None or _execution["state"] != "unknown":
            raise AppError(409, "no-unknown-operation", "No unknown application operation to acknowledge")
        # Read the actual installed manager state before allowing another mutation.
        installed()
        store_execution({**_execution, "state": "failed", "error": {"code": "acknowledged",
                         "message": "Outcome remains unconfirmed; installed state was reloaded"}})
