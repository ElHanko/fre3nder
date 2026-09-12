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
that can be configured, operated, updated at the application level, and used
locally without requiring SSH as the normal user interface.

The release-level requirements and acceptance criteria are defined in
[`requirements-2026.2.md`](requirements-2026.2.md).

### Main path

1. Define and qualify the filesystem, persistence, and volatile-runtime
   contract: an immutable lower filesystem at `/rom`, a writable system overlay
   at `/`, persistent userdata at `/home`, and tmpfs-backed `/run` and `/tmp`.

2. Establish the application persistence contract: qualified baselines may
   reside in the immutable RootFS, application updates may persist in the
   writable system overlay, `/home` owns upgrade-persistent state, and a
   system-overlay reset restores the RootFS baseline.

3. Integrate the qualified stable Moonraker baseline and Python environment in
   the RootFS, with persistent configuration/state and a stable API boundary
   above Klipper. Complete the remaining self-update dependency and S61 restart
   contract.

4. Define and enforce update ownership: Moonraker and application tooling may
   manage applications and user interfaces, but must not replace
   Fre3nder-controlled kernel, RootFS, base Klipper, A/B state, or F005
   firmware and must not manage system packages.

5. Refactor the X2000 build into independently maintainable component builders
   before adding further product components. Separate the current RootFS build
   into a generic `build-x2000-buildroot` RootFS assembler and dedicated
   component builders such as `build-x2000-moonraker`, while keeping
   `build-x2000` as the top-level release orchestrator. Preserve component
   provenance and fail-closed artifact validation so later components such as
   the local display stack can follow the same model.

6. Integrate OctoApp as an independently managed application and
   external-client reference without forcing Moonraker's lifecycle model on it.

7. Establish a frontend-neutral persistent web-UI layer. Qualify Fluidd as the
   first reference frontend while keeping alternative frontends such as
   Mainsail installable without rebuilding the RootFS.

8. Complete the local display stack with GuppyScreen as the native Core-UI.
   Display output, touch input, and backlight control are hardware-qualified on
   the reference system; the reproducible GuppyScreen source integration is at
   its build gate and remains to be built and qualified.

9. Perform integrated `2026.2` qualification across normal boot, persistence,
   Klipper, Moonraker, application management, network UI, OctoApp, local
   display/touch operation, reboot, and a real print.

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
- qualification of multiple alternative web frontends.

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
  enumeration, PC15 pendown, and X/Y input events are demonstrated on the
  reference system; local UI/presentation remains unqualified;
- Moonraker Python/runtime dependency bring-up: **QUALIFIED ON DEVICE**;
  the exact pinned source/dependency mix, local HTTP/API behavior, network
  discovery, and ready Klippy UDS connection have been demonstrated on the
  reference system;
- Moonraker RootFS integration:
  **OFFLINE IMPLEMENTED / RUNTIME PARTIALLY QUALIFIED ON DEVICE**; the fixed
  pinned Git checkout, Python environment, RootFS dependencies, S61 fixed-path
  launch, and strict update-ownership configuration are implemented. The same
  pinned runtime, HTTP/API behavior, Klippy UDS connection, persistent config,
  volatile Moonraker UDS, and S60/S61 boot ordering are qualified on the
  reference system. The newly built-in baseline, self-update dependency
  lifecycle, post-update restart, normal-reboot update persistence, and
  overlay-reset recovery remain to be qualified;
- frontend-neutral web-UI layer: **OFFLINE IMPLEMENTED / PARTIALLY HARDWARE
  QUALIFIED**;
- GuppyScreen local Core-UI: **SOURCE INTEGRATED / BUILD PENDING**; no local-UI
  hardware qualification has started.

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
