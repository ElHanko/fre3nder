# Open X2000 host architecture

## Decision

Phase 3 established **Fre3nder B as a complete open X2000 host** while
preserving Stock A as the initial vendor fallback. The target is an embedded
appliance, not a general-purpose Linux distribution.

The current update architecture transitions from that development arrangement
to true Fre3nder A/B operation: Slot A and Slot B are equivalent Fre3nder host
slots, and updates are staged into whichever slot is inactive. Stock restoration
remains a documented recovery path rather than permanently reserving one A/B
slot for the vendor system.

```text
X2000 BootROM / stock-compatible lower boot boundary
        |
        v
LTS-oriented Linux kernel + board Device Tree
        |
        v
minimal Buildroot root filesystem
        |
        +-- network and SSH
        +-- upstream Klipper -> /dev/ttyS1 -> Mainline F005
        +-- upstream Moonraker -> open Web UI
        +-- touchscreen UI
        +-- USB UVC -> V4L2 /dev/videoX -> localhost MJPEG streamer
        |              -> Lighttpd /webcam/ -> Moonraker webcam -> Fluidd
        +-- upstream Linux Host MCU -> ADXL345 / Input Shaper
        `-- controlled image-based updates
```

This target does not require preserving Creality UI services, WebRTC,
AI middleware, `cam_app`, or proprietary binary extensions. It requires their
needed printer-facing functions to have open replacements.

## Current qualification boundary

The official-Linux-stable host baseline was qualified on the investigated
reference system for boot, network, and SSH. Earlier reference-device
qualification of the F005 print, persistence, Moonraker, web UI,
GuppyScreen, display/touch, camera, and ADXL paths remains scoped to the
artifacts and runs documented in their subject records; it is not
automatically a rerun on every later kernel. The exact current source and
patch identities are in
[`configs/x2000/sources.json`](../configs/x2000/sources.json). The dated
status table is preserved in
[roadmap history](../research/docs/roadmap-history.md#preserved-x2000-architecture-status-and-phase-3-sequence).

## Stock and Fre3nder MCU mode switching

The original transition used Stock in Slot A and Fre3nder in Slot B. Current
Fre3nder A/B operation may put Fre3nder in either slot. The selector patterns
`STOCK_A` and `DEVELOP_B` identify byte values, not slot payloads.

The F005 itself is not A/B; its single active application must match the host
mode that is being booted. Where Stock is retained, a Fre3nder release must
not require a Fre3nder modification or hook in the Stock host. Fre3nder owns
a qualified passive-UART Klippy/runtime leg, exact Stock-MCU ->
Fre3nder-MCU transition, and bootloader-release leg; the preferred Stock-owned
return path and complete coordinated host roundtrip remain **REQUIRES
QUALIFICATION**. The evidence and boundaries are specified in
[`f005-mcu-switching.md`](f005-mcu-switching.md).

## Persistence ownership boundary

The current Fre3nder implementation uses two manually provisioned external
ext4 backends. `FRE3NDERSYS` supplies the logical system-persistence role;
its normal data payload consists of OverlayFS `upper` and `work`, with the
optional `.fre3nder-reset` boot-control marker as the currently defined
exception. `FRE3NDERHOME` supplies the logical userdata role mounted at `/home`.
The early root code identifies these roles by label and filesystem type and
contains no USB device name or eMMC partition number.

Internal p9 and p10 are future backends for the same logical roles, not the
current implementation. On the investigated Stock system p9 remains the vendor
OverlayFS backing store. This implementation does not mount, format, delete, or
otherwise claim internal p9 or p10.

Within userdata, `/home/fre3nder/printer_data` owns persistent printer-facing
state. The current Klipper integration uses `printer_data/config/printer.cfg`
as its runtime configuration source and `printer_data/logs/klippy.log` as its
persistent log. A missing `printer.cfg` is seeded once from the immutable
`/usr/share/fre3nder/defaults/printer.cfg`; an existing userdata configuration
is not overwritten. Fre3nder-owned device-management metadata is kept separate
under `/home/fre3nder/.fre3nder`, currently including the persistent Dropbear
host identity under `.fre3nder/ssh`. Moonraker code and its Python environment
are system state under `/opt`; only `printer_data` belongs in userdata.

Existing persistent `printer.cfg` files do not receive later RootFS default
sections automatically. The reference-system Host-MCU/ADXL qualification
merged those sections manually; see
[F005 hardware validation](f005-hardware-validation.md#2026-09-11-host-mcuadxl-source-integration).
Automatic configuration migration remains a separate product decision.

## Provisioning and administrative access

Provisioning and privileged administration are separate concerns.

The target release image must not contain user-specific WLAN credentials,
authorized SSH keys, or administrative passwords. Device-specific configuration
is supplied after installation rather than compiled into a per-user image.

The intended long-term Fre3nder provisioning model is:

1. normal network configuration is performed locally through the touchscreen UI;
2. WLAN setup is normal device configuration and does not imply privileged
   administrative access;
3. root/SSH administration is disabled until explicitly enabled by the user;
4. enabling root/SSH requires a clear warning and explicit local confirmation;
5. SSH administration uses public-key authentication rather than remote password
   authentication; and
6. authorized public keys are imported separately from the SSH enable/disable
   state.

A FAT32 USB provisioning medium is an acceptable headless and development path.
It may provide files such as `wpa_supplicant.conf` and `authorized_keys` without
embedding those private inputs in the built image. This path is also intended to
remain useful for development, recovery, and headless administration after a
touchscreen provisioning UI exists.

USB provisioning remains boot-local and copies credentials into volatile
storage under `/run`; it does not silently claim Raspberry-Pi-style first-boot
persistence. When the persistent root is active, Dropbear stores only its host
identity under `/home/fre3nder/.fre3nder/ssh`. The SSH enable marker and imported
authorized keys remain separate boot-local inputs until a later product
configuration flow deliberately owns them.

The touchscreen provisioning UI is a later product-level target and is not a
requirement for final `2026.1`; the headless administrative network path remains
the qualified requirement for that release.

## Required design boundaries

The open image must not, without an explicit separately authorized need:

- alter eFuses, RPMB, boot0/boot1, eMMC hardware boot configuration, factory
  identity data, MAC/serial information, or BootROM recovery access;
- consume stock loader/A-B structures merely because they appear unused;
- depend on a non-documented permanent special boot state; or
- infer a complete Stock return or factory-identity preservation from bounded
  recovery and selector checks.

On the investigated reference system, the external USB/RAM-U-Boot path was
qualified for a bounded p1 selector roundtrip, and manual power-cycle return
reached Stock `Printer is ready` twice. The complete software-only
Fre3nder-to-Stock handoff still requires qualification; the vendor Cloner
restore remains execution-unverified. See [recovery](recovery.md) and its
[reference-system evidence](../research/docs/recovery-current-state.md).

The current Fre3nder A/B update design uses the existing kernel and RootFS slot
pairs. The remaining stock loader, factory-data, and storage boundaries are
specified in [storage layout](storage-layout.md) and
[OTA architecture](ota.md). The original Phase-3.1 decision that deferred
storage ownership is preserved in [roadmap history](../research/docs/roadmap-history.md).

## Historical bring-up

The Phase-3 status table and completed-step sequence are preserved in [roadmap history](../research/docs/roadmap-history.md#preserved-x2000-architecture-status-and-phase-3-sequence). The [current roadmap](roadmap.md) lists open work.
