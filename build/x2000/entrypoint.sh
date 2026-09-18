#!/bin/sh
set -eu

project=/project
work=/work
version_file="$project/VERSION"
[ -f "$version_file" ] || {
	echo 'VERSION is missing' >&2
	exit 1
}
version=$(cat "$version_file")
if [ "$(wc -l < "$version_file")" -ne 1 ] ||
	! printf '%s\n' "$version" | cmp -s - "$version_file" ||
	! printf '%s\n' "$version" |
		grep -Eq '^[1-9][0-9]{3}\.[1-9][0-9]*(\.(a|b|rc))?$'; then
	echo 'VERSION must use YEAR.RELEASE[.a|.b|.rc] with a final newline' >&2
	exit 1
fi
release_year=${version%%.*}
version_tail=${version#*.}
release_number=${version_tail%%.*}
case "$version_tail" in
*.a) release_stage=alpha ;;
*.b) release_stage=beta ;;
*.rc) release_stage=rc ;;
*) release_stage=final ;;
esac
release_scope=usable-system
kernel_source="$work/linux-v6.6.18"
kernel_build="$work/linux-build-fre3nder"
buildroot="$work/buildroot"
buildroot_dl="$work/buildroot-dl"
buildroot_external="$project/configs/x2000/buildroot-external"
klipper="$work/klipper"
klipper_linux_config="$project/build/x2000/klipper-linux.config"
moonraker="$work/moonraker-source"
moonraker_wheel_manifest="$project/configs/x2000/moonraker-python-wheels.json"
moonraker_wheel_cache="$work/moonraker-python-wheels"
local_root="$project/local/production"
f005_release_manifest="$project/configs/x2000/f005-mcu-release.json"
f005_target_path=/var/lib/fre3nder/firmware/f005/klipper-f005-mainline.bin
f005_firmware=${FRE3NDER_F005_FIRMWARE:-"$local_root/artifacts/x2000/f005/klipper-f005-mainline.bin"}
artifact_root="$local_root/artifacts/x2000"
full_out="$artifact_root/full"
kernel_out="$artifact_root/kernel-only"
kernel_ximage_diagnostic_out="$artifact_root/kernel-ximage-diagnostic"
rootfs_out="$artifact_root/rootfs-only"
kernel_url=https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git
kernel_commit=d8a27ea2c98685cdaa5fa66c809c7069a4ff394b
kernel_patch_series="$project/configs/x2000/kernel-patches.series"
kernel_defconfig="$project/configs/x2000/kernel-clean-port.defconfig"
kernel_release=6.6.18-fre3nder
kernel_build_user=fre3nder
kernel_build_host=build
kernel_build_version=1
kernel_build_timestamp=
ximage_wrapper_source="$project/build/x2000/ximage-diagnostic/vendor"
ximage_inspector="$project/build/x2000/ximage-diagnostic/inspect_vmlinux.py"
ximage_vendor_url=https://github.com/Llixuma/ingenic-linux-kernel6.6-x2000-v1.0-20250221.git
ximage_vendor_commit=a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b
ximage_outer_load=0x80f00000
ximage_expected_inner_load=0x80100000
buildroot_url=https://gitlab.com/buildroot.org/buildroot.git
buildroot_version=2025.02.18
buildroot_commit=d030e36bbc9669230c015be971b14b6e062cfdde
buildroot_patch="$project/patches/buildroot/0001-mips-add-ingenic-xburst2-target.patch"
buildroot_toolchain_marker=.fre3nder-toolchain-fingerprint
klipper_url=https://github.com/Klipper3d/klipper.git
klipper_commit=0499b30374315f2a9f49fc12808527fc7d0f5cfa
moonraker_url=https://github.com/Arksine/moonraker.git
moonraker_commit=985c1d0bbeb90bc057d34a232c9dc3b05e0c6c8d
kernel_firmware_dir="$work/fre3nder-kernel-firmware"
klipper_overlay="$work/fre3nder-klipper-overlay"
moonraker_overlay="$work/fre3nder-moonraker-overlay"
guppyscreen_overlay="$work/fre3nder-guppyscreen-overlay"
moonraker_component="$artifact_root/moonraker"
guppyscreen_component="$artifact_root/guppyscreen"
development_marker="$klipper_overlay/usr/share/fre3nder/DEVELOPMENT"
artifact_mode=${FRE3NDER_ARTIFACT_MODE:-release}
project_commit=
project_worktree_status=
build_input_sha256=

case "$artifact_mode" in
release|development) ;;
*) echo 'invalid FRE3NDER_ARTIFACT_MODE' >&2; exit 2 ;;
esac

prepare_artifact_provenance() {
	project_commit=$(git -C "$project" rev-parse HEAD)
	if [ -n "$(git -C "$project" status --porcelain=v1)" ]; then
		project_worktree_status=dirty
	else
		project_worktree_status=clean
	fi

	if [ "$artifact_mode" = development ]; then
		build_input_sha256=$(
			"$project/scripts/x2000-build-input-sha256" --root "$project"
		)
	fi
}

write_build_manifest() {
	out=$1
	shift

	if [ "$artifact_mode" = development ]; then
		current_build_input_sha256=$(
			"$project/scripts/x2000-build-input-sha256" --root "$project"
		)
		[ "$current_build_input_sha256" = "$build_input_sha256" ] || {
			echo 'X2000 build inputs changed during the build' >&2
			exit 1
		}
	fi

	export ARTIFACT_OUTPUT="$out"
	export artifact_mode project_commit project_worktree_status build_input_sha256
	export version release_year release_number release_stage release_scope
	python3 - "$@" <<'PY'
import hashlib
import json
import os
import pathlib
import sys

out = pathlib.Path(os.environ["ARTIFACT_OUTPUT"])
artifact_names = sys.argv[1:]
manifest = json.loads(pathlib.Path("/project/configs/x2000/sources.json").read_text())
manifest.update({
    "version": os.environ["version"],
    "release_year": int(os.environ["release_year"]),
    "release_number": int(os.environ["release_number"]),
    "release_stage": os.environ["release_stage"],
    "release_scope": os.environ["release_scope"],
    "artifact_mode": os.environ["artifact_mode"],
    "project_commit": os.environ["project_commit"],
    "project_worktree_status": os.environ["project_worktree_status"],
})
if os.environ["artifact_mode"] == "development":
    manifest["build_input_sha256"] = os.environ["build_input_sha256"]
manifest["artifacts"] = {
    name: hashlib.sha256(out.joinpath(name).read_bytes()).hexdigest()
    for name in artifact_names
}
out.joinpath("build-manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n"
)
PY
}

verify_buildroot_release() {
	[ "$(git -C "$buildroot" rev-parse HEAD)" = "$buildroot_commit" ] ||
		return 1
	[ "$(git -C "$buildroot" cat-file -t \
		"refs/tags/$buildroot_version")" = tag ] ||
		return 1
	[ "$(git -C "$buildroot" rev-parse \
		"refs/tags/${buildroot_version}^{}")" = "$buildroot_commit" ] ||
		return 1
}

prepare_buildroot() {
	[ -d "$buildroot/.git" ]
	[ "$(git -C "$buildroot" remote get-url origin)" = "$buildroot_url" ]
	git -C "$buildroot" reset --hard "$buildroot_commit"
	git -C "$buildroot" clean -fdx
	git -C "$buildroot" checkout --detach "$buildroot_commit"
	verify_buildroot_release
	git -C "$buildroot" apply "$buildroot_patch"
	git -C "$buildroot" apply --reverse --check "$buildroot_patch"
	git -C "$buildroot" diff --check
	grep -Fxq 'config BR2_mips_xburst2' "$buildroot/arch/Config.in.mips"
	grep -Fq 'bool "XBurst II"' "$buildroot/arch/Config.in.mips"
	grep -Fq 'select BR2_MIPS_CPU_MIPS32R5' "$buildroot/arch/Config.in.mips"
	grep -Fq 'select BR2_MIPS_NAN_2008' "$buildroot/arch/Config.in.mips"
	grep -Eq '^[[:space:]]*default "mips32r2"[[:space:]]+if BR2_mips_xburst2$' \
		"$buildroot/arch/Config.in.mips"
	grep -Fxq 'ifneq ($(filter y,$(BR2_mips_xburst) $(BR2_mips_xburst2)),)' \
		"$buildroot/toolchain/toolchain-wrapper.mk"
	grep -Fxq 'TOOLCHAIN_WRAPPER_ARGS += -DBR_FP_CONTRACT_OFF' \
		"$buildroot/toolchain/toolchain-wrapper.mk"
	grep -Fq '"-ffp-contract=off",' \
		"$buildroot/toolchain/toolchain-wrapper.c"
	grep -Fxq 'PYTHON_GREENLET_VERSION = 3.1.1' \
		"$buildroot/package/python-greenlet/python-greenlet.mk"
}

validate_f005_firmware() {
	firmware=$1

	python3 - "$f005_release_manifest" "$f005_target_path" "$firmware" <<'PY'
import hashlib
import json
import pathlib
import sys

manifest_path, target_path, firmware_path = map(pathlib.Path, sys.argv[1:])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
release = manifest["fre3nder_release"]["firmware"]

if release["path"] != str(target_path):
    raise SystemExit("F005 release manifest has an unexpected firmware path")

if firmware_path.is_symlink() or not firmware_path.is_file():
    raise SystemExit("F005 firmware is missing, non-regular, or a symlink")

if firmware_path.stat().st_size != release["size"]:
    raise SystemExit("F005 firmware size does not match the release manifest")

if hashlib.sha256(firmware_path.read_bytes()).hexdigest() != release["sha256"]:
    raise SystemExit("F005 firmware SHA256 does not match the release manifest")

candidate_manifest = firmware_path.parent / "build-manifest.json"
if candidate_manifest.exists():
    candidate = json.loads(candidate_manifest.read_text(encoding="utf-8"))
    if ("qualified_release_match" in candidate
            and candidate["qualified_release_match"] is not True):
        raise SystemExit("F005 candidate does not match the qualified release")
PY
}

buildroot_toolchain_fingerprint() {
	defconfig="$project/configs/x2000/buildroot.defconfig"
	defconfig_record=$(sha256sum "$defconfig")
	patch_record=$(sha256sum "$buildroot_patch")
	defconfig_sha256=${defconfig_record%% *}
	patch_sha256=${patch_record%% *}
	{
		printf '%s\n' \
			'fre3nder-buildroot-toolchain-fingerprint-v1' \
			"buildroot_commit=$buildroot_commit"
		printf 'buildroot.defconfig=%s\n' "$defconfig_sha256"
		printf 'xburst2.patch=%s\n' "$patch_sha256"
	} | sha256sum | awk '{print $1}'
}

read_buildroot_toolchain_fingerprint() {
	marker=$1/$buildroot_toolchain_marker
	[ -f "$marker" ] && [ ! -L "$marker" ] || return 1
	value=$(cat "$marker")
	[ "$(wc -l < "$marker")" -eq 1 ] || return 1
	printf '%s\n' "$value" | cmp -s - "$marker" || return 1
	printf '%s\n' "$value" | grep -Eq '^[0-9a-f]{64}$' || return 1
	printf '%s\n' "$value"
}

buildroot_toolchain_ready() {
	buildroot_output=$1
	prefix="$buildroot_output/host/bin/mipsel-buildroot-linux-gnu-"
	sysroot="$buildroot_output/host/mipsel-buildroot-linux-gnu/sysroot"
	wrapper="$buildroot_output/host/bin/toolchain-wrapper"
	[ -f "$wrapper" ] && [ ! -L "$wrapper" ] && [ -x "$wrapper" ] &&
		[ -L "${prefix}gcc" ] &&
		[ "$(readlink "${prefix}gcc")" = toolchain-wrapper ] &&
		[ -L "${prefix}g++" ] &&
		[ "$(readlink "${prefix}g++")" = toolchain-wrapper ] &&
		[ -f "${prefix}gcc.br_real" ] &&
		[ ! -L "${prefix}gcc.br_real" ] && [ -x "${prefix}gcc.br_real" ] &&
		[ -f "${prefix}ld" ] && [ -x "${prefix}ld" ] &&
		[ -f "${prefix}strip" ] && [ -x "${prefix}strip" ] &&
		[ -f "$sysroot/lib/ld-linux-mipsn8.so.1" ] &&
		[ -f "$sysroot/lib/libc.so.6" ] &&
		[ -f "$sysroot/usr/include/stdio.h" ] &&
		[ -L "$sysroot/usr/lib/libstdc++.so" ] &&
		[ "$(readlink "$sysroot/usr/lib/libstdc++.so")" = \
			libstdc++.so.6.0.32 ] &&
		[ -f "$sysroot/usr/lib/libstdc++.so.6.0.32" ] &&
		[ -f "$buildroot_output/build/toolchain/.stamp_target_installed" ] &&
		[ -f "$buildroot_output/build/toolchain-buildroot/.stamp_target_installed" ] &&
		[ -f "$buildroot_output/build/host-gcc-final-13.4.0/.stamp_host_installed" ] &&
		[ -f "$buildroot_output/build/host-binutils-2.43.1/.stamp_host_installed" ] &&
		[ -f "$buildroot_output/build/glibc-2.41-161-g5dd252cf1d113644b3679f5a158e9ef20217865e/.stamp_staging_installed" ] &&
		[ -f "$buildroot_output/build/linux-headers-6.6.156/.stamp_staging_installed" ]
}

buildroot_toolchain_contract_matches() {
	buildroot_output=$1
	prefix="$buildroot_output/host/bin/mipsel-buildroot-linux-gnu-"
	compiler="${prefix}gcc.br_real"
	wrapper="$buildroot_output/host/bin/toolchain-wrapper"
	sysroot="$buildroot_output/host/mipsel-buildroot-linux-gnu/sysroot"

	[ "$("$compiler" -dumpmachine)" = mipsel-buildroot-linux-gnu ] || return 1
	[ "$("$compiler" -dumpfullversion)" = 13.4.0 ] || return 1
	compiler_version=$("$compiler" --version) || return 1
	expected_compiler_version="mipsel-buildroot-linux-gnu-gcc.br_real (Buildroot ${buildroot_version}-dirty) 13.4.0"
	printf '%s\n' "$compiler_version" |
		grep -Fx "$expected_compiler_version" >/dev/null ||
		return 1
	linker_version=$("${prefix}ld" --version) || return 1
	printf '%s\n' "$linker_version" |
		grep -Fx 'GNU ld (GNU Binutils) 2.43.1' >/dev/null || return 1
	target_options=$("$compiler" -Q --help=target 2>/dev/null) || return 1
	for option in \
		'-mabi=ABI[[:space:]]+32' \
		'-march=ISA[[:space:]]+mips32r2' \
		'-mfp32[[:space:]]+\[enabled\]' \
		'-mhard-float[[:space:]]+\[enabled\]' \
		'-mnan=ENCODING[[:space:]]+2008' \
		'-msoft-float[[:space:]]+\[disabled\]'; do
		printf '%s\n' "$target_options" |
			grep -E "^[[:space:]]*${option}[[:space:]]*$" >/dev/null ||
			return 1
	done
	strings "$wrapper" | grep -Fx -- '-ffp-contract=off' >/dev/null ||
		return 1
	strings "$sysroot/lib/libc.so.6" |
		grep -Fx 'GNU C Library (Buildroot) stable release version 2.41.' \
		>/dev/null ||
		return 1
}

