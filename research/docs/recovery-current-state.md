# Recovery evidence and historical current-state record

This record preserves the reference-system investigation and qualification
history. The operational decision path is in
[`docs/recovery.md`](../../docs/recovery.md).

Its dated device observations run through 2026-08-29. Words such as "current"
in the preserved text describe the state when that investigation was recorded,
not the present state of the printer or the current recovery contract.

This document records the current recovery state for the single reference printer
used by this project. It is a case study, not a universal recovery specification
for every Ender-3 V3 KE revision.

Reference hardware for the current work:

- Creality Ender-3 V3 KE;
- Creality hardware/OTA identifier `F005`;
- controller-board marking `CREALITY NEBULA V1.0.0.28`, dated `2023.5.25`;
- Ingenic X2000-family host platform;
- nominal 8 GB eMMC with the p1-p10 layout documented in
  [`storage-layout.md`](../../docs/storage-layout.md).

The project intentionally optimizes for this one known board and firmware history.
Other owners may use the documentation as a technical reference, but must verify
their own board revision, storage layout, firmware artifacts, and recovery behavior
before applying any step.

## Project decision rule

> Is this step necessary, or clearly useful, to recover this reference board from
> a brick back to the official Creality V1.1.0.12 starting state?

Interesting but non-blocking reverse engineering is intentionally deferred.

## Current recovery target

```text
brick / non-booting normal Linux
  -> Ingenic USB Boot mode
  -> official V1.1.0.12 .ingenic recovery
  -> successful stock V1.1.0.12 boot
  -> optional official V1.1.0.12 -> V1.1.0.15 OTA
  -> validated stock operating state
```

## Low-level USB recovery entry

**CONFIRMED-ON-DEVICE:** the Boot/Reset sequence reaches the Ingenic USB recovery
interface on the reference board without writing firmware.

```text
VID:PID  a108:eaef
Product  Ingenic USB BOOT DEVICE
CPU info X2000
```

The official Windows/Creality Cloner remains the reference for the vendor flow,
protocol behavior, and recovery policy. It is **VENDOR-DOCUMENTED, BUT NOT
PERSONALLY VERIFIED ON THIS DEVICE**. The private Linux client was used once in
a non-destructive RAM-only attempt, but did not reach Stage 2. The complete
recovery route remains documented but not personally rehearsed; no guaranteed
restore is claimed.

## KE GINFO and Stage 1

```text
GINFO   0xb2401000
SPL     0xb2401800
Stage 2 0x80100000
```

The final GINFO is 0x180 bytes:

```text
INFO wrapper
GPIO payload without GPIO wrapper header
DDR wrapper
```

A private clean-room generator reproduces the functional GINFO required by the
selected Creality X2000E/LPDDR2 path. Producer byte identity is not claimed.

**OFFLINE-CONFIRMED:** the original 9,720-byte Creality SPL performs CPU/clock,
UART, timer, PLL, and DDR initialization and then returns. No MMC/eMMC storage
controller path, erase operation, or persistent storage write was found in the
SPL itself.

## Stage-2 upload and protocol

Official KE Stage-2:

```text
load/start address  0x80100000
size                424684 bytes
SHA-256             194da4cce4481e2975d2fbf35dd7325df80cfb9a15a673643b2323a39863ab9d
```

Corrected host sequence:

```text
GET_CPU_INFO
-> send GINFO/SPL
-> run Stage 1
-> wait
-> host-side is_adb() check
-> upload uboot.bin
-> cache flush
-> run Stage 2
```

An earlier interpretation that placed `stage2_init()` between SPL and U-Boot was
caused by a misread C++ subobject/vtable offset and has been discarded.

Relevant Stage-2 requests:

| Request | Role |
|---:|---|
| `0x10` | ACK/status |
| `0x11` | module init |
| `0x12` | write |
| `0x13` | read |
| `0x14` | configuration upload |

For MMC reads, the media/operation word at command offset `+0x08` must be
`0x00020000` for the registered MMC module.

