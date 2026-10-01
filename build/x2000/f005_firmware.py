#!/usr/bin/env python3
"""Validate the explicit qualified/candidate F005 RootFS input contract."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


FIRMWARE_NAME = "klipper-f005-mainline.bin"
TARGET_PATH = f"/var/lib/fre3nder/firmware/f005/{FIRMWARE_NAME}"
# Schema 1 input inventory emitted by scripts/build-f005.
CANDIDATE_INPUTS = (
    "VERSION",
    "build/klipper-f005/Dockerfile",
    "build/klipper-f005/build-x2000-chelper.sh",
    "build/klipper-f005/f005-gd32f303.config",
    "build/x2000/Dockerfile",
    "build/x2000/entrypoint.sh",
    "configs/x2000/buildroot.defconfig",
    "configs/x2000/buildroot.fragment",
    "configs/x2000/sources.json",
    "patches/klipper/0001-gd32f303-f005-mainline.patch",
    "patches/klipper/0002-f005-serial-bootloader-request.patch",
    "scripts/build-f005",
    "scripts/source-value",
    "scripts/package_f005_firmware.py",
)


def regular_file(path, label):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} is missing, non-regular, or a symlink")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root, firmware, mode, artifact_mode, candidate_manifest=None):
    if mode not in ("qualified", "candidate"):
        raise ValueError("invalid FRE3NDER_F005_FIRMWARE_MODE")
    if artifact_mode not in ("release", "development"):
        raise ValueError("invalid artifact mode")
    if mode == "candidate" and artifact_mode != "development":
        raise ValueError("F005 candidate requires a development RootFS")
    regular_file(firmware, "F005 firmware")
    sidecar = candidate_manifest or firmware.parent / "build-manifest.json"

    if mode == "qualified":
        release = json.loads(
            (root / "configs/x2000/f005-mcu-release.json").read_text()
        )["fre3nder_release"]
        expected = release["firmware"]
        if expected["path"] != TARGET_PATH:
            raise ValueError("F005 release manifest has an unexpected firmware path")
        if sidecar.exists() or sidecar.is_symlink():
            regular_file(sidecar, "F005 build manifest")
            candidate = json.loads(sidecar.read_text())
            if ("qualified_release_match" in candidate
                    and candidate["qualified_release_match"] is not True):
                raise ValueError("F005 candidate does not match the qualified release")
        identity = {"classification": "qualified", "runtime_version": release["version"]}
        label = "release"
    else:
        regular_file(sidecar, "F005 candidate manifest")
        candidate = json.loads(sidecar.read_text())
        if type(candidate.get("schema")) is not int or candidate["schema"] != 1:
            raise ValueError("unsupported F005 candidate manifest schema")
        if candidate.get("classification") != "candidate":
            raise ValueError("F005 manifest classification is not candidate")
        if type(candidate.get("qualified_release_match")) is not bool:
            raise ValueError("F005 qualified_release_match must be boolean")
        upstream = candidate["upstream"]
        sources = json.loads((root / "configs/x2000/sources.json").read_text())
        if upstream["commit"] != sources["userspace"]["klipper"]["commit"]:
            raise ValueError("F005 candidate Klipper upstream commit mismatch")
        current_commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        if candidate.get("project_commit") != current_commit:
            raise ValueError("F005 candidate project commit mismatch")
        inputs = candidate["inputs"]
        if set(inputs) != set(CANDIDATE_INPUTS):
            raise ValueError("F005 candidate input inventory mismatch")
        for relative in CANDIDATE_INPUTS:
            path = root / relative
            regular_file(path, f"F005 input {relative}")
            if inputs[relative] != sha256(path):
                raise ValueError(f"stale F005 candidate input: {relative}")
        runtime = candidate["runtime_version"]
        if not isinstance(runtime, str) or not runtime:
            raise ValueError("F005 candidate has no runtime version")
        expected = candidate["artifacts"][FIRMWARE_NAME]
        identity = {
            "classification": "candidate",
            "runtime_version": runtime,
            "upstream_commit": upstream["commit"],
        }
        if "prepared_source_commit" in upstream:
            identity["prepared_source_commit"] = upstream["prepared_source_commit"]
        label = "candidate"

    if type(expected["size"]) is not int or firmware.stat().st_size != expected["size"]:
        raise ValueError(f"F005 firmware size does not match the {label} manifest")
    actual_sha256 = sha256(firmware)
    if actual_sha256 != expected["sha256"]:
        raise ValueError(f"F005 firmware SHA256 does not match the {label} manifest")
    identity.update({"size": expected["size"], "sha256": actual_sha256})
    return identity


def runtime_target(root, firmware, mode, artifact_mode, candidate_manifest=None):
    identity = validate(root, firmware, mode, artifact_mode, candidate_manifest)
    target = json.loads((root / "configs/x2000/f005-mcu-release.json").read_text())
    release = target["fre3nder_release"]
    if release["firmware"]["path"] != TARGET_PATH:
        raise ValueError("F005 release manifest has an unexpected firmware path")
    if mode == "candidate":
        release["name"] = "f005-development-candidate"
        release["evidence"] = "Candidate build manifest; hardware qualification pending"
        release["version"] = identity["runtime_version"]
        release["firmware"].update(size=identity["size"], sha256=identity["sha256"])
    target["firmware_target"] = {
        "classification": mode,
        "artifact_mode": artifact_mode,
        "hardware_qualified": mode == "qualified",
    }
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--firmware", type=Path, required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--artifact-mode", required=True)
    parser.add_argument("--candidate-manifest", type=Path)
    parser.add_argument("--runtime-target", action="store_true",
                        help="emit the effective schema-1 Runtime target instead of build identity")
    args = parser.parse_args()
    try:
        validator = runtime_target if args.runtime_target else validate
        identity = validator(args.root, args.firmware, args.mode,
                             args.artifact_mode, args.candidate_manifest)
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"F005 validation failed: {error}\n")
    print(json.dumps(identity, sort_keys=True))


if __name__ == "__main__":
    main()
