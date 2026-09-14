# Changelog

This file records the user-visible and architecturally relevant changes of
Fre3nder releases. Technical documentation describes the current system rather
than preserving release-specific acceptance checklists.

## 2026.2 - Unreleased

The usable-system scope is implemented and hardware-qualified on the
investigated reference system. The integrated release-mode `2026.2.a` candidate
at commit `885706f121c76190d6d74177ffac3895cd58c78d` qualified the core system;
later current-main testing completed the persistence failure cases, Fluidd
control and uninstall, and the redistributable WLAN source path. Those later
results are not retroactive properties of the historical candidate artifacts.
A final release-mode build from the reviewed current source and the `2026.2`
release tag are still pending.

### Added

- Added an immutable SquashFS plus writable OverlayFS runtime, with separate
  system persistence and `/home` userdata and volatile `/run` and `/tmp`.
  Missing or invalid persistence now fails closed into an immutable diagnostic
  boot without formatting, repair, or fallback to Stock data partitions. The
  normal, reset, recovery, and all four missing/invalid system and userdata
  cases are hardware-qualified.
- Added a marker-authorized system-overlay reset that preserves `/home`, plus a
  verified recovery path that recreates the persistence filesystems and restores
  userdata from backup.
- Added the generic `fre3nder install|uninstall|status|restore` managed-
  application layer and a frontend-neutral web service. Fluidd is the qualified
  reference frontend; installation, explicit restore, reboot persistence,
  printer control, and uninstall are hardware-qualified. Compatible alternative
  frontends remain possible but were not part of this release's hardware
  qualification.
- Added a pinned Moonraker baseline with its runtime dependencies, API and
  WebSocket integration, persistent configuration, and recovery after a system-
  overlay reset. The integrated lifecycle is hardware-qualified.
- Added the native GuppyScreen local interface with framebuffer output, touch,
  backlight control, standby/wake, touch feedback, and Moonraker integration. A
  real print started from GuppyScreen completed successfully on the reference
  system.
- Added qualified UVC camera integration through the frontend-neutral web path.
- Added the Linux host-MCU and onboard ADXL345 path, including hardware-qualified
  input shaping, and an OrcaSlicer profile for the Ender-3 V3 KE.

### Changed

- Split the X2000 build into dedicated Buildroot, kernel, Moonraker, and
  GuppyScreen component builders under the top-level release orchestrator.
  Component artifacts and final composition carry reproducible identities,
  hashes, and provenance and are validated before consumption.
- Moved the RootFS to Buildroot 2025.02 LTS and qualified the concrete
  Buildroot 2025.02.18 userspace and kernel toolchains as part of the integrated
  candidate.
- Replaced the proprietary Stock `mcu_util` dependency in the Fre3nder path with
  the open F005 transition implementation while keeping MCU flashing separate
  from normal build and deployment.
- Replaced the WLAN BYOF input with redistributable linux-firmware `20250211`
  firmware and CLM data plus the unmodified BSD-3-Clause Radxa AZW372 NVRAM.
  The exact three inputs and their resulting kernel and RootFS integration are
  hardware-qualified together for WLAN; Bluetooth is not qualified.
- Relicensed project-authored productive Fre3nder material to
  `AGPL-3.0-or-later`. Project-authored research material remains MIT-licensed,
  and third-party material retains its own license.

## 2026.1 - 2026-08-29

First printable networked open-host release.

### Added

- Established the reproducible X2000 Linux host on the Ingenic 6.6.18-rt23
  kernel basis with an immutable SquashFS RootFS and an A/B-compatible Slot-B
  development path.
- Integrated upstream Klipper with the open, hardware-qualified F005 MCU port
  and configuration. The first complete Fre3nder print without Stock Klippy
  finished successfully on the investigated reference system.
- Added the bounded A/B selector and early rollback path while preserving the
  Stock slots. Manual power-cycle recovery was qualified; uninterrupted
  software-only Fre3nder-to-Stock handoff remained later work.
- Added the production administrative network path with USB provisioning,
  Ethernet-first operation, SDIO WLAN fallback, public-key Dropbear SSH,
  interactive shell access, persistent host identity, and access after a normal
  Fre3nder reboot.
- Completed the Point-of-Return foundations: validated backups, protected
  device identity and factory data, documented eMMC boot configuration, archived
  recovery material, and a documented external return-to-Stock route. The full
  external recovery procedure remained execution-unverified.

The untagged `2026.1.a` milestone on 2026-08-23 first demonstrated the open
X2000 Slot-B boot, RootFS, WLAN, and SSH path. It was a development milestone,
not a separate final release.
