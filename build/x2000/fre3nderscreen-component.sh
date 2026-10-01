#!/bin/sh
set -eu

project=/project
work=/work
source_dir=$work/fre3nderscreen-source
artifact_dir=$project/local/production/artifacts/x2000/fre3nderscreen
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

repository=$(source_field userspace.fre3nderscreen.repository)
release=$(source_field userspace.fre3nderscreen.release)
pinned_commit=$(source_field userspace.fre3nderscreen.commit)
commit=$pinned_commit
source_ref=$pinned_commit
if [ "$artifact_mode" = development ]; then
	source_ref=main
fi

fetch() {
	# Fetch and build run in separate containers. The build container has
	# --network none, so the source checkout must not remain a promisor clone
	# with lazily fetched blobs.
	if [ -d "$source_dir/.git" ] &&
		git -C "$source_dir" config --bool --get remote.origin.promisor 2>/dev/null |
			grep -Fxq true; then
		echo 'Fre3nderScreen source cache: replacing partial clone'
		rm -rf -- "$source_dir"
	fi

	if [ -d "$source_dir/.git" ]; then
		git -C "$source_dir" reset --hard
		git -C "$source_dir" clean -fdx
		git -C "$source_dir" submodule foreach --recursive \
			'git reset --hard && git clean -fdx'
		git -C "$source_dir" remote set-url origin "$repository"
	else
		mkdir -p "$source_dir"
		git -C "$source_dir" init -q
		git -C "$source_dir" remote add origin "$repository"
	fi

	[ "$(git -C "$source_dir" remote get-url origin)" = "$repository" ]
	git -C "$source_dir" fetch --depth=1 origin "$source_ref"
	git -C "$source_dir" checkout --detach FETCH_HEAD

	if git -C "$source_dir" config --bool --get remote.origin.promisor 2>/dev/null |
		grep -Fxq true; then
		echo 'Fre3nderScreen fetch left a promisor clone behind' >&2
		return 1
	fi

	git -C "$source_dir" submodule sync --recursive
	git -C "$source_dir" submodule update --init --recursive
}

prepare_source() {
	[ -d "$source_dir/.git" ]
	[ "$(git -C "$source_dir" remote get-url origin)" = "$repository" ]
	if [ "$artifact_mode" = development ]; then
		commit=$(git -C "$source_dir" rev-parse HEAD)
		case "$release" in
		*.*.*) release=${release%.*} ;;
		esac
		release="$release.$(git -C "$source_dir" rev-parse --short=7 HEAD)"
	else
		commit=$pinned_commit
	fi
	git -C "$source_dir" reset --hard "$commit"
	git -C "$source_dir" clean -fdx
	git -C "$source_dir" submodule update --init --recursive
	git -C "$source_dir" submodule foreach --recursive 'git reset --hard && git clean -fdx'
	git -C "$source_dir" checkout --detach "$commit"
	[ "$(git -C "$source_dir" rev-parse HEAD)" = "$commit" ]

	python3 - "$source_dir" "$artifact_mode" <<'PY'
import json
import pathlib
import subprocess
import sys

source = pathlib.Path(sys.argv[1])
mode = sys.argv[2]
data = json.loads(pathlib.Path("/project/configs/x2000/sources.json").read_text())
expected = data["userspace"]["fre3nderscreen"]["submodules"]
actual = {}
for line in subprocess.check_output(
        ["git", "-C", str(source), "submodule", "status"], text=True).splitlines():
    commit, name, *_ = line.lstrip("-+ ").split()
    actual[name] = commit
if set(actual) != set(expected):
    raise SystemExit("Fre3nderScreen submodule set mismatch")
for name, record in expected.items():
    if mode == "release" and actual[name] != record["commit"]:
        raise SystemExit(f"Fre3nderScreen submodule mismatch: {name}")
PY

	grep -Fq 'GNU GENERAL PUBLIC LICENSE' "$source_dir/LICENSE"
	grep -Fq 'MIT licence' "$source_dir/lvgl/LICENCE.txt"
	grep -Fq 'MIT License' "$source_dir/lv_drivers/LICENSE"
	grep -Fq 'BSD 3-Clause License' "$source_dir/libhv/LICENSE"
	grep -Fq 'The MIT License (MIT)' "$source_dir/spdlog/LICENSE"
	grep -Fq 'BSD license' "$source_dir/wpa_supplicant/COPYING"
	grep -Fq 'Bitstream Vera Fonts Copyright' \
		"$source_dir/licenses/DEJAVU-FONTS-LICENSE.txt"
	grep -Fq 'Apache License' \
		"$source_dir/licenses/MATERIAL-DESIGN-ICONS-LICENSE.txt"

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