buildroot_legacy_toolchain_adoptable() {
	buildroot_output=$1
	config="$buildroot_output/.config"
	# Markerless adoption is intentionally limited to the currently pinned
	# upstream 2025.02.18 tag; a later pin must start clean.
	[ "$buildroot_commit" = d030e36bbc9669230c015be971b14b6e062cfdde ] ||
		return 1
	[ -f "$config" ] && [ ! -L "$config" ] || return 1
	grep -Fxq "# Buildroot ${buildroot_version}-dirty Configuration" "$config" ||
		return 1
	for setting in \
		'BR2_mipsel=y' \
		'BR2_mips_xburst2=y' \
		'BR2_MIPS_CPU_MIPS32R5=y' \
		'# BR2_MIPS_SOFT_FLOAT is not set' \
		'BR2_MIPS_FP32_MODE_XX=y' \
		'BR2_MIPS_NAN_2008=y' \
		'BR2_MIPS_OABI32=y' \
		'BR2_GCC_TARGET_ARCH="mips32r2"' \
		'BR2_GCC_TARGET_ABI="32"' \
		'BR2_GCC_TARGET_FP32_MODE="xx"' \
		'BR2_GCC_TARGET_NAN="2008"' \
		'BR2_TOOLCHAIN_BUILDROOT=y' \
		'BR2_TOOLCHAIN_BUILDROOT_GLIBC=y' \
		'BR2_TOOLCHAIN_BUILDROOT_LIBC="glibc"' \
		'BR2_KERNEL_HEADERS_6_6=y' \
		'BR2_BINUTILS_VERSION="2.43.1"' \
		'BR2_GCC_VERSION="13.4.0"' \
		'BR2_TOOLCHAIN_BUILDROOT_CXX=y'; do
		grep -Fxq "$setting" "$config" || return 1
	done
	! grep -Eq '^BR2_TOOLCHAIN_EXTERNAL(=|_)' "$config" || return 1
	! grep -Fxq 'BR2_MIPS_SOFT_FLOAT=y' "$config" || return 1
	! grep -Fxq 'BR2_MIPS_NAN_LEGACY=y' "$config" || return 1
	buildroot_toolchain_ready "$buildroot_output" || return 1
	buildroot_toolchain_contract_matches "$buildroot_output"
}

prepare_buildroot_output() {
	buildroot_output=$1
	marker="$buildroot_output/$buildroot_toolchain_marker"

	if [ "$artifact_mode" = release ]; then
		if [ "${FRE3NDER_REUSE_PREPARED_TOOLCHAIN:-0}" = 1 ]; then
			stored_fingerprint=$(read_buildroot_toolchain_fingerprint "$buildroot_output") || {
				echo 'prepared Buildroot toolchain fingerprint is missing or invalid' >&2
				exit 1
			}
			[ "$stored_fingerprint" = "$(buildroot_toolchain_fingerprint)" ] &&
				buildroot_toolchain_ready "$buildroot_output" &&
				buildroot_toolchain_contract_matches "$buildroot_output" || {
				echo 'prepared Buildroot toolchain is incompatible' >&2
				exit 1
			}
			echo 'Buildroot release toolchain: REUSED'
			return
		fi
		echo 'Buildroot release build: CLEAN'
		rm -rf -- "$buildroot_output"
		return
	fi

	if [ ! -d "$buildroot_output" ]; then
		reason='output missing'
	elif [ ! -e "$marker" ] && [ ! -L "$marker" ]; then
		if buildroot_legacy_toolchain_adoptable "$buildroot_output"; then
			write_buildroot_toolchain_fingerprint "$buildroot_output"
			echo 'Buildroot development cache: ADOPTED (legacy output without fingerprint)'
			return
		fi
		reason='legacy output not safely adoptable'
	elif ! stored_fingerprint=$(
		read_buildroot_toolchain_fingerprint "$buildroot_output"
	); then
		reason='fingerprint marker missing or invalid'
	elif [ "$stored_fingerprint" != "$(buildroot_toolchain_fingerprint)" ]; then
		reason='toolchain fingerprint changed'
	elif ! buildroot_toolchain_ready "$buildroot_output"; then
		reason='toolchain output incomplete'
	elif ! buildroot_toolchain_contract_matches "$buildroot_output"; then
		reason='toolchain output incompatible'
	else
		echo 'Buildroot development cache: HIT'
		return
	fi

	echo "Buildroot development cache: MISS ($reason)"
	rm -rf -- "$buildroot_output"
}

write_buildroot_toolchain_fingerprint() {
	buildroot_output=$1
	marker="$buildroot_output/$buildroot_toolchain_marker"
	temporary_marker="$marker.tmp.$$"
	if ! buildroot_toolchain_ready "$buildroot_output" ||
		! buildroot_toolchain_contract_matches "$buildroot_output"; then
		echo 'Buildroot toolchain is incomplete; fingerprint not recorded' >&2
		return 1
	fi
	printf '%s\n' "$(buildroot_toolchain_fingerprint)" > "$temporary_marker"
	mv -f -- "$temporary_marker" "$marker"
}

configure_buildroot() {
	buildroot_output=$1
	extra_overlay=${2:-}
	rootfs_overlay="$project/configs/x2000/rootfs-overlay"
	[ -z "$extra_overlay" ] || rootfs_overlay="$rootfs_overlay $extra_overlay"
	prepare_buildroot_output "$buildroot_output"
	rm -f -- "$buildroot_output/$buildroot_toolchain_marker"
	make -C "$buildroot" O="$buildroot_output" \
		BR2_EXTERNAL="$buildroot_external" \
		BR2_DEFCONFIG="$project/configs/x2000/buildroot.defconfig" defconfig
	cat "$project/configs/x2000/buildroot.fragment" >> "$buildroot_output/.config"
	cat >> "$buildroot_output/.config" <<EOF
BR2_DL_DIR="$buildroot_dl"
BR2_GLOBAL_PATCH_DIR="$project/patches"
BR2_ROOTFS_OVERLAY="$rootfs_overlay"
EOF
	make -C "$buildroot" O="$buildroot_output" olddefconfig
	grep -Fxq 'BR2_mipsel=y' "$buildroot_output/.config"
	grep -Fxq 'BR2_mips_xburst2=y' "$buildroot_output/.config"
	grep -Fxq 'BR2_MIPS_CPU_MIPS32R5=y' "$buildroot_output/.config"
	grep -Fxq '# BR2_MIPS_SOFT_FLOAT is not set' "$buildroot_output/.config"
	grep -Fxq 'BR2_MIPS_FP32_MODE_XX=y' "$buildroot_output/.config"
	grep -Fxq 'BR2_MIPS_NAN_2008=y' "$buildroot_output/.config"
	! grep -Fxq 'BR2_MIPS_NAN_LEGACY=y' "$buildroot_output/.config"
	grep -Fxq 'BR2_MIPS_OABI32=y' "$buildroot_output/.config"
	grep -Fxq 'BR2_GCC_TARGET_ARCH="mips32r2"' "$buildroot_output/.config"
	grep -Fxq 'BR2_GCC_TARGET_ABI="32"' "$buildroot_output/.config"
	grep -Fxq 'BR2_GCC_TARGET_FP32_MODE="xx"' "$buildroot_output/.config"
	grep -Fxq 'BR2_GCC_TARGET_NAN="2008"' "$buildroot_output/.config"
	grep -Fxq 'BR2_TOOLCHAIN_BUILDROOT=y' "$buildroot_output/.config"
	grep -Fxq 'BR2_TOOLCHAIN_BUILDROOT_GLIBC=y' "$buildroot_output/.config"
	grep -Fxq 'BR2_KERNEL_HEADERS_6_6=y' "$buildroot_output/.config"
	grep -Fxq 'BR2_BINUTILS_VERSION="2.43.1"' "$buildroot_output/.config"
	grep -Fxq 'BR2_GCC_VERSION="13.4.0"' "$buildroot_output/.config"
	grep -Fxq 'BR2_TOOLCHAIN_BUILDROOT_CXX=y' "$buildroot_output/.config"
	grep -Fxq 'BR2_PACKAGE_LINUX_FIRMWARE=y' "$buildroot_output/.config"
	grep -Fxq 'BR2_PACKAGE_LINUX_FIRMWARE_CYPRESS_CYW43XXX=y' \
		"$buildroot_output/.config"
	! grep -Eq '^BR2_TOOLCHAIN_EXTERNAL(=|_)' "$buildroot_output/.config"
	grep -Fxq "BR2_DL_DIR=\"$buildroot_dl\"" "$buildroot_output/.config"
	grep -Fxq "BR2_GLOBAL_PATCH_DIR=\"$project/patches\"" \
		"$buildroot_output/.config"
	grep -Fxq "export BR2_EXTERNAL_FRE3NDER_PATH = $buildroot_external" \
		"$buildroot_output/.br2-external.mk"
}

fetch_moonraker_python_wheels() {
	export MOONRAKER_WHEEL_MANIFEST="$moonraker_wheel_manifest"
	export MOONRAKER_WHEEL_CACHE="$moonraker_wheel_cache"

	python3 - <<'PYFETCH'
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile

manifest_path = pathlib.Path(os.environ["MOONRAKER_WHEEL_MANIFEST"])
cache = pathlib.Path(os.environ["MOONRAKER_WHEEL_CACHE"])
sources_path = pathlib.Path("/project/configs/x2000/sources.json")

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
sources = json.loads(sources_path.read_text(encoding="utf-8"))

if manifest.get("schema") != 1:
    raise SystemExit("unsupported Moonraker wheel manifest schema")

if manifest.get("source") != "PyPI":
    raise SystemExit("Moonraker wheel manifest source must be PyPI")

target = manifest.get("target")
if not isinstance(target, dict):
    raise SystemExit("Moonraker wheel manifest target is missing")

for key in ("python", "platform", "implementation", "abi"):
    if not isinstance(target.get(key), str) or not target[key]:
        raise SystemExit(f"invalid Moonraker wheel target field: {key}")

if target["platform"] != "any":
    raise SystemExit("Moonraker wheel platform must be any")
if target["implementation"] != "py":
    raise SystemExit("Moonraker wheel implementation must be py")
if target["abi"] != "none":
    raise SystemExit("Moonraker wheel ABI must be none")

system_python = sources["userspace"]["python"]["version"]
system_python_minor = ".".join(system_python.split(".")[:2])

if target["python"] != system_python_minor:
    raise SystemExit(
        "Moonraker wheel Python target mismatch: "
        f"{target['python']} != {system_python_minor}"
    )

wheels = manifest.get("wheels")
if not isinstance(wheels, list) or not wheels:
    raise SystemExit("Moonraker wheel manifest contains no wheels")

required_fields = {
    "name",
    "version",
    "filename",
    "sha256",
    "license",
    "source_url",
}

seen_names = set()
seen_filenames = set()

for wheel in wheels:
    if not isinstance(wheel, dict):
        raise SystemExit("invalid Moonraker wheel manifest entry")

    missing = required_fields - wheel.keys()
    if missing:
        raise SystemExit(
            "Moonraker wheel entry missing fields: "
            + ", ".join(sorted(missing))
        )

    name = wheel["name"]
    filename = wheel["filename"]
    digest = wheel["sha256"]

    if name in seen_names:
        raise SystemExit(f"duplicate Moonraker wheel name: {name}")
    if filename in seen_filenames:
        raise SystemExit(f"duplicate Moonraker wheel filename: {filename}")

    seen_names.add(name)
    seen_filenames.add(filename)

    if not filename.endswith(".whl"):
        raise SystemExit(f"not a wheel filename: {filename}")

    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise SystemExit(f"invalid SHA256 for {filename}")

cache.parent.mkdir(parents=True, exist_ok=True)

staging = pathlib.Path(
    tempfile.mkdtemp(
        prefix=cache.name + ".tmp.",
        dir=cache.parent,
    )
)

try:
    requirements = staging / "requirements.txt"

    requirements.write_text(
        "".join(
            f"{wheel['name']}=={wheel['version']} "
            f"--hash=sha256:{wheel['sha256']}\n"
            for wheel in wheels
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            "-m",
            "pip",
            "--isolated",
            "download",
            "--disable-pip-version-check",
            "--no-cache-dir",
            "--index-url",
            "https://pypi.org/simple",
            "--dest",
            str(staging),
            "--require-hashes",
            "--only-binary=:all:",
            "--no-deps",
            "--platform",
            target["platform"],
            "--python-version",
            target["python"],
            "--implementation",
            target["implementation"],
            "--abi",
            target["abi"],
            "--requirement",
            str(requirements),
        ],
        check=True,
    )

    requirements.unlink()

    actual = {
        item.name
        for item in staging.iterdir()
        if item.is_file()
    }
    expected = {
        wheel["filename"]
        for wheel in wheels
    }

    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)

        raise SystemExit(
            "Moonraker wheel filename set mismatch; "
            f"missing={missing}, unexpected={unexpected}"
        )

    for wheel in wheels:
        wheel_path = staging / wheel["filename"]
        actual_hash = hashlib.sha256(
            wheel_path.read_bytes()
        ).hexdigest()

        if actual_hash != wheel["sha256"]:
            raise SystemExit(
                f"SHA256 mismatch for {wheel['filename']}: "
                f"{actual_hash} != {wheel['sha256']}"
            )

    if cache.exists():
        shutil.rmtree(cache)

    staging.rename(cache)
    staging = None

finally:
    if staging is not None and staging.exists():
        shutil.rmtree(staging)

print(
    "Moonraker Python wheels: "
    f"{len(wheels)} verified for Python {target['python']}"
)

for wheel in wheels:
    print(
        f"  {wheel['filename']} "
        f"sha256={wheel['sha256']}"
    )
PYFETCH
}

fetch_moonraker_inputs() {
	[ -d "$moonraker/.git" ] ||
		git clone --filter=blob:none --no-checkout "$moonraker_url" "$moonraker"
	[ "$(git -C "$moonraker" remote get-url origin)" = "$moonraker_url" ]
	git -C "$moonraker" fetch origin "$moonraker_commit"
	git -C "$moonraker" reset --hard "$moonraker_commit"
	git -C "$moonraker" clean -fdx
	git -C "$moonraker" checkout -B master "$moonraker_commit"
	git -C "$moonraker" branch --set-upstream-to=origin/master master
	[ "$(git -C "$moonraker" rev-parse HEAD)" = "$moonraker_commit" ]

	fetch_moonraker_python_wheels
}

fetch_buildroot_release() {
	[ -d "$buildroot/.git" ] ||
		git clone --filter=blob:none --no-checkout --no-tags \
			"$buildroot_url" "$buildroot"
	[ "$(git -C "$buildroot" remote get-url origin)" = "$buildroot_url" ]
	git -C "$buildroot" fetch --no-tags origin "$buildroot_commit"
	git -C "$buildroot" fetch --no-tags origin \
		"refs/tags/$buildroot_version:refs/tags/$buildroot_version"
	git -C "$buildroot" checkout --detach "$buildroot_commit"
	verify_buildroot_release
}

fetch_buildroot_inputs() {
	fetch_buildroot_release
	prepare_buildroot

	brfetch="$work/buildroot-fetch"
	configure_buildroot "$brfetch"
	make -C "$buildroot" O="$brfetch" source
}

verify_kernel_source() {
	[ -d "$kernel_source/.git" ]
	[ "$(git -C "$kernel_source" remote get-url origin)" = "$kernel_url" ]
	[ "$(git -C "$kernel_source" cat-file -t "$kernel_commit")" = commit ]
	[ "$(git -C "$kernel_source" rev-parse HEAD)" = "$kernel_commit" ]
	[ -z "$(git -C "$kernel_source" status --porcelain=v1)" ]
}

fetch_kernel_inputs() {
	[ -d "$kernel_source/.git" ] ||
		git clone --filter=blob:none --no-checkout "$kernel_url" "$kernel_source"
	[ "$(git -C "$kernel_source" remote get-url origin)" = "$kernel_url" ]
	git -C "$kernel_source" fetch --no-tags origin "$kernel_commit"
	git -C "$kernel_source" checkout --detach "$kernel_commit"
	git -C "$kernel_source" reset --hard "$kernel_commit"
	git -C "$kernel_source" clean -fdx
	verify_kernel_source

	fetch_buildroot_inputs
}

fetch_rootfs_inputs() {
	fetch_buildroot_inputs

	[ -d "$klipper/.git" ] ||
		git clone --filter=blob:none --no-checkout "$klipper_url" "$klipper"
	[ "$(git -C "$klipper" remote get-url origin)" = "$klipper_url" ]
	git -C "$klipper" fetch origin "$klipper_commit"
	git -C "$klipper" checkout --detach "$klipper_commit"
	[ "$(git -C "$klipper" rev-parse HEAD)" = "$klipper_commit" ]

}

