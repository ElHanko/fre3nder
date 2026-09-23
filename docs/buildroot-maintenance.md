# Buildroot maintenance policy

The productive RootFS uses the official upstream Buildroot checkout pinned in
[`configs/x2000/sources.json`](../configs/x2000/sources.json). It does not use
the Ingenic Buildroot fork, `halley5_linux_minimal_defconfig`, or an external
userspace toolchain. Buildroot package downloads are kept outside its Git
checkout so checkout cleanup does not discard the offline cache.

The internal toolchain targets little-endian MIPS32r2/O32 hard-float with
FPXX and NaN2008, using Linux 6.6 headers. Upstream Buildroot's XBurst
`-ffp-contract=off` workaround remains active for userspace. The kernel uses
the same Buildroot toolchain family through `gcc.br_real`, but Kbuild supplies
its separate MIPS32r5/O32/soft-float/legacy-NaN flags; userspace wrapper flags
must not be applied to the kernel. The F005 `c_helper.so` uses the userspace
toolchain. The F005 firmware uses a separate ARM bare-metal toolchain.

Development builds can reuse the fingerprint-matched Buildroot output. A
markerless legacy output is adopted only after its Buildroot version,
effective toolchain configuration, compiler contract, sysroot, and completion
stamps match; ambiguous output is removed. Release builds never adopt old
output. On the reference build environment, adoption reported `ADOPTED` once
and the next RootFS-only build reported `HIT`; the repeated build also
validated replacement of stale Moonraker Git metadata by the idempotent
post-build hook. These are historical build-environment results, not a
reproducibility promise for an arbitrary development cache.

The productive X2000 RootFS follows only the Buildroot `2025.02.x` LTS line.
Routine updates move between patch releases in that line, for example from
`2025.02.17` to `2025.02.18`. Quarterly stable releases such as `2026.05` or
`2026.08` are not automatic update targets.

Before the Fre3nder 2026.2 release candidate, the baseline was advanced to
Buildroot `2025.02.18`, the direct next patch release in the same LTS series.
It carries bug fixes and security maintenance, including updates to expat,
glibc, libcurl, and OpenSSL used by Fre3nder. This does not change the
Fre3nder architecture model or move to a new Buildroot feature series. The
commit pin remains authoritative; its exact annotated release tag is fetched
and verified against that commit because Buildroot uses it for version identity.
The ABI and architecture profiles were hardware-qualified with the previous
baseline. The concrete Buildroot `2025.02.18` toolchain was subsequently built
as part of the release-mode `2026.2.a` candidate from project commit
`885706f121c76190d6d74177ffac3895cd58c78d` and hardware-qualified on the
investigated reference system. Successful boot, system-overlay recovery,
Fre3nder-to-Fre3nder reboot persistence, the complete service stack, and a real
print exercised both the userspace and kernel toolchain profiles. Both are now
recorded as hardware-qualified in `configs/x2000/sources.json`. This evidence
applies to the exact `2025.02.18` pin; a later Buildroot patch release requires
fresh qualification.

The productive CYW43430 firmware follows the `linux-firmware` version selected
by this Buildroot pin rather than a separate project download. Buildroot
2025.02.18 selects linux-firmware `20250211`. Any later Buildroot update must
therefore recheck the package version, archive and selected-file hashes,
`WHENCE` aliases, `LICENCE.cypress`, and WLAN hardware behavior. The
board-specific NVRAM is an independently pinned, hash-checked BSD-3-Clause
input vendored unchanged from Radxa/rkwifibt; it is not coupled to the
linux-firmware package version.
The regular package provides the `cypress/cyfmac43430-sdio.bin` and matching
CLM blob, with `brcm/brcmfmac43430-sdio.*` aliases created from `WHENCE`.
The earlier WLAN BYOF path `local/production/inputs/wifi` is not a current
build input.

