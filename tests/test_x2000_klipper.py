#!/usr/bin/env python3
"""Offline unit tests for the Fre3nder Klipper/MCU lifecycle helpers."""

import copy
import hashlib
import importlib.util
from importlib.machinery import SourceFileLoader
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
LIBEXEC = ROOT / "configs/x2000/rootfs-overlay/usr/libexec/fre3nder"
BASE_MANIFEST = ROOT / "configs/x2000/f005-mcu-release.json"
sys.dont_write_bytecode = True
sys.path.insert(0, str(LIBEXEC))


def load_script(name, module_name):
    path = LIBEXEC / name
    spec = importlib.util.spec_from_loader(
        module_name, SourceFileLoader(module_name, str(path)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


import f005_mcu
import f005_bootloader
transition_module = load_script(
    "f005-stock-to-fre3nder", "f005_stock_to_fre3nder")


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))

    def observed(self, identity):
        return {
            "version": identity["version"],
            "constants": copy.deepcopy(identity["constants"]),
        }

    def test_exact_stock_and_fre3nder_classification(self):
        stock = self.observed(self.manifest["stock_identity"])
        fre3nder = self.observed(self.manifest["fre3nder_release"])
        self.assertEqual(f005_mcu.classify_identity(stock, self.manifest),
                         "stock")
        self.assertEqual(f005_mcu.classify_identity(fre3nder, self.manifest),
                         "fre3nder")

    def test_any_identity_difference_is_unknown(self):
        for key in ("version", "MCU", "CLOCK_FREQ", "SERIAL_BAUD"):
            observed = self.observed(self.manifest["stock_identity"])
            if key == "version":
                observed[key] += "-different"
            else:
                observed["constants"][key] = "different"
            self.assertEqual(
                f005_mcu.classify_identity(observed, self.manifest),
                "unknown")

    def test_candidate_and_exact_qualified_predecessor(self):
        target = copy.deepcopy(self.manifest)
        target["fre3nder_release"]["version"] = "candidate-runtime"
        for identity, state in ((target["fre3nder_release"], "fre3nder"),
                                (self.manifest["fre3nder_release"], "fre3nder-qualified"),
                                (target["stock_identity"], "stock")):
            with self.subTest(state=state):
                self.assertEqual(f005_mcu.classify_identity(self.observed(identity), target,
                                                           self.manifest), state)
        observed = self.observed(self.manifest["fre3nder_release"])
        observed["version"] += "-unknown"
        self.assertEqual(f005_mcu.classify_identity(observed, target, self.manifest), "unknown")
        for name in f005_mcu.REQUIRED_CONSTANTS:
            observed = self.observed(self.manifest["fre3nder_release"])
            observed["constants"][name] = "mismatch"
            self.assertEqual(f005_mcu.classify_identity(observed, target, self.manifest), "unknown")

    def test_current_qualified_target_is_not_predecessor(self):
        self.assertEqual(f005_mcu.classify_identity(
            self.observed(self.manifest["fre3nder_release"]), self.manifest, self.manifest),
            "fre3nder")

    def test_state_helper_loads_both_records_and_reports_four_states(self):
        helper = load_script("f005-mcu-state", "f005_state_fixture")
        for state in ("stock", "fre3nder", "fre3nder-qualified", "unknown"):
            with self.subTest(state=state), patch("sys.argv", ["f005-mcu-state"]), \
                    patch.object(helper, "load_release_manifest", return_value=self.manifest) as load, \
                    patch.object(helper, "probe_mcu", return_value={"state": state}) as probe, \
                    patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(helper.main(), 1 if state == "unknown" else 0)
                self.assertEqual(output.getvalue(), state + "\n")
                self.assertEqual(load.call_count, 2)
                load.assert_called_with(f005_mcu.QUALIFIED_RELEASE_MANIFEST)
                probe.assert_called_once_with(self.manifest, qualified_manifest=self.manifest)


