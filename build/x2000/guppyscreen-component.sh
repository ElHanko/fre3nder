#!/bin/sh
set -eu

project=/project
work=/work
source_dir=$work/guppyscreen-source
artifact_dir=$project/local/production/artifacts/x2000/guppyscreen
buildroot_output=$work/buildroot-output-fre3nder
artifact_mode=${FRE3NDER_ARTIFACT_MODE:-release}

case "$artifact_mode" in
release|development) ;;
*) echo 'invalid FRE3NDER_ARTIFACT_MODE' >&2; exit 2 ;;
esac

source_field() {
	python3 - "$1" <<'PY'
import json
import pathlib
import sys

value = json.loads(pathlib.Path("/project/configs/x2000/sources.json").read_text())
for key in sys.argv[1].split("."):
    value = value[key]
print(value)
PY
}

repository=$(source_field userspace.guppyscreen.repository)
release=$(source_field userspace.guppyscreen.release)
commit=$(source_field userspace.guppyscreen.commit)

fetch() {
	if [ -d "$source_dir/.git" ]; then
		git -C "$source_dir" reset --hard
		git -C "$source_dir" clean -fdx
		git -C "$source_dir" submodule foreach --recursive \
			'git reset --hard && git clean -fdx'
		git -C "$source_dir" remote set-url origin "$repository"
	else
		git clone --filter=blob:none --no-checkout "$repository" "$source_dir"
	fi
	[ "$(git -C "$source_dir" remote get-url origin)" = "$repository" ]
	git -C "$source_dir" fetch origin "$commit"
	git -C "$source_dir" checkout --detach "$commit"
	git -C "$source_dir" submodule sync --recursive
	git -C "$source_dir" submodule update --init --recursive
}

prepare_source() {
	[ -d "$source_dir/.git" ]
	[ "$(git -C "$source_dir" remote get-url origin)" = "$repository" ]
	git -C "$source_dir" reset --hard "$commit"
	git -C "$source_dir" clean -fdx
	git -C "$source_dir" submodule update --init --recursive
	git -C "$source_dir" submodule foreach --recursive 'git reset --hard && git clean -fdx'
	git -C "$source_dir" checkout --detach "$commit"
	[ "$(git -C "$source_dir" rev-parse HEAD)" = "$commit" ]

	python3 - "$source_dir" <<'PY'
import json
import pathlib
import subprocess
import sys

source = pathlib.Path(sys.argv[1])
data = json.loads(pathlib.Path("/project/configs/x2000/sources.json").read_text())
expected = data["userspace"]["guppyscreen"]["submodules"]
actual = {}
for line in subprocess.check_output(
        ["git", "-C", str(source), "submodule", "status"], text=True).splitlines():
    commit, name, *_ = line.lstrip("-+ ").split()
    actual[name] = commit
if set(actual) != set(expected):
    raise SystemExit("GuppyScreen submodule set mismatch")
for name, record in expected.items():
    if actual[name] != record["commit"]:
        raise SystemExit(f"GuppyScreen submodule mismatch: {name}")
PY

	grep -Fq 'GNU GENERAL PUBLIC LICENSE' "$source_dir/LICENSE"
	grep -Fq 'MIT licence' "$source_dir/lvgl/LICENCE.txt"
	grep -Fq 'MIT License' "$source_dir/lv_drivers/LICENSE"
	grep -Fq 'BSD 3-Clause License' "$source_dir/libhv/LICENSE"
	grep -Fq 'The MIT License (MIT)' "$source_dir/spdlog/LICENSE"
	grep -Fq 'BSD license' "$source_dir/wpa_supplicant/COPYING"

	git -C "$source_dir/lv_drivers" apply --check \
		"$source_dir/patches/0001-lv_driver_fb_ioctls.patch"
	git -C "$source_dir/lv_drivers" apply \
		"$source_dir/patches/0001-lv_driver_fb_ioctls.patch"
	git -C "$source_dir/spdlog" apply --check \
		"$source_dir/patches/0002-spdlog_fmt_initializer_list.patch"
	git -C "$source_dir/spdlog" apply \
		"$source_dir/patches/0002-spdlog_fmt_initializer_list.patch"
	git -C "$source_dir/lvgl" apply --check \
		"$source_dir/patches/0003-lvgl-dpi-text-scale.patch"
	git -C "$source_dir/lvgl" apply \
		"$source_dir/patches/0003-lvgl-dpi-text-scale.patch"
}

