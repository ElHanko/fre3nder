# Buildroot maintenance policy

The productive RootFS uses official upstream Buildroot from
[`configs/x2000/sources.json`](../configs/x2000/sources.json). It uses neither
the Ingenic Buildroot fork nor an external userspace toolchain. Downloads are
cached outside the source checkout. The current supported update line is
`2025.02.x` LTS; quarterly feature releases are not automatic update targets.

## Toolchain and cache contract

Userspace targets little-endian MIPS32r2/O32 hard-float, FPXX, NaN2008, and
Linux 6.6 headers. Upstream Buildroot's XBurst `-ffp-contract=off` workaround
remains active. Kbuild uses the underlying `gcc.br_real` with its independent
MIPS32r5/O32/soft-float/legacy-NaN flags; userspace wrapper flags must not be
applied to the kernel. F005 `c_helper.so` uses the userspace toolchain; MCU
firmware uses a separate ARM bare-metal toolchain.

Development may reuse fingerprint-matched Buildroot output. Markerless output
is adopted only after version, effective toolchain configuration, compiler
contract, sysroot, and completion stamps match; ambiguous output is removed.
Release builds never adopt old output. The separate
`buildroot.legacy_adoption_commit` records the qualified adoption basis; later
pins do not inherit that qualification.

## WLAN firmware and NVRAM ownership

Retain the regular Buildroot/linux-firmware path. The pinned Buildroot selects
linux-firmware `20250211`, CYW43430 firmware `7.45.98.118` / FWID `01-32059766`,
the matching CLM blob, and driver aliases supplied by upstream `WHENCE`.
The board NVRAM is independently pinned, hash-checked, unchanged Radxa AZW372
content under BSD-3-Clause. Exact hashes, source identities and license terms
are in [sources.json](../configs/x2000/sources.json) and
[licensing and provenance](licensing-and-provenance.md#cyw43430-wlan-firmware).

WLAN is qualified on the investigated reference system for the recorded
integration. Bluetooth was not tested or qualified. A new Buildroot/firmware
pin does not inherit that hardware qualification. Recheck firmware package
version, selected-file/archive hashes, aliases, license and WLAN behavior when
updating. A separate Infineon fetch remains an evidence-backed fallback for an
observed regression, not a current build input. Kernel early-firmware loading
is specified in the [hardware contract](x2000-hardware-contract.md#wlan-early-firmware-contract).

Historical cache experiments, external firmware comparisons, exact artifact
hashes and deployment results remain in
[build history](../research/docs/x2000-build-history.md#buildroot-maintenance-and-wlan-qualification-snapshot).

## External package patches

`BR2_GLOBAL_PATCH_DIR` is set to the project's `patches/` directory. Buildroot
therefore applies package-specific patches from `patches/<package-name>/`,
after its own package patches. The current RootFS contract needs neither a
local MIPS target patch nor a Greenlet compiler-compatibility patch.

The Klipper upstream pin in [`sources.json`](../configs/x2000/sources.json)
requires `greenlet 3.3.2` and `cffi 2.1.1` on Python 3.12. The pinned Buildroot
recipes are updated by
[`0002-klipper-python-dependencies.patch`](../patches/buildroot/0002-klipper-python-dependencies.patch),
without changing the Buildroot release. Its source URLs and archive hashes
come from the [greenlet 3.3.2](https://pypi.org/pypi/greenlet/3.3.2/json) and
[cffi 2.1.1](https://pypi.org/pypi/cffi/2.1.1/json) PyPI records; license-file
hashes were checked against those archives. CFFI 2.1.1 declares MIT-0.

## Routine 2025.02.x update

For every patch release update:

1. Determine the latest `2025.02.x` LTS release from the official Buildroot
   site and resolve its official tag to the underlying commit.
2. Review `CHANGES` between the current and proposed patch release, with
   particular attention to `arch/mips`, internal toolchains, Python, BusyBox,
   Dropbear, wpa_supplicant, linux-firmware, libffi, and SquashFS.
3. Update only `buildroot.version` and `buildroot.commit` in
   `configs/x2000/sources.json`; consumers read them with `scripts/source-value`.
4. Confirm that the XBurst II patch applies and that its wrapper selects
   `-ffp-contract=off`.
5. Regenerate the effective Buildroot configuration from clean output.
6. Confirm the userspace contract: mipsel, MIPS32r2, O32, hard-float, FPXX,
   NaN2008, internal glibc toolchain, Linux 6.6 headers, and C++.
7. Confirm the effective GCC and binutils versions and that no external
   toolchain is selected.
8. Run exactly one `scripts/build-x2000` from clean output so
   the candidate Kernel and RootFS use the same current Buildroot basis. Do not
   add `--f005-build`; retain the qualified F005 release baseline.
9. Confirm the package-version, Python, ELF, and ABI checks from that build.
10. Record the change as build-validated only after the build passes.
    Hardware validation remains a separate status and must not be inferred
    from build success.

Check for a new `2025.02.x` patch release before every Fre3nder release and at
least monthly. Prefer timely updates when a relevant security fix is available.

## Migrating to a new LTS line

A later move such as `2025.02.x` to `2027.02.x` is not a routine update. Before
that migration, reassess at minimum:

- which GCC, binutils, glibc, and kernel-header versions are selected;
- whether all used Kconfig symbols still exist;
- whether upstream XBurst still activates the floating-point workaround;
- which Python version is provided and whether all Klipper Python dependencies
  build;
- whether `c_helper.so` satisfies the selected userspace ABI; and
- whether init, BusyBox, networking, and Dropbear behavior changes.