prepare_rootfs_component() {
	component=$1
	artifact_dir=$2
	overlay=$3
	manifest=$artifact_dir/component-manifest.json
	archive=$artifact_dir/rootfs-overlay.tar
	current_build_input_sha256=$(
		"$project/scripts/x2000-build-input-sha256" --root "$project"
	)
	export artifact_mode component current_build_input_sha256
	export project_commit project_worktree_status
	if ! python3 - "$manifest" "$archive" \
		"$project/configs/x2000/sources.json" <<'PY'
import hashlib
import json
import os
import pathlib
import sys
import tarfile

manifest_path, archive, sources_path = map(pathlib.Path, sys.argv[1:])
if manifest_path.is_symlink() or not manifest_path.is_file():
    raise SystemExit(f"missing component manifest: {manifest_path}")
if archive.is_symlink() or not archive.is_file():
    raise SystemExit(f"missing component artifact: {archive}")
manifest = json.loads(manifest_path.read_text())
if manifest.get("schema") != 1:
    raise SystemExit("unsupported component manifest schema")
component = os.environ["component"]
if manifest.get("component") != component:
    raise SystemExit(f"component identity mismatch: {component}")
for field in ("artifact_mode", "project_commit", "project_worktree_status"):
    if manifest.get(field) != os.environ[field]:
        raise SystemExit(f"component {component} disagrees on {field}")
if manifest.get("build_input_sha256") != os.environ["current_build_input_sha256"]:
    raise SystemExit(f"component {component} has stale build inputs")
artifact = manifest.get("artifact", {})
if artifact.get("name") != archive.name:
    raise SystemExit(f"component {component} artifact name mismatch")
actual = hashlib.sha256(archive.read_bytes()).hexdigest()
if artifact.get("sha256") != actual:
    raise SystemExit(f"component {component} artifact SHA256 mismatch")
with tarfile.open(archive) as tar:
    for member in tar:
        relative = pathlib.PurePosixPath(member.name)
        if relative.is_absolute() or ".." in relative.parts:
            raise SystemExit(f"unsafe component archive path: {member.name}")
        if not (member.isfile() or member.isdir() or member.issym()):
            raise SystemExit(f"unsupported component archive member: {member.name}")
sources = json.loads(sources_path.read_text())
expected = sources["userspace"][component]
source = manifest.get("source", {})
for field in ("repository", "commit", "license"):
    if source.get(field) != expected[field]:
        raise SystemExit(f"component {component} source {field} mismatch")
if "release" in expected and source.get("release") != expected["release"]:
    raise SystemExit(f"component {component} source release mismatch")
PY
	then
		return 1
	fi
	rm -rf -- "$overlay"
	mkdir -p "$overlay"
	tar -xf "$archive" -C "$overlay"
}

record_rootfs_components() {
	manifest=$1/build-manifest.json
	python3 - "$manifest" \
		"$moonraker_component/component-manifest.json" \
		"$guppyscreen_component/component-manifest.json" <<'PY'
import json
import pathlib
import sys

output = pathlib.Path(sys.argv[1])
manifest = json.loads(output.read_text())
components = {}
for path_text in sys.argv[2:]:
    component = json.loads(pathlib.Path(path_text).read_text())
    components[component["component"]] = {
        "source": component["source"],
        "build_input_sha256": component["build_input_sha256"],
        "artifact_sha256": component["artifact"]["sha256"],
    }
manifest["rootfs_components"] = components
output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
PY
}

prepare_moonraker_source() {
	[ -d "$moonraker/.git" ]
	[ "$(git -C "$moonraker" remote get-url origin)" = "$moonraker_url" ]
	git -C "$moonraker" reset --hard "$moonraker_commit"
	git -C "$moonraker" clean -fdx
	git -C "$moonraker" checkout -B master "$moonraker_commit"
	git -C "$moonraker" branch --set-upstream-to=origin/master master
	[ "$(git -C "$moonraker" rev-parse HEAD)" = "$moonraker_commit" ]
	[ -z "$(git -C "$moonraker" status --porcelain=v1)" ]
	grep -Fxq 'GNU GENERAL PUBLIC LICENSE' "$moonraker/LICENSE"
	[ -f "$moonraker/moonraker/moonraker.py" ]
}
prepare_klipper_overlay() {
	git -C "$klipper" clean -fdx
	git -C "$klipper" reset --hard "$klipper_commit"
	git -C "$klipper" checkout --detach "$klipper_commit"
	[ "$(git -C "$klipper" rev-parse HEAD)" = "$klipper_commit" ]
	git -C "$klipper" apply --check \
		"$project/patches/klipper/0004-x2000-passive-uart-opt-in.patch"
	git -C "$klipper" apply \
		"$project/patches/klipper/0004-x2000-passive-uart-opt-in.patch"
	git -C "$klipper" apply --reverse --check \
		"$project/patches/klipper/0004-x2000-passive-uart-opt-in.patch"

	rm -rf -- "$klipper_overlay"
	install -d -m 0755 \
		"$klipper_overlay/usr/share/klipper" \
		"$klipper_overlay/usr/share/fre3nder" \
		"$klipper_overlay/usr/share/fre3nder/defaults" \
		"$klipper_overlay/var/lib/fre3nder/firmware/f005"
	rsync -a --exclude=.git/ "$klipper/" \
		"$klipper_overlay/usr/share/klipper/"
	printf '%s\n' 'v0.13.0-733-g0499b3037-fre3nder-passive-uart-v2' > \
		"$klipper_overlay/usr/share/klipper/klippy/.version"
	install -m 0644 "$project/configs/klipper-f005/printer-f005-mainline.cfg" \
		"$klipper_overlay/usr/share/fre3nder/defaults/printer.cfg"
	install -m 0644 "$project/configs/x2000/f005-mcu-release.json" \
		"$klipper_overlay/usr/share/fre3nder/f005-mcu-release.json"
	validate_f005_firmware "$f005_firmware"
	install -m 0644 "$f005_firmware" \
		"$klipper_overlay$f005_target_path"
	install -m 0644 "$version_file" \
		"$klipper_overlay/usr/share/fre3nder/VERSION"
	# A dirty tree has no remotely reconstructible app-definition revision.
	app_ref=unpublished
	[ "$project_worktree_status" != clean ] || app_ref=$project_commit
	printf '%s\n' "$app_ref" > "$klipper_overlay/usr/share/fre3nder/APP_REF"
	if [ "$artifact_mode" = development ]; then
		printf '%s\n' \
			'mode=development' \
			"commit=$project_commit" \
			"build_input_sha256=$build_input_sha256" \
			> "$development_marker"
	fi
}

