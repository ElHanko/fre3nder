#!/usr/bin/env python3
"""Purely offline USB storage-preparation tests; never access real devices."""

import contextlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/prepare-first-install-storage"
loader = importlib.machinery.SourceFileLoader("usb_storage_prepare", str(PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
storage = importlib.util.module_from_spec(spec)
loader.exec_module(storage)

DEVICE = "/dev/sdz"
SIZE = 8 * 1024 ** 3


class FakeHost:
    def __init__(self):
        self.commands = []
        self.partitioned = False
        self.mounted = False
        self.transport = "usb"
        self.size = SIZE
        self.serial = "SERIAL-001"
        self.device_id = 42
        self.part1_size = storage.SYS_MIB * storage.MIB

    def stat(self, path):
        assert path == DEVICE
        return SimpleNamespace(st_mode=stat.S_IFBLK | 0o600,
                               st_rdev=self.device_id)

    def run(self, argv, *, input_text=None):
        self.commands.append((list(argv), input_text))
        op = argv[0]
        if op == "lsblk":
            node = {"path": DEVICE, "type": "disk", "tran": self.transport,
                    "size": self.size, "log-sec": 512, "ro": 0,
                    "mountpoints": [None], "model": "USB test", "serial": self.serial}
            if self.partitioned:
                node["children"] = [
                    {"path": f"{DEVICE}1", "type": "part", "partn": 1,
                     "size": self.part1_size, "mountpoints": [None]},
                    {"path": f"{DEVICE}2", "type": "part", "partn": 2,
                     "size": storage.HOME_MIB * storage.MIB, "mountpoints": [None]},
                    {"path": f"{DEVICE}3", "type": "part", "partn": 3,
                     "size": self.size - (1 + storage.SYS_MIB + storage.HOME_MIB) * storage.MIB,
                     "mountpoints": [None]},
                ]
            if self.mounted:
                node["mountpoints"] = ["/mnt/test"]
            return json.dumps({"blockdevices": [node]})
        if op == "sfdisk":
            assert "start=2048" in input_text
            assert "type=c" in input_text
            self.partitioned = True
            return ""
        if op == "blkid":
            part = int(argv[-1][-1])
            typ, label = {
                1: ("ext4", "FRE3NDERSYS"),
                2: ("ext4", "FRE3NDERHOME"),
                3: ("vfat", "X2000DEV"),
            }[part]
            return (typ if argv[-2] == "TYPE" else label) + "\n"  # -s TYPE|LABEL
        return ""


class USBStorageTests(unittest.TestCase):
    def setUp(self):
        self.host = FakeHost()
        original_stat = storage.os.stat

        def device_stat_only(path, *args, **kwargs):
            if str(path) == DEVICE:
                return self.host.stat(DEVICE)
            return original_stat(path, *args, **kwargs)

        self.patchers = [
            patch.object(storage.os, "stat", side_effect=device_stat_only),
            patch.object(storage, "run", side_effect=self.host.run),
            patch.object(storage.shutil, "which", return_value="/fake/tool"),
            patch.object(storage.os, "geteuid", return_value=0),
            patch.object(storage.os, "sync"),
        ]
        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)

    def call(self, *more, answer=None):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with patch("builtins.input", return_value=answer or ""):
                result = storage.main(["--device", DEVICE, *more])
        return result, output.getvalue()

    def operations(self):
        return [argv[0] for argv, _ in self.host.commands]

    def test_partitions_use_300_mib_sys_6_gib_home_remainder_fat(self):
        plan = storage.partition_script()
        self.assertIn("label: dos", plan)
        self.assertIn("size=614400, type=83", plan)
        self.assertIn("size=12582912, type=83", plan)
        self.assertIn("type=c", plan)

    def test_preflight_is_read_only(self):
        result, output = self.call()
        self.assertEqual(result, 0)
        self.assertIn("USB_STORAGE_PREFLIGHT=PASS", output)
        self.assertEqual(self.operations(), ["lsblk"])
        self.assertIn("-T", self.host.commands[0][0])

    def test_refuse_internal_disk(self):
        self.host.transport = "sata"
        with self.assertRaisesRegex(storage.Refused, "USB transport"):
            self.call()
        self.assertEqual(self.operations(), ["lsblk"])

    def test_refuse_mounted_usb(self):
        self.host.mounted = True
        with self.assertRaisesRegex(storage.Refused, "mounted"):
            self.call("--write", answer=f"ERASE {DEVICE}")
        self.assertNotIn("sfdisk", self.operations())

    def test_refuse_too_small_usb(self):
        self.host.size = 4 * 1024 ** 3
        with self.assertRaisesRegex(storage.Refused, "too small"):
            self.call()
        self.assertNotIn("sfdisk", self.operations())

    def test_refuse_partition_device(self):
        with self.assertRaisesRegex(storage.Refused, "whole disk"):
            storage.main(["--device", DEVICE + "1"])
        self.assertEqual(self.operations(), [])

    def test_confirmation_must_match_exact_device(self):
        with self.assertRaisesRegex(storage.Refused, "confirmation did not match"):
            self.call("--write", answer="ERASE /dev/sdy")
        self.assertNotIn("sfdisk", self.operations())

    def test_write_refuses_nonroot(self):
        with patch.object(storage.os, "geteuid", return_value=1000):
            with self.assertRaisesRegex(storage.Refused, "requires root"):
                self.call("--write", answer=f"ERASE {DEVICE}")
        self.assertNotIn("sfdisk", self.operations())

    def test_write_creates_and_verifies_exact_three_filesystems(self):
        result, output = self.call("--write", answer=f"ERASE {DEVICE}")
        self.assertEqual(result, 0)
        self.assertIn("USB_STORAGE_PREPARE=PASS", output)
        self.assertEqual(self.operations().count("sfdisk"), 1)
        self.assertEqual(self.operations().count("mkfs.ext4"), 2)
        self.assertEqual(self.operations().count("mkfs.vfat"), 1)
        calls = [cmd for cmd, _ in self.host.commands]
        self.assertIn(["mkfs.ext4", "-F", "-m", "0", "-L", "FRE3NDERSYS", DEVICE + "1"], calls)
        self.assertIn(["mkfs.ext4", "-F", "-m", "0", "-L", "FRE3NDERHOME", DEVICE + "2"], calls)
        self.assertIn(["mkfs.vfat", "-F", "32", "-n", "X2000DEV", DEVICE + "3"], calls)
        self.assertLess(self.operations().index("sfdisk"), self.operations().index("mkfs.ext4"))

    def test_identity_change_blocks_writes(self):
        original = self.host.run
        def changed(argv, *, input_text=None):
            result = original(argv, input_text=input_text)
            if argv[0] == "lsblk":
                self.host.serial = "DIFFERENT"
            return result
        with patch.object(storage, "run", side_effect=changed):
            with self.assertRaisesRegex(storage.Refused, "device changed"):
                self.call("--write", answer=f"ERASE {DEVICE}")
        self.assertNotIn("sfdisk", self.operations())

    def test_partition_size_mismatch_blocks_formatting(self):
        self.host.part1_size = storage.SYS_MIB * storage.MIB - 512
        with self.assertRaisesRegex(storage.Refused, "sizes do not match"):
            self.call("--write", answer=f"ERASE {DEVICE}")
        self.assertIn("sfdisk", self.operations())
        self.assertNotIn("mkfs.ext4", self.operations())


if __name__ == "__main__":
    unittest.main()
