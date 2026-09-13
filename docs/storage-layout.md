# Storage layout

See [`system-inventory.md`](../research/docs/system-inventory.md) for platform context and
[`ssh-command-log.md`](../research/docs/ssh-command-log.md) for the evidence-producing commands.
The initial Phase 0 inventory did not copy block-device contents. A later Phase 1
private capture read the eMMC user area and boot0/boot1 without writing to the
printer. Device-specific images, GUIDs, identity data, logs, and hashes remain
outside public Git.

Unless stated otherwise, this layout was observed on the reference system running
Creality firmware `V1.1.0.15`. It must be verified before use with another
firmware or hardware revision.

## Fre3nder persistence roles

The current Fre3nder `2026.2` implementation does not use internal p9 or p10.
Its external Development backend consists of two independently provisioned ext4
filesystems:

| Logical role | Current backend | Runtime role | Future internal backend |
| --- | --- | --- | --- |
| System persistence | `LABEL=FRE3NDERSYS` | OverlayFS `upper` and `work` for `/`, plus explicitly defined boot-control metadata | p9 |
| Userdata persistence | `LABEL=FRE3NDERHOME` | mounted at `/home` | p10 |

The immutable SquashFS remains the OverlayFS lower and is visible at `/rom`
after the early root switch. `/run` and `/tmp` are tmpfs. The normal data
payload of `FRE3NDERSYS` consists of `upper` and `work`. The currently defined
additional boot-control object is the optional `.fre3nder-reset` marker whose exact
`RESET_ON_NEXT_BOOT` content authorizes recreation of those two directories
after the filesystem has been uniquely identified and mounted successfully.
The implementation resolves the current backends by exact label and ext4 type
and has no dependency on USB device names or future partition numbers. This
external path is offline implemented and partially hardware-qualified on the
investigated reference system: normal persistence and marker-authorized reset
of the system overlay with retained `/home` are demonstrated. Explicit missing
or invalid system/userdata-backend cases remain open.

The rest of this document records the observed Stock storage layout and does not
assign its internal writable partitions to the current Fre3nder implementation.

## Storage type

**Confirmed:** Internal non-volatile storage is eMMC, not MTD/NAND exposed through
Linux MTD. `/proc/mtd` contains only its header, `/sys/class/mtd` is empty, and no
`/dev/mtd*` or `/dev/mtdblock*` nodes exist.

The eMMC identifies as:

- type `MMC`, name `DG4008`
- manufacturer ID `0x45`, OEM ID `0x0100`
- 15,273,600 logical sectors at 512 bytes = 7,820,083,200 bytes
  (about 7.28 GiB)
- separate 4 MiB `boot0`, 4 MiB `boot1`, and 4 MiB RPMB areas

Unit-specific eMMC manufacturing and identity fields are kept only in the ignored
`local-device.md`.

BusyBox `fdisk` printed the whole device as `3361M`; this is inconsistent with its
own sector count and `/proc/partitions` and is **inferred** to be a 32-bit size
format/overflow defect. Sector counts are used below.

Both eMMC boot areas report `ro=1` and `force_ro=1`. During the later private
read-only capture, boot0 and boot1 were each read at their exact 4 MiB size. Both
images are byte-for-byte identical and consist entirely of `0x00`. Their private
capture hashes were independently verified.

## EXT CSD metadata

**Confirmed on the reference system:** P1.2-02a read the complete 512-byte
EXT_CSD with read-only access to the kernel debugfs file at
`/sys/kernel/debug/mmc0/mmc0:0001/ext_csd`. The read returned successfully. No
`mmc` utility, block-device read, mount operation, or configuration change was
used. The full raw value is intentionally not reproduced in this public document.