prepare_moonraker_overlay() {
	prepare_moonraker_source
	[ -d "$moonraker_wheel_cache" ]

	rm -rf -- "$moonraker_overlay"
	moonraker_root="$moonraker_overlay/opt/fre3nder/moonraker"
	moonraker_env="$moonraker_overlay/opt/fre3nder/moonraker-env"
	site_packages="$moonraker_env/lib/python3.12/site-packages"
	install -d -m 0755 "$moonraker_root" "$moonraker_env/bin" "$site_packages"
	rsync -a --exclude='__pycache__/' --exclude='*.pyc' \
		"$moonraker/" "$moonraker_root/"

	# Keep a real upstream Git checkout for Moonraker's own git_repo updater,
	# while dropping transient local-clone records from the immutable baseline.
	rm -rf -- "$moonraker_root/.git/logs"
	rm -f -- \
		"$moonraker_root/.git/FETCH_HEAD" \
		"$moonraker_root/.git/ORIG_HEAD" \
		"$moonraker_root/.git/index"
	git -C "$moonraker_root" config core.logAllRefUpdates false
	git -C "$moonraker_root" read-tree HEAD
	[ "$(git -C "$moonraker_root" remote get-url origin)" = "$moonraker_url" ]
	[ "$(git -C "$moonraker_root" rev-parse HEAD)" = "$moonraker_commit" ]
	[ -d "$moonraker_root/.git" ]
	[ ! -e "$moonraker_root/.fre3nder-git" ]
	mv "$moonraker_root/.git" "$moonraker_root/.fre3nder-git"
	[ -d "$moonraker_root/.fre3nder-git" ]
	[ ! -e "$moonraker_root/.git" ]

	printf '%s\n' \
		'home = /usr/bin' \
		'include-system-site-packages = true' \
		'version = 3.12.14' \
		'executable = /usr/bin/python3' \
		'command = /usr/bin/python3 -m venv --system-site-packages /opt/fre3nder/moonraker-env' \
		> "$moonraker_env/pyvenv.cfg"
	printf '%s\n' \
		'VIRTUAL_ENV=/opt/fre3nder/moonraker-env' \
		'export VIRTUAL_ENV' \
		'PATH="$VIRTUAL_ENV/bin:$PATH"' \
		'export PATH' \
		> "$moonraker_env/bin/activate"
	ln -s /usr/bin/python3 "$moonraker_env/bin/python"
	ln -s /usr/bin/python3 "$moonraker_env/bin/python3"
	ln -s /usr/bin/pip3 "$moonraker_env/bin/pip"

	export MOONRAKER_SITE_PACKAGES="$site_packages"
	export MOONRAKER_WHEEL_MANIFEST="$moonraker_wheel_manifest"
	export MOONRAKER_WHEEL_CACHE="$moonraker_wheel_cache"
	python3 - <<'PYSTAGE'
import hashlib
import json
import os
import pathlib
import stat
import zipfile

site_packages = pathlib.Path(os.environ["MOONRAKER_SITE_PACKAGES"])
manifest_path = pathlib.Path(os.environ["MOONRAKER_WHEEL_MANIFEST"])
wheel_cache = pathlib.Path(os.environ["MOONRAKER_WHEEL_CACHE"])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

installed = set()
for wheel in manifest["wheels"]:
    path = wheel_cache / wheel["filename"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != wheel["sha256"]:
        raise SystemExit(f"wheel SHA256 mismatch: {path.name}")

    with zipfile.ZipFile(path) as archive:
        for member in sorted(archive.infolist(), key=lambda item: item.filename):
            relative = pathlib.PurePosixPath(member.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise SystemExit(f"unsafe wheel member: {member.filename}")
            if not relative.parts:
                continue
            if "__pycache__" in relative.parts or relative.suffix in (".pyc", ".pyo"):
                continue
            file_type = (member.external_attr >> 16) & 0o170000
            if file_type == stat.S_IFLNK:
                raise SystemExit(f"wheel symlink is not supported: {member.filename}")

            target = site_packages.joinpath(*relative.parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                target.chmod(0o755)
                continue
            if relative.as_posix() in installed or target.exists():
                raise SystemExit(f"duplicate wheel member: {member.filename}")
            installed.add(relative.as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))
            mode = (member.external_attr >> 16) & 0o777
            target.chmod(0o755 if mode & 0o111 else 0o644)
PYSTAGE

	if find "$site_packages" \
		\( -type d -name __pycache__ -o -type f \( -name '*.pyc' -o -name '*.pyo' \) \) \
		-print -quit | grep -q .; then
		echo 'Moonraker environment contains forbidden Python bytecode/cache files' >&2
		exit 1
	fi

	[ -f "$moonraker_root/moonraker/moonraker.py" ]
	[ -f "$moonraker_env/bin/activate" ]
	[ "$(readlink "$moonraker_env/bin/python")" = /usr/bin/python3 ]
	[ "$(readlink "$moonraker_env/bin/pip")" = /usr/bin/pip3 ]
	[ -n "$(find "$site_packages" -mindepth 1 -print -quit)" ]
}

build_moonraker_component() {
	prepare_artifact_provenance
	prepare_moonraker_overlay
	build_input=$(
		"$project/scripts/x2000-build-input-sha256" --root "$project"
	)
	tmp=$moonraker_component.tmp
	rm -rf -- "$tmp"
	mkdir -p "$tmp"
	tar --sort=name --format=ustar --mtime='@0' --owner=0 --group=0 \
		--numeric-owner -C "$moonraker_overlay" -cf "$tmp/rootfs-overlay.tar" .
	export artifact_mode build_input moonraker_commit moonraker_url project_commit project_worktree_status
	python3 - "$tmp/rootfs-overlay.tar" "$tmp/component-manifest.json" <<'PY'
import hashlib
import json
import os
import pathlib
import sys

artifact, output = map(pathlib.Path, sys.argv[1:])
manifest = {
    "schema": 1,
    "component": "moonraker",
    "source": {
        "repository": os.environ["moonraker_url"],
        "commit": os.environ["moonraker_commit"],
        "license": "GPL-3.0-only",
    },
    "artifact_mode": os.environ["artifact_mode"],
    "project_commit": os.environ["project_commit"],
    "project_worktree_status": os.environ["project_worktree_status"],
    "build_input_sha256": os.environ["build_input"],
    "artifact": {
        "name": artifact.name,
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    },
}
output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
PY
	(cd "$tmp" && sha256sum component-manifest.json rootfs-overlay.tar > SHA256SUMS)
	(cd "$tmp" && sha256sum -c SHA256SUMS)
	rm -rf -- "$moonraker_component"
	mv "$tmp" "$moonraker_component"
}
build_klipper_chelper() {
	buildroot_output=$1
	cc="$buildroot_output/host/bin/mipsel-buildroot-linux-gnu-gcc"
	strip="$buildroot_output/host/bin/mipsel-buildroot-linux-gnu-strip"
	chelper="$klipper_overlay/usr/share/klipper/klippy/chelper"
	[ -x "$cc" ]
	[ -x "$strip" ]
	set -- $(python3 - "$chelper/__init__.py" <<'PY'
import ast
import pathlib
import sys

tree = ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
for node in tree.body:
    if isinstance(node, ast.Assign):
        if any(isinstance(target, ast.Name) and target.id == "SOURCE_FILES"
               for target in node.targets):
            for name in ast.literal_eval(node.value):
                print(name)
            break
else:
    raise SystemExit("Klipper chelper SOURCE_FILES not found")
PY
	)
	(
		cd "$chelper"
		"$cc" -Wall -g -O2 -shared -fPIC \
			-flto -fwhole-program -fno-use-linker-plugin \
			-o c_helper.so "$@"
		"$strip" --strip-unneeded c_helper.so
	)
	file "$chelper/c_helper.so" | grep -q 'ELF 32-bit LSB shared object, MIPS, MIPS32 rel2'
	! readelf -S "$chelper/c_helper.so" | grep -qE '\.debug(_|$)'
	readelf -h "$chelper/c_helper.so" | grep -Fq 'Class:                             ELF32'
	readelf -h "$chelper/c_helper.so" | grep -Fq 'Data:                              2'
	readelf -h "$chelper/c_helper.so" | grep -Eq 'Flags:.*o32, mips32r2'
	readelf -h "$chelper/c_helper.so" | grep -Fq 'nan2008'
	readelf -A "$chelper/c_helper.so" | grep -Fq 'ISA: MIPS32r2'
	readelf -A "$chelper/c_helper.so" |
		grep -Fq 'FP ABI: Hard float (32-bit CPU, Any FPU)'
	readelf -d "$chelper/c_helper.so" | grep -Fq 'Shared library: [libc.so.6]'
	readelf -d "$chelper/c_helper.so" |
		grep -Fq 'Shared library: [ld-linux-mipsn8.so.1]'
}

build_klipper_mcu() {
	buildroot_output=$1
	cross_prefix="$buildroot_output/host/bin/mipsel-buildroot-linux-gnu-"
	strip="${cross_prefix}strip"
	mcu="$klipper_overlay/usr/bin/klipper_mcu"
	[ -x "${cross_prefix}gcc" ]
	[ -x "$strip" ]
	cmp -s "$klipper_linux_config" "$klipper/test/configs/linuxprocess.config"

	make -C "$klipper" distclean
	cp "$klipper_linux_config" "$klipper/.config"
	make -C "$klipper" CROSS_PREFIX="$cross_prefix" olddefconfig
	grep -Fxq 'CONFIG_MACH_LINUX=y' "$klipper/.config"
	make -C "$klipper" -j"${JOBS:-4}" CROSS_PREFIX="$cross_prefix"
	install -D -m 0755 "$klipper/out/klipper.elf" "$mcu"
	"$strip" --strip-unneeded "$mcu"

	file "$mcu" | grep -q 'ELF 32-bit LSB.*MIPS, MIPS32 rel2'
	! readelf -S "$mcu" | grep -qE '\.debug(_|$)'
	readelf -h "$mcu" | grep -Eq 'Flags:.*o32, mips32r2'
	readelf -h "$mcu" | grep -Fq 'nan2008'
	readelf -A "$mcu" | grep -Fq 'ISA: MIPS32r2'
	readelf -A "$mcu" |
		grep -Fq 'FP ABI: Hard float (32-bit CPU, Any FPU)'
	readelf -l "$mcu" |
		grep -Fq 'Requesting program interpreter: /lib/ld-linux-mipsn8.so.1'
	readelf -d "$mcu" | grep -Fq 'Shared library: [libc.so.6]'
}

stage_kernel_firmware() {
	buildroot_output=$1
	firmware="$buildroot_output/target/lib/firmware/cypress/cyfmac43430-sdio.bin"
	clm="$buildroot_output/target/lib/firmware/cypress/cyfmac43430-sdio.clm_blob"
	nvram="$project/configs/x2000/rootfs-overlay/lib/firmware/brcm/brcmfmac43430-sdio.txt"

	[ "$(sha256sum "$firmware" | awk '{print $1}')" = \
		93f3c40c94340c29a40714cb04e3e89974870fcae42a844b8a4544750159f40d ] || {
		echo 'linux-firmware CYW43430 firmware hash mismatch' >&2
		exit 1
	}
	[ "$(sha256sum "$clm" | awk '{print $1}')" = \
		3376b9c9b32d16bf762e21c7fafb665365070ae240d092498d0d1987c22022aa ] || {
		echo 'linux-firmware CYW43430 CLM hash mismatch' >&2
		exit 1
	}
	[ "$(sha256sum "$nvram" | awk '{print $1}')" = \
		6167b8aaa5e80eabe09ac5bd8570760e5241aa3a9a6243a94be9fcba33cc1915 ] || {
		echo 'Radxa AZW372 WLAN NVRAM hash mismatch' >&2
		exit 1
	}
	[ "$(wc -c < "$nvram")" -eq 1016 ]

	rm -rf -- "$kernel_firmware_dir"
	install -d -m 0700 "$kernel_firmware_dir/brcm"
	install -m 0644 "$firmware" \
		"$kernel_firmware_dir/brcm/brcmfmac43430-sdio.bin"
	install -m 0644 "$clm" \
		"$kernel_firmware_dir/brcm/brcmfmac43430-sdio.clm_blob"
	install -m 0644 "$nvram" \
		"$kernel_firmware_dir/brcm/brcmfmac43430-sdio.txt"
}

validate_kernel_patch_series() {
	validated_series="$work/fre3nder-kernel-patches.validated"
	available_series="$work/fre3nder-kernel-patches.available"
	patch_directory="$project/patches/linux"
	rm -f -- "$validated_series" "$available_series"

	if [ ! -f "$kernel_patch_series" ] || [ -L "$kernel_patch_series" ]; then
		echo 'kernel patch series is missing, non-regular, or a symlink' >&2
		return 1
	fi
	[ "$(tail -c 1 "$kernel_patch_series")" = '' ] || {
		echo 'kernel patch series must end with a newline' >&2
		return 1
	}
	[ -d "$patch_directory" ] || {
		echo 'kernel patch directory is missing' >&2
		return 1
	}

	awk '
		function fail(message) {
			failed = 1
			print message > "/dev/stderr"
			exit 1
		}
		{
			digest = substr($0, 1, 64)
			separator = substr($0, 65, 2)
			path = substr($0, 67)
			if (length(digest) != 64 || digest ~ /[^0-9a-f]/)
				fail("invalid kernel patch SHA256 at line " NR)
			if (separator != "  ")
				fail("invalid kernel patch separator at line " NR)
			if (path !~ /^patches\/linux\/[0-9][0-9][0-9][0-9]-[a-z0-9-]+\.patch$/)
				fail("invalid kernel patch path at line " NR)
			name = path
			sub(/^patches\/linux\//, "", name)
			if (index(name, sprintf("%04d-", NR)) != 1)
				fail("kernel patch series is out of order at line " NR)
			if (seen[path]++)
				fail("duplicate kernel patch path at line " NR)
			printf "%s\t%s\n", digest, path
		}
		END {
			if (!failed && NR != 14)
				fail("kernel patch series must contain exactly 14 entries")
		}
	' "$kernel_patch_series" > "$validated_series"

	find "$patch_directory" -mindepth 1 -maxdepth 1 -name '*.patch' \
		-printf 'patches/linux/%f\n' | LC_ALL=C sort > "$available_series"
	cut -f2 "$validated_series" | LC_ALL=C sort | cmp -s - "$available_series" || {
		echo 'kernel patch series does not match patches/linux' >&2
		return 1
	}

	tab=$(printf '\t')
	while IFS="$tab" read -r expected_digest relative_patch; do
		patch="$project/$relative_patch"
		if [ ! -f "$patch" ] || [ -L "$patch" ]; then
			echo "kernel patch is missing, non-regular, or a symlink: $relative_patch" >&2
			return 1
		fi
		actual_digest=$(sha256sum "$patch")
		actual_digest=${actual_digest%% *}
		[ "$actual_digest" = "$expected_digest" ] || {
			echo "kernel patch SHA256 mismatch: $relative_patch" >&2
			return 1
		}
	done < "$validated_series"

	rm -f -- "$available_series"
}

prepare_kernel() {
	[ -d "$kernel_source/.git" ]
	[ "$(git -C "$kernel_source" remote get-url origin)" = "$kernel_url" ]
	[ "$(git -C "$kernel_source" cat-file -t "$kernel_commit")" = commit ]
	[ "$(git -C "$kernel_source" rev-parse HEAD)" = "$kernel_commit" ] || {
		echo 'kernel source is not at the pinned base commit' >&2
		return 1
	}
	git -C "$kernel_source" reset --hard "$kernel_commit"
	git -C "$kernel_source" clean -fdx
	verify_kernel_source

	kernel_commit_epoch=$(
		git -C "$kernel_source" show -s --format=%ct "$kernel_commit"
	)
	case "$kernel_commit_epoch" in
	''|*[!0-9]*)
		echo 'invalid pinned kernel commit timestamp' >&2
		return 1
		;;
	esac
	kernel_build_timestamp=$(
		date -u -d "@$kernel_commit_epoch" '+%Y-%m-%d %H:%M:%S +0000'
	)
	[ -n "$kernel_build_timestamp" ]

	rm -rf -- "$kernel_build"
	install -d -m 0755 "$kernel_build"
	validate_kernel_patch_series

	tab=$(printf '\t')
	while IFS="$tab" read -r expected_digest relative_patch; do
		patch="$project/$relative_patch"
		actual_digest=$(sha256sum "$patch")
		actual_digest=${actual_digest%% *}
		[ "$actual_digest" = "$expected_digest" ] || {
			echo "kernel patch changed before apply: $relative_patch" >&2
			return 1
		}
		git -C "$kernel_source" apply --check "$patch"
		git -C "$kernel_source" apply "$patch"
		git -C "$kernel_source" apply --reverse --check "$patch"
	done < "$validated_series"
	rm -f -- "$validated_series"

	[ "$(git -C "$kernel_source" rev-parse HEAD)" = "$kernel_commit" ]
	git -C "$kernel_source" diff --check
}

check_kernel_config() {
	config=$1

	required_y='
MACH_INGENIC_SOC
DT_ENDER3_V3_KE
CPU_LITTLE_ENDIAN
CPU_MIPS32_R5
SMP
HZ_100
PREEMPT
HIGH_RES_TIMERS
NO_HZ_IDLE
SYS_SUPPORTS_ZBOOT
MMC
MMC_BLOCK
MMC_SDHCI
MMC_SDHCI_PLTFM
MMC_SDHCI_INGENIC
PWRSEQ_SIMPLE
SQUASHFS
SQUASHFS_XZ
OVERLAY_FS
EXT4_FS
SERIAL_8250
SERIAL_8250_INGENIC
SERIAL_OF_PLATFORM
I2C
I2C_JZ4780
TOUCHSCREEN_NS2009
PWM
PWM_X2000
USB_SUPPORT
USB
USB_DWC2
USB_DWC2_HOST
USB_ROLE_SWITCH
PHY_INGENIC_USB
USB_STORAGE
USB_USBNET
USB_NET_AX88179_178A
USB_NET_CDC_NCM
USB_NET_CDCETHER
BRCMFMAC
BRCMFMAC_SDIO
REGULATOR_FIXED_VOLTAGE
SPI_GPIO
SPI_SPIDEV
VFAT_FS
USB_VIDEO_CLASS
FB
FB_X2000_DPU
FB_X2000_DPU_ENDER3_V3_KE
BACKLIGHT_GPIO
'

	for symbol in $required_y; do
		grep -Fxq "CONFIG_${symbol}=y" "$config" || {
			echo "required kernel option is not enabled: CONFIG_${symbol}" >&2
			return 1
		}
	done

	required_n='
CPU_BIG_ENDIAN
PREEMPT_RT
HZ_250
NETWORK_FILESYSTEMS
USB_DWC2_PERIPHERAL
USB_DWC2_DUAL_ROLE
USB_GADGET
USB_LIBCOMPOSITE
USB_CONFIGFS
BRCMFMAC_USB
IIO
MTD
SOUND
WATCHDOG
BACKLIGHT_PWM
LOCALVERSION_AUTO
'

	for symbol in $required_n; do
		if grep -Eq "^CONFIG_${symbol}=(y|m)$" "$config"; then
			echo "forbidden kernel option is active: CONFIG_${symbol}" >&2
			return 1
		fi
	done

	legacy='
DT_HALLEY5_V30
FB_INGENIC
FB_INGENIC_STAGE
STAGE_ENDER3_V3_KE_480X272
SERIAL_INGENIC
SERIAL_INGENIC_UART
SERIAL_INGENIC_CONSOLE
I2C_INGENIC
PWM_INGENIC_V2
PINCTRL_INGENIC_V2
BCMDHD
SND_ASOC_INGENIC
VIDEOBUF2_DMA_CONTIG_INGENIC
INGENIC_SPI
INGENIC_SFC
INGENIC_RSA
VIDEO_INGENIC_ISP
VIDEO_INGENIC_ROTATE
VIDEO_INGENIC_VCODEC
HALLEY5_CAMERA_BOARD
RD_X2000_HALLEY5_CAMERA_4V3
INGENIC_ISP_CAMERA_OV2735A
TOUCHSCREEN_GT9XX
INGENIC_MAC
INGENIC_WDT
'

	for symbol in $legacy; do
		if grep -Eq "^CONFIG_${symbol}=(y|m)$" "$config"; then
			echo "legacy vendor kernel option is active: CONFIG_${symbol}" >&2
			return 1
		fi
	done

	grep -Fxq 'CONFIG_NR_CPUS=2' "$config"
	grep -Fxq 'CONFIG_MMC_BLOCK_MINORS=16' "$config"
	grep -Fxq 'CONFIG_INITRAMFS_SOURCE=""' "$config"
	grep -Fxq 'CONFIG_LOCALVERSION="-fre3nder"' "$config"
	grep -Fxq 'CONFIG_ZBOOT_LOAD_ADDRESS=0x80F00000' "$config"
	grep -Fxq \
		'CONFIG_EXTRA_FIRMWARE="brcm/brcmfmac43430-sdio.bin brcm/brcmfmac43430-sdio.clm_blob brcm/brcmfmac43430-sdio.txt"' \
		"$config"
	grep -Fxq \
		"CONFIG_EXTRA_FIRMWARE_DIR=\"$kernel_firmware_dir\"" \
		"$config"

	if grep -Eq \
		'ttyS4|halley5|6\.6\.18-rt23|STAGE_ENDER|FB_INGENIC' \
		"$config"; then
		echo 'stale vendor kernel identity remains in effective config' >&2
		return 1
	fi
}

configure_kernel() {
	if [ ! -f "$kernel_defconfig" ] || [ -L "$kernel_defconfig" ]; then
		echo 'clean-port kernel defconfig is missing, non-regular, or a symlink' >&2
		return 1
	fi
	[ -x "$kernel_source/scripts/config" ]
	[ -x "$kernel_cc" ]
	[ -d "$kernel_firmware_dir" ]

	cp "$kernel_defconfig" "$kernel_build/.config"

	make -C "$kernel_source" O="$kernel_build" \
		ARCH=mips CROSS_COMPILE="$kernel_cross_compile" CC="$kernel_cc" \
		HOSTCFLAGS='-Wno-error=incompatible-pointer-types' olddefconfig

	# The repository defconfig must already be the canonical savedefconfig
	# for the pinned clean-port tree.
	make -s -C "$kernel_source" O="$kernel_build" \
		ARCH=mips CROSS_COMPILE="$kernel_cross_compile" CC="$kernel_cc" \
		HOSTCFLAGS='-Wno-error=incompatible-pointer-types' savedefconfig
	cmp -s "$kernel_build/defconfig" "$kernel_defconfig" || {
		echo 'clean-port kernel defconfig is not canonical for the pinned tree' >&2
		return 1
	}
	rm -f -- "$kernel_build/defconfig"

	base_config="$work/fre3nder-kernel-config.base"
	base_normalized="$work/fre3nder-kernel-config.base.normalized"
	final_normalized="$work/fre3nder-kernel-config.final.normalized"

	cp "$kernel_build/.config" "$base_config"

	"$kernel_source/scripts/config" \
		--file "$kernel_build/.config" \
		--set-str EXTRA_FIRMWARE_DIR "$kernel_firmware_dir"

	make -C "$kernel_source" O="$kernel_build" \
		ARCH=mips CROSS_COMPILE="$kernel_cross_compile" CC="$kernel_cc" \
		HOSTCFLAGS='-Wno-error=incompatible-pointer-types' olddefconfig

	# EXTRA_FIRMWARE_DIR is the only dynamic Kconfig value permitted.
	sed \
		's|^CONFIG_EXTRA_FIRMWARE_DIR=.*$|CONFIG_EXTRA_FIRMWARE_DIR="<dynamic>"|' \
		"$base_config" > "$base_normalized"
	sed \
		's|^CONFIG_EXTRA_FIRMWARE_DIR=.*$|CONFIG_EXTRA_FIRMWARE_DIR="<dynamic>"|' \
		"$kernel_build/.config" > "$final_normalized"

	cmp -s "$base_normalized" "$final_normalized" || {
		echo 'dynamic firmware path changed additional kernel options' >&2
		diff -u "$base_normalized" "$final_normalized" >&2 || true
		return 1
	}

	rm -f -- "$base_config" "$base_normalized" "$final_normalized"

	check_kernel_config "$kernel_build/.config"
}


check_kernel_boot_image() {
	image=$1

	if [ ! -f "$image" ] || [ -L "$image" ]; then
		echo "kernel boot image missing, non-regular, or symlink: $image" >&2
		return 1
	fi

	image_info=$(dumpimage -l "$image") || return 1
	printf '%s\n' "$image_info"

	printf '%s\n' "$image_info" |
		grep -Eq '^Image Name:[[:space:]]+Linux-6\.6\.18-fre3nder$'

	printf '%s\n' "$image_info" |
		grep -Eq '^Image Type:[[:space:]]+MIPS Linux Kernel Image \(uncompressed\)$'

	printf '%s\n' "$image_info" |
		grep -Eiq '^Load Address:[[:space:]]+80f00000$'

	printf '%s\n' "$image_info" |
		grep -Eiq '^Entry Point:[[:space:]]+80f00000$'

	[ "$(stat -c '%s' "$image")" -lt 8388608 ] || {
		echo 'kernel boot image is not strictly smaller than 8 MiB' >&2
		return 1
	}
}

inspect_ximage_vmlinux() {
	vmlinux=$1
	contract=$2

	if [ ! -f "$ximage_inspector" ] || [ -L "$ximage_inspector" ]; then
		echo 'xImage vmlinux inspector is missing, non-regular, or a symlink' >&2
		return 1
	fi
	if [ ! -f "$vmlinux" ] || [ -L "$vmlinux" ]; then
		echo 'xImage input vmlinux is missing, non-regular, or a symlink' >&2
		return 1
	fi

	python3 "$ximage_inspector" --outer-load "$ximage_outer_load" \
		"$vmlinux" > "$contract"
	ximage_inner_load=$(python3 - "$contract" <<'PY'
import json
import pathlib
import sys

print(json.loads(pathlib.Path(sys.argv[1]).read_text())["load_address"])
PY
	)
	ximage_kernel_entry=$(python3 - "$contract" <<'PY'
import json
import pathlib
import sys

print(json.loads(pathlib.Path(sys.argv[1]).read_text())["kernel_entry"])
PY
	)

	[ "$ximage_inner_load" = "$ximage_expected_inner_load" ] || {
		echo "unexpected clean-port vmlinux load address: $ximage_inner_load" >&2
		return 1
	}
	grep -Fxq 'CONFIG_SMP=y' "$kernel_build/.config"
	grep -Fxq 'CONFIG_NR_CPUS=2' "$kernel_build/.config"
	strings "$vmlinux" | grep -Fq 'Linux version 6.6.18-fre3nder'
	strings "$vmlinux" | grep -Fq 'creality,ender-3-v3-ke'
	if strings "$vmlinux" | grep -Fq 'ingenic,halley5'; then
		echo 'xImage payload has Vendor-kernel identity' >&2
		return 1
	fi
}

install_ximage_wrapper() {
	fragment="$ximage_wrapper_source/arch-mips-Makefile.fragment"

	if [ -e "$ximage_wrapper_destination" ] || \
		[ -L "$ximage_wrapper_destination" ]; then
		echo 'unexpected pre-existing zcompressed wrapper directory' >&2
		return 1
	fi
	for source in Makefile head.S misc.c ld.script dummy.c \
		arch-mips-Makefile.fragment; do
		if [ ! -f "$ximage_wrapper_source/$source" ] || \
			[ -L "$ximage_wrapper_source/$source" ]; then
			echo "xImage wrapper source missing or non-regular: $source" >&2
			return 1
		fi
	done

	rm -f -- "$ximage_arch_makefile_backup"
	cp "$ximage_arch_makefile" "$ximage_arch_makefile_backup"
	ximage_arch_makefile_saved=true
	ximage_wrapper_destination_owned=true
	install -d -m 0755 "$ximage_wrapper_destination"
	install -m 0644 \
		"$ximage_wrapper_source/Makefile" \
		"$ximage_wrapper_source/head.S" \
		"$ximage_wrapper_source/misc.c" \
		"$ximage_wrapper_source/ld.script" \
		"$ximage_wrapper_source/dummy.c" \
		"$ximage_wrapper_destination/"
	printf '\n' >> "$ximage_arch_makefile"
	cat "$fragment" >> "$ximage_arch_makefile"
}

remove_ximage_wrapper() {
	cleanup_failed=false

	if [ "$ximage_wrapper_destination_owned" = true ]; then
		if rm -rf -- "$ximage_wrapper_destination"; then
			ximage_wrapper_destination_owned=false
		else
			echo 'failed to remove partial xImage wrapper directory' >&2
			cleanup_failed=true
		fi
	fi

	if [ "$ximage_arch_makefile_saved" = true ]; then
		if [ -f "$ximage_arch_makefile_backup" ] && \
			[ ! -L "$ximage_arch_makefile_backup" ] && \
			mv -f -- "$ximage_arch_makefile_backup" \
				"$ximage_arch_makefile"; then
			ximage_arch_makefile_saved=false
		else
			echo 'failed to restore arch/mips/Makefile after xImage wrapper' >&2
			cleanup_failed=true
		fi
	elif ! rm -f -- "$ximage_arch_makefile_backup"; then
		echo 'failed to remove partial xImage Makefile backup' >&2
		cleanup_failed=true
	fi

	[ "$cleanup_failed" = false ]
}

build_ximage_wrapper() {
	jobs=$1
	contract=$2
	vmlinux="$kernel_build/vmlinux"
	wrapper_build="$kernel_build/arch/mips/boot/zcompressed"
	ximage_arch_makefile="$kernel_source/arch/mips/Makefile"
	ximage_arch_makefile_backup="$work/fre3nder-ximage-arch-mips-Makefile"
	ximage_wrapper_destination="$kernel_source/arch/mips/boot/zcompressed"
	ximage_arch_makefile_saved=false
	ximage_wrapper_destination_owned=false

	inspect_ximage_vmlinux "$vmlinux" "$contract"
	vmlinux_sha256_before=$(sha256sum "$vmlinux")
	vmlinux_sha256_before=${vmlinux_sha256_before%% *}

	trap remove_ximage_wrapper EXIT
	trap 'exit 1' HUP INT TERM
	install_ximage_wrapper
	SOURCE_DATE_EPOCH="$kernel_commit_epoch" \
	LOCALVERSION='' \
	KBUILD_BUILD_USER="$kernel_build_user" \
	KBUILD_BUILD_HOST="$kernel_build_host" \
	KBUILD_BUILD_TIMESTAMP="$kernel_build_timestamp" \
	KBUILD_BUILD_VERSION="$kernel_build_version" \
	make -C "$kernel_source" O="$kernel_build" -j"$jobs" ARCH=mips \
		CROSS_COMPILE="$kernel_cross_compile" CC="$kernel_cc" \
		HOSTCFLAGS='-Wno-error=incompatible-pointer-types' \
		FRE3NDER_XIMAGE_INNER_LOAD="$ximage_inner_load" \
		FRE3NDER_XIMAGE_KERNEL_ENTRY="$ximage_kernel_entry" \
		FRE3NDER_XIMAGE_OUTER_LOAD="$ximage_outer_load" \
		fre3nder-ximage-diagnostic
	remove_ximage_wrapper
	trap - EXIT HUP INT TERM

	vmlinux_sha256_after=$(sha256sum "$vmlinux")
	vmlinux_sha256_after=${vmlinux_sha256_after%% *}
	[ "$vmlinux_sha256_after" = "$vmlinux_sha256_before" ] || {
		echo 'vmlinux changed while building the diagnostic wrapper' >&2
		return 1
	}

	[ -f "$wrapper_build/vmlinux.bin" ] && \
		[ ! -L "$wrapper_build/vmlinux.bin" ]
	ximage_payload_size=$(stat -c '%s' "$wrapper_build/vmlinux.bin")
	ximage_payload_end=$(python3 - "$ximage_inner_load" \
		"$ximage_payload_size" <<'PY'
import sys

print(f"0x{int(sys.argv[1], 0) + int(sys.argv[2]):08x}")
PY
	)
	python3 - "$ximage_payload_end" "$ximage_outer_load" <<'PY'
import sys

if int(sys.argv[1], 0) > int(sys.argv[2], 0):
    raise SystemExit("decompressed payload overlaps the xImage wrapper")
PY

	[ -f "$wrapper_build/xImage" ] && [ ! -L "$wrapper_build/xImage" ]
}

write_kernel_final_diff() {
	output=$1
	temporary_index="${output}.index.$$"

	rm -f -- "$output" "$temporary_index"

	if ! GIT_INDEX_FILE="$temporary_index" \
		git -C "$kernel_source" read-tree "$kernel_commit"; then
		rm -f -- "$temporary_index"
		return 1
	fi

	if ! GIT_INDEX_FILE="$temporary_index" \
		git -C "$kernel_source" add -A -- .; then
		rm -f -- "$temporary_index"
		return 1
	fi

	if ! LC_ALL=C GIT_INDEX_FILE="$temporary_index" \
		git -C "$kernel_source" diff \
			--cached --binary --full-index --no-ext-diff \
			"$kernel_commit" -- > "$output"; then
		rm -f -- "$output" "$temporary_index"
		return 1
	fi

	rm -f -- "$temporary_index"

	[ -s "$output" ] || {
		echo 'kernel final patch-result diff is empty' >&2
		return 1
	}
}

record_kernel_build() {
	out=$1
	buildroot_output=$2
	manifest="$out/build-manifest.json"

	for file in \
		"$manifest" \
		"$kernel_build/vmlinux" \
		"$kernel_build/.config" \
		"$kernel_build/include/config/kernel.release" \
		"$out/kernel.uImage" \
		"$out/ender3-v3-ke.dtb" \
		"$out/effective-kernel-config"; do
		if [ ! -f "$file" ] || [ -L "$file" ]; then
			echo "kernel provenance input missing or non-regular: $file" >&2
			return 1
		fi
	done

	actual_base_commit=$(git -C "$kernel_source" rev-parse HEAD)
	[ "$actual_base_commit" = "$kernel_commit" ] || {
		echo 'kernel provenance base commit mismatch' >&2
		return 1
	}

	actual_base_tree=$(
		git -C "$kernel_source" rev-parse "${kernel_commit}^{tree}"
	)
	[ -n "$actual_base_tree" ]

	patch_series_sha256=$(sha256sum "$kernel_patch_series")
	patch_series_sha256=${patch_series_sha256%% *}

	defconfig_sha256=$(sha256sum "$kernel_defconfig")
	defconfig_sha256=${defconfig_sha256%% *}

	effective_config_sha256=$(sha256sum "$kernel_build/.config")
	effective_config_sha256=${effective_config_sha256%% *}

	actual_kernel_release=$(cat "$kernel_build/include/config/kernel.release")
	[ "$actual_kernel_release" = "$kernel_release" ] || {
		echo "unexpected kernel release: $actual_kernel_release" >&2
		return 1
	}

	compiler_target=$("$kernel_cc" -dumpmachine)
	compiler_version=$("$kernel_cc" -dumpfullversion)
	compiler_identity=$("$kernel_cc" --version | sed -n '1p')

	[ -n "$compiler_target" ]
	[ -n "$compiler_version" ]
	[ -n "$compiler_identity" ]

	toolchain_fingerprint=$(
		read_buildroot_toolchain_fingerprint "$buildroot_output"
	) || {
		echo 'kernel toolchain fingerprint missing or invalid' >&2
		return 1
	}

	final_diff="$work/fre3nder-kernel-final.diff"
	write_kernel_final_diff "$final_diff"
	final_diff_sha256=$(sha256sum "$final_diff")
	final_diff_sha256=${final_diff_sha256%% *}
	rm -f -- "$final_diff"

	vmlinux_sha256=$(sha256sum "$kernel_build/vmlinux")
	vmlinux_sha256=${vmlinux_sha256%% *}

	export KERNEL_BASE_COMMIT="$actual_base_commit"
	export KERNEL_BASE_TREE="$actual_base_tree"
	export KERNEL_PATCH_SERIES_SHA256="$patch_series_sha256"
	export KERNEL_FINAL_DIFF_SHA256="$final_diff_sha256"
	export KERNEL_DEFCONFIG_SHA256="$defconfig_sha256"
	export KERNEL_EFFECTIVE_CONFIG_SHA256="$effective_config_sha256"
	export KERNEL_RELEASE="$actual_kernel_release"
	export KERNEL_COMPILER_TARGET="$compiler_target"
	export KERNEL_COMPILER_VERSION="$compiler_version"
	export KERNEL_COMPILER_IDENTITY="$compiler_identity"
	export KERNEL_TOOLCHAIN_FINGERPRINT="$toolchain_fingerprint"
	export KERNEL_VMLINUX_SHA256="$vmlinux_sha256"
	export KERNEL_BUILD_USER="$kernel_build_user"
	export KERNEL_BUILD_HOST="$kernel_build_host"
	export KERNEL_BUILD_TIMESTAMP="$kernel_build_timestamp"
	export KERNEL_BUILD_VERSION="$kernel_build_version"
	export KERNEL_CC="$kernel_cc"

	python3 - "$manifest" "$kernel_patch_series" "$project" <<'PY'
import hashlib
import json
import os
import pathlib
import sys

manifest_path = pathlib.Path(sys.argv[1])
series_path = pathlib.Path(sys.argv[2])
project = pathlib.Path(sys.argv[3])

manifest = json.loads(manifest_path.read_text())
series_sha256 = hashlib.sha256(series_path.read_bytes()).hexdigest()

if series_sha256 != os.environ["KERNEL_PATCH_SERIES_SHA256"]:
    raise SystemExit("kernel patch-series SHA256 changed during provenance capture")

patches = []
for line in series_path.read_text().splitlines():
    digest, relative_text = line.split("  ", 1)
    relative = pathlib.PurePosixPath(relative_text)
    patch = project.joinpath(*relative.parts)
    actual = hashlib.sha256(patch.read_bytes()).hexdigest()
    if actual != digest:
        raise SystemExit(f"kernel patch changed during provenance capture: {relative}")
    patches.append({
        "path": relative.as_posix(),
        "sha256": actual,
    })

artifacts = manifest.get("artifacts", {})
kernel_artifact_names = (
    "kernel.uImage",
    "ender3-v3-ke.dtb",
    "effective-kernel-config",
)

missing = [
    name
    for name in kernel_artifact_names
    if name not in artifacts
]
if missing:
    raise SystemExit(
        "kernel manifest missing artifact hashes: " + ", ".join(missing)
    )

if artifacts["effective-kernel-config"] != os.environ[
    "KERNEL_EFFECTIVE_CONFIG_SHA256"
]:
    raise SystemExit(
        "exported effective kernel config differs from Kbuild .config"
    )

try:
    series_relative = series_path.relative_to(project).as_posix()
except ValueError:
    raise SystemExit("kernel patch-series path is outside the project")

kernel_build = {
    "base_commit": os.environ["KERNEL_BASE_COMMIT"],
    "base_tree": os.environ["KERNEL_BASE_TREE"],
    "patch_series": {
        "path": series_relative,
        "sha256": os.environ["KERNEL_PATCH_SERIES_SHA256"],
        "patches": patches,
    },
    "final_diff_sha256": os.environ["KERNEL_FINAL_DIFF_SHA256"],
    "defconfig": {
        "path": "configs/x2000/kernel-clean-port.defconfig",
        "sha256": os.environ["KERNEL_DEFCONFIG_SHA256"],
    },
    "effective_config_sha256": os.environ[
        "KERNEL_EFFECTIVE_CONFIG_SHA256"
    ],
    "kernelrelease": os.environ["KERNEL_RELEASE"],
    "compiler": {
        "binary": pathlib.Path(os.environ["KERNEL_CC"]).name,
        "target": os.environ["KERNEL_COMPILER_TARGET"],
        "version": os.environ["KERNEL_COMPILER_VERSION"],
        "identity": os.environ["KERNEL_COMPILER_IDENTITY"],
    },
    "buildroot_toolchain_fingerprint": os.environ[
        "KERNEL_TOOLCHAIN_FINGERPRINT"
    ],
    "kbuild": {
        "build_user": os.environ["KERNEL_BUILD_USER"],
        "build_host": os.environ["KERNEL_BUILD_HOST"],
        "build_timestamp": os.environ["KERNEL_BUILD_TIMESTAMP"],
        "build_version": int(os.environ["KERNEL_BUILD_VERSION"]),
    },
    "vmlinux_sha256": os.environ["KERNEL_VMLINUX_SHA256"],
    "artifacts": {
        name: artifacts[name]
        for name in kernel_artifact_names
    },
}

manifest["kernel_build"] = kernel_build
manifest_path.write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n"
)
PY
}

record_ximage_diagnostic() {
	out=$1
	contract=$2
	manifest="$out/build-manifest.json"

	export XIMAGE_CONTRACT="$contract"
	export XIMAGE_VMLINUX="$kernel_build/vmlinux"
	export XIMAGE_OUTPUT="$out/kernel.uImage"
	export XIMAGE_WRAPPER_SOURCE="$ximage_wrapper_source"
	export XIMAGE_VENDOR_URL="$ximage_vendor_url"
	export XIMAGE_VENDOR_COMMIT="$ximage_vendor_commit"
	export XIMAGE_OUTER_LOAD="$ximage_outer_load"
	export XIMAGE_PAYLOAD_SIZE="$ximage_payload_size"
	export XIMAGE_PAYLOAD_END="$ximage_payload_end"
	export XIMAGE_KERNEL_COMMIT="$kernel_commit"

	python3 - "$manifest" "$project" <<'PY'
import hashlib
import json
import os
import pathlib
import sys

manifest_path = pathlib.Path(sys.argv[1])
project = pathlib.Path(sys.argv[2])
contract = json.loads(pathlib.Path(os.environ["XIMAGE_CONTRACT"]).read_text())
manifest = json.loads(manifest_path.read_text())

if manifest.get("artifact_mode") != "development":
    raise SystemExit("xImage diagnostic manifest is not in development mode")

vmlinux = pathlib.Path(os.environ["XIMAGE_VMLINUX"])
image = pathlib.Path(os.environ["XIMAGE_OUTPUT"])
source_root = pathlib.Path(os.environ["XIMAGE_WRAPPER_SOURCE"])
source_names = (
    "Makefile",
    "head.S",
    "misc.c",
    "ld.script",
    "dummy.c",
    "arch-mips-Makefile.fragment",
)

source_files = {}
for name in source_names:
    source = source_root / name
    if source.is_symlink() or not source.is_file():
        raise SystemExit(f"invalid xImage wrapper source: {source}")
    source_files[
        source.relative_to(project).as_posix()
    ] = hashlib.sha256(source.read_bytes()).hexdigest()

vmlinux_sha256 = hashlib.sha256(vmlinux.read_bytes()).hexdigest()
image_sha256 = hashlib.sha256(image.read_bytes()).hexdigest()
if manifest.get("kernel_build", {}).get("vmlinux_sha256") != vmlinux_sha256:
    raise SystemExit("diagnostic vmlinux disagrees with kernel provenance")
if manifest.get("artifacts", {}).get("kernel.uImage") != image_sha256:
    raise SystemExit("diagnostic image disagrees with artifact provenance")

manifest["ximage_diagnostic"] = {
    "mode": "development-diagnostic",
    "hardware_validated": False,
    "upstream_kernel_commit": os.environ["XIMAGE_KERNEL_COMMIT"],
    "vmlinux": {
        "sha256": vmlinux_sha256,
        "elf_load_address": contract["load_address"],
        "elf_entry": contract["elf_entry"],
        "kernel_entry": contract["kernel_entry"],
        "load_file_end": contract["load_file_end"],
        "load_memory_end": contract["load_memory_end"],
        "payload_binary_size": int(os.environ["XIMAGE_PAYLOAD_SIZE"]),
        "payload_decompression_end": os.environ["XIMAGE_PAYLOAD_END"],
    },
    "ximage": {
        "outer_load_address": os.environ["XIMAGE_OUTER_LOAD"],
        "outer_entry": os.environ["XIMAGE_OUTER_LOAD"],
        "kernel_uimage_sha256": image_sha256,
    },
    "wrapper": {
        "role": "Ingenic gzip decompressor and XBurst cache-flush handoff only",
        "source_repository": os.environ["XIMAGE_VENDOR_URL"],
        "vendor_source_commit": os.environ["XIMAGE_VENDOR_COMMIT"],
        "vendor_source_path": "arch/mips/boot/zcompressed",
        "license": "GPL-2.0-only",
        "source_files": source_files,
    },
}

manifest_path.write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n"
)
PY
}

