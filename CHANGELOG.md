# Changelog

This file records the user-visible and architecturally relevant changes of
Fre3nder releases. Technical documentation describes the current system rather
than preserving release-specific acceptance checklists.

## 2026.3 - 2026-09-20

Fre3nder 2026.3 completes the transition away from the vendor kernel. The
release scope ID is `independent-kernel-stack`; its final tag points to commit
`883010c7bca32aef165dd6b7fe1c3892ce025b4b`.
The released X2000 kernel starts from official Linux stable `v6.6.157` and
applies an ordered, provenance-separated five-patch Fre3nder X2000 hardware
support series. Applied in order, that series reproduces the exact
`40d8b5cee4341505c12373e9bb1386e80241f0d6` source tree already exercised as
`6.6.157-fre3nder`.

User-facing printer behavior is intentionally largely unchanged. The release
changes the kernel ownership and maintenance boundary.

The `2026.3` hardware qualification is scoped to the new kernel host baseline
and the exercised boot, network, and SSH path. It does not by itself re-qualify
previously qualified display/touch, camera, ADXL/Input Shaper, GuppyScreen, or
complete-print flows on `6.6.157-fre3nder`.

### Changed

- Replaced the productive Ingenic/Creality-derived `6.6.18-rt23` kernel basis
  with official Linux stable `v6.6.157` plus the ordered Fre3nder X2000
  hardware-support patch series. Historical Ingenic kernel/SDK material remains
  migration provenance only and is no longer a productive kernel source.
- Removed the PREEMPT_RT/RT23 dependency. The resulting
  `6.6.157-fre3nder` host baseline was exercised on the investigated reference
  Ender-3 V3 KE through kernel boot, network, and SSH. The qualified deployment
  updated p6 only, reused the existing Fre3nder p8, left Stock p5 and p7
  unchanged, and retained working administrative access.
- Split the retained X2000 support by provenance into explicit platform,
  display, touch, WLAN, and Fre3nder board-integration layers while preserving
  the exact previously qualified result tree.
- Made the kernel baseline independently maintainable from official Linux
  stable so future `6.6.y` updates can be ported incrementally against the
  documented Fre3nder patch series.

## 2026.2 - 2026-09-14

The usable-system scope is implemented and hardware-qualified on the
investigated reference system. The integrated release-mode `2026.2.a` candidate
at commit `885706f121c76190d6d74177ffac3895cd58c78d` qualified the core system;
later current-main testing completed the persistence failure cases, Fluidd
control and uninstall, and the redistributable WLAN source path. Those later
results are not retroactive properties of the historical candidate artifacts.
The release scope ID is `usable-system`.
The final `2026.2` release was built, validated, and tagged from commit
`fcabe6089dba72ded7c256b8550ea65bc7a34ec6`.

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
The reference-system first-print scope was recorded as
**`2026.1 FUNCTIONALLY ACHIEVED: 2026-08-29.`** before the final tag.
The release scope ID is `first-printable-networked-open-host`; the final tag
points to commit `27194a4f583243d87eb0c01dd3df5596e548e536`. Its scope
required an open-host boot, functioning CPU/SMP and filesystem, at least one
qualified administrative network path with stable IP configuration, reliable
SSH administration and persistent SSH host identity, network and SSH usable
after normal reboot, and a real Mainline-F005 print without Stock Klippy.
Moonraker, Mainsail, local display/touch, camera, ADXL/Input Shaper,
Bluetooth, consumer installation, automatic updates, and a
hardware-qualified Stock return were
outside that release scope.

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