| Field | Observed value | Interpretation |
|---|---:|---|
| `EXT_CSD_REV` | `0x08` | EXT_CSD revision 1.8 / eMMC 5.1 |
| `SEC_COUNT` | `0x00e90e80` | 15,273,600 sectors; confirms the 7,820,083,200-byte user area |
| `BOOT_SIZE_MULTI` | `0x20` | boot0 and boot1 are 4 MiB each |
| `RPMB_SIZE_MULT` | `0x20` | RPMB is 4 MiB |
| `PARTITION_CONFIG` | `0x00` | `BOOT_PARTITION_ENABLE=0`, `PARTITION_ACCESS=0`, `BOOT_ACK=0` |
| `BOOT_BUS_CONDITIONS` | `0x00` | Stored boot-bus configuration is x1, single-data-rate, backward-compatible mode |
| `BOOT_INFO` | `0x07` | The eMMC reports support for alternative boot, DDR boot, and high-speed boot |
| `RST_n_FUNCTION` | `0x00` | The eMMC hardware-reset function is in its temporary disabled/default state |

`PARTITION_CONFIG=0x00` means that the standard eMMC boot operation from boot0,
boot1, or the user area is not currently enabled. This does **not** show that
boot0/boot1 contain no relevant data, nor does it exclude an SoC-specific or
alternative boot mechanism. `BOOT_INFO=0x07` reports capabilities only; it does
not show that the reference system uses any of those boot modes.

Observed health indicators:

| Field | Value | Conservative interpretation |
|---|---:|---|
| `PRE_EOL_INFO` | `0x01` | Normal |
| `DEVICE_LIFE_TIME_EST_TYP_A` | `0x02` | Estimated 10-20% lifetime usage |
| `DEVICE_LIFE_TIME_EST_TYP_B` | `0x01` | Estimated 0-10% lifetime usage |

These are coarse eMMC/JEDEC indicators, not exact wear measurements.

Relevant partitioning, reliability, and write-protection register values were:

| Field | Observed value |
|---|---:|
| `PARTITIONING_SUPPORT` | `0x07` |
| `PARTITION_SETTING_COMPLETED` | `0x00` |
| `PARTITIONS_ATTRIBUTE` | `0x00` |
| `GP_SIZE_MULT_1` through `GP_SIZE_MULT_4` | all zero |
| `ENH_START_ADDR` / `ENH_SIZE_MULT` | both zero |
| `WR_REL_PARAM` | `0x15` |
| `WR_REL_SET` | `0x1f` |
| `USER_WP` | `0x00` |
| `BOOT_WP` | `0x00` |
| `BOOT_WP_STATUS` | `0x00` |
| `BOOT_CONFIG_PROT` | `0x00` |

These are observed register values only. Their functional effect was not tested.
In particular, `PARTITION_SETTING_COMPLETED=0x00` must not be treated as an
invitation to complete or modify the eMMC partition configuration. Changing this
or any other EXT_CSD configuration field is not part of the project.

## GPT user-area layout

**Confirmed on the reference system:** P1.2-02b used the installed BusyBox 1.31.1
`fdisk` as the only available suitable GPT reader. The read-only command
`fdisk -u -l /dev/mmcblk0` returned zero and reported `Found valid GPT with
protective MBR; using GPT`. No raw sectors, partition contents, or gap contents
were read.

The logical and physical block sizes are both 512 bytes. The user area has
15,273,600 sectors, covers physical LBA 0-15,273,599, and is 7,820,083,200 bytes.
The first usable LBA is 34 and the last usable LBA is 15,271,935. The concrete
disk GUID and unique partition GUIDs are not reproduced in this public document.

