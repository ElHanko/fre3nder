# Recovery analysis

This document combines mechanisms observed read-only on the reference device with
explicitly labeled vendor documentation and community research. A
non-destructive Linux RAM-only Boot-ROM attempt was executed on the reference
device; no Stage-2 start, restore, or persistent flashing procedure succeeded.

Unless stated otherwise, these mechanisms were observed on the reference system
running Creality firmware `V1.1.0.15`. Their behavior must be verified on other
firmware revisions before use.

## Evidence levels

- **CONFIRMED-ON-DEVICE:** directly observed read-only on the V1.1.0.15 reference
  device or preserved in its captured persistent data.
- **OFFLINE-CONFIRMED:** directly established by static/read-only analysis of
  captured device images or archived vendor artifacts without executing them.
- **VENDOR-DOCUMENTED:** described by Creality for the Ender-3 V3 KE, but not
  performed on the reference device.
- **COMMUNITY-RESEARCH:** relevant external technical work, but not validated for
  this KE or its exact hardware/storage layout.
- **INFERENCE:** a working hypothesis derived from multiple observations.
- **OPEN:** not yet established.

## Recovery mechanisms and evidence

### 1. A/B system OTA

**CONFIRMED-ON-DEVICE:** The GPT provides paired `rtos`/`rtos2`,
`kernel`/`kernel2`, and `rootfs`/`rootfs2` partitions. `/etc/ota_bin` contains
local and network OTA implementations.

The updater:

1. reads a short selector from partition `ota`;
2. selects the inactive RTOS, kernel, and RootFS partitions;
3. validates image metadata/size and per-piece MD5 values;
4. streams each image directly to its target block device;
5. changes the `ota` selector only after the selected images succeed.

This is a transactional A/B update design at the system-image level. It reduces
risk from a failed write before selector change, but it does not itself prove an
automatic boot-attempt counter or automatic rollback after a bad-but-successfully
written image.

The private capture shows selector `ota:kernel`, active RootFS A
(`/dev/mmcblk0p7`) at V1.1.0.15, and an intact V1.1.0.12 B side whose RTOS, kernel,
and RootFS payloads match the archived official recovery payloads exactly before
zero padding. Bootability of B has not been exercised after capture.

### 2. Local and network update entry points

**CONFIRMED-ON-DEVICE:** The reference RootFS contains the following update
entry points:

- `/etc/ota_bin/local_ota_update.sh` accepts a Creality `.img` bundle, extracts it
  under `/usr/data/creality`, and uses the same A/B writer.
- `/etc/ota_bin/network_ota_update.sh` implements network acquisition.
- `upgrade-server` is part of the Creality application stack and references
  `/etc/ota_bin`, `/usr/data/creality/upgrade`, and removable-media paths.
- The UI/runtime logs identify firmware `V1.1.0.15`, hardware `F005`.

**INFERENCE:** A valid Creality firmware `.img` on removable media can be submitted
through the Creality update flow while Linux and the UI stack still run. A
vendor-documented pre-Linux USB recovery mode now exists as a separate mechanism
below; it is not the same as this `.img` OTA path.

### 3. Official USB brick recovery