check_kernel_dtb() {
	ksource=$1
	kbuild=$2
	dts="$ksource/arch/mips/boot/dts/ingenic/ender3-v3-ke.dts"
	dtb="$kbuild/arch/mips/boot/dts/ingenic/ender3-v3-ke.dtb"
	decoded="$work/fre3nder-x2000-kernel-only.dts"

	[ -f "$dts" ]
	[ -f "$dtb" ]

	grep -Fq 'compatible = "creality,ender-3-v3-ke", "ingenic,x2000";' "$dts"
	grep -Fq 'bootargs = "console=ttyS4,115200 root=/dev/mmcblk0p8 rootwait rootfstype=squashfs ro";' "$dts"
	grep -Fq 'compatible = "pwm-beeper";' "$dts"
	grep -Fq 'pwms = <&pwm 3 1000000 0>;' "$dts"
	grep -Fq 'compatible = "creality,ender-3-v3-ke-panel";' "$dts"
	grep -Fq 'reset-gpios = <&gpb 16 GPIO_ACTIVE_LOW>;' "$dts"
	grep -Fq 'vmmc-supply = <&wifi_bt_power>;' "$dts"
	grep -Fq 'mmc-pwrseq = <&wlan_pwrseq>;' "$dts"
	grep -Fq 'post-power-on-delay-ms = <100>;' "$dts"
	grep -Fq 'dr_mode = "host";' "$dts"
	grep -Fq 'vbus-supply = <&usb_vbus>;' "$dts"
	grep -Fq 'compatible = "spi-gpio";' "$dts"
	grep -Fq 'compatible = "rohm,dh2228fv";' "$dts"

	if grep -Eq \
		'wlan-reg-on-gpios|ingenic,drvvbus-gpio|ingenic,vbus-dete-gpio' \
		"$dts"; then
		echo 'legacy vendor DT properties remain in clean-port DTS' >&2
		return 1
	fi

	dtc -I dtb -O dts -o "$decoded" "$dtb"

	grep -Fq 'creality,ender-3-v3-ke' "$decoded"
	grep -Fq 'creality,ender-3-v3-ke-panel' "$decoded"
	grep -Fq 'compatible = "pwm-beeper";' "$decoded"
	grep -Fq 'root=/dev/mmcblk0p8' "$decoded"
	grep -Fq 'regulator-wifi-bt' "$decoded"
	grep -Fq 'vmmc-supply' "$decoded"
	grep -Fq 'mmc-pwrseq' "$decoded"
	grep -Fq 'dr_mode = "host";' "$decoded"
	grep -Fq 'spi2 = "/spi-gpio-adxl345";' "$decoded"
	grep -Fq 'compatible = "spi-gpio";' "$decoded"
	grep -Fq 'compatible = "rohm,dh2228fv";' "$decoded"
	grep -Fq 'spi-max-frequency = <0x1e8480>;' "$decoded"

	if grep -Eq \
		'wlan-reg-on-gpios|ingenic,drvvbus-gpio|ingenic,vbus-dete-gpio' \
		"$decoded"; then
		echo 'legacy vendor DT properties remain in compiled clean-port DTB' >&2
		return 1
	fi

	rm -f -- "$decoded"
}
check_default_initramfs() {
	initramfs_build=$1
	archive="$initramfs_build/usr/initramfs_data.cpio"
	[ -f "$archive" ]
	entries=$(cpio -it < "$archive" 2>/dev/null)
	[ "$(printf '%s\n' "$entries" | sed '/^$/d' | wc -l)" -eq 3 ]
	printf '%s\n' "$entries" | grep -Fxq dev
	printf '%s\n' "$entries" | grep -Fxq dev/console
	printf '%s\n' "$entries" | grep -Fxq root
	! printf '%s\n' "$entries" | grep -Eq '(^|/)init$'
	nm -C --defined-only "$initramfs_build/vmlinux" | awk '{print $3}' | grep -Fxq '__initramfs_size'
}

