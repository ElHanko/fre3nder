# Fre3nder roadmap

Fre3nder `2026.1` is achieved on the investigated reference system. It
establishes the reproducible open X2000 host, upstream Klipper operation,
network administration, persistent host identity, a complete Mainline-F005
print, qualified open F005 transitions, and qualified installation of the
current kernel/RootFS pair on Slot B.

The next product milestone is Fre3nder `2026.2`, the first deliberately
user-facing and normally operable system.

Persistent or hardware-changing operations remain explicit WARNING / RED ZONE
work under `AGENTS.md`.

## Current product baseline

- Open X2000 host with read-only SquashFS RootFS and A/B-compatible Stock
  return path.
- Upstream Klipper host with the qualified F005 UART integration.
- Hardware-validated F005 mainline configuration and complete Fre3nder-B print
  on the investigated reference system.
- Hardware-validated Fre3nder-B persistence, SSH access, and bounded selector
  tooling; no credentials or vendor binaries are embedded in the image.
- Open bidirectional F005 MCU transitions are qualified on the investigated
  reference system.
- The proprietary Stock `mcu_util` dependency has been removed from the
  Fre3nder product path and replaced by the open F005 implementation.
- Standardized X2000 and F005 build/deployment interfaces exist.
- The standardized F005 build path is deterministically reproducible and
  OFFLINE CONFIRMED.
- Installation of a complete current-main Fre3nder kernel and RootFS pair on
  Slot B is qualified on the investigated reference system.

## Next release target - 2026.2 Usable System

The goal of `2026.2` is to turn the proven open printing platform into a system
that can be configured, operated, and used locally without requiring SSH as
the normal user interface. Application update automation may follow after this
release; the ownership boundary for such updates remains part of `2026.2`.

The release-level requirements and acceptance criteria are defined in
[`requirements-2026.2.md`](requirements-2026.2.md).

### Main path

1. Define and qualify the filesystem, persistence, and volatile-runtime
   contract: an immutable lower filesystem at `/rom`, a writable system overlay
   at `/`, persistent userdata at `/home`, and tmpfs-backed `/run` and `/tmp`.

2. Establish the application persistence contract: qualified baselines may
   reside in the immutable RootFS, separately installed application payloads
   may persist in the writable system overlay, `/home` owns upgrade-persistent
   desired state and user state, and a system-overlay reset restores the RootFS
   baseline while an explicit install/restore action reconstructs a separately
   installed application.

3. Integrate the qualified stable Moonraker baseline and Python environment in
   the RootFS, with persistent configuration/state and a stable API boundary
   above Klipper. Qualify that baseline and state across normal reboot and the
   defined system-overlay reset path.

4. Define and enforce update ownership: current lifecycle actions and future
   application-level updaters may manage applications and user interfaces, but
   must not replace Fre3nder-controlled kernel, RootFS, base Klipper, A/B state,
   or F005 firmware and must not manage system packages.

5. Refactor the X2000 build into independently maintainable component builders
   before adding further product components. Separate the current RootFS build
   into a generic `build-x2000-buildroot` RootFS assembler and dedicated
   component builders such as `build-x2000-moonraker`, while keeping
   `build-x2000` as the top-level release orchestrator. Preserve component
   provenance and fail-closed artifact validation so later components such as
   the local display stack can follow the same model.

6. Establish the generic managed-application interface and qualify Fluidd as
   its `2026.2` reference application. Installation, status, explicit restore,
   and removal must remain independent of the kernel and RootFS build.

7. Establish a frontend-neutral persistent web-UI layer. Qualify Fluidd as the
   first reference frontend while keeping alternative frontends such as
   Mainsail installable without rebuilding the RootFS.

8. Complete the local display stack with GuppyScreen as the native Core-UI.
   The exact current pin is persistently deployed and hardware-qualified on the
   reference system: startup, fbdev output, dynamic evdev discovery, physical
   rotation, calibrated touch mapping, automatic backlight startup, 60-second
   standby/wake, touch-beep feedback, and a complete real print initiated
   through GuppyScreen are demonstrated.

9. Perform integrated `2026.2` qualification across normal boot, persistence,
   Klipper, Moonraker, managed-application lifecycle, Fluidd through the
   frontend-neutral network-UI layer, local display/touch operation, reboot,
   and a real print.

## Later product work

The following work remains valuable but is not inherently part of the
`2026.2` usable-system milestone unless it becomes necessary for a release
requirement:

- runtime and hotplug network failover beyond the currently qualified boot-time
  network policy;