| Part. | Node | Sectors | Size | GPT name | Observed/inferred role |
|---:|---|---:|---:|---|---|
| 1 | `/dev/mmcblk0p1` | 2048-4095 | 1 MiB | `ota` | **Confirmed captured state:** `ota:kernel` plus two newlines followed by NUL bytes; selects side A |
| 2 | `/dev/mmcblk0p2` | 4096-6143 | 1 MiB | `sn_mac` | **Confirmed:** device identity/model/board/factory fields |
| 3 | `/dev/mmcblk0p3` | 6144-14335 | 4 MiB | `rtos` | **Confirmed:** RTOS A update target/name |
| 4 | `/dev/mmcblk0p4` | 14336-22527 | 4 MiB | `rtos2` | **Confirmed captured state:** exact V1.1.0.12 recovery RTOS payload plus zero padding |
| 5 | `/dev/mmcblk0p5` | 22528-38911 | 8 MiB | `kernel` | **Confirmed active A kernel:** differs from the archived V1.1.0.12 recovery `xImage` |
| 6 | `/dev/mmcblk0p6` | 38912-55295 | 8 MiB | `kernel2` | **Confirmed captured state:** exact V1.1.0.12 recovery `xImage` plus zero padding |
| 7 | `/dev/mmcblk0p7` | 55296-1079295 | 500 MiB | `rootfs` | **Confirmed active:** valid SquashFS; `/etc/ota_info` identifies V1.1.0.15/F005 |
| 8 | `/dev/mmcblk0p8` | 1079296-2103295 | 500 MiB | `rootfs2` | **Confirmed captured state:** exact V1.1.0.12 recovery SquashFS plus zero padding; `/etc/ota_info` identifies V1.1.0.12/F005 |
| 9 | `/dev/mmcblk0p9` | 2103296-2717695 | 300 MiB | `rootfs_data` | **Confirmed active:** ext4 writable overlay; offline-derived image passed read-only `e2fsck -fn` |
| 10 | `/dev/mmcblk0p10` | 2717696-15271935 | 6130 MiB | `userdata` | **Confirmed active:** ext4 mounted at `/usr/data`; raw live-capture image contains expected consistency errors and is complemented by a readable file-level archive |

The partition starts and sector counts were independently cross-checked through
kernel sysfs. Partitions p1 through p10 are contiguous; there are no gaps between
them.

### Sectors outside p1-p10

| Region | LBA range | Sectors | Bytes | Status |
|---|---:|---:|---:|---|
| GPT prefix | 0-33 | 34 | 17,408 | Contains at least the protective MBR, primary GPT header, and primary partition-entry array; not free space |
| Usable pre-p1 alignment region | 34-2047 | 2,014 | 1,031,168 | Captured: vendor-style boot code occupies the beginning of this region; bytes after offset 212,295 through p1 are all zero |
| Gaps between p1-p10 | none | 0 | 0 | All ten partitions are contiguous |
| Usable space after p10 | none | 0 | 0 | p10 ends at the last usable LBA |
| Physical tail after p10 | 15,271,936-15,273,599 | 1,664 | 851,968 | Captured; no `EFI PART` backup-GPT header signature is present anywhere in the tail |

The p1 start at LBA 2048 is consistent with ordinary 1 MiB alignment. The
later private capture establishes that the LBA 34-2047 region contains the
vendor-style pre-p1 loader material at its beginning and is zero-filled after
the captured vendor payload through the p1 boundary. The physical tail after p10
contains no backup-GPT header signature; it should still be treated as captured
device structure rather than generic free space.

### GPT verification

The later private whole-user-area capture allowed a complete offline primary-GPT
integrity check. The primary header CRC and primary partition-entry-array CRC both
validate. The captured primary header uses:

- `current_lba = 1`;
- `backup_lba = 15,271,935`;
- `last_usable_lba = 15,271,935`.

Thus `backup_lba` points to the final LBA of p10 rather than the physical eMMC end
at LBA 15,273,599. No backup-GPT header signature was found anywhere in the
851,968-byte physical tail.

The same unconventional `backup_lba`/`last_usable_lba` relationship is present in
the archived V1.1.0.12 `.ingenic` recovery GPT. Comparing the live GPT with that
recovery GPT shows that geometry, names, type GUIDs, attributes, and partition
boundaries match. The only partition-entry differences are the ten unique
partition GUIDs; in the header, the disk GUID and the CRC values derived from
those identifiers differ. Concrete GUID values remain private.

## Active mount graph

```text
/dev/mmcblk0p7 (SquashFS, read-only)
  -> /rom
     + /dev/mmcblk0p9 (ext4, /overlay)
       -> overlayfs root /

/dev/mmcblk0p10 (ext4)
  -> /usr/data
```