check_rootfs() {
	brout=$1
	target="$brout/target"
	inittab="$target/etc/inittab"
	busybox_config=$(find "$brout/build" -maxdepth 2 -path '*/busybox-*/.config' -print -quit)
	dropbear_options=$(find "$brout/build" -maxdepth 2 -path '*/dropbear-*/localoptions.h' -print -quit)

	if find "$project/configs/x2000/rootfs-overlay" \
		\( -type d -name __pycache__ -o -type f \( -name '*.pyc' -o -name '*.pyo' \) \) \
		-print -quit | grep -q .; then
		echo 'RootFS overlay contains forbidden Python bytecode/cache files' >&2
		exit 1
	fi

	grep -Fxq 'BR2_ROOTFS_DEVICE_CREATION_DYNAMIC_MDEV=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_WPA_SUPPLICANT=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_WPA_SUPPLICANT_NL80211=y' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_WPA_SUPPLICANT_WEXT is not set' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_WPA_SUPPLICANT_EAP is not set' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_WPA_SUPPLICANT_DBUS is not set' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_LIBNL=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_DROPBEAR=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_DROPBEAR_SMALL=y' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_DROPBEAR_CLIENT is not set' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_DROPBEAR_LOCALOPTIONS_FILE="/project/configs/x2000/dropbear.localoptions"' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON3=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON3_ZLIB=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON3_PYEXPAT=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON3_SQLITE=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_PIP=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_SETUPTOOLS=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON3_SSL=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_CA_CERTIFICATES=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_NUMPY=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_LIGHTTPD=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_LIGHTTPD_PCRE=y' "$brout/.config"
	[ "$(grep -Ec '^BR2_PACKAGE_LIGHTTPD.*=y$' "$brout/.config")" -eq 2 ]
	grep -Fxq 'BR2_PACKAGE_PYTHON_PILLOW=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_PYYAML=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_TORNADO=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_MARKUPSAFE=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_CFFI=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_GREENLET=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_JINJA2=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_MARKUPSAFE=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_SERIAL=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_ZEROCONF=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_DBUS_FAST=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_STREAMING_FORM_DATA=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_DISTRO=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_PAHO_MQTT=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_PERIPHERY=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_CERTIFI=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_REQUESTS=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_REQUESTS_OAUTHLIB=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_CLICK=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_MARKDOWN=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_PYASN1=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_PYTHON_WRAPT=y' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_PYTHON_CAN is not set' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_ALSA_LIB is not set' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_ALSA_UTILS is not set' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_OPENSSL=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_MJPG_STREAMER=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_JPEG=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_EXPAT=y' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_SQLITE=y' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_NCURSES is not set' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_READLINE is not set' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_ZLIB=y' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_MTD is not set' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_BUSYBOX_SHOW_OTHERS is not set' "$brout/.config"
	grep -Fxq 'BR2_PACKAGE_IPROUTE2=y' "$brout/.config"
	[ -z "$(find "$brout/build" -maxdepth 1 -type d \
		-name 'i2c-tools-*' -print -quit)" ]

	grep -Fxq 'CONFIG_I2CGET=y' "$busybox_config"
	grep -Fxq 'CONFIG_I2CSET=y' "$busybox_config"
	grep -Fxq 'CONFIG_I2CDUMP=y' "$busybox_config"
	grep -Fxq 'CONFIG_I2CDETECT=y' "$busybox_config"
	grep -Fxq 'CONFIG_I2CTRANSFER=y' "$busybox_config"
	grep -Fxq '# CONFIG_IP is not set' "$busybox_config"
	grep -Fxq '# BR2_PACKAGE_INPUT_EVENT_DAEMON is not set' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_SPI_TOOLS is not set' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_SYSSTAT is not set' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_IFUPDOWN_SCRIPTS is not set' "$brout/.config"
	[ -z "$(find "$brout/build" -maxdepth 1 -type d \
		-name 'bash-*' -print -quit)" ]
	[ ! -e "$target/bin/bash" ]
	[ "$(readlink "$target/bin/sh")" = busybox ]
	grep -Fxq 'CONFIG_ASH=y' "$busybox_config"
	grep -Fxq '# BR2_PACKAGE_ANDROID_TOOLS is not set' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_DAEMON is not set' "$brout/.config"
	grep -Fxq '# BR2_PACKAGE_UTIL_LINUX is not set' "$brout/.config"
	grep -Fxq '# BR2_TARGET_GENERIC_REMOUNT_ROOTFS_RW is not set' "$brout/.config"
	grep -Fxq '# BR2_TARGET_ROOTFS_JFFS2 is not set' "$brout/.config"
	grep -Fxq '# BR2_TARGET_ROOTFS_UBIFS is not set' "$brout/.config"
	grep -Fxq 'BR2_TARGET_ROOTFS_SQUASHFS4_XZ=y' "$brout/.config"
	[ -x "$target/etc/init.d/fre3nder-root" ]
	for init_script in S10mdev S20fre3nder-provision \
		S40fre3nder-network S50dropbear S59fre3nder-klipper-mcu \
		S60fre3nder-klipper \
		S61fre3nder-moonraker S64fre3nder-guppyscreen; do
		[ -x "$target/etc/init.d/$init_script" ]
	done
	[ ! -e "$target/etc/init.d/S51fre3nder-ssh-recovery-test" ]
	[ ! -e "$target/usr/share/fre3nder-ssh-recovery-test" ]
	printf '%s\n' \
		S20fre3nder-provision \
		S40fre3nder-network \
		S50dropbear \
		S59fre3nder-klipper-mcu \
		S60fre3nder-klipper \
		S61fre3nder-moonraker \
		S64fre3nder-guppyscreen | sort -C
	[ -n "$busybox_config" ]
	[ -n "$dropbear_options" ]
	[ "$(readlink "$target/sbin/init")" = ../bin/busybox ]
	[ -x "$target/bin/busybox" ]
	[ -x "$target/lib/ld-linux-mipsn8.so.1" ]
	[ -x "$target/lib/libc.so.6" ]
	[ ! -e "$target/lib/ld.so.1" ]
	for elf in \
		"$target/bin/busybox" \
		"$target/usr/sbin/lighttpd" \
		"$target/usr/lib/lighttpd/mod_proxy.so" \
		"$target/sbin/ip" \
		"$target/lib/ld-linux-mipsn8.so.1" \
		"$target/lib/libc.so.6"; do
		file "$elf" | grep -q 'ELF 32-bit LSB.*MIPS, MIPS32 rel2'
		readelf -h "$elf" | grep -Eq 'Flags:.*nan2008, o32, mips32r2'
		readelf -A "$elf" | grep -Fq 'ISA: MIPS32r2'
		readelf -A "$elf" |
			grep -Fq 'FP ABI: Hard float (32-bit CPU, Any FPU)'
	done
	readelf -l "$target/bin/busybox" |
		grep -Fq 'Requesting program interpreter: /lib/ld-linux-mipsn8.so.1'
	readelf -d "$target/bin/busybox" | grep -Fq 'Shared library: [libc.so.6]'
	readelf -d "$target/bin/busybox" |
		grep -Fq 'Shared library: [ld-linux-mipsn8.so.1]'
	readelf -d "$target/lib/ld-linux-mipsn8.so.1" |
		grep -Fq 'Library soname: [ld-linux-mipsn8.so.1]'
	readelf -l "$target/lib/libc.so.6" |
		grep -Fq 'Requesting program interpreter: /lib/ld-linux-mipsn8.so.1'
	readelf -d "$target/lib/libc.so.6" |
		grep -Fq 'Shared library: [ld-linux-mipsn8.so.1]'
	grep -Fxq '# CONFIG_UDHCPD is not set' "$busybox_config"
	grep -Fxq 'CONFIG_UDHCPC=y' "$busybox_config"
	grep -Fxq 'CONFIG_NTPD=y' "$busybox_config"
	grep -Fxq '# CONFIG_FEATURE_NTPD_SERVER is not set' "$busybox_config"
	grep -Fxq '# CONFIG_FEATURE_NTPD_CONF is not set' "$busybox_config"
	grep -Fxq '# CONFIG_FEATURE_NTP_AUTH is not set' "$busybox_config"
	grep -Fxq '#define DROPBEAR_SVR_PASSWORD_AUTH 0' "$dropbear_options"
	[ -x "$target/sbin/udhcpc" ]
	[ -x "$target/sbin/ip" ]
	[ ! -L "$target/sbin/ip" ]
	[ -x "$target/usr/sbin/ntpd" ]
	[ -x "$target/sbin/blkid" ]
	[ -x "$target/sbin/pivot_root" ]
	[ -x "$target/bin/mount" ]
	[ -x "$target/bin/umount" ]
	[ ! -e "$target/usr/sbin/udhcpd" ]
	[ -x "$target/usr/sbin/wpa_supplicant" ]
	[ -x "$target/usr/sbin/dropbear" ]
	[ -x "$target/usr/bin/dropbearkey" ]
	[ -x "$target/usr/bin/python3" ]
	numpy_dir="$target/usr/lib/python3.12/site-packages/numpy"
	[ -d "$numpy_dir" ]
	find "$numpy_dir" -maxdepth 2 -type f \
		\( -name '__init__.py' -o -name '__init__*.pyc' \) \
		-print -quit | grep -q .
	find "$numpy_dir/core" -type f -name '_multiarray_umath*.so' \
		-print -quit | grep -q .
	[ -x "$target/usr/bin/fre3nder" ]
	[ -x "$target/usr/sbin/lighttpd" ]
	[ -f "$target/usr/lib/lighttpd/mod_proxy.so" ]
	[ -x "$target/etc/init.d/S62fre3nder-web" ]
	[ -x "$target/usr/bin/mjpg_streamer" ]
	[ -f "$target/usr/lib/mjpg-streamer/input_uvc.so" ]
	[ -f "$target/usr/lib/mjpg-streamer/output_http.so" ]
	[ -x "$target/etc/init.d/S63fre3nder-camera" ]
	[ ! -e "$target/etc/init.d/S50lighttpd" ]
	cmp -s "$project/configs/x2000/rootfs-overlay/etc/lighttpd/fre3nder.conf" \
		"$target/etc/lighttpd/fre3nder.conf"
	app_ref=unpublished
	[ "$project_worktree_status" != clean ] || app_ref=$project_commit
	printf '%s\n' "$app_ref" | cmp -s - "$target/usr/share/fre3nder/APP_REF"
	[ -x "$target/usr/libexec/fre3nder/f005-mcu-state" ]
	[ -x "$target/usr/libexec/fre3nder/f005-stock-to-fre3nder" ]
	[ -x "$target/usr/bin/git" ]
	[ -f "$target/usr/libexec/fre3nder/f005_bootloader.py" ]
	[ -f "$target/usr/share/klipper/COPYING" ]
	[ -f "$target/usr/share/klipper/klippy/klippy.py" ]
	[ -f "$target/usr/share/klipper/klippy/chelper/c_helper.so" ]
	[ -x "$target/usr/bin/klipper_mcu" ]
	[ -f "$target/usr/share/fre3nder/f005-mcu-release.json" ]
	validate_f005_firmware "$target$f005_target_path"
	[ "$(stat -c '%a' "$target$f005_target_path")" = 644 ]
	cmp -s "$version_file" "$target/usr/share/fre3nder/VERSION"
	if [ "$artifact_mode" = development ]; then
		printf '%s\n' \
			'mode=development' \
			"commit=$project_commit" \
			"build_input_sha256=$build_input_sha256" |
			cmp -s - "$target/usr/share/fre3nder/DEVELOPMENT"
	else
		[ ! -e "$target/usr/share/fre3nder/DEVELOPMENT" ]
	fi
	[ -f "$target/usr/share/fre3nder/defaults/printer.cfg" ]
	[ -f "$target/usr/share/fre3nder/defaults/moonraker.conf" ]
	[ -f "$target/usr/share/fre3nder/defaults/camera.conf" ]
	[ -f "$target/usr/share/fre3nder/defaults/guppyconfig.json" ]
	cmp -s "$project/configs/klipper-f005/printer-f005-mainline.cfg" \
		"$target/usr/share/fre3nder/defaults/printer.cfg"
	cmp -s \
		"$project/configs/x2000/rootfs-overlay/usr/share/fre3nder/defaults/moonraker.conf" \
		"$target/usr/share/fre3nder/defaults/moonraker.conf"
	cmp -s \
		"$project/configs/x2000/rootfs-overlay/usr/share/fre3nder/defaults/camera.conf" \
		"$target/usr/share/fre3nder/defaults/camera.conf"
	cmp -s \
		"$project/configs/x2000/rootfs-overlay/usr/share/fre3nder/defaults/guppyconfig.json" \
		"$target/usr/share/fre3nder/defaults/guppyconfig.json"
	grep -Fxq 'x2000_passive_uart: True' \
		"$target/usr/share/fre3nder/defaults/printer.cfg"
	file "$target/usr/bin/klipper_mcu" |
		grep -q 'ELF 32-bit LSB.*MIPS, MIPS32 rel2'
	readelf -h "$target/usr/bin/klipper_mcu" |
		grep -Eq 'Flags:.*o32, mips32r2'
	readelf -h "$target/usr/bin/klipper_mcu" | grep -Fq 'nan2008'
	readelf -A "$target/usr/bin/klipper_mcu" |
		grep -Fq 'FP ABI: Hard float (32-bit CPU, Any FPU)'
	readelf -l "$target/usr/bin/klipper_mcu" |
		grep -Fq 'Requesting program interpreter: /lib/ld-linux-mipsn8.so.1'
	[ "$(stat -c '%a' "$target/usr/bin/klipper_mcu")" = 755 ]
	[ ! -e "$target/etc/klipper/printer.cfg" ]
	host_mcu_service="$target/etc/init.d/S59fre3nder-klipper-mcu"
	grep -Fq 'binary=${FRE3NDER_KLIPPER_MCU:-/usr/bin/klipper_mcu}' \
		"$host_mcu_service"
	grep -Fq 'host_tty=${FRE3NDER_KLIPPER_HOST_MCU_TTY:-/tmp/klipper_host_mcu}' \
		"$host_mcu_service"
	grep -Fq 'spi_device=${FRE3NDER_ADXL_SPI_DEVICE:-/dev/spidev2.0}' \
		"$host_mcu_service"
	grep -Fq '"$binary" -r -I "$host_tty"' "$host_mcu_service"
	grep -Fq 'set_status spi-unavailable' "$host_mcu_service"
	grep -Fq 'set_status startup-failed' "$host_mcu_service"
	service="$target/etc/init.d/S60fre3nder-klipper"
	grep -Fq 'input_tty=$runtime/printer' "$service"
	grep -Fq 'api_socket=${FRE3NDER_KLIPPER_API_SOCKET:-$runtime/klippy.sock}' \
		"$service"
	grep -Fq 'set_status starting' "$service"
	grep -Fq -- '-a "$api_socket"' "$service"
	grep -Fq 'set_status startup-failed' "$service"
	grep -Fq 'set_status host-mcu-unavailable' "$service"
	grep -Fq 'rm -f "$pid_file" "$input_tty" "$api_socket"' "$service"
	if grep -Fq '"$python" "$klippy" "$config" -l "$log_file"' "$service"; then
		echo 'Fre3nder RootFS contains obsolete Klippy /tmp input-TTY launch' >&2
		exit 1
	fi
	moonraker_service="$target/etc/init.d/S61fre3nder-moonraker"
	grep -Fq 'root_active()' "$moonraker_service"
	grep -Fq 'klipper_active()' "$moonraker_service"
	grep -Fq 'moonraker_root=${FRE3NDER_MOONRAKER_ROOT:-/opt/fre3nder/moonraker}' \
		"$moonraker_service"
	grep -Fq 'python=${FRE3NDER_PYTHON:-/opt/fre3nder/moonraker-env/bin/python}' \
		"$moonraker_service"
	grep -Fxq 'startup_timeout=${FRE3NDER_MOONRAKER_START_TIMEOUT:-30}' \
		"$moonraker_service"
	grep -Fq 'if [ "$seconds" -ge "$startup_timeout" ]; then' \
		"$moonraker_service"
	grep -Fxq '[include fre3nder/*.conf]' \
		"$target/usr/share/fre3nder/defaults/moonraker.conf"
	grep -Fxq '[webcam fre3nder_camera]' \
		"$target/usr/share/fre3nder/defaults/camera.conf"
	grep -Fxq 'stream_url: /webcam/?action=stream' \
		"$target/usr/share/fre3nder/defaults/camera.conf"
	grep -Fxq 'snapshot_url: /webcam/?action=snapshot' \
		"$target/usr/share/fre3nder/defaults/camera.conf"
	grep -Fq 'PIP_ONLY_BINARY=:all:' "$moonraker_service"
	grep -Fq -- '-d "$printer_data"' "$moonraker_service"
	grep -Fq -- '-u "$uds"' "$moonraker_service"
	grep -Fq 'uds=$runtime/moonraker.sock' "$moonraker_service"
	! grep -Eq 'pip|https?://' "$moonraker_service"
	moonraker_root="$target/opt/fre3nder/moonraker"
	moonraker_env="$target/opt/fre3nder/moonraker-env"
	[ -f "$moonraker_root/moonraker/moonraker.py" ]
	[ -d "$moonraker_root/.git" ]
	[ "$(git -C "$moonraker_root" rev-parse HEAD)" = "$moonraker_commit" ]
	[ "$(git -C "$moonraker_root" symbolic-ref --short HEAD)" = master ]
	[ "$(git -C "$moonraker_root" remote get-url origin)" = "$moonraker_url" ]
	[ "$(git -C "$moonraker_root" config --get branch.master.remote)" = origin ]
	[ "$(git -C "$moonraker_root" config --get branch.master.merge)" = refs/heads/master ]
	[ -f "$moonraker_env/pyvenv.cfg" ]
	grep -Fxq 'include-system-site-packages = true' "$moonraker_env/pyvenv.cfg"
	[ -f "$moonraker_env/bin/activate" ]
	[ "$(readlink "$moonraker_env/bin/python")" = /usr/bin/python3 ]
	[ "$(readlink "$moonraker_env/bin/pip")" = /usr/bin/pip3 ]
	[ -d "$moonraker_env/lib/python3.12/site-packages" ]
	guppyscreen="$target/opt/fre3nder/guppyscreen/guppyscreen"
	[ -x "$guppyscreen" ] && [ ! -L "$guppyscreen" ]
	file "$guppyscreen" | grep -q 'ELF 32-bit LSB.*MIPS, MIPS32 rel2'
	file "$guppyscreen" | grep -Fq 'statically linked'
	readelf -h "$guppyscreen" | grep -Eq 'Flags:.*nan2008, o32, mips32r2'
	readelf -A "$guppyscreen" |
		grep -Fq 'FP ABI: Hard float (32-bit CPU, Any FPU)'
	if readelf -l "$guppyscreen" | grep -Eq '^[[:space:]]*INTERP[[:space:]]'; then
		echo 'RootFS GuppyScreen binary unexpectedly contains a PT_INTERP segment' >&2
		exit 1
	fi
	[ -f "$target/usr/share/guppyscreen/themes/blue.json" ]
	[ -f "$target/usr/share/licenses/guppyscreen/COPYING" ]
	guppy_service="$target/etc/init.d/S64fre3nder-guppyscreen"
	grep -Fq 'input_name=${FRE3NDER_GUPPYSCREEN_INPUT_NAME:-ns2009_ts}' \
		"$guppy_service"
	grep -Fq 'GUPPYSCREEN_CONFIG="$config"' "$guppy_service"
	grep -Fq 'GUPPYSCREEN_THEME_DIR="$theme_dir"' "$guppy_service"
	grep -Fq 'GUPPYSCREEN_INPUT="$input_link"' "$guppy_service"
	! grep -Fq '/dev/input/event0' "$guppy_service"
	[ ! -e "$target/usr/share/klipper/.git" ]
	grep -Fxq '[update_manager]' \
		"$target/usr/share/fre3nder/defaults/moonraker.conf"
	grep -Fxq 'channel: stable' \
		"$target/usr/share/fre3nder/defaults/moonraker.conf"
	grep -Fxq 'enable_system_updates: False' \
		"$target/usr/share/fre3nder/defaults/moonraker.conf"
	file "$target/usr/share/klipper/klippy/chelper/c_helper.so" |
		grep -q 'ELF 32-bit LSB shared object, MIPS, MIPS32 rel2'
	readelf -h "$target/usr/share/klipper/klippy/chelper/c_helper.so" |
		grep -Eq 'Flags:.*o32, mips32r2'
	readelf -h "$target/usr/share/klipper/klippy/chelper/c_helper.so" |
		grep -Fq 'nan2008'
	readelf -A "$target/usr/share/klipper/klippy/chelper/c_helper.so" |
		grep -Fq 'FP ABI: Hard float (32-bit CPU, Any FPU)'
	if find "$target" -type f -name mcu_util -print -quit | grep -q .; then
		echo 'Fre3nder RootFS contains forbidden BYOF mcu_util' >&2
		exit 1
	fi
	[ ! -e "$target/init" ]
	[ -d "$target/dev/pts" ]
	[ -d "$target/home" ] && [ ! -L "$target/home" ]
	[ -d "$target/rom" ] && [ ! -L "$target/rom" ]
	[ -d "$target/mnt/fre3nder-root" ] && [ ! -L "$target/mnt/fre3nder-root" ]
	[ -d "$target/var" ] && [ ! -L "$target/var" ]
	[ "$(readlink "$target/var/run")" = ../run ]
	[ "$(readlink "$target/var/lock")" = ../run/lock ]
	[ -d "$target/root/.ssh" ] && [ ! -L "$target/root/.ssh" ]
	[ "$(readlink "$target/etc/resolv.conf")" = ../run/fre3nder/resolv.conf ]
	mkdir_line=$(grep -nF '::sysinit:/bin/mkdir -p /dev/pts' "$inittab" | cut -d: -f1)
	mount_line=$(grep -nF '::sysinit:/bin/mount -t devpts devpts /dev/pts' "$inittab" | cut -d: -f1)
	[ "$mkdir_line" -lt "$mount_line" ]
	grep -Fq '::sysinit:/bin/mount -t tmpfs -o mode=1777,nosuid,nodev tmpfs /tmp' \
		"$inittab"
	grep -Fq '"$mount_cmd" -t vfat -o ro,nosuid,nodev,noexec' \
		"$target/etc/init.d/S20fre3nder-provision"
	! grep -Eq 'blkid.*TYPE|TYPE=.*vfat' \
		"$target/etc/init.d/S20fre3nder-provision"
	grep -Fq 'usb_wait_seconds=${FRE3NDER_USB_WAIT_SECONDS:-10}' \
		"$target/etc/init.d/S20fre3nder-provision"
	grep -Fq 'multiple provisioning volumes found; refusing all' \
		"$target/etc/init.d/S20fre3nder-provision"
	[ ! -e "$target/persist" ]
	[ ! -e "$target/etc/init.d/S09fre3nder-storage" ]
	[ ! -e "$target/etc/init.d/S10fre3nder-persistence" ]
	root_setup="$target/etc/init.d/fre3nder-root"
	grep -Fxq '::sysinit:/etc/init.d/fre3nder-root start' "$inittab"
	root_setup_line=$(
		grep -nF '::sysinit:/etc/init.d/fre3nder-root start' "$inittab" |
		cut -d: -f1
	)
	rcs_line=$(
		grep -nF '::sysinit:/etc/init.d/rcS' "$inittab" |
		cut -d: -f1
	)
	[ "$root_setup_line" -lt "$rcs_line" ]
	grep -Fq 'LABEL="FRE3NDERSYS"' "$root_setup"
	grep -Fq 'LABEL="FRE3NDERHOME"' "$root_setup"
	! grep -Fq 'TYPE="ext4"' "$root_setup"
	[ "$(grep -Fc '"$mount_cmd" -t ext4 -o rw,nosuid,nodev' "$root_setup")" -eq 2 ]
	grep -Fq 'lowerdir=/,upperdir=$system_mount/upper,workdir=$system_mount/work' \
		"$root_setup"
	grep -Fq '"$pivot_root_cmd" "$new_root" "$new_root/rom"' "$root_setup"
	! grep -Eq 'fsck|mkfs|mke2fs|mmcblk0p(9|10)|/dev/sd[a-z]|FRE3NDERDATA' \
		"$root_setup"
	grep -Fq 'root_state=${FRE3NDER_ROOT_STATE:-/run/fre3nder-root}' \
		"$target/etc/init.d/S60fre3nder-klipper"
	grep -Fq 'while [ "$seconds" -lt 30 ]' \
		"$target/etc/init.d/S40fre3nder-network"
	grep -Fq '"$ifconfig" lo 127.0.0.1 netmask 255.0.0.0 up' \
		"$target/etc/init.d/S40fre3nder-network"
	grep -Fq 'Ethernet selected; DHCP lease acquired' \
		"$target/etc/init.d/S40fre3nder-network"
	grep -Fq 'lease_file=$runtime/lease' \
		"$target/etc/init.d/S40fre3nder-network"
	grep -Fq 'printf '\''%s\n'\'' "$interface" > "$lease_file"' \
		"$target/usr/libexec/fre3nder-udhcpc"
	grep -Fq '"$udhcpc" -f -i "$interface"' \
		"$target/etc/init.d/S40fre3nder-network"
	! grep -Eq 'udhcpc .*-[^ ]*b.*-[^ ]*q|udhcpc .*-[^ ]*q.*-[^ ]*b' \
		"$target/etc/init.d/S40fre3nder-network"
	grep -Fq '[ ! -s "$provisioning/enable_ssh" ]' \
		"$target/etc/init.d/S50dropbear"
	grep -Fq 'config=$provisioning/wpa_supplicant.conf' \
		"$target/etc/init.d/S40fre3nder-network"
	grep -Fq 'install -m 0600 "$provisioning/authorized_keys"' \
		"$target/etc/init.d/S50dropbear"
	grep -Fq '/dev/pts devpts ' "$target/etc/init.d/S50dropbear"
	grep -Fq 'dropbear_ed25519_host_key' "$target/etc/init.d/S50dropbear"
	grep -Fq 'root_active()' "$target/etc/init.d/S50dropbear"
	grep -Fq 'fre3nder_ssh_dir=${FRE3NDER_SSH_DIR:-$fre3nder_state_dir/ssh}' \
		"$target/etc/init.d/S50dropbear"
	! grep -E -i -q 's09x2000|fre3nderdata|usb|sd\[a-z\]|mmcblk0|p9|p10' \
		"$target/etc/init.d/S50dropbear"
	grep -Fq '"$dropbear" -r "$hostkey" -P "$pid_file"' \
		"$target/etc/init.d/S50dropbear"
	! grep -Eq '"\$dropbear"[[:space:]]+-s([[:space:]]|$)' \
		"$target/etc/init.d/S50dropbear"
	if find "$target" -type f \( -name authorized_keys -o -name wpa_supplicant.conf -o -name 'id_*' \) -print -quit | grep -q .; then
		echo 'Fre3nder RootFS contains credential files' >&2
		exit 1
	fi
	if find "$target" -type f -name enable_ssh -print -quit | grep -q .; then
		echo 'Fre3nder RootFS enables SSH at build time' >&2
		exit 1
	fi
	if find "$target" -type f -name '*dropbear*host*key*' -print -quit | grep -q .; then
		echo 'Fre3nder RootFS contains persistent Dropbear host keys' >&2
		exit 1
	fi
	if find "$target/root/.ssh" -mindepth 1 -print -quit | grep -q .; then
		echo 'Fre3nder RootFS contains SSH state' >&2
		exit 1
	fi
	if grep -R -I -E -q -- '-----BEGIN [A-Z ]*PRIVATE KEY-----|(^|[[:space:]])psk=' \
		"$target/etc" "$target/root" 2>/dev/null; then
		echo 'Fre3nder RootFS contains credential material' >&2
		exit 1
	fi
	if grep -R -E -i -q 'mmcblk0p(1|9|10)|ota:kernel|slot-b-selector|slot-b-revert' \
		"$target/etc/init.d" "$target/etc/inittab" "$target/etc/fstab" 2>/dev/null; then
		echo 'Fre3nder RootFS contains selector or reserved-partition logic' >&2
		exit 1
	fi

	firmware="$target/lib/firmware/cypress/cyfmac43430-sdio.bin"
	firmware_link="$target/lib/firmware/brcm/brcmfmac43430-sdio.bin"
	clm="$target/lib/firmware/cypress/cyfmac43430-sdio.clm_blob"
	clm_link="$target/lib/firmware/brcm/brcmfmac43430-sdio.clm_blob"
	nvram="$target/lib/firmware/brcm/brcmfmac43430-sdio.txt"
	license="$target/usr/share/licenses/linux-firmware/LICENCE.cypress"
	nvram_license="$target/usr/share/licenses/radxa-rkwifibt/LICENSE"
	[ "$(sha256sum "$firmware" | awk '{print $1}')" = \
		93f3c40c94340c29a40714cb04e3e89974870fcae42a844b8a4544750159f40d ]
	[ -L "$firmware_link" ]
	[ "$(readlink "$firmware_link")" = ../cypress/cyfmac43430-sdio.bin ]
	[ "$(sha256sum "$clm" | awk '{print $1}')" = \
		3376b9c9b32d16bf762e21c7fafb665365070ae240d092498d0d1987c22022aa ]
	[ -L "$clm_link" ]
	[ "$(readlink "$clm_link")" = ../cypress/cyfmac43430-sdio.clm_blob ]
	[ "$(sha256sum "$nvram" | awk '{print $1}')" = \
		6167b8aaa5e80eabe09ac5bd8570760e5241aa3a9a6243a94be9fcba33cc1915 ]
	[ "$(wc -c < "$nvram")" -eq 1016 ]
	cmp -s \
		"$project/configs/x2000/rootfs-overlay/lib/firmware/brcm/brcmfmac43430-sdio.txt" \
		"$nvram"
	[ "$(sha256sum "$license" | awk '{print $1}')" = \
		ae0db6cc4db33941148df0f67de53e76a77b1b5a46b3165edb7040aa2750015f ]
	[ "$(sha256sum "$nvram_license" | awk '{print $1}')" = \
		ec1dabfa95bf2e8f0de4311a9ceacfd841c45a772bf7eab3aa4c121284616df2 ]
	cmp -s \
		"$project/configs/x2000/rootfs-overlay/usr/share/licenses/radxa-rkwifibt/LICENSE" \
		"$nvram_license"
}

