# Building Fre3nder

All builds are offline-oriented and operate on local source trees and ignored
build output. They do not access or modify a printer.

## X2000 host

Use [`scripts/build-x2000`](../scripts/build-x2000) with the pinned sources and
configuration under [`configs/x2000`](../configs/x2000). The container recipe
is [`build/x2000`](../build/x2000), and the source manifest is
[`configs/x2000/sources.json`](../configs/x2000/sources.json).

The resulting host image uses Linux 6.6.18-rt23, a read-only SquashFS RootFS,
`root=/dev/mmcblk0p8`, upstream Klipper at the pinned revision, and the
project's passive-UART patch. BYOF firmware and credentials remain outside the
repository and are never embedded automatically.

The productive source and configuration layers are separated as follows:

```text
Ingenic SDK
└── Kernel 6.6.18-rt23 source

Upstream Buildroot 2025.02.18
└── internal GCC 13.4.0 / binutils 2.43.1 / glibc toolchain
    ├── Kernel compiler
    ├── RootFS / userspace compiler
    └── F005 X2000 host-helper compiler

Debian ARM bare-metal toolchain
└── F005 / GD32F303 MCU firmware

Fre3nder
├── buildroot.defconfig
├── buildroot.fragment
├── BusyBox fragment
└── RootFS overlays
```

The RootFS build uses the official upstream Buildroot checkout pinned in
[`configs/x2000/sources.json`](../configs/x2000/sources.json). It no longer
depends on the Ingenic Buildroot fork, its
`halley5_linux_minimal_defconfig`, or an external userspace toolchain. The
internal toolchain targets little-endian MIPS32r2/O32 hard-float with FPXX and
NaN2008, using Linux 6.6 headers. The XBurst II target retains upstream
Buildroot's `-ffp-contract=off` XBurst workaround for userspace. The kernel uses the same Buildroot toolchain
family through the underlying `gcc.br_real`, but Kbuild supplies its separate
MIPS32r5/O32/soft-float/legacy-NaN target contract. The userspace wrapper flags
are not applied to the kernel. The Ingenic SDK remains only the separately
pinned source of the vendor kernel. Buildroot package downloads are retained
outside its Git checkout so source-tree cleanup does
not discard the offline-build cache. See
[`buildroot-maintenance.md`](buildroot-maintenance.md) for the LTS update
policy.

The ignored productive tree is organized as follows:

```text
local/production/
├── inputs/wifi/
│   ├── brcmfmac43430-sdio.bin
│   └── brcmfmac43430-sdio.txt
├── work/x2000/
└── artifacts/x2000/
    ├── moonraker/
    ├── guppyscreen/
    ├── full/
    ├── kernel-only/
    └── rootfs-only/
```

`scripts/build-x2000` always builds the Moonraker and GuppyScreen components and
then the RootFS. `--kernel-build` adds a Kernel build before them, and
`--f005-build` reproduces the F005 candidate before RootFS assembly; the Kernel
and RootFS artifacts are composed into `full/` only when the Kernel was built
in that same run. The individual builders are
`scripts/build-x2000-moonraker`, `scripts/build-x2000-guppyscreen`,
`scripts/build-x2000-buildroot`, and `scripts/build-x2000-kernel`. The
Buildroot builder's `--toolchain` phase precedes GuppyScreen compilation and its
`--assemble` phase consumes the two validated component archives. The removed
`build-x2000-rootfs` name has no compatibility alias, so there is only one
RootFS assembly path. The two WLAN files are BYOF inputs and are checked against
the hashes recorded in
[`configs/x2000/sources.json`](../configs/x2000/sources.json).

Normal builds are marked as `release` artifacts and retain the strict clean-tree
deployment checks. Add `--develop` explicitly to create a `development`
artifact from the current worktree. Development manifests contain a
deterministic SHA256 fingerprint of the relevant X2000 inputs, including
untracked files in those paths, and deployment requires both an explicit
`--develop` and an exact match with the current input fingerprint. This option
does not imply deployment `--write` or relax any hardware gate.

Development builds may reuse the existing Buildroot output and internal
toolchain when its dedicated toolchain fingerprint still matches. The current
Buildroot configuration is reapplied before the incremental build. Release
builds remove the Buildroot output before their toolchain phase and reuse
exactly that fingerprint-validated prepared toolchain for subsequent component
compilation and RootFS assembly in the same orchestration. Development reuse is
an iteration aid, not a reproducibility guarantee.

On the first development run after introduction of the fingerprint, a legacy
markerless output may be adopted only when its Buildroot version, effective
toolchain configuration, compiler contract, sysroot, and completion stamps all
match the current pinned toolchain. An unsafe or ambiguous legacy output is
removed. Release builds never adopt existing output.

