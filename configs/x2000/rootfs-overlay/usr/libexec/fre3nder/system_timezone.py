"""Installed IANA zones and root-managed HOME configuration, shared by init/API."""

import contextlib
import os
from pathlib import Path
import re
import secrets
import stat
import sys


ZONEINFO = Path("/usr/share/zoneinfo")
HOME = Path("/home")
LOCALTIME = Path("/etc/localtime")
TIMEZONE = Path("/etc/timezone")
DEFAULT = "Etc/UTC"
_NAME = re.compile(r"[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)+\Z")


def available():
    """Use only installed TZif data; exclude duplicate posix/right namespaces.

    Buildroot links the normal region directories into posix/. Links within
    zoneinfo are legitimate; links escaping the database and cycles are not.
    """
    root = ZONEINFO.resolve(strict=True)
    zones = []

    def visit(path, ancestors):
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root) or resolved in ancestors:
                return
            if resolved.is_dir():
                for child in sorted(path.iterdir()):
                    visit(child, ancestors | {resolved})
            elif resolved.is_file():
                name = path.relative_to(ZONEINFO).as_posix()
                if _NAME.fullmatch(name):
                    with path.open("rb") as data:
                        if data.read(4) == b"TZif":
                            zones.append(name)
        except (OSError, RuntimeError):
            return

    for path in sorted(ZONEINFO.iterdir()):
        if path.name not in ("posix", "right") and path.is_dir():
            visit(path, set())
    return sorted(zones)


def _trusted(metadata, directory=False):
    # Same manager-owned/non-writable convention as managementd.check_dir.
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(metadata.st_mode) or metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022:
        raise ValueError("Timezone configuration has unsafe ownership or permissions")


@contextlib.contextmanager
def _config_dir(create=False):
    """Anchor each component with O_NOFOLLOW, including HOME itself."""
    fd = os.open(HOME, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        _trusted(os.fstat(fd), directory=True)
        for name in (".fre3nder", "system"):
            if create:
                try:
                    os.mkdir(name, mode=0o700, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            _trusted(os.fstat(fd), directory=True)
        yield fd
    finally:
        os.close(fd)


def configured(zones):
    try:
        with _config_dir() as directory:
            fd = os.open("timezone", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd, "rb") as source:
                _trusted(os.fstat(source.fileno()))
                raw = source.read(257)
        name = raw.decode("ascii")
        if name.endswith("\n") and name[:-1] in zones:
            return name[:-1]
    except (OSError, UnicodeError, ValueError):
        pass
    return DEFAULT


def active(zones):
    try:
        target = Path(os.path.normpath(LOCALTIME.parent / os.readlink(LOCALTIME)))
        name = target.relative_to(ZONEINFO).as_posix()
        return name if name in zones else None
    except FileNotFoundError:
        # glibc's default when localtime is absent, including pre-feature Core.
        return DEFAULT
    except (OSError, ValueError):
        return None


def status(zones=None):
    zones = available() if zones is None else zones
    selected, running = configured(zones), active(zones)
    return {"active": running, "configured": selected,
            "reboot_required": selected != running}


def save(name, zones):
    if not isinstance(name, str) or name not in zones:
        raise ValueError("Select a valid installed IANA timezone")
    with _config_dir(create=True) as directory:
        try:
            _trusted(os.stat("timezone", dir_fd=directory, follow_symlinks=False))
        except FileNotFoundError:
            pass
        temporary = ".timezone." + secrets.token_hex(12)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write((name + "\n").encode("ascii"))
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, "timezone", src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass


def activate(runtime):
    # S45 restart/start must not activate settings saved during this boot.
    marker = runtime / "timezone"
    if marker.exists():
        return
    zones = available()
    name = configured(zones)
    if name not in zones:
        raise ValueError("Installed IANA UTC fallback is unavailable")
    temporary = LOCALTIME.with_name(".localtime." + secrets.token_hex(12))
    try:
        temporary.symlink_to(ZONEINFO / name)
        os.replace(temporary, LOCALTIME)
    finally:
        temporary.unlink(missing_ok=True)
    # Keep Buildroot's derived /etc/timezone consistent with /etc/localtime.
    TIMEZONE.write_text(name + "\n", encoding="ascii")
    marker.write_text(name + "\n", encoding="ascii")


if __name__ == "__main__":
    try:
        activate(Path(sys.argv[1]))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"fre3nder timezone: {exc}", file=sys.stderr)
        sys.exit(1)