build() {
	jobs=${JOBS:-4}
	prepare_buildroot
	prepare_klipper_overlay
	prepare_rootfs_component moonraker "$moonraker_component" "$moonraker_overlay"
	prepare_rootfs_component guppyscreen "$guppyscreen_component" "$guppyscreen_overlay"
	brout="$work/buildroot-output-fre3nder"
	extra_overlay="$klipper_overlay $moonraker_overlay $guppyscreen_overlay"
	configure_buildroot "$brout" "$extra_overlay"
	make -C "$buildroot" O="$brout" -j"$jobs" toolchain
	write_buildroot_toolchain_fingerprint "$brout"
	make -C "$buildroot" O="$brout" -j"$jobs" linux-firmware
	stage_kernel_firmware "$brout"
	kernel_cross_compile="$brout/host/bin/mipsel-buildroot-linux-gnu-"
	kernel_cc="${kernel_cross_compile}gcc.br_real"
	[ -x "$kernel_cc" ]
	prepare_kernel
	configure_kernel
	k="$kernel_source"
	SOURCE_DATE_EPOCH="$kernel_commit_epoch" \
	LOCALVERSION= \
	KBUILD_BUILD_USER="$kernel_build_user" \
	KBUILD_BUILD_HOST="$kernel_build_host" \
	KBUILD_BUILD_TIMESTAMP="$kernel_build_timestamp" \
	KBUILD_BUILD_VERSION="$kernel_build_version" \
	make -C "$k" O="$kernel_build" -j"$jobs" ARCH=mips \
		CROSS_COMPILE="$kernel_cross_compile" CC="$kernel_cc" \
		HOSTCFLAGS='-Wno-error=incompatible-pointer-types' uzImage.bin dtbs
	check_default_initramfs "$kernel_build"
	check_kernel_dtb "$k" "$kernel_build"

	out="$full_out"
	build_klipper_chelper "$brout"
	build_klipper_mcu "$brout"
	make -C "$buildroot" O="$brout" -j"$jobs"
	check_rootfs "$brout"

	rm -rf -- "$out"
	mkdir -p "$out"
	cp "$kernel_build/arch/mips/boot/uzImage.bin" "$out/kernel.uImage"
	cp "$brout/images/rootfs.squashfs" "$out/rootfs.squashfs"
	cp "$kernel_build/arch/mips/boot/dts/ingenic/ender3-v3-ke.dtb" "$out/ender3-v3-ke.dtb"
	cp "$kernel_build/.config" "$out/effective-kernel-config"
	cp "$brout/.config" "$out/buildroot.config"

	write_build_manifest "$out" \
		buildroot.config \
		effective-kernel-config \
		ender3-v3-ke.dtb \
		kernel.uImage \
		rootfs.squashfs
	record_kernel_build "$out" "$brout"
	record_rootfs_components "$out"
	(cd "$out" && sha256sum build-manifest.json buildroot.config \
		effective-kernel-config ender3-v3-ke.dtb kernel.uImage rootfs.squashfs) \
		> "$out/SHA256SUMS"
	(cd "$out" && sha256sum -c SHA256SUMS)

	[ "$(find "$out" -maxdepth 1 -type f | wc -l)" -eq 7 ]
	file "$out/kernel.uImage" "$out/rootfs.squashfs" "$out/ender3-v3-ke.dtb"
	file "$out/rootfs.squashfs" | grep -q ', xz compressed,'
	check_kernel_boot_image "$out/kernel.uImage"
	fdtdump "$out/ender3-v3-ke.dtb" 2>&1 | grep -E \
		'ender-3-v3-ke|root=/dev/mmcblk0p8|wifi-bt-power|wlan-reg-on-gpios'
	[ "$(stat -c '%s' "$out/rootfs.squashfs")" -lt 524288000 ]
	unsquashfs -ll "$out/rootfs.squashfs" | grep -q '/dev/pts$'
	! strings "$kernel_build/vmlinux" | grep -q 'ingenic,halley5'
	strings "$kernel_build/vmlinux" | grep -q 'creality,ender-3-v3-ke'
}

