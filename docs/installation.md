# Installing and updating Fre3nder

The current X2000 deployment tool is
[`scripts/deploy-x2000`](../scripts/deploy-x2000). It stages the host kernel
and RootFS into the inactive X2000 A/B slot. Slot A uses p5/p7 and Slot B uses
p6/p8.

Without a component option, both kernel and RootFS are selected. The same
selection can be requested explicitly with `--all`; `--kernel` and `--rootfs`
allow either component to be deployed independently.

Without `--write`, the tool performs a fail-closed read-only preflight. The
`--write` mode is an explicit persistent-operation boundary and requires the
operator's authorization and risk acceptance described by `AGENTS.md`.

Development artifacts require an additional explicit `--develop`. Their stored
X2000 input fingerprint must be valid and match the current calculated
fingerprint; release artifacts retain the clean-worktree deployment gate.
`--develop` does not authorize `--write` or relax any hardware gate.

For each selected component, the tool verifies the local artifact against
`SHA256SUMS` and the build manifest, checks that relevant build inputs have not
changed since the artifact source commit, identifies the active and inactive
A/B slots, and requires the boot selector to still point to the active slot.
It validates the inactive target partitions and, in `--write` mode, writes only
the selected inactive-slot artifacts followed by a complete artifact-length
SHA-256 readback. The active kernel and RootFS partitions are hashed before and
after staging and must remain unchanged.

`deploy-x2000` is intentionally a staging operation. It does not change the boot
selector, arm a system-persistence reset, activate the staged slot, or reboot
the printer. Activation is a separate OTA transaction step.

Stock-A host restoration is an explicit variant of the same staging interface.
`--stock` stages a complete raw Stock kernel/RootFS pair to p5/p7 and is accepted
only while Slot B is active and the selector still points to B. The default
source is `local/backup/stock/image/`; an alternative source directory may be
given directly after `--stock`. A Stock source directory must contain exact
full-partition `p5.img` and `p7.img` files plus `SHA256SUMS`.

Stock staging always treats p5/p7 as one pair; it cannot be combined with the
individual component options or `--develop`. It does not restore p9/p10, change
the X2000 selector, reboot the host, or restore the F005 MCU. Those remain
separate recovery/activation responsibilities. Vendor and device backup files
under `local/` remain local-only and are not repository artifacts.

The X2000 deploy tool intentionally does not install or update the F005 MCU.
MCU firmware lifecycle management is a separate responsibility and is not part
of `deploy-x2000`.

Moonraker is part of the RootFS artifact rather than a separately installed
application artifact. Later Moonraker updates are intended to copy up under
`/opt/fre3nder/moonraker` and `/opt/fre3nder/moonraker-env` in the writable
system OverlayFS. A normal reboot retains those changes; an authorized
system-overlay reset exposes the platform release's RootFS baseline again while
preserving `/home/fre3nder/printer_data`.

The current F005 build tool is
[`scripts/build-f005`](../scripts/build-f005). It is build-only and has no
printer or hardware access. `--check` validates the recipe without fetching,
building, or writing artifacts. A normal build produces an unqualified
candidate under `local/production/artifacts/f005/candidate/` and deliberately
does not replace the currently qualified F005 deployment artifact.

The current transitional F005 deployment tool is
[`scripts/deploy-f005`](../scripts/deploy-f005). It is separate from X2000
host deployment and operates only on an already running Fre3nder B system with
the selector restored to the qualified `STOCK_A` fallback state.

Without `--write`, `deploy-f005` performs a fail-closed read-only preflight. It
validates the local release manifest and F005 firmware artifact, verifies that
the installed Fre3nder F005 product helpers match the current project sources,
requires an active persistent root, and accepts only an MCU state already classified
by the normal startup gate as exact Fre3nder or exact supported Stock.

With `--write`, the current transitional path stages the exact validated F005
firmware under `/var/lib/fre3nder/firmware/f005/` when required. This is
reconstructible, release-specific system state in the writable root overlay; it
is intentionally not userdata retained across a system-persistence reset. An
already current Fre3nder MCU is not reflashed. An exact supported Stock MCU is
first checked through the qualified no-write transition preflight and is then
passed once to the existing open Stock-to-Fre3nder transition helper.

`deploy-f005` does not modify the X2000 selector or the host A/B partitions.
The Fre3nder RootFS carries the qualified F005 release as its immutable
baseline, so a system-overlay reset makes that image visible again. Any replacement in the
writable system overlay and every MCU transition remain explicit
operator-controlled `deploy-f005` actions; normal boot does not flash the MCU.

The `deploy-f005` wrapper is currently **OFFLINE CONFIRMED** by fixture tests.
The underlying bounded Stock-to-Fre3nder F005 transition remains separately
**QUALIFIED ON DEVICE** on the investigated reference system.

The current build/deployment contract is summarized in
[`docs/x2000-open-host-architecture.md`](x2000-open-host-architecture.md).

The established bounded p1 selector helper is
[`scripts/x2000-ab`](../scripts/x2000-ab). The external BootROM selector
fallback is [`scripts/x2000-usb-selector-to-a`](../scripts/x2000-usb-selector-to-a).
Neither tool is a general recovery guarantee.

## Reference-system deployment qualification

On 2026-08-30 the existing deployment path was exercised successfully with
the untagged current-main build `2026.1-1-gc4c6fa1` from project commit
`c4c6fa18e659a82ada32c708720202a5ad6592ac`.

The deployed `rootfs.squashfs` was 31760384 bytes with SHA-256
`5ac3a01985789476f0db73fbb2091f3b7fbfcce98578392c6c7c1f14abfbddf2`.
The helper booted Stock A, wrote Slot-B p8, performed a full artifact-length
readback with an exact SHA-256 match, selected B, booted the newly written
read-only SquashFS, and finally restored the selector to `STOCK_A`.

Post-boot checks confirmed active p8, read-only SquashFS, both expected
persistence bindings, the expected F005 product files and manifest, absence of
`mcu_util` from the immutable RootFS, and active Klipper. This qualification
applies to the investigated reference system and does not turn the untagged
current-main build into a new public release.

## Full kernel and RootFS qualification

On 2026-08-30 a subsequent full build that was current-main at the time,
from project commit `833cbd43132e5a818a422f25d9478cd6b3f76123`
(`2026.1-4-g833cbd4`) was installed on the same reference system.

The Slot-B kernel artifact was 4878400 bytes with SHA-256
`5d350222ae07efb710aaeb4f43f8753180d0e04ea6f74ab687089fd07fdc7e6f`.
The Slot-B RootFS artifact was 31760384 bytes with SHA-256
`6cecb56bafd931874d296d81089d20596632cb342a0bd605e723bddfe83b7b62`.

Installation was performed from Stock A with p6 and p8 unmounted. The kernel
was written to p6 and the RootFS to p8, and both were verified by complete
artifact-length SHA-256 readback. Stock p5 and p7 remained byte-for-byte
unchanged.

The newly written p6/p8 pair subsequently booted successfully with Linux
`6.6.18-rt23`, read-only SquashFS root on p8, active persistence, active
Klipper, and hostname `fre3nder`. The selector was finally restored to
`STOCK_A` while Fre3nder remained active on p8.

This qualifies the complete kernel-plus-RootFS installation of that
2026-08-30 build on the investigated reference system. It was an untagged
current-main qualification build at the time and is not a new public `2026.1`
release.
