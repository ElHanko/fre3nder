"""Read-only system snapshots for the existing Management API.

Missing observations are null, distinct from an observed empty list or selection.
Never invoke service status hooks: even those can change application state.
"""

import datetime
import importlib.machinery
import importlib.util
import ipaddress
import json
import math
import os
import pathlib
import re
import stat
import subprocess


PROC = pathlib.Path("/proc")
SYS = pathlib.Path("/sys")
ROOT = pathlib.Path("/")
PACKAGE_CORE = pathlib.Path(__file__).with_name("package-core")

_loader = importlib.machinery.SourceFileLoader(
    "fre3nder_system_ota", str(pathlib.Path(__file__).with_name("ota-core"))
)
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
ota = importlib.util.module_from_spec(_spec)
_loader.exec_module(ota)


def text(path):
    try:
        return path.read_text().strip("\0\n\r \t") or None
    except (OSError, UnicodeError):
        return None


def children(path):
    try:
        return sorted(path.iterdir())
    except OSError:
        return None


def number(value, convert=float):
    try:
        result = convert(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def platform(version_file):
    cpu = {}
    for line in (text(PROC / "cpuinfo") or "").splitlines():
        key, separator, value = line.partition(":")
        if separator:
            cpu.setdefault(key.strip().lower(), value.strip())
    return {
        "version": text(version_file),
        "hardware_model": text(SYS / "firmware/devicetree/base/model")
        or text(PROC / "device-tree/model") or cpu.get("system type"),
        "cpu_model": cpu.get("model name") or cpu.get("cpu model"),
        "architecture": os.uname().machine,
        "kernel_version": text(PROC / "sys/kernel/osrelease"),
        "hostname": text(PROC / "sys/kernel/hostname"),
    }


def runtime():
    uptime = (text(PROC / "uptime") or "").split()
    load = (text(PROC / "loadavg") or "").split()
    averages = [number(value) for value in load[:3]]
    return {
        "uptime_seconds": number(uptime[0]) if uptime else None,
        "system_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "load_average": averages if len(averages) == 3 and None not in averages else None,
    }


def memory():
    values = {}
    for line in (text(PROC / "meminfo") or "").splitlines():
        match = re.fullmatch(r"(\w+):\s+(\d+) kB", line)
        if match:
            values[match[1]] = int(match[2]) * 1024
    total, available = values.get("MemTotal"), values.get("MemAvailable")
    swap_total, swap_free = values.get("SwapTotal"), values.get("SwapFree")
    if total is not None and available is not None and available > total:
        available = None
    if swap_total is not None and swap_free is not None and swap_free > swap_total:
        swap_free = None
    return {
        "total_bytes": total, "available_bytes": available,
        "used_bytes": total - available if total is not None and available is not None else None,
        "swap_total_bytes": swap_total, "swap_free_bytes": swap_free,
        "swap_used_bytes": swap_total - swap_free if swap_total is not None and swap_free is not None else None,
    }


def storage():
    mounts = ota.parse_mounts(text(PROC / "mounts") or "")
    result = []
    for role, mountpoint in (("SYS", ota.SYS_MOUNT), ("HOME", ota.HOME_MOUNT)):
        item = {"role": role, "mountpoint": mountpoint, "device": None,
                "filesystem": None, "total_bytes": None, "used_bytes": None,
                "available_bytes": None}
        matches = [(source, fs) for source, target, fs in mounts if target == mountpoint]
        if len(matches) == 1:
            source, fs = matches[0]
            item.update(device=source, filesystem=fs)
            try:
                usage = os.statvfs(ROOT / mountpoint.lstrip("/"))
                item.update(total_bytes=usage.f_blocks * usage.f_frsize,
                            used_bytes=(usage.f_blocks - usage.f_bfree) * usage.f_frsize,
                            available_bytes=usage.f_bavail * usage.f_frsize)
            except OSError:
                pass
        result.append(item)
    return result


def boot(root_status):
    try:
        slot, _target, rootfs = ota.discover_active_slot(text(PROC / "cmdline") or "")
    except ValueError:
        slot, rootfs = None, None
    return {"active_slot": slot, "active_rootfs": rootfs,
            "root_status": text(root_status)}


def addresses():
    # ifconfig is already part of the platform network lifecycle. Query only;
    # support both BusyBox's "inet addr:" and net-tools' "inet" output.
    try:
        result = subprocess.run(["/sbin/ifconfig", "-a"], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=5, check=False,
                                env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"})
        if result.returncode:
            return None
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return None
    found = {}
    current = None
    for line in result.stdout.splitlines():
        if line and not line[0].isspace():
            current = line.split()[0].split(":")[0]
            found.setdefault(current, [])
        match = re.search(r"\binet6?\s+(?:addr:\s*)?([0-9a-fA-F.:]+(?:/\d+)?)", line)
        if current and match:
            try:
                address = str(ipaddress.ip_interface(match[1]))
            except ValueError:
                continue
            # Do not invent a prefix for ifconfig's unprefixed IPv4 address.
            found[current].append(address if "/" in match[1] else str(ipaddress.ip_address(match[1])))
    return found


def network():
    entries = children(SYS / "class/net")
    ips = addresses()
    interfaces = None if entries is None else []
    for entry in entries or []:
        if text(entry / "type") != "1":
            continue
        interfaces.append({
            "name": entry.name, "kind": "wlan" if (entry / "wireless").is_dir() or (entry / "phy80211").is_dir() else "ethernet",
            "state": text(entry / "operstate"),
            "carrier": {"0": False, "1": True}.get(text(entry / "carrier")),
            "addresses": ips.get(entry.name) if ips is not None else None,
        })
    route_text = text(PROC / "net/route")
    routes = None if route_text is None else []
    for line in (route_text or "").splitlines()[1:]:
        fields = line.split()
        try:
            if len(fields) >= 8 and int(fields[1], 16) == 0 and int(fields[7], 16) == 0 and int(fields[3], 16) & 1:
                routes.append({"interface": fields[0], "gateway": str(ipaddress.IPv4Address(
                    int(fields[2], 16).to_bytes(4, "little"))), "metric": int(fields[6])})
        except (ValueError, OverflowError):
            continue
    minimum = min((route["metric"] for route in routes or []), default=None)
    preferred = [route for route in routes or [] if route["metric"] == minimum]
    return {"interfaces": interfaces, "default_ipv4_routes": routes,
            "default_ipv4_route": preferred[0] if len(preferred) == 1 else None}


def driver(path):
    try:
        return (path / "driver").resolve(strict=True).name
    except OSError:
        return None


def usb():
    entries = children(SYS / "bus/usb/devices")
    if entries is None:
        return None
    devices = []
    for entry in entries:
        if not re.fullmatch(r"usb\d+|\d+-\d+(?:\.\d+)*", entry.name):
            continue
        interfaces = [{"interface": part.name, "driver": driver(part)}
                      for part in entries if part.name.startswith(entry.name + ":")]
        parent = None if entry.name.startswith("usb") else (
            entry.name.rsplit(".", 1)[0] if "." in entry.name else "usb" + entry.name.split("-")[0])
        devices.append({"port": entry.name, "parent": parent,
                        "manufacturer": text(entry / "manufacturer"), "product": text(entry / "product"),
                        "vendor_id": text(entry / "idVendor"), "product_id": text(entry / "idProduct"),
                        "driver": driver(entry), "interfaces": interfaces})
    return devices


def process_running(pid_path, arguments):
    pid = text(pid_path)
    if pid is None or not pid.isdecimal() or int(pid) <= 1:
        return None
    try:
        command = (PROC / pid / "cmdline").read_bytes().split(b"\0")
    except FileNotFoundError:
        return False
    except OSError:
        return None
    return all(argument.encode() in command for argument in arguments)


def services():
    specs = (
        ("Klipper", "fre3nder-klipper", "klippy.pid", ("/usr/share/klipper/klippy/klippy.py",)),
        ("Moonraker", "fre3nder-moonraker", "moonraker.pid", ("/opt/fre3nder/moonraker/moonraker/moonraker.py",)),
        ("Management", "fre3nder-management", "managementd.pid", ("/usr/libexec/fre3nder/managementd",)),
        ("Web server", "fre3nder-web", "lighttpd.pid", ("/usr/sbin/lighttpd", "-f", "/run/fre3nder-web/lighttpd.conf")),
        ("Maintenance web server", "fre3nder-maintenance-web", "lighttpd.pid", ("/usr/sbin/lighttpd", "-f", "/run/fre3nder-maintenance-web/lighttpd.conf")),
        ("Camera", "fre3nder-camera", "mjpg_streamer.pid", ("/usr/bin/mjpg_streamer",)),
        ("Time synchronization", "fre3nder/time", "ntpd.pid", ("/usr/sbin/ntpd",)),
        ("SSH", "fre3nder/dropbear", "dropbear.pid", ("/usr/sbin/dropbear",)),
    )
    result = []
    for name, directory, pid, arguments in specs:
        path = ROOT / "run" / directory
        recorded = text(path / "status")
        running = process_running(path / pid, arguments)
        status = recorded
        if recorded == "active":
            status = "active" if running is True else "not-running" if running is False else "unconfirmed"
        elif recorded is None and running is not None:
            status = "running" if running else "not-running"
        result.append({"name": name, "status": status, "recorded_status": recorded,
                       "process_running": running})
    result.append({"name": "Display manager", "status": text(ROOT / "run/fre3nder-display/status"),
                   "recorded_status": text(ROOT / "run/fre3nder-display/status"), "process_running": None})
    return result


def selection(kind):
    path = ROOT / "home/.fre3nder" / kind / "active"
    try:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022:
            raise ValueError("unsafe selection")
        value = path.read_text()
        if not value.endswith("\n") or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value[:-1]):
            raise ValueError("invalid selection")
        return {"status": "selected", "name": value[:-1]}
    except FileNotFoundError:
        return {"status": "none", "name": None}
    except (OSError, ValueError):
        return {"status": "unavailable", "name": None}


def applications():
    count = None
    # Unlike Apps overview/detail, list executes no package service hooks and
    # creates neither staging directories nor temporary stdout files.
    try:
        env = {key: value for key, value in os.environ.items() if not key.startswith("FRE3NDER_")}
        result = subprocess.run([str(PACKAGE_CORE), "list"], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=20, check=False, env=env)
        value = json.loads(result.stdout)
        if (result.returncode == 0 and isinstance(value, dict) and value.get("api_version") == 1 and value.get("ok") is True
                and isinstance(value.get("apps"), list)):
            count = len(value["apps"])
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return {"installed_count": count, "web_frontend": selection("frontend"),
            "display_frontend": selection("display"),
            "display_runtime_status": text(ROOT / "run/fre3nder-display/status")}


def snapshot(version_file, root_status, maintenance_enabled, web_status_file, execution):
    try:
        enabled = maintenance_enabled()
    except (OSError, ValueError):
        enabled = None
    try:
        update = ota.status_response()
    except (OSError, ValueError):
        update = None
    return {"platform": platform(version_file), "runtime": runtime(), "memory": memory(),
            "storage": storage(), "boot": boot(root_status), "network": network(),
            "usb": usb(), "services": services(), "applications": applications(),
            "maintenance": {"enabled": enabled, "web_status": text(web_status_file),
                            "ota": update, "execution": execution}}
