# Open X2000 host architecture

## Decision

Phase 3 uses the selected target: **Fre3nder B as a complete open X2000 host**.
The target is an embedded appliance, not a general-purpose Linux distribution.
Its A/B design preserves Stock A as an untouched Creality vendor fallback
domain; Fre3nder B replaces the Creality Linux/application stack only while it
is selected.

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
        +-- V4L2 camera -> open streamer
        +-- upstream Linux Host MCU -> ADXL345 / Input Shaper
        `-- controlled image-based updates
```

This target does not require preserving Creality UI services, WebRTC,
AI middleware, `cam_app`, or proprietary binary extensions. It requires their
needed printer-facing functions to have open replacements.

## Status of the architecture

- `PROVEN`: a reference-system observation or offline capture directly
  establishes the component/interface.
- `TARGET`: selected architecture, not yet implemented.
- `LIKELY`: an open path is technically indicated but needs Phase-3.2 kernel/DT
  feasibility evidence.
- `UNKNOWN`: required property not established.
- `DEFERRED`: not needed to make the Phase-3.2 decision now.

| Area | Status | Architecture consequence |
| --- | --- | --- |
| Main F005 path | PROVEN | Mainline Klipper communicates with the investigated F005 over `/dev/ttyS1` at 230400. Retain this contract; do not redesign it in Phase 3. |
| X2000 CPU, RAM, eMMC | PROVEN | An X2000 Linux appliance is the hardware target; Phase 3.2 selected the Ingenic Linux 6.6.18 X2000 SDK source basis. |
| Lower boot chain | LIKELY | Preserve the existing pre-p1 loader boundary unless evidence requires replacement. Exact normal BootROM/SPL/U-Boot handoff remains UNKNOWN. |
| LTS kernel + DT | PROVEN | The pinned Ingenic Linux 6.6.18 X2000 SDK mirror, project KE DTS, and minimal patch series boot the bounded `2026.1.a` Slot-B baseline. Long-term maintenance and peripheral completion remain separate work. |
| Minimal Buildroot root filesystem | PROVEN BASE / PARTIALLY HARDWARE QUALIFIED PERSISTENCE | The bounded `2026.1.a` system runs its immutable Buildroot SquashFS RootFS from p8. The former single-volume `/persist` Development adapter was qualified through a normal Develop-B -> Develop-B reboot and is now superseded. The `2026.2` implementation resolves separate external ext4 filesystems labelled `FRE3NDERSYS` and `FRE3NDERHOME`, builds a writable root OverlayFS, exposes the immutable lower at `/rom`, and mounts userdata at `/home`. Normal persistence and the marker-authorized system reset with retained `/home` are qualified on the reference system; explicit missing or invalid backend cases remain open. |
| Network/SSH | PROVEN | The Production S20 -> S40 -> S50 path is hardware-validated on the investigated reference system: USB provisioning, CDC-NCM Ethernet-first operation, WLAN fallback, public-key login, and interactive SSH PTY allocation and shell operation all succeeded. The image embeds no user credentials. A persistent Dropbear host key was reused over a normal Develop-B -> Develop-B reboot and verified as both Dropbear's configured key and the key presented over SSH; SSH became available again afterward. This qualification is limited to the Development USB-adapter path; runtime/hotplug failover remains open. |
| Moonraker | OFFLINE IMPLEMENTED / RUNTIME PARTIALLY PROVEN | The RootFS build stages the pinned stable Git checkout under `/opt/fre3nder/moonraker` and a system-site-packages-enabled environment under `/opt/fre3nder/moonraker-env`. Persistent state remains in `/home`; PID/status/socket remain in `/run`. The pinned runtime and Klippy/API behavior are hardware-qualified, while the newly built-in baseline, self-update dependency lifecycle, S61 post-update restart, and OverlayFS recovery remain unqualified. |
| Display/touch | LIKELY / PARTIAL OFFLINE CONFIRMATION | The NS2009/I2C endpoint and stock framebuffers are observed. The project DTS now has a minimal GPC22 active-high `gpio-backlight` node without `default-on`, **OFFLINE IMPLEMENTED** and **OFFLINE CONFIRMED** in the generated DTB. Physical backlight-off, framebuffer clearing, panel output, and touch acceptance remain open. |
| Camera | LIKELY | The reference camera is USB UVC using `uvcvideo`; standard V4L2 plus an open streamer remains the target, with later reference-board acceptance of the selected SDK USB path. |
| Linux Host MCU / ADXL345 | INPUT SHAPING QUALIFIED ON DEVICE | On the investigated reference device, the complete chain through `/dev/spidev2.0`, Linux-process MCU, NumPy, `SHAPER_CALIBRATE` X/Y, the extended 100-Hz X sweep, and `SAVE_CONFIG` succeeded. The reference baseline is MZV at 62.4 Hz for X and MZV at 39.8 Hz for Y, with conservative `max_accel: 4500`; other printers require independent calibration. |
| BL24C16F | DEFERRED | It is not evidenced as necessary for the required open-host/ADXL path. Preserve rather than modify its data. |
| Update/rollback model | PROVEN / HARDWARE VALIDATED | The automatic p1 one-shot model proved bounded Slot-B boot and Stock-A return for `2026.1.a`; it remains the safety/regression path. The separate host-side operator tool is hardware-validated for explicit p1 A -> B and B -> A selector changes and has no automatic B -> A fallback. Normal Develop-B -> Develop-B reboot persistence is qualified on the investigated reference system. An unreachable Develop system relies on the qualified external Ingenic USB / RAM-U-Boot p1 rollback. Persistent updates remain unqualified. |
| Stock return | QUALIFIED PARTIAL / SOFTWARE-ONLY HANDOFF OPEN | Gate 1 is satisfied by the current evidence review. The documented full-device vendor recovery process remains execution-unverified and is not a guaranteed restore on the reference device. Fre3nder `FIRMWARE_RESTART` -> UART release -> exact bootloader identity is **QUALIFIED ON DEVICE**. The 2026-08-29 software-only handoff reached Stock A but ended with `Lost communication with MCU 'mcu'` and timeouts before ready, so it **REQUIRES QUALIFICATION**. Manual power-cycle recovery to Stock `Printer is ready` is **QUALIFIED ON DEVICE (2/2)** on the reference device. |