build_kernel_only() {
	jobs=${JOBS:-4}
	prepare_buildroot
	brout="$work/buildroot-output-fre3nder"
	configure_buildroot "$brout"
	make -C "$buildroot" O="$brout" -j"$jobs" toolchain
	write_buildroot_toolchain_fingerprint "$brout"
	make -C "$buildroot" O="$brout" -j"$jobs" linux-firmware
	stage_kernel_firmware "$brout"
	kernel_cross_compile="$brout/host/bin/mipsel-buildroot-linux-gnu-"
	kernel_cc="${kernel_cross_compile}gcc.br_real"
	[ -x "$kernel_cc" ]
	prepare_kernel
	configure_kernel
	k="$kernel_source"
	SOURCE_DATE_EPOCH="$kernel_commit_epoch" \
	LOCALVERSION= \
	KBUILD_BUILD_USER="$kernel_build_user" \
	KBUILD_BUILD_HOST="$kernel_build_host" \
	KBUILD_BUILD_TIMESTAMP="$kernel_build_timestamp" \
	KBUILD_BUILD_VERSION="$kernel_build_version" \
	make -C "$k" O="$kernel_build" -j"$jobs" ARCH=mips \
		CROSS_COMPILE="$kernel_cross_compile" CC="$kernel_cc" \
		HOSTCFLAGS='-Wno-error=incompatible-pointer-types' uzImage.bin dtbs
	check_default_initramfs "$kernel_build"
	check_kernel_dtb "$k" "$kernel_build"

	out="$kernel_out"
	rm -rf -- "$out"
	mkdir -p "$out"
	cp "$kernel_build/arch/mips/boot/uzImage.bin" "$out/kernel.uImage"
	cp "$kernel_build/arch/mips/boot/dts/ingenic/ender3-v3-ke.dtb" "$out/ender3-v3-ke.dtb"
	cp "$kernel_build/.config" "$out/effective-kernel-config"
	write_build_manifest "$out" \
		kernel.uImage ender3-v3-ke.dtb effective-kernel-config
	record_kernel_build "$out" "$brout"
	(cd "$out" && sha256sum build-manifest.json kernel.uImage \
		ender3-v3-ke.dtb effective-kernel-config) \
		> "$out/SHA256SUMS"
	(cd "$out" && sha256sum -c SHA256SUMS)

	[ "$(find "$out" -maxdepth 1 -type f | wc -l)" -eq 5 ]
	file "$out/kernel.uImage" "$out/ender3-v3-ke.dtb"
	check_kernel_boot_image "$out/kernel.uImage"
	if strings "$kernel_build/vmlinux" | grep -q 'ingenic,halley5'; then
		exit 1
	fi
	strings "$kernel_build/vmlinux" | grep -q 'creality,ender-3-v3-ke'
}

build_kernel_ximage_diagnostic() {
	[ "$artifact_mode" = development ] || {
		echo 'xImage diagnostic build requires FRE3NDER_ARTIFACT_MODE=development' >&2
		return 1
	}

	jobs=${JOBS:-4}
	prepare_buildroot
	brout="$work/buildroot-output-fre3nder"
	configure_buildroot "$brout"
	make -C "$buildroot" O="$brout" -j"$jobs" toolchain
	write_buildroot_toolchain_fingerprint "$brout"
	make -C "$buildroot" O="$brout" -j"$jobs" linux-firmware
	stage_kernel_firmware "$brout"
	kernel_cross_compile="$brout/host/bin/mipsel-buildroot-linux-gnu-"
	kernel_cc="${kernel_cross_compile}gcc.br_real"
	[ -x "$kernel_cc" ]
	prepare_kernel
	configure_kernel
	SOURCE_DATE_EPOCH="$kernel_commit_epoch" \
	LOCALVERSION='' \
	KBUILD_BUILD_USER="$kernel_build_user" \
	KBUILD_BUILD_HOST="$kernel_build_host" \
	KBUILD_BUILD_TIMESTAMP="$kernel_build_timestamp" \
	KBUILD_BUILD_VERSION="$kernel_build_version" \
	make -C "$kernel_source" O="$kernel_build" -j"$jobs" ARCH=mips \
		CROSS_COMPILE="$kernel_cross_compile" CC="$kernel_cc" \
		HOSTCFLAGS='-Wno-error=incompatible-pointer-types' uzImage.bin dtbs
	check_default_initramfs "$kernel_build"
	check_kernel_dtb "$kernel_source" "$kernel_build"

	ximage_contract="$work/fre3nder-ximage-vmlinux-contract.json"
	build_ximage_wrapper "$jobs" "$ximage_contract"

	out="$kernel_ximage_diagnostic_out"
	rm -rf -- "$out"
	mkdir -p "$out"
	cp "$kernel_build/arch/mips/boot/zcompressed/xImage" "$out/kernel.uImage"
	cp "$kernel_build/arch/mips/boot/dts/ingenic/ender3-v3-ke.dtb" \
		"$out/ender3-v3-ke.dtb"
	cp "$kernel_build/.config" "$out/effective-kernel-config"
	write_build_manifest "$out" \
		kernel.uImage ender3-v3-ke.dtb effective-kernel-config
	record_kernel_build "$out" "$brout"
	record_ximage_diagnostic "$out" "$ximage_contract"
	(cd "$out" && sha256sum build-manifest.json kernel.uImage \
		ender3-v3-ke.dtb effective-kernel-config) > "$out/SHA256SUMS"
	(cd "$out" && sha256sum -c SHA256SUMS)

	[ "$(find "$out" -maxdepth 1 -type f | wc -l)" -eq 5 ]
	file "$out/kernel.uImage" "$out/ender3-v3-ke.dtb"
	check_kernel_boot_image "$out/kernel.uImage"
}

build_rootfs_only() {
	prepare_buildroot
	prepare_klipper_overlay
	prepare_rootfs_component moonraker "$moonraker_component" "$moonraker_overlay"
	prepare_rootfs_component guppyscreen "$guppyscreen_component" "$guppyscreen_overlay"
	brout="$work/buildroot-output-fre3nder"
	configure_buildroot "$brout" \
		"$klipper_overlay $moonraker_overlay $guppyscreen_overlay"
	make -C "$buildroot" O="$brout" -j"${JOBS:-4}" toolchain
	write_buildroot_toolchain_fingerprint "$brout"
	build_klipper_chelper "$brout"
	build_klipper_mcu "$brout"
	make -C "$buildroot" O="$brout" rootfs-squashfs
	check_rootfs "$brout"

	out="$rootfs_out"
	rm -rf -- "$out"
	mkdir -p "$out"
	cp "$brout/images/rootfs.squashfs" "$out/rootfs.squashfs"
	cp "$brout/.config" "$out/buildroot.config"
	write_build_manifest "$out" buildroot.config rootfs.squashfs
	record_rootfs_components "$out"
	(cd "$out" && sha256sum build-manifest.json buildroot.config \
		rootfs.squashfs) > "$out/SHA256SUMS"
	(cd "$out" && sha256sum -c SHA256SUMS)

	[ "$(find "$out" -maxdepth 1 -type f | wc -l)" -eq 4 ]
	file "$out/rootfs.squashfs" | grep -q ', xz compressed,'
	[ "$(stat -c '%s' "$out/rootfs.squashfs")" -lt 524288000 ]
}

prepare_buildroot_toolchain() {
	prepare_artifact_provenance
	prepare_buildroot
	brout="$work/buildroot-output-fre3nder"
	configure_buildroot "$brout"
	make -C "$buildroot" O="$brout" -j"${JOBS:-4}" toolchain
	write_buildroot_toolchain_fingerprint "$brout"
}

case "${1:-build}" in
	fetch-kernel) fetch_kernel_inputs ;;
	fetch-rootfs) fetch_rootfs_inputs ;;
	fetch-buildroot) fetch_buildroot_inputs ;;
	fetch-moonraker) fetch_moonraker_inputs ;;
	fetch-guppyscreen) "$project/build/x2000/guppyscreen-component.sh" fetch ;;
	build) prepare_artifact_provenance; build ;;
	build-kernel-only) prepare_artifact_provenance; build_kernel_only ;;
	build-kernel-ximage-diagnostic) prepare_artifact_provenance; build_kernel_ximage_diagnostic ;;
	build-rootfs-only) prepare_artifact_provenance; build_rootfs_only ;;
	build-moonraker-component) build_moonraker_component ;;
	build-guppyscreen-component) "$project/build/x2000/guppyscreen-component.sh" build ;;
	prepare-buildroot-toolchain) prepare_buildroot_toolchain ;;
	*) echo 'usage: fre3nder-x2000 {fetch-kernel|fetch-rootfs|fetch-buildroot|fetch-moonraker|fetch-guppyscreen|build|build-kernel-only|build-kernel-ximage-diagnostic|build-rootfs-only|build-moonraker-component|build-guppyscreen-component|prepare-buildroot-toolchain}' >&2; exit 2 ;;
esac