- camera support;
- ADXL/input shaping and other non-required peripherals;
- uninterrupted software-only Fre3nder-to-Stock handoff;
- remaining coordinated F005/Stock host-handoff qualification;
- broader hardware and firmware-revision qualification;
- qualification of multiple alternative web frontends;
- OctoApp integration;
- Moonraker, Fluidd, and generic managed-application self-update automation,
  including any required post-update service restart; and
- automatic reconstruction of separately installed applications after a
  system-overlay reset.

## Current qualification boundaries

- software-only Fre3nder -> Stock: **REQUIRES QUALIFICATION**;
- F005-only open Stock -> Fre3nder and Fre3nder -> Stock transitions:
  **QUALIFIED ON DEVICE**;
- complete current-main Fre3nder kernel-plus-RootFS installation on the
  investigated reference system: **QUALIFIED ON DEVICE**;
- deterministic standardized F005 build: **OFFLINE CONFIRMED**;
- newly rebuilt deterministic F005 candidate: **REQUIRES HARDWARE
  QUALIFICATION BEFORE PROMOTION**;
- product hostname `fre3nder`: **QUALIFIED ON DEVICE**;
- power-cycle Stock recovery: **QUALIFIED ON DEVICE (2/2)**;
- physical PC22 backlight effect: **QUALIFIED ON DEVICE**;
- integrated display/backlight/touch hardware path:
  **QUALIFIED ON DEVICE**; framebuffer output, panel colors, NS2009 I2C
  enumeration, PC15 pendown, X/Y input events, and the GuppyScreen core local
  presentation path are demonstrated on the reference system;
- Moonraker Python/runtime dependency bring-up: **QUALIFIED ON DEVICE**;
  the exact pinned source/dependency mix, local HTTP/API behavior, network
  discovery, and ready Klippy UDS connection have been demonstrated on the
  reference system;
- Moonraker RootFS integration:
  **NORMAL AND RECOVERY LIFECYCLE QUALIFIED ON DEVICE**; the fixed pinned Git
  checkout, Python environment, RootFS dependencies, S61 fixed-path launch,
  Klippy UDS connection, persistent configuration, LAN API path, and strict
  update-ownership boundary are demonstrated. The final `2026.2.a` candidate
  additionally qualified system-overlay baseline recovery and
  Fre3nder-to-Fre3nder reboot state retention;
- frontend-neutral web-UI layer: **FLUIDD REFERENCE PATH QUALIFIED ON
  DEVICE**; selected Fluidd payload delivery, LAN HTTP, Moonraker HTTP API,
  WebSocket forwarding, active-frontend persistence, and recovery after an
  explicit payload restore are demonstrated on the reference system;
- managed-application interface and Fluidd lifecycle: **RESTORE AND REBOOT
  HARDWARE QUALIFIED / FLUIDD UI CONTROL OPEN**; initial install, selection,
  service integration, network use, system-overlay reconstruction, and
  normal-reboot persistence are demonstrated. Explicit normal printer control
  through the Fluidd UI remains open;
- GuppyScreen local Core-UI: **HARDWARE QUALIFIED ON DEVICE**; the exact current
  pin is persistently deployed and demonstrates startup, fbdev output, NS2009
  evdev input, `display_rotate: 1`, calibrated touch mapping, automatic
  backlight startup, 60-second standby/wake, `pwm-beeper` touch feedback, and a
  successful real print initiated through GuppyScreen;
- integrated `2026.2.a` usable-system candidate: **HARDWARE QUALIFIED ON
  DEVICE**; kernel/RootFS deployment, system-overlay recovery, persistent
  configuration, Klipper/Moonraker/F005 operation, Fluidd LAN availability,
  GuppyScreen printing, and Fre3nder-to-Fre3nder reboot persistence passed on
  the investigated reference system. See `docs/qualification-2026.2.md`.

## Mandatory gates

Gate 1, **POINT OF RETURN**, is satisfied by the current evidence review. Its
minimum evidence remains a validated backup, protected device identity and
factory data, documented eMMC boot configuration, archived original firmware
material, a recovery route independent of normal Linux boot, and a documented
route back to Stock. The official recovery route is still
execution-unverified on the reference device; persistent work remains RED ZONE
work.

Gate 2, **CREALITY DELTA UNDERSTOOD**, is satisfied for the required
first-print scope. Required behavior is classified as `UPSTREAM`, `KEEP`,
`REIMPLEMENT`, `DROP`, or `UNKNOWN`; the detailed classification and evidence
remain in [`docs/klipper-stock.md`](klipper-stock.md) and the historical gate
record.

The detailed historical gate record is preserved in
[`research/docs/roadmap-history.md`](../research/docs/roadmap-history.md).
