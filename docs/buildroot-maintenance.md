# Buildroot maintenance policy

The productive X2000 RootFS follows only the Buildroot `2025.02.x` LTS line.
Routine updates move between patch releases in that line, for example from
`2025.02.17` to `2025.02.18`. Quarterly stable releases such as `2026.05` or
`2026.08` are not automatic update targets.

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
   Dropbear, wpa_supplicant, libffi, and SquashFS.
3. Update the Buildroot version and exact commit in the build logic and
   `configs/x2000/sources.json`.
4. Confirm that the XBurst II patch applies and that its wrapper selects
   `-ffp-contract=off`.
5. Regenerate the effective Buildroot configuration from clean output.
6. Confirm the userspace contract: mipsel, MIPS32r2, O32, hard-float, FPXX,
   NaN2008, internal glibc toolchain, Linux 6.6 headers, and C++.
7. Confirm the effective GCC and binutils versions and that no external
   toolchain is selected.
8. Run `scripts/build-x2000` from clean output and execute the
   package-version, Python, ELF, and ABI checks.
9. Run exactly one `scripts/build-x2000 --kernel-build` after the RootFS-only
   validation.
10. Record the change as build-validated only after those builds pass.
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