Concrete free-space and usage values are transient, device-specific observations
and are kept only in the ignored `local-device.md`. Verify sufficient free space
on both writable filesystems before backup, deployment, or migration operations.

Only partitions 9 and 10 returned UUIDs through `blkid`. Partition 7's SquashFS
type is nevertheless directly confirmed by both the command line and mount table.
No filesystem claims are made for the inactive/raw partitions because their
contents were not sampled.

## A/B behavior

**Confirmed from OTA scripts:** The `ota` partition contains a short selector of
the form `ota:kernel` or `ota:kernel2`. If it names `kernel2`, the updater targets
the A partitions (`kernel`, `rootfs`, `rtos`); otherwise it targets the B
partitions. After all selected images have been written and verified, the updater
changes the selector to the newly written side.

**Confirmed from the private capture:** p1 begins with exactly `ota:kernel\n\n`
and is otherwise NUL-filled. Side A is therefore selected. The active p7 RootFS
identifies itself as V1.1.0.15/F005.

The inactive B side is preserved as V1.1.0.12: p4 is byte-identical to the
official recovery `zero.bin` RTOS payload followed only by zero padding; p6 is
byte-identical to the recovery `xImage` followed only by zero padding; and p8 is
byte-identical to the recovery `rootfs.squashfs` followed only by zero padding.
The p8 `/etc/ota_info` independently identifies V1.1.0.12/F005.

A retained Creality `upgrade-server.log` records the same reference device
running V1.1.0.12 on 2024-11-22, selecting the official
`Ender-3_V3_KE_F005_ota_img_V1.1.0.15.img` from removable media, invoking
`/etc/ota_bin/local_ota_update.sh` on that image, and subsequently reporting
V1.1.0.15. This confirms that a direct V1.1.0.12-to-V1.1.0.15 local OTA path was
successfully used on the reference device.

## Bootloader and non-user areas

The private capture resolves the principal placement questions for this reference
device:

- `mmcblk0boot0` and `mmcblk0boot1` are each exactly 4 MiB and entirely `0x00`;
- EXT_CSD still reports `PARTITION_CONFIG=0x00`;
- LBA0 of the live user area is byte-identical to the V1.1.0.12 recovery
  `u-boot-with-spl-mbr-gpt.bin`;
- after the GPT structures, the vendor-style boot payload occupies user-area
  bytes through offset 212,295;
- the entire remaining region from offset 212,296 to the p1 start is zero.

Comparing the live pre-p1 boot material with the V1.1.0.12 recovery payload shows
only two classes of differences. GPT differences are limited to the disk GUID,
the ten unique partition GUIDs, and the corresponding CRC fields. Outside GPT,
only 14 bytes differ, all belonging to two copies of the embedded bootloader build
timestamp: the live image contains `Oct 09 2023 - 16:41:52`, while the recovery
payload contains `Dec 29 2023 - 18:01:54`.

This establishes persistent SPL/U-Boot-style loader material in the eMMC user
area before p1 for the captured reference device and closely matches the vendor
recovery layout. Because the exact X2000 ROM boot sequence remains unknown, the
capture alone does not prove every step by which that material is selected or
executed. Serial-console behavior and low-level recovery commands also remain
open.

## Risks and open questions

- **Risk:** Live raw capture of mounted ext4 partitions can be crash-consistent at
  best and internally inconsistent at worst. The captured p10 image demonstrates
  this limitation and must not be described as a clean filesystem snapshot.
- **Risk:** Restoring the wrong A/B selector with mismatched kernel/rootfs/RTOS
  images can make both sides unbootable.
- **Open:** Reliable RPMB access and whether RPMB is provisioned or used.
- **Open:** Exact X2000 ROM-to-user-area boot sequencing, serial-console access,
  and available bootloader commands.
- **Open:** Exact runtime semantics of the vendor Cloner erase policy and whether
  p2 `sn_mac` is preserved in a real recovery run.
- **Open:** Safe physical main-MCU flash readback remains unavailable.