build_component() {
	prefix=$buildroot_output/host/bin/mipsel-buildroot-linux-gnu-
	[ -x "${prefix}gcc" ] && [ -x "${prefix}g++" ] && [ -x "${prefix}strip" ] || {
		echo 'prepared Fre3nder Buildroot toolchain is missing' >&2
		exit 1
	}
	[ -f "$buildroot_output/.fre3nder-toolchain-fingerprint" ] || {
		echo 'prepared Fre3nder Buildroot toolchain has no fingerprint' >&2
		exit 1
	}
	prepare_source

	CROSS_COMPILE="$prefix" \
	GUPPY_SMALL_SCREEN=1 \
	GUPPY_ROTATE=1 \
	EVDEV_CALIBRATE=1 \
	GUPPYSCREEN_VERSION="$release" \
		make -C "$source_dir" -j"${JOBS:-4}" build

	binary=$source_dir/build/bin/guppyscreen
	[ -f "$binary" ] && [ ! -L "$binary" ] && [ -x "$binary" ]
	"${prefix}strip" "$binary"
	file "$binary" | grep -q 'ELF 32-bit LSB.*MIPS, MIPS32 rel2'
	file "$binary" | grep -Fq 'statically linked'
	readelf -h "$binary" | grep -Eq 'Flags:.*nan2008, o32, mips32r2'
	readelf -A "$binary" | grep -Fq 'FP ABI: Hard float (32-bit CPU, Any FPU)'
	if readelf -l "$binary" | grep -Eq '^[[:space:]]*INTERP[[:space:]]'; then
		echo 'GuppyScreen binary unexpectedly contains a PT_INTERP segment' >&2
		exit 1
	fi

	stage=$work/guppyscreen-component-overlay
	rm -rf -- "$stage"
	install -d -m 0755 \
		"$stage/opt/fre3nder/guppyscreen" \
		"$stage/usr/share/guppyscreen/themes" \
		"$stage/usr/share/licenses/guppyscreen"
	install -m 0755 "$binary" "$stage/opt/fre3nder/guppyscreen/guppyscreen"
	for theme in blue green pink purple red yellow; do
		install -m 0644 "$source_dir/themes/$theme.json" \
			"$stage/usr/share/guppyscreen/themes/$theme.json"
	done
	install -m 0644 "$source_dir/LICENSE" \
		"$stage/usr/share/licenses/guppyscreen/COPYING"
	install -m 0644 "$source_dir/lvgl/LICENCE.txt" \
		"$stage/usr/share/licenses/guppyscreen/LVGL-LICENSE"
	install -m 0644 "$source_dir/lv_drivers/LICENSE" \
		"$stage/usr/share/licenses/guppyscreen/LV-DRIVERS-LICENSE"
	install -m 0644 "$source_dir/libhv/LICENSE" \
		"$stage/usr/share/licenses/guppyscreen/LIBHV-LICENSE"
	install -m 0644 "$source_dir/spdlog/LICENSE" \
		"$stage/usr/share/licenses/guppyscreen/SPDLOG-LICENSE"
	install -m 0644 "$source_dir/wpa_supplicant/COPYING" \
		"$stage/usr/share/licenses/guppyscreen/WPA-SUPPLICANT-LICENSE"

	project_commit=$(git -C "$project" rev-parse HEAD)
	project_worktree_status=clean
	[ -z "$(git -C "$project" status --porcelain=v1)" ] ||
		project_worktree_status=dirty
	build_input_sha256=$(
		"$project/scripts/x2000-build-input-sha256" --root "$project"
	)

	tmp=$artifact_dir.tmp
	rm -rf -- "$tmp"
	mkdir -p "$tmp"
	tar --sort=name --format=ustar --mtime='@0' --owner=0 --group=0 \
		--numeric-owner -C "$stage" -cf "$tmp/rootfs-overlay.tar" .
	export artifact_mode build_input_sha256 commit project_commit
	export project_worktree_status release repository
	python3 - "$tmp/rootfs-overlay.tar" "$tmp/component-manifest.json" <<'PY'
import hashlib
import json
import os
import pathlib
import sys

artifact, output = map(pathlib.Path, sys.argv[1:])
manifest = {
    "schema": 1,
    "component": "guppyscreen",
    "source": {
        "repository": os.environ["repository"],
        "release": os.environ["release"],
        "commit": os.environ["commit"],
        "license": "GPL-3.0-only",
    },
    "artifact_mode": os.environ["artifact_mode"],
    "project_commit": os.environ["project_commit"],
    "project_worktree_status": os.environ["project_worktree_status"],
    "build_input_sha256": os.environ["build_input_sha256"],
    "artifact": {
        "name": artifact.name,
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    },
}
output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
PY
	(cd "$tmp" && sha256sum component-manifest.json rootfs-overlay.tar > SHA256SUMS)
	(cd "$tmp" && sha256sum -c SHA256SUMS)
	rm -rf -- "$artifact_dir"
	mv "$tmp" "$artifact_dir"
}

case "${1:-}" in
fetch) fetch ;;
build) build_component ;;
*) echo "usage: $0 {fetch|build}" >&2; exit 2 ;;
esac