**VENDOR-DOCUMENTED / ENTRY LOCALLY VALIDATED:** Creality documents a
Linux-independent “Brick Rescue / Wire Brushing” path for the Ender-3 V3 KE in
its [wiki guide](https://wiki.creality.com/en/ender-series/ender-3-v3-ke/quick-start-guide/firmware-open-source/brick-rescue-wire-brushing-process)
and official [Annex recovery-tool directory](https://github.com/CrealityOfficial/Ender-3_V3_KE_Annex/tree/main/firmware%20recovery%20tool).
The directory contains English and Chinese recovery PDFs and
`cloner-2.5.18-windows_alpha.zip`.

The documented vendor flow disconnects and opens the controller, connects its
MicroUSB port to a PC, holds Boot and Reset together for about three seconds,
releases Reset first and Boot second, and expects Windows to detect `Ingenic USB
BOOT DEVICE`. Creality then installs the supplied Windows driver, loads a
`.ingenic` image in the Ingenic Cloner utility, starts the tool, and repeats the
Boot/Reset sequence to begin flashing.

This establishes that Creality provides a KE-specific low-level USB recovery path
which does not require the normal Creality Linux system to boot. It also
establishes `.ingenic` as a distinct vendor recovery/wire-flash artifact type and
a Boot/Reset-initiated Ingenic USB mode on the controller board.

For this reference setup the Windows Cloner is retained only as the vendor
protocol and policy reference. It is **VENDOR-DOCUMENTED, BUT NOT PERSONALLY
VERIFIED ON THIS DEVICE**. A private KE-specific Linux client implements only
the Boot-ROM RAM-only transfer sequence and has 22 passing offline tests.

The first fresh Linux RAM-only hardware attempt reached and completed the
Boot-ROM Stage-1 transfer: GET_CPU_INFO identified X2000, GINFO and the
original SPL were transferred, and PROGRAM_START1 was accepted. After the
approximately 1100-ms handoff, the first Stage-2 SET_DATA_ADDRESS for
`0x80100000` timed out after about two seconds. Stage 2 was therefore not
loaded or started by this client. No CONFIG, INIT, READ, WRITE, MMC/eMMC,
erase, or other persistent operation was executed.

**CONFIRMED-ON-DEVICE:** the reference board has since entered this low-level USB
mode without starting a flash. It enumerated as VID:PID `a108:eaef` with product
string `Ingenic USB BOOT DEVICE`; a non-writing CPU-info request returned `X2000`.

It does **not** establish:

- successful SPL/Stage-2 start or complete recovery on the reference device;
- a demonstrated complete restore or return to the reference state;
- which eMMC regions Cloner writes, including GPT, bootloader, A/B system images,
  and factory identity;
- whether arbitrary project-created images are accepted;
- whether signature or secure-boot checks apply;
- that the private Linux RAM-only client can load or start Stage 2 on this KE
  hardware.

The official [V1.1.0.12 release](https://github.com/CrealityOfficial/Ender-3_V3_KE_Klipper/releases/tag/V1.1.0.12)
publishes two different firmware artifact types:

| Artifact | Published size | Vendor role documented here |
|---|---:|---|
| `Ender-3_V3_KE_1.1.0.12.ingenic` | 130,364,076 bytes | Brick/wire-recovery image type used by Cloner |
| `Ender-3_V3_KE_F005_ota_img_V1.1.0.12.img` | 118,559,722 bytes | F005 OTA/normal firmware-update bundle |

Their different roles and sizes do not show that their contents are equivalent.
The reference device runs V1.1.0.15.

### Offline analysis of the archived vendor recovery set

The official vendor files are archived only in the ignored local workspace; their
hashes and findings may be documented publicly. Offline verification confirmed:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `Ender-3_V3_KE_1.1.0.12.ingenic` | 130,364,076 bytes | `5388b16810e51c8233d6ee978b5b4a09347a4c9a4a516d3c5bf8c686e6783f3c` |
| `Ender-3_V3_KE_F005_ota_img_V1.1.0.12.img` | 118,559,722 bytes | `a0107f5a868f6e6ee3e0f00239242a5029839b71ca562e39eb3713a763055d16` |
| `Ender-3_V3_KE_F005_ota_img_V1.1.0.15.img` | 118,738,362 bytes | `2539467fb489caeaf28708e1e30c338b4d357aeece664c9dd25b6a645386c153` |

The two OTA `.img` files use the same outer 7-Zip container format with encrypted
headers. Their internal component lists and package metadata could therefore not
be confirmed offline with the available non-invasive tooling.

**OFFLINE-CONFIRMED:** The V1.1.0.12 recovery RootFS/update implementation shows:

- the installed board/version data is represented as `ota_board_name=F005` and
  `ota_version=1.1.0.12`;
- the updater rejects a target version when the local version is greater than or
  equal to the target version;
- the inspected update descriptors contain target version, image type/name/size,
  and per-image MD5 values;
- no `minimum_version`, `from_version`, `source_version`, `base_version`,
  `required_version`, explicit intermediate-version requirement, or prescribed
  upgrade chain was found;
- RTOS, kernel, and RootFS payloads are written to the inactive A/B side and the
  `ota` selector is changed only after the selected writes succeed.

**CONFIRMED-ON-DEVICE:** retained `upgrade-server.log` data records the reference
device running V1.1.0.12 on 2024-11-22, selecting
`Ender-3_V3_KE_F005_ota_img_V1.1.0.15.img` from removable media, invoking
`/etc/ota_bin/local_ota_update.sh` directly on that image, and subsequently
reporting V1.1.0.15. No V1.1.0.13 or V1.1.0.14 stage appears in that recorded
transaction. The captured A/B state is consistent with the same event: B remains
the exact V1.1.0.12 system-image set while A is the active V1.1.0.15 side.

The `.ingenic` file is not a whole-eMMC image. It is a ZIP-based Ingenic Cloner
package containing generic Cloner resources and a selected KE/X2000 configuration.
Four target payloads were identified:

| Payload | Target offset | Size | Offline finding |
|---|---:|---:|---|
| `u-boot-with-spl-mbr-gpt.bin` | `0x00000000` | 212,296 bytes | SPL/U-Boot, protective MBR, primary GPT, and additional boot code before p1 |
| `zero.bin` | `0x00300000` (p3) | 432,824 bytes | RTOS/FreeRTOS image despite the generic filename |
| `xImage` | `0x00b00000` (p5) | 4,087,872 bytes | U-Boot legacy Linux image, kernel 4.4.94 |
| `rootfs.squashfs` | `0x01b00000` (p7) | 115,122,176 bytes | SquashFS 4.0 RootFS |

The embedded GPT matches the documented p1-p10 boundaries. The boot payload begins
at byte zero and contains executable boot code in the user area before p1. It does
not cover the whole pre-p1 area, and the package contains no payload for p1 `ota`,
p2 `sn_mac`, p4 `rtos2`, p6 `kernel2`, p8 `rootfs2`, p9 `rootfs_data`, p10
`userdata`, boot0, boot1, or RPMB.

The embedded primary GPT header is internally CRC-valid, but its `alternate_lba`
and `last_usable_lba` both point to LBA 15,271,935. The `.ingenic` payload contains
no backup GPT at the physical end of the reference eMMC.

**CONFIRMED-ON-DEVICE:** the captured live V1.1.0.15 GPT has the same
`backup_lba = last_usable_lba = 15,271,935` relationship. Its primary header and
partition-entry-array CRCs validate, while no backup-GPT header signature exists
anywhere in the physical tail through LBA 15,273,599. The unconventional GPT
layout is therefore not merely an artifact of the archived recovery package.
Whether Cloner performs any transient GPT repair or normalization during flashing
remains untested.

The selected Cloner configuration enables writes for boot/SPL/U-Boot/GPT, p3
RTOS, p5 kernel, and p7 RootFS. It also contains:

```text
erase_all=1
erase_list="0x0,0x1fffff;0x300000,0xffffffff;"
force_erase=2
```

**OFFLINE-CONFIRMED for the configured map:** projected onto the reference GPT,
the configured erase ranges remove p1, p3-p9, and the beginning of p10 while p2
lies exactly between the ranges. No active recovery payload targets p2. The
expected immediate recovery state is therefore p2 preserved, p3/p5/p7 rewritten,
p4/p6/p8/p9 erased, and p10 partially erased. Exact runtime behavior remains a
practical validation point until the first destructive recovery.

**OFFLINE-CONFIRMED:** the V1.1.0.12 RootFS recreates p9 `/overlay` and p10
`/usr/data` as ext4 after mount failure.

The recovery also erases p1 and supplies no replacement selector. Boot strings
strongly support an A-side default unless `ota:kernel2` selects B, but direct
control flow for a completely erased selector has not been proven. This is an
accepted residual risk for manual recovery review.

See [`recovery-current-state.md`](recovery-current-state.md) for the recorded
reference-board state.

No official V1.1.0.15 `.ingenic` image has been located. The locally archived
V1.1.0.15 F005 OTA image and the V1.1.0.12 recovery package describe the
vendor-documented multi-stage path. It is not personally verified on this
device and is not a guaranteed restore, but it satisfies the current Gate-1
evidence requirement for an external recovery route.

### Accepted recovery target for Gate 1

Gate 1 does not require a one-step, bit-for-bit restoration directly to the last
firmware version used on the reference device. A reproducible and validated
multi-stage path to a known working starting state is sufficient. For example,
the following is an acceptable recovery model to validate:

```text
brick
  -> official V1.1.0.12 .ingenic brick recovery
  -> successful normal boot
  -> official update to V1.1.0.15
  -> restore protected device-specific data and settings
  -> known working starting state
```

The complete brick-to-stock sequence is still **not locally validated** because
the destructive `.ingenic` recovery stage has not been exercised. The
V1.1.0.12-to-V1.1.0.15 OTA stage, however, is now historically confirmed on the
reference device by its retained upgrade log and captured A/B state. V1.1.0.12 is
not prescribed as the final or only recovery route. An official matching
V1.1.0.15 `.ingenic` image could replace the intermediate recovery/update stages.
Device identity or factory data may be restored only to its original device and
only after the Cloner write coverage is understood; the real procedure must place
that restoration at a verified safe stage if `.ingenic` changes those areas.

Gate 1 requires a documented return path with preserved and offline-validated
material, not a technically elegant or one-step implementation. The private
Linux client is now retained as an unsuccessful, non-demonstrated research
artifact; no further recovery research or new recovery-tool development is
planned. The official Windows/Cloner route remains vendor-documented but
unverified on this device, and recovery execution remains documented but not
personally rehearsed.

### 4. Factory reset

**CONFIRMED-ON-DEVICE:** `S58factoryreset` recognizes a `factory_reset` flag on
mounted USB media and also has an explicit reset action. Its implementation
deletes most of `/overlay/upper` and `/usr/data`, while deliberately retaining
selected identity/network/root-opt-in data, then reboots.

This is **not** a firmware recovery and **not** a restoration of erased A/B images.
It is a destructive userdata/overlay reset. It was not invoked.

### 5. MCU recovery/update

**CONFIRMED-ON-DEVICE:** At normal Stock boot `S13mcu_update` uses
`mcu_util` on `/dev/ttyS1`; its general upload form is
`mcu_util -i <tty> -u -f <image>`. The original F005 main-MCU image is present
at `/usr/share/klipper/fw/F005/mcu0_001_G32-mcu0_005_000.bin` with SHA-256
`0b8ecfad8e65e90a3cfc08dd8534dd568e341c160897e6050eadcbf1eb917d4a`.
The Mainline image previously flashed through this Stock updater is retained at
`/usr/data/klipper-f005-mainline.bin` with SHA-256
`5b9678731b10a0f8c6159b3cf2432b1a499d6310b9466419d129dc42242e23ac`.
That historical Stock -> Mainline flash succeeded; it does not prove the reverse
direction.

**DIRECT RUNNING-APPLICATION TEST:** after Stock Klipper was stopped through
its intended init service and `/dev/ttyS1` was verified free, the non-writing
commands `mcu_util -i /dev/ttyS1 -c`, `-g`, and `-s` each timed out with return
code 1. No MCU firmware was written. This establishes only that direct
`mcu_util` access does not itself move the already running Mainline application
into the Creality bootloader.

**CONFIRMED-ON-DEVICE on 2026-08-27:** a subsequent separately authorized
no-write test kept Stock Klipper connected long enough for Moonraker to accept
`FIRMWARE_RESTART`. Stock Klipper was then stopped, `/dev/ttyS1` was verified
free, and the Creality bootloader immediately answered `mcu_util -c`.
`mcu_util -g` returned `mcu0_001_G32-mcu0_004_000`, and `mcu_util -s` returned
`app_run`; all three operations returned 0. Stock Klipper then restarted and
reconnected to the unchanged Mainline application, returning to the same known
`read_swap_prtouch` protocol error.

This establishes a usable software-reset path from the running Mainline MCU to
the retained Creality serial bootloader and a no-write return to the existing
application:

**MAINLINE MCU -> CREALITY MCU BOOTLOADER -> EXISTING MAINLINE APP RETURN:
QUALIFIED ON DEVICE.**

A subsequent separately authorized test on 2026-08-27 restored the preserved
original Stock F005 image with one project-initiated `mcu_util` update
invocation over this qualified bootloader path. `mcu_util` returned success and
`app_run`. Stock Klipper then loaded the
original 116-command MCU firmware and reached `Printer is ready`.

Therefore **MAINLINE F005 MCU -> ORIGINAL STOCK F005 MCU FIRMWARE RETURN:
QUALIFIED ON DEVICE**. No SWD requirement is established by the current
evidence.

## Bootloader status

**CONFIRMED-ON-DEVICE:** eMMC exposes 4 MiB boot0 and boot1 hardware areas, both
protected by the kernel's force-read-only setting. There are no `/boot` files, no
U-Boot environment config, and no bootloader version in the inspected runtime
files.

**CONFIRMED-ON-DEVICE:** A read-only EXT_CSD read returned
`PARTITION_CONFIG=0x00`, so the
standard eMMC boot operation from boot0, boot1, or the user area is not currently
enabled. The eMMC reports `BOOT_INFO=0x07`, indicating support for alternative
boot, DDR boot, and high-speed boot. These are device capabilities, not evidence
that the reference system uses them.

**OFFLINE-CONFIRMED for the vendor recovery package:** the V1.1.0.12 `.ingenic`
boot payload writes SPL/U-Boot, the protective MBR, primary GPT, and additional
boot code into the eMMC user area starting at byte zero and extending into the
pre-p1 region.

**CONFIRMED-ON-DEVICE:** boot0 and boot1 were captured read-only at their exact
4 MiB sizes and are entirely zero-filled. The live user-area boot/GPT material was
also captured. LBA0 matches the V1.1.0.12 recovery payload exactly. GPT geometry,
names, type GUIDs, attributes, and partition boundaries match; only disk/unique
partition GUIDs and their dependent CRCs differ. In the post-GPT boot payload only
14 bytes differ, all belonging to the embedded build timestamp
(`Oct 09 2023 - 16:41:52` live versus `Dec 29 2023 - 18:01:54` recovery). Bytes
after the vendor payload end through the p1 start are all zero.
`PARTITION_CONFIG=0x00` continues to show that standard eMMC boot-partition
selection is disabled.

**OPEN:**

- exact X2000 ROM sequence that selects/executes the captured user-area loader
  while standard eMMC boot-partition selection is disabled;
- exact SPL/U-Boot version identity beyond the embedded build timestamp;
- serial console accessibility on ttyS4 and available bootloader commands;
- exact ROM protocol, memory setup, and payload constraints behind the
  vendor-documented Ingenic USB boot mode;
- board test points, pinout, and whether external eMMC programming is feasible;
- automatic rollback/boot-attempt semantics.

Answering several of these would require raw-device reads, boot interruption,
hardware access, or writes. They remain intentionally open.

## Closed USB-boot research direction

**CONFIRMED-ON-DEVICE:** The reference device tree reports
`ingenic,x2000_module_base` and `ingenic,x2000`. Independently,
**VENDOR-DOCUMENTED** recovery expects an `Ingenic USB BOOT DEVICE`. Together
these make an Ingenic Boot-ROM or comparable low-level USB path plausible, but do
not establish the exact ROM sequence, independently identify the package as X2000
versus X2000E, or show that this project can load SPL/U-Boot.

**COMMUNITY-RESEARCH / BOUNDED KE VALIDATION:** The
[`ingenic-usbboot`](https://github.com/ballaswag/ingenic-usbboot) project targets
Creality K1/K1 Max boards using an Ingenic X2000E. It demonstrates a related
Boot/Reset entry sequence, temporary SPL loading into internal SRAM/TCSM, U-Boot
loading into DRAM, and eMMC partition access/dumps. Its K1 example labels a 1 MiB
`uboot(gpt/uboot)` region before `ota`.

The pinned public upstream basis is commit
`c65eaa337cc9fb64fd8a2ea22bcf3f9395c9945c`. The SPL and U-Boot from that
commit were used unchanged on the reference KE through the separately
conserved RAM-U-Boot path. The locally conserved host client differs only by
the already documented CPUINFO/libusb return-value fix. This confirmed
BootROM/CPUINFO, RAM SPL/U-Boot, MMC access, and a bounded p1-only A -> B -> A
selector roundtrip with Stock-A return. This does not generalize the K1 loader
to every KE revision, prove Slot-B bootability, or validate p6/p8 deployment.

The K1 description alone is not evidence that the Ender-3 V3 KE accepts the
same K1 loaders or uses the same ROM/SRAM/DRAM sequence. The bounded KE test
above is separate device evidence and does not generalize to every revision.
The later private KE capture does establish
persistent SPL/U-Boot-style material in the user area before p1, closely matching
the official KE recovery payload. The private KE client was attempted once and
completed Stage 1, but timed out at the first Stage-2 address transfer. It
contains no Stage-2, MMC/eMMC, erase, read, or write operation. The client and
this research direction are retained for provenance only; no further recovery
research is planned.

## Brick scenarios and visible options

| Failure | Visible recovery prospect | Confidence |
|---|---|---|
| Broken writable overlay/config | Factory reset or file-level repair while Linux/SSH works | High mechanism confidence; destructive and untested |
| Broken active RootFS/kernel, inactive side valid | Change/boot alternate A/B side | Medium; layout/update logic confirmed, bootloader control unknown |
| Linux boots, firmware image needs reinstall | Creality local/network OTA via `upgrade-server` | Local V1.1.0.12-to-V1.1.0.15 OTA is historically confirmed on the reference device; network OTA remains unexercised |
| Mainline firmware currently running on main MCU | Original Stock F005 image is preserved; software reset into the retained Creality bootloader, exactly one Stock-image write, and successful Stock Klipper startup are qualified on-device | **QUALIFIED ON DEVICE:** Mainline -> Creality bootloader -> original Stock F005 firmware -> Stock Klipper `ready` was completed on 2026-08-27 |
| Both kernel/RootFS sides broken | Official Creality Ingenic USB/Cloner recovery using the `.ingenic` policy | USB Boot entry and Stage-1 transport observed; Stage-2 did not start; configured erase/write coverage analyzed offline; complete recovery remains vendor-documented but unverified |
| Bootloader/eMMC boot path corrupted | Official Ingenic USB/Cloner recovery or external programmer | Vendor procedure documented but bootloader/GPT coverage and practical recovery remain open |
| Identity partition (`sn_mac`) lost | Restore device-specific partition from prior backup | High need; no generic replacement should be assumed |

## Remaining recovery prerequisites

Completed prerequisites include the archived official V1.1.0.12 recovery/OTA and
V1.1.0.15 OTA artifacts, captured EXT_CSD and user-area/boot-area state, verified
A/B selector and inactive-side contents, and the validated private backup described
in [`backup-plan.md`](backup-plan.md).

Gate 1 is **SATISFIED** by the current evidence review. The non-writing USB entry
and Stage-1 transport are observed, but the private Linux client did not reach
Stage 2 and the official destructive vendor recovery has not been run. No further
recovery research is planned in this project phase. The remaining claims are
therefore split explicitly: the package and erase map are technically analyzed
offline, the Linux RAM-only result is an unsuccessful practical attempt, and the
complete Windows/Cloner restore remains vendor-documented but not personally
rehearsed.

The second independent physical copy of the private recovery set has been created
and verified by re-reading all manifest-covered artifacts from separate storage.

The open KE-specific Ingenic client remains only as an unsuccessful,
non-demonstrated research artifact; no further client or recovery research is
planned and it is not a Gate-1 prerequisite.

## Risks

- **Risk:** Factory reset is destructive and preserves only a hard-coded subset of
  data; it is not a substitute for a backup.
- **Risk:** A/B recovery fails if both sides, the selector, GPT, or bootloader are
  damaged.
- **Risk:** Restoring another printer's `sn_mac`, certificates, or Creality
  userdata could duplicate identity or break cloud/device pairing.
- **Risk:** MCU images must match the exact board and MCU; filenames for other
  models are present beside F005 images.
- **Risk:** Changing `force_ro`, boot partitions, A/B selector, or SWD state is a
  high-consequence operation and was not authorized.
- **Risk:** The selected V1.1.0.12 Cloner configuration appears to erase p1,
  the inactive A/B side, p9, and part of p10 while only rewriting boot/GPT, p3,
  p5, and p7. The exact runtime erase semantics remain unvalidated, so the vendor
  procedure must be treated as broadly destructive until proven otherwise.
- **Risk:** A vendor-documented flashing procedure is not a guaranteed restore.
  Backup and offline validation are now in place, and Gate 1 is satisfied under
  the current evidence criteria, but destructive brick-recovery behavior,
  identity preservation/restoration, and end-to-end execution remain unverified.

## WARNING / RED ZONE

Further work may intentionally change the bootloader, partitions, kernel,
RootFS, MCU firmware, or other persistent contents. Because no complete
recovery has been demonstrated on this device, such work may leave it
unbootable, require additional hardware intervention, or permanently damage or
destroy it. Backups reduce risk but do not prove that restoration will work.
This warning is a risk boundary, not an implicit authorization for any specific
write or flash operation.