The optional read-only LBA-0 preflight was removed from the critical path because
fresh Stage-2 MMC initialization requires configuration and the complete backend
command path was not statically proven non-persistent.

## Separate upstream/community RAM-U-Boot path

**CONFIRMED-ON-DEVICE for a bounded p1 test:** a separate path based on the
public [`ballaswag/ingenic-usbboot`](https://github.com/ballaswag/ingenic-usbboot)
commit `c65eaa337cc9fb64fd8a2ea22bcf3f9395c9945c` loaded its unchanged SPL and
U-Boot into RAM, reached X2000 CPU info, and provided the expected MMC access.

The exact upstream identities, fresh-checkout procedure, and the narrow
CPUINFO/libusb source fix are documented under
[`research/patches/ingenic-usbboot/`](../patches/ingenic-usbboot/README.md). The CPUINFO
patch changes only `jz_get_cpu_info()` and is not required by the
`--uboot`, `--dump-partition`, or `--swap-ota` paths used by
`scripts/x2000-usb-selector-to-a`.

The exact host-client executable used for every historical USB operation is not
established by the preserved logs. No per-run host-binary identity is therefore
claimed. The unchanged SPL and U-Boot loader identities are preserved and
documented separately.

This is a separate upstream/community-derived RAM-U-Boot path. It must not be
identified with the private KE-specific Linux recovery client above or with the
official KE Stage-2. The private Linux client remains **UNSUCCESSFUL / NOT
DEMONSTRATED**, while the official Windows/Creality Cloner remains
**VENDOR-DOCUMENTED, BUT NOT PERSONALLY VERIFIED ON THIS DEVICE**.

The path was used for a bounded p1-only selector test. A 512-byte Stock-A
selector was read, changed A -> B and read back byte-for-byte, then changed
B -> A and read back byte-for-byte. No B boot was attempted; p6 and p8 were
not written; no kernel, RootFS, or MCU firmware was changed. After the
roundtrip, normal Stock A boot from `/dev/mmcblk0p7` was confirmed and p1 again
matched the original A hash. This establishes the additional **p1 A/B rollback
gate** only; it does not establish Slot-B bootability or a complete recovery.

## `read_from_flash.bin`

**OFFLINE-CONFIRMED:** `read_from_flash.bin` is a local host-side `PolicyRead`
output file, not firmware and not executable code for the printer.

## Official V1.1.0.12 recovery package

```text
Ender-3_V3_KE_1.1.0.12.ingenic
size    130364076 bytes
SHA-256 5388b16810e51c8233d6ee978b5b4a09347a4c9a4a516d3c5bf8c686e6783f3c
```

| Payload | Target offset | Size |
|---|---:|---:|
| `u-boot-with-spl-mbr-gpt.bin` | `0x00000000` | 212,296 bytes |
| `zero.bin` | `0x00300000` | 432,824 bytes |
| `xImage` | `0x00b00000` | 4,087,872 bytes |
| `rootfs.squashfs` | `0x01b00000` | 115,122,176 bytes |

Selected MMC policy:

```text
erase_all=1
erase_list="0x0,0x1fffff;0x300000,0xffffffff;"
force_erase=2
```

## Expected post-recovery eMMC state

| Partition | Expected immediate post-Cloner state |
|---|---|
| p1 `ota` | erased, no payload |
| p2 `sn_mac` | preserved by configured erase/write map |
| p3 `rtos` | erased, then `zero.bin` written |
| p4 `rtos2` | erased, no payload |
| p5 `kernel` | erased, then `xImage` written |
| p6 `kernel2` | erased, no payload |
| p7 `rootfs` | erased, then `rootfs.squashfs` written |
| p8 `rootfs2` | erased, no payload |
| p9 `rootfs_data` | erased, no payload |
| p10 `userdata` | partially erased from its start to the 4-GiB address boundary |

For this exact GPT, p2 lies between the configured erase ranges and has no active
write payload. Actual post-flash identity preservation remains a Gate-1 checkpoint.

## First boot

**OFFLINE-CONFIRMED:** V1.1.0.12 invokes `mount_mmc_ext4.sh` for p9 and p10.
On mount failure it runs `mke2fs` for the complete partition.

- p9 is recreated as ext4 and mounted as `/overlay`;
- p10 is recreated as ext4 and mounted as `/usr/data`.

The B-side p4/p6/p8 remains empty until a later OTA transaction fills it.

## Accepted unresolved p1 risk

The recovery erases p1 and writes no replacement selector. The boot payload
contains both A- and B-root boot arguments plus `ota:kernel2`, strongly supporting
the model that `ota:kernel2` selects B and a non-matching selector selects A.

The direct MIPS control flow for an erased/all-`0xff`/invalid selector has not been
fully resolved. This is now an explicitly accepted residual risk and must remain
visible in manual recovery review.

## Backup and offline preflight

Two physically separate copies of the complete raw user-area backup have been
re-read and verified against the same privately recorded SHA-256.

A private offline preflight under `local/` re-verifies the vendor archive, erase
policy, active payloads, SPL/U-Boot identity, GPT geometry, p2 preservation map,
p9/p10 first-boot evidence, and both raw backup copies.

The offline preflight result was:

```text
READY FOR MANUAL RECOVERY REVIEW
NOT READY TO FLASH
```

No offline preflight failure remains. This result is not a flash-readiness or
restore guarantee. Known warnings are the accepted p1 selector risk, partial
physical erase of p10, and empty B slots after recovery.

The private recovery set also includes a current pre-recovery configuration
snapshot. It preserves the active printer and Moonraker configuration, active
includes, Creality user configuration, and calibration-relevant settings such as
bed mesh, input shaper, heater PID, PR-touch/Z compensation, and relevant motion
and macro parameters. Device-specific values remain private.

## Private Linux RAM-only client

A private client is restricted to this reference board and validates the exact
V1.1.0.12 archive, GINFO, original SPL, original Stage 2, active payloads,
write offsets, erase policy, and p2 preservation map before it can open a device.
Its Boot-ROM transport uses system `libusb-1.0` and has 22 passing offline tests.

The intended hardware sequence was deliberately finite:

```text
a108:eaef -> X2000 -> GINFO -> original SPL -> PROGRAM_START1 -> 1100 ms
-> original Stage 2 -> CACHE_FLUSH -> PROGRAM_START2
-> RAM_ONLY_STAGE2_READY -> close -> STOP
```

The first fresh hardware attempt completed the Boot-ROM Stage-1 transport:
GET_CPU_INFO identified X2000, GINFO and the original SPL were transferred, and
PROGRAM_START1 was accepted. The first Stage-2 `SET_DATA_ADDRESS` for
`0x80100000` then timed out after approximately two seconds. Stage 2 was not
loaded or started. `CONFIG`, `INIT`, `READ`, `WRITE`, MMC/eMMC access, erase,
and persistent writes were not reached.

## Current Stock host and Mainline MCU state

**CONFIRMED-ON-DEVICE on 2026-08-27:** Stock A is active from
`/dev/mmcblk0p7` with selector `STOCK_A`, while the F005 MCU still runs the
previously flashed Mainline Klipper firmware. Stock Klipper connects and reads
the MCU protocol, but its Creality-specific configuration fails with:

```text
mcu 'mcu': Unknown command: read_swap_prtouch
```

Klipper consequently enters `error` with an MCU Protocol error. The Stock
`master-server` maps this to fault code 3002 and error class 2; the
`display-server` carries it as `errorcode=3002` and `k1_errorcode=2`, producing
the visible Stock system error. This incompatibility is not hidden with UI
patches, error-map changes, or fabricated Klipper state.

The preserved Stock and current Mainline MCU artifacts are:

| Role | Path | SHA-256 |
| --- | --- | --- |
| Original Stock F005 image | `/usr/share/klipper/fw/F005/mcu0_001_G32-mcu0_005_000.bin` | `0b8ecfad8e65e90a3cfc08dd8534dd568e341c160897e6050eadcbf1eb917d4a` |
| Current Mainline image | `/usr/data/klipper-f005-mainline.bin` | `5b9678731b10a0f8c6159b3cf2432b1a499d6310b9466419d129dc42242e23ac` |

The earlier Stock -> Mainline flash through Creality `mcu_util` is proven. A
first non-writing return-path test stopped Stock Klipper, verified
`/dev/ttyS1` free, and then ran `mcu_util -c`, `-g`, and `-s` directly against
the already running Mainline application. All three operations timed out with
return code 1. No MCU firmware was written. This establishes only that direct
`mcu_util` access does not itself move the running Mainline application into
the Creality bootloader.

A subsequent separately authorized no-write test established the missing
transition on the reference device. Stock Klipper initially owned
`/dev/ttyS1`; Moonraker accepted `FIRMWARE_RESTART`, after which Stock Klipper
was stopped and the UART was verified free. `mcu_util -c` then completed with
return code 0, `mcu_util -g` returned
`mcu0_001_G32-mcu0_004_000` with return code 0, and `mcu_util -s` returned
`app_run` with return code 0. Stock Klipper was restarted successfully and
reconnected to the same Mainline MCU version, returning to the previously known
`read_swap_prtouch` protocol error. No erase or firmware upload occurred.

**MAINLINE MCU -> CREALITY MCU BOOTLOADER -> EXISTING MAINLINE APP RETURN:
QUALIFIED ON DEVICE.**

**HISTORICAL PROJECT-CONTROLLED MAINLINE F005 MCU -> ORIGINAL STOCK F005 MCU
FIRMWARE RETURN: QUALIFIED ON DEVICE.** On 2026-08-27 the preserved original Stock image was
verified at 31436 bytes with SHA-256
`0b8ecfad8e65e90a3cfc08dd8534dd568e341c160897e6050eadcbf1eb917d4a`,
then restored by one project-initiated `mcu_util` update invocation over the
qualified Creality bootloader path. `mcu_util` returned success and `app_run`.
Stock Klipper subsequently loaded
the original 116-command MCU firmware and reached `Printer is ready`.

## Current boundary

The Linux-hosted Ingenic recovery investigation is closed at this evidence
boundary. The private Linux path is **UNSUCCESSFUL / NOT DEMONSTRATED** and no
further tooling for that path is planned. The separate upstream/community
RAM-U-Boot path is **CONFIRMED-ON-DEVICE** only for the bounded p1 selector
roundtrip described above; it is not a complete recovery route. The official
Windows/Cloner path is only vendor-documented and remains unverified on this
device.

Separately, the original Stock F005 image is preserved and the running Mainline
MCU can now be reset into the surviving Creality bootloader and returned to its
unchanged Mainline application. That no-write roundtrip is
**QUALIFIED ON DEVICE**. Writing and starting the original Stock F005 image through that bootloader
was subsequently completed successfully on 2026-08-27. It does not qualify the
current full software-only Fre3nder-B -> Stock handoff: on 2026-08-29, Stock
Klipper reported `Lost communication with MCU 'mcu'` and timed out before
`Printer is ready`, so that path **REQUIRES QUALIFICATION**. The manual
power-cycle Stock recovery reached `Printer is ready` twice on the reference
device and is **QUALIFIED ON DEVICE (2/2)**.

Gate 1 is **SATISFIED** by the current evidence review. Recovery execution remains
**DOCUMENTED / NOT PERSONALLY REHEARSED**; destructive recovery, first boot, and
actual identity preservation remain unverified and are not claimed as guaranteed.

## WARNING / RED ZONE

Further work may intentionally modify the bootloader, partitions, kernel,
RootFS, MCU firmware, or other persistent contents. Because complete recovery has
not been personally rehearsed on this device, the printer may become unbootable,
require additional hardware intervention, or be permanently damaged or
destroyed. Backups reduce risk but do not prove a working restore. This warning
does not itself authorize a write or flash operation.