class ResetSafetyTests(unittest.TestCase):
    def test_exact_source_state_controls_reset(self):
        qualified = json.loads(BASE_MANIFEST.read_text())
        target = copy.deepcopy(qualified)
        target["fre3nder_release"]["version"] = "candidate-runtime"
        cases = (
            (qualified["stock_identity"], "stock", True),
            (qualified["fre3nder_release"], "stock", False),
            (qualified["fre3nder_release"], "fre3nder-qualified", True),
            (target["fre3nder_release"], "fre3nder-qualified", False),
            (qualified["stock_identity"], "fre3nder-qualified", False),
            (dict(target["fre3nder_release"], version="unknown"), "fre3nder-qualified", False),
        )
        for identity, reset_state, allowed in cases:
            with self.subTest(identity=identity["version"], reset_state=reset_state):
                callbacks = []
                reactor = Mock()
                reactor.register_callback.side_effect = callbacks.append
                reactor.run.side_effect = lambda: callbacks[0](0)
                parser = Mock()
                parser.get_version_info.return_value = (identity["version"], "fixture-build")
                parser.get_constants.return_value = identity["constants"]
                parser.lookup_command.return_value = SimpleNamespace(msgformat="reset")
                reader = Mock()
                reader.get_msgparser.return_value = parser
                modules = {"reactor": SimpleNamespace(Reactor=lambda: reactor),
                           "serialhdl": SimpleNamespace(SerialReader=lambda *a, **k: reader)}
                with patch.dict(sys.modules, modules), patch.object(f005_mcu, "_send_reset_once") as reset:
                    options = {"qualified_manifest": qualified}
                    if reset_state != "stock":
                        options["expected_reset_state"] = reset_state
                    if allowed:
                        result = f005_mcu.probe_mcu(target, send_reset=True, **options)
                        self.assertTrue(result["reset_sent"])
                        self.assertTrue(result["connection_closed"])
                        reset.assert_called_once_with(reader, parser)
                    else:
                        with self.assertRaises(f005_mcu.SafetyError):
                            f005_mcu.probe_mcu(target, send_reset=True, **options)
                        reset.assert_not_called()
                reader.disconnect.assert_called_once()
                reader.connect_uart_passive.assert_called_once_with("/dev/ttyS1", 230400)
        for state in ("fre3nder", "unknown"):
            with self.assertRaises(f005_mcu.SafetyError):
                f005_mcu.probe_mcu(target, send_reset=True, expected_reset_state=state)


