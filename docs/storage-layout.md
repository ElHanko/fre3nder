# Storage layout

This is the current Fre3nder storage contract for the investigated X2000
reference system. Verify physical layout before using another hardware/firmware
revision. Historical Stock captures do not assign ownership to Fre3nder.

## Fre3nder persistence roles

The current Fre3nder implementation does not use internal p9 or p10.
Its external Development backend consists of two independently provisioned ext4
filesystems:

| Logical role | Current backend | Runtime role |
| --- | --- | --- |
| System persistence | `LABEL=FRE3NDERSYS` | OverlayFS `upper` and `work` for `/`, plus explicitly defined boot-control metadata |
| Userdata persistence | `LABEL=FRE3NDERHOME` | mounted at `/home` |

The immutable SquashFS remains the OverlayFS lower and is visible at `/rom`
after the early root switch. `/run` and `/tmp` are tmpfs. The normal data
payload of `FRE3NDERSYS` consists of `upper` and `work`. Additional boot-control
metadata includes the optional legacy `.fre3nder-reset` marker whose exact
`RESET_ON_NEXT_BOOT` content authorizes recreation of those two directories
after the filesystem has been uniquely identified and mounted successfully.
The targeted `.fre3nder-reset-target` marker is consumed only by its intended
A/B root. OTA also stores activation and known-good records alongside `upper`
and `work`; their lifecycle is described in
[OTA](ota.md#persistent-activation-handoff).
Backend discovery uses exact labels and the expected ext4 type, independently
of USB device names or future partition numbers. Current backend qualification is limited to the exact recorded reference
artifacts, including diagnostic operation when a backend is absent or invalid.
No internal p9/p10 fallback is implemented. Detailed degraded-runtime results
remain in [storage evidence](../research/docs/storage-layout.md#fre3nder-persistence-roles).

## Regular software shutdown

Fre3nder's [inittab](../configs/x2000/rootfs-overlay/etc/inittab) replaces the
Buildroot file during RootFS overlay assembly. BusyBox 1.37.0 reads its
`shutdown` actions in file order and waits for each command; it does not add
default actions when an `inittab` exists (`init/init.c`, `parse_inittab` and
`run_actions`). Fre3nder retains the
[Buildroot 2025.02.18 shutdown sequence](https://gitlab.com/buildroot.org/buildroot/-/blob/d030e36bbc9669230c015be971b14b6e062cfdde/package/busybox/inittab):
`/etc/init.d/rcK`, `/sbin/swapoff -a`, then `/bin/umount -a -r`.
Buildroot's existing `rcK` calls `S??*` scripts with `stop` in reverse name
order, including Moonraker before Klipper and the host MCU, and network and
logging afterward. BusyBox Init then signals remaining processes and syncs
before the final reboot, halt or poweroff.

The administrative deployment and OTA reboot paths use `reboot` without `-f`,
so they request this Init sequence. The early `fre3nder-root` bootstrap stays
outside `rcK`; filesystem teardown uses the existing BusyBox `umount`, whose
`-r` option attempts a read-only remount when unmounting reports a busy mount.
Successful teardown of `/home`, the OverlayFS root and its SYS backing mount
still requires qualification with a separately authorized controlled reboot.
Routine removal of power does not run this sequence; ext4 journal recovery and
Moonraker's unsafe-shutdown counter after power loss are not by themselves
evidence that regular software shutdown failed.

## Current A/B mapping

| Logical slot | Kernel | RootFS |
| --- | --- | --- |
| A | `/dev/mmcblk0p5` (`kernel`, 8 MiB) | `/dev/mmcblk0p7` (`rootfs`, 500 MiB) |
| B | `/dev/mmcblk0p6` (`kernel2`, 8 MiB) | `/dev/mmcblk0p8` (`rootfs2`, 500 MiB) |

The existing p1 selector names `ota:kernel` or `ota:kernel2`. Historical
`STOCK_A`/`DEVELOP_B` names identify byte patterns, not present payload ownership.
Identify the active runtime and validate the inactive partition identities before
an authorized write. [OTA](ota.md) and [installation](installation.md) define
those operations; neither slot is permanently reserved for Stock.

## Protected structures and recovery

Preserve GPT and the pre-p1 loader, p2 factory/identity material, p3/p4 RTOS,
boot0/boot1, eMMC hardware boot configuration and RPMB. They are not generic
free space or public configuration stores. Internal p9/p10 are Stock writable
structures and remain outside current Fre3nder persistence ownership.
Gate satisfaction does not authorize partition, selector, bootloader or firmware
writes; follow [AGENTS.md](../AGENTS.md) and [recovery](recovery.md).

The full reference GPT/EXT_CSD, mount graph, bootloader placement, capture
limitations and A/B investigation remain in
[Stock storage evidence](../research/docs/storage-layout.md). A live raw ext4
capture is not a clean filesystem snapshot; preserve the separately verified
recovery set and identity material rather than treating a normal HOME/SYS
backup as a complete Stock return set.