Static inspection identifies the selected linux-firmware binary as
`7.45.98.118` / FWID `01-32059766` (SHA-256
`93f3c40c94340c29a40714cb04e3e89974870fcae42a844b8a4544750159f40d`),
with CLM SHA-256
`3376b9c9b32d16bf762e21c7fafb665365070ae240d092498d0d1987c22022aa`.
It is not byte-identical to the Infineon combination that NebulaOS qualified
on the Ender-3 V3 KE: `7.45.98.125` / FWID `01-f420b81d`, binary SHA-256
`82ed67a211877efa47aff4aab83d6d2d1ccf3d5d0f5c396df97f292ade01de9e`,
and CLM SHA-256
`1dbe1a396b68786bb189b7c255318ae546fd2e9d15f70ccc8ecbdc52b6cd4c47`.
That pair comes from
[Infineon/ifx-linux-firmware commit `4334275b5801bcf5256c3101395e7bc983ce640d`](https://github.com/Infineon/ifx-linux-firmware/tree/4334275b5801bcf5256c3101395e7bc983ce640d/firmware),
as recorded by the
[NebulaOS dependency manifest](https://github.com/coreflake1/NebulaOS-firmware/blob/d0a657a16c2a7e4a16d6c42cd5f0e2004f24ce10/manifests/dependencies.conf).
NebulaOS used a different NVRAM file with that pair. Its external qualification
therefore does not qualify Fre3nder's selected firmware/CLM/NVRAM integration.

The KISS choice retains the regular Buildroot/linux-firmware path. Fre3nder
hardware-qualified that path on 2026-09-14 with the complete Kernel/NVRAM/
RootFS integration described below. A separate Infineon fetch and pin would add
project-owned download, hash, license, and update logic and remains only an
evidence-backed fallback if a later update regresses the selected path.

Fre3nder vendors Radxa/rkwifibt's unmodified
`firmware/infineon/CYW43438/cyw43438_azw372.txt` from commit
`3d93dbcf5ff6e04fa760a56a0dad9f6077394072`. The 1016-byte file has SHA-256
`6167b8aaa5e80eabe09ac5bd8570760e5241aa3a9a6243a94be9fcba33cc1915`
and retains its upstream values, including `ccode=ALL`, power tables, and RF
parameters. On 2026-09-14 this exact content was tested on the investigated
reference Ender-3 V3 KE with the selected `7.45.98.118` / FWID `01-32059766`
firmware: the MAC address was preserved, WPA association and DHCP passed, and
10/10 gateway ICMP packets returned without loss. Restoring the previous NVRAM
and reassociating also passed.

The subsequent development build used the historical
`scripts/build-x2000 --kernel-build --develop` invocation (the current full
build command is `scripts/build-x2000 --develop`), with build-input SHA-256
`84f625bd0984a9eb8511eec27af7d35e55f5c9202f3f572c8da74df55ed81d33`,
qualified the complete production WLAN path on the same date. The resulting
Kernel SHA-256 was
`93207a7b627442759bbc74716876c94592edfacb94cacd0ea52f1a9c09ab9d13` and
the RootFS SHA-256 was
`f86ad04f6a63653ef79f0f8280a91d951838102cba8d509e019e78332404055b`.
Kernel p6 and RootFS p8 writes passed readback while Stock p5 and p7 remained
unchanged. Fre3nder B booted from `/dev/mmcblk0p8`, its persistent-root runtime
contract passed, and the runtime NVRAM file matched SHA-256
`6167b8aaa5e80eabe09ac5bd8570760e5241aa3a9a6243a94be9fcba33cc1915`.
The driver detected `BCM43430/1` and reported firmware
`7.45.98.118 (7d96287 CY)` / FWID `01-32059766`; WPA association, DHCP, and
10/10 gateway packets passed without loss. The Ethernet default path remained
unchanged and the final selector was `STOCK_A`. This qualifies the exact
official linux-firmware `.bin` and `.clm_blob`, vendored Radxa NVRAM, Kernel,
and RootFS together for WLAN. Bluetooth was not tested or qualified.

A move to a new LTS line, such as `2027.02`, is a separate migration requiring
its own qualification. Buildroot may rename MIPS or internal-toolchain Kconfig
symbols, change compiler or libc versions, change Python major/minor versions,
or alter BusyBox, Dropbear, or wpa_supplicant behavior.

## External package patches

`BR2_GLOBAL_PATCH_DIR` is set to the project's `patches/` directory. Buildroot
therefore applies package-specific patches from `patches/<package-name>/`,
after its own package patches. The current RootFS contract needs neither a
local MIPS target patch nor a Greenlet compiler-compatibility patch.

## Routine 2025.02.x update

For every patch release update:

1. Determine the latest `2025.02.x` LTS release from the official Buildroot
   site and resolve its official tag to the underlying commit.
2. Review `CHANGES` between the current and proposed patch release, with
   particular attention to `arch/mips`, internal toolchains, Python, BusyBox,
   Dropbear, wpa_supplicant, linux-firmware, libffi, and SquashFS.
3. Update the Buildroot version and exact commit in the build logic and
   `configs/x2000/sources.json`.
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