class FakeProbe:
    def __init__(self, states):
        self.states = list(states)
        self.calls = []
        self.reset_count = 0
        self.options = []

    def __call__(self, manifest, send_reset=False, qualified_manifest=None,
                 expected_reset_state="stock"):
        state = self.states.pop(0)
        self.calls.append(send_reset)
        self.options.append((qualified_manifest, expected_reset_state))
        result = {"state": state, "reset_supported": True}
        if send_reset and state == expected_reset_state:
            self.reset_count += 1
            result["reset_sent"] = True
            result["connection_closed"] = True
        return result


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.status = root / "status"
        self.status.write_text("active\n", encoding="ascii")
        self.firmware = root / "klipper-f005-mainline.bin"
        self.manifest = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))
        self.firmware.write_bytes(self.make_image())
        firmware = self.manifest["fre3nder_release"]["firmware"]
        firmware["path"] = str(self.firmware)
        firmware["size"] = self.firmware.stat().st_size
        firmware["sha256"] = hashlib.sha256(
            self.firmware.read_bytes()).hexdigest()
        self.manifest_path = root / "manifest.json"
        self.qualified_path = root / "qualified.json"
        self.qualified_path.write_bytes(BASE_MANIFEST.read_bytes())
        self.write_manifest()

    def tearDown(self):
        self.temp.cleanup()

    def make_image(self):
        image = bytearray((index * 17 + 3) & 0xff for index in range(2500))
        struct.pack_into("<II", image, 0, f005_bootloader.RAM_END,
                         f005_bootloader.APP_FLASH_START + 0x41)
        image[f005_bootloader.METADATA_OFFSET:f005_bootloader.BOARD_INFO_END] = (
            b"\0" * (f005_bootloader.BOARD_INFO_END
                       - f005_bootloader.METADATA_OFFSET))
        image[f005_bootloader.METADATA_OFFSET:
              f005_bootloader.METADATA_OFFSET + 12] = b"mcu0_004_000"
        struct.pack_into("<I", image, f005_bootloader.LENGTH_OFFSET, len(image))
        masked = bytearray(image)
        masked[f005_bootloader.CRC_OFFSET:
               f005_bootloader.LENGTH_OFFSET + 4] = b"\0" * 6
        struct.pack_into("<H", image, f005_bootloader.CRC_OFFSET,
                         f005_bootloader.crc16_ccitt(masked))
        return bytes(image)

    def write_manifest(self):
        self.manifest_path.write_text(
            json.dumps(self.manifest), encoding="utf-8")

    def run_transition(self, probe, write=False, flash=None, sleep=None, from_qualified=False):
        if flash is None:
            def flash(*args, **kwargs):
                raise AssertionError("flash must not be invoked")
        if sleep is None:
            sleep = lambda _: None
        return transition_module.transition(
            write=write, manifest_path=str(self.manifest_path),
            root_status=str(self.status), probe=probe, flash=flash,
            sleep=sleep, from_qualified=from_qualified,
            qualified_manifest_path=str(self.qualified_path))

    def test_dry_run_sends_no_reset_or_flash(self):
        probe = FakeProbe(["stock"])
        self.assertEqual(self.run_transition(probe), "dry-run-ready")
        self.assertEqual(probe.calls, [False])
        self.assertEqual(probe.reset_count, 0)

    def test_bad_firmware_hash_blocks_before_probe(self):
        self.manifest["fre3nder_release"]["firmware"]["sha256"] = "0" * 64
        self.write_manifest()
        probe = FakeProbe(["stock"])
        with self.assertRaises(f005_mcu.SafetyError):
            self.run_transition(probe, write=True)
        self.assertEqual(probe.calls, [])

    def test_degraded_root_blocks_before_probe(self):
        self.status.write_text("no-userdata-source\n", encoding="ascii")
        probe = FakeProbe(["stock"])
        with self.assertRaises(f005_mcu.SafetyError):
            self.run_transition(probe, write=True)
        self.assertEqual(probe.calls, [])

    def test_unknown_mcu_blocks_flash_and_reset_confirmation(self):
        probe = FakeProbe(["unknown"])
        with self.assertRaises(f005_mcu.SafetyError):
            self.run_transition(probe, write=True)
        self.assertEqual(probe.reset_count, 0)

    def test_write_resets_once_flashes_once_and_reidentifies(self):
        probe = FakeProbe(["stock", "fre3nder"])
        calls = []
        sleeps = []

        def flash(image, policy):
            calls.append((image, policy))

        self.assertEqual(self.run_transition(
            probe, write=True, flash=flash, sleep=sleeps.append),
                         "transition-complete")
        self.assertEqual(probe.reset_count, 1)
        self.assertEqual(probe.calls, [True, False])
        self.assertEqual(len(calls), 1)
        self.assertEqual(sleeps, [1.0])

    def test_missing_uart_cleanup_blocks_flash(self):
        def probe(manifest, send_reset=False):
            return {
                "state": "stock",
                "reset_supported": True,
                "reset_sent": send_reset,
            }

        with self.assertRaises(f005_mcu.SafetyError):
            self.run_transition(probe, write=True)

    def test_flash_failure_has_no_second_attempt(self):
        probe = FakeProbe(["stock"])
        calls = []

        def flash(image, policy):
            calls.append((image, policy))
            raise f005_bootloader.FlasherError("fixture failure")

        with self.assertRaises(f005_mcu.SafetyError):
            self.run_transition(probe, write=True, flash=flash)

        self.assertEqual(probe.reset_count, 1)
        self.assertEqual(probe.calls, [True])
        self.assertEqual(len(calls), 1)

    def test_final_fre3nder_identity_is_required(self):
        probe = FakeProbe(["stock", "unknown"])
        calls = []
        with self.assertRaises(f005_mcu.SafetyError):
            self.run_transition(probe, write=True,
                                flash=lambda image, policy: calls.append(image))
        self.assertEqual(len(calls), 1)

    def prepare_candidate_target(self):
        self.manifest["fre3nder_release"]["version"] = "candidate-runtime"
        self.write_manifest()

    def test_default_path_rejects_qualified_predecessor(self):
        self.prepare_candidate_target()
        probe = FakeProbe(["fre3nder-qualified"])
        with self.assertRaises(f005_mcu.SafetyError):
            self.run_transition(probe, write=True)
        self.assertEqual(probe.reset_count, 0)

    def test_qualified_predecessor_dry_run_has_no_reset_or_flash(self):
        self.prepare_candidate_target()
        probe = FakeProbe(["fre3nder-qualified"])
        self.assertEqual(self.run_transition(probe, from_qualified=True), "dry-run-ready")
        self.assertEqual(probe.calls, [False])
        self.assertEqual(probe.reset_count, 0)
        self.assertEqual(probe.options[0][0], json.loads(BASE_MANIFEST.read_text()))
        self.assertEqual(probe.options[0][1], "fre3nder-qualified")

    def test_qualified_update_is_one_reset_one_flash_one_second_and_exact_target(self):
        self.prepare_candidate_target()
        probe = FakeProbe(["fre3nder-qualified", "fre3nder"])
        flashes, waits = [], []
        result = self.run_transition(probe, write=True, from_qualified=True,
                                     flash=lambda image, policy: flashes.append(image), sleep=waits.append)
        self.assertEqual(result, "transition-complete")
        self.assertEqual(probe.calls, [True, False])
        self.assertEqual(probe.reset_count, 1)
        self.assertEqual(len(flashes), 1)
        self.assertEqual(waits, [1.0])

    def test_wrong_predecessor_never_resets_or_flashes(self):
        self.prepare_candidate_target()
        for state in ("stock", "fre3nder", "unknown"):
            probe = FakeProbe([state])
            with self.assertRaises(f005_mcu.SafetyError):
                self.run_transition(probe, write=True, from_qualified=True)
            self.assertEqual(probe.reset_count, 0)

    def test_qualified_flash_failure_is_not_retried(self):
        self.prepare_candidate_target()
        probe = FakeProbe(["fre3nder-qualified"])
        flash = Mock(side_effect=f005_bootloader.FlasherError("fixture failure"))
        with self.assertRaises(f005_mcu.SafetyError):
            self.run_transition(probe, write=True, from_qualified=True, flash=flash)
        flash.assert_called_once()
        self.assertEqual(probe.calls, [True])
        self.assertEqual(probe.reset_count, 1)

    def test_qualified_update_rejects_final_identity_mismatch(self):
        self.prepare_candidate_target()
        for final_state in ("unknown", "fre3nder-qualified"):
            probe = FakeProbe(["fre3nder-qualified", final_state])
            flash = Mock()
            with self.assertRaises(f005_mcu.SafetyError):
                self.run_transition(probe, write=True, from_qualified=True, flash=flash)
            flash.assert_called_once()
            self.assertEqual(probe.calls, [True, False])

    def test_cli_requires_explicit_from_qualified_flag(self):
        with patch("sys.argv", ["f005-stock-to-fre3nder", "--from-qualified", "--write"]), \
                patch.object(transition_module, "transition", return_value="transition-complete") as transition, \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(transition_module.main(), 0)
        transition.assert_called_once_with(write=True, from_qualified=True)


if __name__ == "__main__":
    unittest.main()
