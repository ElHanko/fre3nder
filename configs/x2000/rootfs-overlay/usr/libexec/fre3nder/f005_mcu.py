#!/usr/bin/env python3
"""Minimal identify-only access to the F005 over the qualified passive UART."""

import json
import re
import sys


UART_PATH = "/dev/ttyS1"
UART_BAUD = 230400
KLIPPY_DIR = "/usr/share/klipper/klippy"
RUNTIME_TARGET_MANIFEST = "/usr/share/fre3nder/f005-runtime-target.json"
QUALIFIED_RELEASE_MANIFEST = "/usr/share/fre3nder/f005-mcu-release.json"
RESET_QUEUE_DEADLINE = 0.050
BYTES_WRITE_RE = re.compile(r"(?:^|\s)bytes_write=([0-9]+)(?:\s|$)")
REQUIRED_CONSTANTS = ("MCU", "CLOCK_FREQ", "SERIAL_BAUD")


class SafetyError(Exception):
    pass


def load_release_manifest(path=RUNTIME_TARGET_MANIFEST):
    """Load a schema-1 qualified record or the effective RootFS firmware target."""
    with open(path, "r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    if manifest.get("schema") != 1:
        raise SafetyError("unsupported F005 release manifest schema")
    uart = manifest.get("uart", {})
    if uart != {"path": UART_PATH, "baud": UART_BAUD}:
        raise SafetyError("release manifest does not select the qualified UART")
    for identity_name in ("stock_identity", "fre3nder_release"):
        identity = manifest.get(identity_name, {})
        if not isinstance(identity.get("version"), str):
            raise SafetyError("release manifest lacks %s version" % identity_name)
        constants = identity.get("constants", {})
        if any(name not in constants for name in REQUIRED_CONSTANTS):
            raise SafetyError("release manifest lacks %s constants" % identity_name)
    return manifest


def identity_matches(observed, expected):
    if observed.get("version") != expected.get("version"):
        return False
    observed_constants = observed.get("constants", {})
    expected_constants = expected.get("constants", {})
    return all(observed_constants.get(name) == expected_constants.get(name)
               for name in REQUIRED_CONSTANTS)


def classify_identity(observed, manifest, qualified_manifest=None):
    if identity_matches(observed, manifest["fre3nder_release"]):
        return "fre3nder"
    if identity_matches(observed, manifest["stock_identity"]):
        return "stock"
    if (qualified_manifest is not None
            and identity_matches(observed, qualified_manifest["fre3nder_release"])):
        return "fre3nder-qualified"
    return "unknown"


def dictionary_has_reset(msgparser):
    try:
        command = msgparser.lookup_command("reset")
    except Exception:
        return False
    return command.msgformat == "reset"


def _bytes_written(reader):
    stats = reader.stats(reader.reactor.monotonic())
    match = BYTES_WRITE_RE.search(stats)
    if match is None:
        raise SafetyError("serialqueue statistics lack bytes_write")
    return int(match.group(1))


def _send_reset_once(reader, msgparser):
    if not dictionary_has_reset(msgparser):
        raise SafetyError("MCU dictionary does not contain exact reset command")
    encoded = msgparser.create_command("reset")
    before = _bytes_written(reader)
    reader.raw_send(encoded, 0, 0, reader.get_default_command_queue())
    deadline = reader.reactor.monotonic() + RESET_QUEUE_DEADLINE
    while reader.reactor.monotonic() < deadline:
        if _bytes_written(reader) > before:
            return
        reader.reactor.pause(min(deadline,
                                 reader.reactor.monotonic() + 0.001))
    raise SafetyError("reset was queued but no UART write was observed")


def probe_mcu(manifest, send_reset=False, klippy_dir=KLIPPY_DIR,
              qualified_manifest=None, expected_reset_state="stock"):
    if expected_reset_state not in ("stock", "fre3nder-qualified"):
        raise SafetyError("unsupported reset source state")
    if klippy_dir not in sys.path:
        sys.path.insert(0, klippy_dir)
    import reactor
    import serialhdl

    reactor_instance = reactor.Reactor()
    result = {"value": None, "error": None}

    def identify(eventtime):
        reader = serialhdl.SerialReader(reactor_instance, mcu_name="f005-state")
        try:
            reader.connect_uart_passive(UART_PATH, UART_BAUD)
            msgparser = reader.get_msgparser()
            version, build_versions = msgparser.get_version_info()
            observed = {
                "version": version,
                "build_versions": build_versions,
                "constants": msgparser.get_constants(),
                "reset_supported": dictionary_has_reset(msgparser),
            }
            observed["state"] = classify_identity(observed, manifest, qualified_manifest)
            if send_reset:
                if observed["state"] != expected_reset_state:
                    raise SafetyError("reset requires exact %s identity" % expected_reset_state)
                _send_reset_once(reader, msgparser)
                observed["reset_sent"] = True
            result["value"] = observed
        except Exception as exc:
            result["error"] = exc
        finally:
            try:
                reader.disconnect()
                if result["value"] is not None:
                    result["value"]["connection_closed"] = True
            except Exception as exc:
                if result["error"] is None:
                    result["error"] = exc
            reactor_instance.end()
        return reactor_instance.NEVER

    reactor_instance.register_callback(identify)
    reactor_instance.run()
    if result["error"] is not None:
        raise result["error"]
    if result["value"] is None:
        raise SafetyError("MCU identify produced no result")
    return result["value"]