## Stock and Fre3nder MCU mode switching

The target is **Stock/Fre3nder dual-mode operation**: Stock A is the preserved
vendor fallback domain and Fre3nder B is the project-owned domain. The F005 is
not A/B; its single active application must match the selected mode. A release
must not require a Fre3nder modification or hook in Stock A. Fre3nder B now
owns a qualified passive-UART Klippy/runtime leg, exact Stock-MCU ->
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

During the 2026-09-11 Host-MCU/ADXL qualification, the persistent
`printer.cfg` already existed, so the new RootFS-default sections were copied
into it for the controlled test. This is expected seed-once behavior, not an
ADXL or deployment failure. Automatic configuration migration remains a
separate product decision.

The previously observed `S13mcu_update` whiteout, disabled copy, and one-shot
marker were historical bring-up residue, not the intended persistence design.
Their targeted cleanup is evidence about that specific old state; direct
editing of a mounted OverlayFS upper directory is not a general recovery
procedure.

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
- claim stock recovery, rollback, or identity preservation has been validated.

The stock GPT/update arrangement is evidence about constraints, not an adopted
open update design. A later implementation may reserve stock structures and use
a separate update strategy, but Phase 3.1 does not select storage ownership.

## Smallest next phases

1. **3.1 Hardware + Boot Contract — complete.** Record only the REQUIRED
   interfaces and compatibility constraints in
   [x2000-hardware-contract.md](x2000-hardware-contract.md).
2. **3.2 Kernel / Device-Tree feasibility — complete.** The bounded result is
   [x2000-kernel-dt-feasibility.md](../research/docs/x2000-kernel-dt-feasibility.md): the pinned
   Ingenic Linux 6.6.18 X2000 SDK mirror is selected over a large upstream-6.12
   forward port. NebulaOS is KE prior art only, not an adopted distribution.
3. **3.3 A/B bring-up qualification — complete for `2026.1.a`.** The selected
   Slot-B kernel/DT/rootfs, bounded network administration path, and one-shot
   return-to-Stock-A sequence are proven. The RAM-only prototype remains a
   deferred alternative.
4. **Separate manual Slot-B selection — HARDWARE VALIDATED.** The host-side
   `scripts/x2000-ab` tool intentionally has no
   automatic B -> A fallback and leaves the one-shot paths unchanged.
   Explicit p1 A -> B and B -> A selector changes are hardware-validated.
   Normal Develop-B -> Develop-B reboot persistence is qualified on the
   investigated reference system; loss of Mainline reachability remains an
   external-p1-rollback recovery case.
5. **3.4 Minimal Buildroot appliance — Production base hardware-validated.**
   The immutable USB-provisioned Ethernet-first/WLAN-fallback and public-key SSH
   path is implemented and proven on the investigated reference system. The
   RootFS deployment orchestrator and Development persistent SSH identity across
   a normal Develop-B -> Develop-B reboot are also hardware-validated. Broader
   persistent configuration remains later work.
6. **3.5 Dual-mode MCU lifecycle — MCU transitions qualified, coordinated host
   roundtrip open.** Fre3nder identity gating, the exact Stock-MCU ->
   Fre3nder-MCU transition, passive UART release, exact bootloader identity, and
   the project-controlled Stock image update are qualified on device. Automatic
   shutdown clear is **NOT IMPLEMENTED**; the original shutdown reason after a
   host reboot and the preferred uninterrupted handoff remain **REQUIRES
   QUALIFICATION**.
7. **3.6 Klipper host integration and printer validation — QUALIFIED ON DEVICE.** Upstream Klippy
   with the passive UART patch, exact 88-command dictionary, complete
   configuration, ClockSync, target-zero heater/ADC telemetry, S60 gate, and
   writable input PTY are qualified on device. The 2026-08-29 complete
   Fre3nder-B print is also **QUALIFIED ON DEVICE**, making `2026.1`
   **FUNCTIONALLY ACHIEVED**. The loopback Moonraker runtime/service chain is
   partially qualified; its RootFS baseline and update lifecycle remain open,
   as does user-facing UI work.
8. **3.7 Complete dual-mode roundtrip validation.** Qualify the Stock <->
   Fre3nder roundtrip with Stock A unchanged.
9. **3.8 Remaining peripheral and product integration.** Integrate display/touch,
   camera, the open Web UI, touchscreen UI, and camera streamer. Moonraker
   self-update, post-update S61 restart, overlay recovery, and LAN-facing
   product configuration remain part of product integration.
   SDIO WLAN itself is
   already proven by `2026.1.a`; production network lifecycle work belongs to
   the appliance/network path above rather than to remaining peripheral
   bring-up.
10. **3.9 Persistent deployment / update model.** Design and validate persistence,
   image activation, rollback, and configuration migration only after the
   preceding non-persistent result.

Display/touch, camera, Moonraker update completion, and the user-facing UI stack
remain later feature/product-integration work and are not prerequisites for the
functionally achieved printable networked open-host release `2026.1`.