build_app() {
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

	# libhv embeds __DATE__/__TIME__. Derive SOURCE_DATE_EPOCH from the
	# resolved Fre3nderScreen commit so repeated builds remain byte-reproducible.
	source_date_epoch=$(git -C "$source_dir" show -s --format=%ct "$commit")
	printf '%s\n' "$source_date_epoch" | grep -Eq '^[0-9]+$'

	SOURCE_DATE_EPOCH="$source_date_epoch" \
	CROSS_COMPILE="$prefix" \
	FRE3NDERSCREEN_VERSION="$release" \
		make -C "$source_dir" -j"${JOBS:-4}" build

	binary=$source_dir/build/bin/fre3nderscreen
	[ -f "$binary" ] && [ ! -L "$binary" ] && [ -x "$binary" ]
	"${prefix}strip" "$binary"
	file "$binary" | grep -q 'ELF 32-bit LSB.*MIPS, MIPS32 rel2'
	file "$binary" | grep -Fq 'statically linked'
	readelf -h "$binary" | grep -Eq 'Flags:.*nan2008, o32, mips32r2'
	readelf -A "$binary" | grep -Fq 'FP ABI: Hard float (32-bit CPU, Any FPU)'
	if readelf -l "$binary" | grep -Eq '^[[:space:]]*INTERP[[:space:]]'; then
		echo 'Fre3nderScreen binary unexpectedly contains a PT_INTERP segment' >&2
		exit 1
	fi

	tmp=$artifact_dir.tmp
	rm -rf -- "$tmp"
	install -d -m 0755 "$tmp/app/bin" "$tmp/app/themes" "$tmp/app/licenses"
	install -m 0755 "$binary" "$tmp/app/bin/fre3nderscreen"
	for theme in blue green pink purple red yellow; do
		install -m 0644 "$source_dir/themes/$theme.json" \
			"$tmp/app/themes/$theme.json"
	done
	install -m 0644 "$source_dir/LICENSE" \
		"$tmp/app/licenses/COPYING"
	install -m 0644 "$source_dir/lvgl/LICENCE.txt" \
		"$tmp/app/licenses/LVGL-LICENSE"
	install -m 0644 "$source_dir/lv_drivers/LICENSE" \
		"$tmp/app/licenses/LV-DRIVERS-LICENSE"
	install -m 0644 "$source_dir/libhv/LICENSE" \
		"$tmp/app/licenses/LIBHV-LICENSE"
	install -m 0644 "$source_dir/spdlog/LICENSE" \
		"$tmp/app/licenses/SPDLOG-LICENSE"
	install -m 0644 "$source_dir/wpa_supplicant/COPYING" \
		"$tmp/app/licenses/WPA-SUPPLICANT-LICENSE"
	install -m 0644 "$source_dir/licenses/DEJAVU-FONTS-LICENSE.txt" \
		"$tmp/app/licenses/DEJAVU-FONTS-LICENSE"
	install -m 0644 "$source_dir/licenses/MATERIAL-DESIGN-ICONS-LICENSE.txt" \
		"$tmp/app/licenses/MATERIAL-DESIGN-ICONS-LICENSE"

	project_commit=$(git -C "$project" rev-parse HEAD)
	project_worktree_status=clean
	[ -z "$(git -C "$project" status --porcelain=v1)" ] ||
		project_worktree_status=dirty
	build_input_sha256=$(
		"$project/scripts/x2000-build-input-sha256" --root "$project"
	)

	export artifact_mode build_input_sha256 commit project_commit
	export project_worktree_status release repository
	python3 - "$tmp/app" "$source_dir" <<'PY'
import hashlib
import json
import os
import pathlib
import subprocess
import sys

app, source_dir = map(pathlib.Path, sys.argv[1:])

source_config = json.loads(pathlib.Path("/project/configs/x2000/sources.json").read_text())
expected_submodules = source_config["userspace"]["fre3nderscreen"]["submodules"]
submodules = {}
for line in subprocess.check_output(
        ["git", "-C", str(source_dir), "submodule", "status"], text=True).splitlines():
    submodule_commit, name, *_ = line.lstrip("-+ ").split()
    expected = expected_submodules[name]
    # prepare_source validated the license markers in this checkout.
    record = {"commit": submodule_commit, "license": expected["license"]}
    if submodule_commit == expected["commit"]:
        record.update({
            key: value for key, value in expected.items()
            if key not in ("commit", "license")
        })
    submodules[name] = record
files = {
    path.relative_to(app).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in app.rglob("*") if path.is_file()
}
app_manifest = {
    "schema": 1,
    "artifact": "fre3nderscreen-x2000-app",
    "artifact_mode": os.environ["artifact_mode"],
    "source": {
        "repository": os.environ["repository"],
        "release": os.environ["release"],
        "commit": os.environ["commit"],
        "license": "GPL-3.0-only",
    },
    "submodules": submodules,
    "abi": {
        "arch": "mipsel",
        "isa": "mips32r2",
        "float_abi": "hard",
        "nan": "nan2008",
        "linkage": "static",
    },
    "project_commit": os.environ["project_commit"],
    "project_worktree_status": os.environ["project_worktree_status"],
    "build_input_sha256": os.environ["build_input_sha256"],
    "files": files,
}
(app / "artifact-manifest.json").write_text(
    json.dumps(app_manifest, indent=2, sort_keys=True) + "\n")
(app / "SHA256SUMS").write_text("".join(
    f"{hashlib.sha256((app / name).read_bytes()).hexdigest()}  {name}\n"
    for name in sorted((*files, "artifact-manifest.json"))
))
PY
	(cd "$tmp/app" && sha256sum -c SHA256SUMS)
	rm -rf -- "$artifact_dir"
	mv "$tmp" "$artifact_dir"
}

case "${1:-}" in
fetch) fetch ;;
build) build_app ;;
*) echo "usage: $0 {fetch|build}" >&2; exit 2 ;;
esac
