# Configuring Fre3nder

The repository contains generic build inputs and a hardware-validated
**reference** printer configuration. On a running Fre3nder system, user
configuration lives primarily under persistent `/home`; an existing user file
is retained when a new RootFS is installed. Values measured on the
investigated F005/GD32F303RET6 printer, including probe offset, PID, mesh,
and input shaping, require independent calibration on another printer.

## Find the setting to change

| Purpose | Runtime path or input | Owner and persistence |
| --- | --- | --- |
| Klipper printer configuration | `/home/fre3nder/printer_data/config/printer.cfg` | Userdata in HOME; seeded once from the RootFS default if missing |
| Moonraker main configuration | `/home/fre3nder/printer_data/config/moonraker.conf` | Userdata in HOME; seeded once, existing file retained |
| Fre3nder Moonraker fragments | `/home/fre3nder/printer_data/config/fre3nder/*.conf` | Platform/app fragments in HOME; main config needs `[include fre3nder/*.conf]` |
| Fre3nderScreen settings and touch calibration | `/home/fre3nder/.fre3nder/fre3nderscreen/fre3nderscreen.json` | Userdata in HOME; seeded once, then retained; obsolete GuppyScreen configuration is not imported |
| Web frontend selection and app intent | `/home/fre3nder/.fre3nder/frontend/active` and `.fre3nder/services/` | Userdata in HOME; managed through `fre3nder app` |
| SSH host identity | `/home/fre3nder/.fre3nder/ssh/` | Persistent host identity when persistent root is active |
| WLAN and SSH boot provisioning | FAT32 USB root: `wpa_supplicant.conf`, `authorized_keys`, `enable_ssh` | Boot-local inputs copied to volatile `/run`; not baked into a build |
| System code and application payloads | `/opt`, `/usr`, and the writable SYS overlay | Reconstructible system state; reset exposes the immutable RootFS baseline |

The logical HOME/SYS roles and current external ext4 backends are specified in
[storage layout](storage-layout.md). `FRE3NDERHOME` backs `/home`;
`FRE3NDERSYS` backs the writable system OverlayFS. Internal Stock p9/p10 are
not current Fre3nder persistence backends. `/run` and `/tmp` are volatile.

## Configure the printer

1. Start from the installed `printer.cfg` and compare it with the current
   tracked reference
   [`printer-f005-mainline.cfg`](../configs/klipper-f005/printer-f005-mainline.cfg).
   The RootFS default seeds only a missing file; an update does not merge new
   sections into an existing persistent file.
2. Confirm board identity and pin mapping against the
   [F005 pin matrix](f005-pin-matrix.md) before changing pins, motor directions,
   heaters, fans, probe, or the `[mcu]` serial path. The current F005 host
   path is passive `/dev/ttyS1` at 230400 baud. Normal Klippy starts only after
   exact Fre3nder MCU identity classification; a Stock or unknown MCU leaves
   it stopped.
3. Calibrate probe/Z offset, heater PID, bed mesh, and resonance/input-shaper
   values on the actual printer. The reference `z_offset: 2.180` and shaper
   baseline are evidence for one investigated unit, not factory defaults for
   every Ender-3 V3 KE. Preserve a copy of valuable configuration before
   changing it; [backup](backup.md) covers HOME and SYS archives.
4. Validate the edited configuration through Klipper/Moonraker before relying
   on motion or heat. If a new RootFS added default sections, merge only the
   required sections manually into the persistent file; inspect the relevant
   release and [F005 configuration](f005-mainline-config.md) documentation.

The OrcaSlicer preset and its import instructions are in
[`configs/orcaslicer/README.md`](../configs/orcaslicer/README.md). It inherits
OrcaSlicer's built-in KE profile and supplies Fre3nder-specific G-code and
motion-limit overrides.

## Configure services and access

Moonraker's main configuration must include the exact line
`[include fre3nder/*.conf]` for platform and managed-app fragments to load.
Newly seeded defaults include it; older persistent files are **not** rewritten.
The [managed-app guide](apps.md#moonraker-configuration-and-update-ownership)
explains the one-time edit, Fluidd ownership, and service restart.
[Moonraker runtime](moonraker-bringup-current-state.md) describes its baseline
and the current updater limit.

Fre3nderScreen uses its own persistent JSON settings, while framebuffer, NS2009
input discovery, and backlight are platform hardware paths. See
[Fre3nderScreen integration](fre3nderscreen.md) for runtime behavior and
[display/touch hardware](x2000-display-touch.md) for physical interfaces.

The boot-local FAT32 provisioning path can provide WLAN configuration and
public-key SSH access without storing credentials in the repository. The
`enable_ssh` marker is separate from `authorized_keys`; WLAN setup alone does
not enable SSH. Existing provisioned inputs are copied under `/run` for that
boot. The [X2000 architecture](x2000-open-host-architecture.md#provisioning-and-administrative-access)
explains the access boundary. Keep credentials and device-specific values out
of public documentation and build artifacts.

Source identities and build-time versions live in
[`configs/x2000/sources.json`](../configs/x2000/sources.json); they are build
inputs, not user calibration files. Do not alter the F005 firmware manifest,
boot selector, partition layout, factory identity, or the RootFS trust anchor
as a routine configuration change. Refer to [installation](installation.md),
[storage](storage-layout.md), and [recovery](recovery.md) for those boundaries.