The development reuse path is qualified on the reference build environment: a
legacy output reported `ADOPTED` once and the following RootFS-only build
reported the fingerprint-matched `HIT` path. The repeated build also qualified
replacement of stale Moonraker Git metadata by the current overlay in the
idempotent post-build hook. Release remains the clean build boundary.

### Buildroot host tools

Buildroot installs host-side tools produced or required by the X2000 build
under:

    local/production/work/x2000/buildroot-output-fre3nder/host/bin/

These tools are available even when the corresponding utility is not installed
system-wide on the development host. Development, inspection, and qualification
commands should prefer the Buildroot-provided tool when applicable instead of
assuming that a host package is installed.

For example, the SquashFS inspection tool produced by Buildroot is:

    local/production/work/x2000/buildroot-output-fre3nder/host/bin/unsquashfs

A RootFS artifact can therefore be inspected with:

    local/production/work/x2000/buildroot-output-fre3nder/host/bin/unsquashfs \
        -ll local/production/artifacts/x2000/rootfs-only/rootfs.squashfs

### Moonraker RootFS baseline

`build-x2000-moonraker` fetches the pinned Moonraker source and hash-pinned
pure-Python wheels before its network-disabled component phase. It produces a
deterministic, manifested RootFS-overlay archive which `build-x2000-buildroot`
validates before consumption. The RootFS contains
the upstream Git checkout at `/opt/fre3nder/moonraker` and a PEP 405 environment
at `/opt/fre3nder/moonraker-env`. Native Python dependencies come from
Buildroot; pure-Python wheel contents are staged in the environment. No target
source build or boot-time dependency installation is required.

The checkout retains its upstream origin and exact pinned HEAD so Moonraker can
recognize its own source for later stable-channel updates. Fre3nder Klipper is
still installed without Git metadata and remains outside Moonraker's update
ownership.

### GuppyScreen RootFS baseline

`build-x2000-guppyscreen` fetches the exact published source and submodule pins
before its network-disabled component phase, applies the source-carried
dependency patches, and cross-compiles with the prepared Buildroot toolchain.
Fre3nder's runtime-path overrides are carried directly by the pinned
GuppyScreen fork. Its deterministic component archive supplies the native
binary, immutable themes, and license texts. Because libhv embeds
`__DATE__`/`__TIME__`, the component builder derives `SOURCE_DATE_EPOCH` from
the pinned GuppyScreen commit before compilation. Together with the normalized
archive metadata this makes repeated component builds byte-reproducible. The
service/default configuration remain generic RootFS overlay inputs. See
[`guppyscreen.md`](guppyscreen.md) for the full runtime and build-gate contract.

## F005 MCU

Use [`scripts/build-f005`](../scripts/build-f005) as the standard product
entry point for an F005 MCU build.

`scripts/build-f005 --check` validates the pinned source, productive patches,
configuration, packager, and build-container contract without fetching,
building, or writing artifacts.

A normal `scripts/build-f005` run requires a clean Fre3nder project worktree.
It prepares the pinned upstream Klipper revision, applies the productive F005
MCU and serial-bootloader-request patches, builds the firmware with network
access disabled during compilation, packages the updater-compatible image, and
writes an unqualified candidate set under:

    local/production/artifacts/f005/candidate/

The candidate includes the raw firmware, ELF, Klipper dictionary, resolved
configuration, packaged F005 image, X2000 `c_helper.so`, packaging report,
build manifest, and checksums.

Candidate output is deliberately separate from the currently
hardware-qualified F005 artifact used by the default `deploy-f005` path.
Successful compilation does not promote a candidate to a qualified release.
The qualified image is embedded in the immutable RootFS baseline at
`/var/lib/fre3nder/firmware/f005/klipper-f005-mainline.bin`; a persistent system
overlay may replace it, but the MCU write remains operator-controlled.

The underlying container recipe remains
[`build/klipper-f005`](../build/klipper-f005), and
[`scripts/package_f005_firmware.py`](../scripts/package_f005_firmware.py)
provides the F005 board-information packaging step. The F005 build mounts the
existing X2000 Buildroot `host/` output read-only and uses its normal wrapper
for `c_helper.so`; it neither downloads nor builds another MIPS toolchain. The
MCU firmware continues to use the separate `arm-none-eabi` bare-metal
toolchain. Fre3nder therefore has one productive MIPS-Linux toolchain, not one
compiler across all architectures.

The entire `build-f005` path is build-only. It performs no printer, UART,
selector, partition, reboot, flash, or other hardware operation.

The validated source, version, and license basis are recorded in
[`docs/licensing-and-provenance.md`](licensing-and-provenance.md).

For the complete historical first-print reproduction, including the older
staged candidates, see
[`research/docs/f005-first-print-reproduction.md`](../research/docs/f005-first-print-reproduction.md).
