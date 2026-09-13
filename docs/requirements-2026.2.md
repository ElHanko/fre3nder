# Fre3nder 2026.2 requirements (Lastenheft)

## Purpose

Fre3nder `2026.2` is the planned **Usable System** release.

`2026.1` established that the investigated Ender-3 V3 KE can boot and print
reliably on the open Fre3nder X2000/Klipper platform. `2026.2` adds the
persistent runtime, application, API, web-UI, and local display layers required
for normal day-to-day operation without SSH being the primary user interface.

This document defines release requirements. Implementation details may evolve
while preserving these requirements.

## Release boundary

A final `2026.2` must provide:

- reliable persistent user and application state;
- clean volatile runtime storage;
- a generic persistent managed-application layer with defined lifecycle and
  recovery ownership;
- Moonraker as the supported API layer;
- a frontend-neutral web-UI mechanism;
- Fluidd as the qualified reference managed application and web frontend;
- local display and touch operation through the native GuppyScreen Core-UI;
- preservation of the established Fre3nder printing and recovery boundaries.

Application self-updates, automatic application reconciliation after a system-
overlay reset, OctoApp, camera support, ADXL/Input Shaping, seamless Stock
handoff, and qualification of every possible web frontend are not release
requirements unless later evidence makes one of them necessary for the
usable-system goal. The update-ownership boundary remains a release requirement
even though application self-update does not.

## REQ-2026.2-001 - Filesystem and persistence contract

Status: **OFFLINE IMPLEMENTED / PARTIALLY HARDWARE QUALIFIED**

Fre3nder shall use three logical filesystem roles independent of concrete device
names or partition numbers:

- an immutable SquashFS RootFS as the read-only OverlayFS lower layer;
- system persistence whose normal payload consists of the OverlayFS
  `upper` and `work` directories, with only explicitly defined boot-control
  metadata such as the authorized reset marker outside those directories; and
- userdata persistence mounted at `/home`.

The current external Development backend resolves the system-persistence role
from the unique ext4 filesystem labelled `FRE3NDERSYS` and the userdata role
from the unique ext4 filesystem labelled `FRE3NDERHOME`. Future internal
backends may assign these roles to p9 and p10 respectively, but the root setup
shall not depend on those partition numbers.

During a normal boot, `/` shall be the writable OverlayFS, `/rom` shall expose
the unchanged immutable lower filesystem, and `/home` shall expose userdata
persistence. System paths including `/etc`, `/opt`, `/usr`, and `/var` are
therefore retained across a normal reboot but intentionally discarded when
system persistence is reset for a firmware upgrade. Upgrade-persistent user and
desired application state belong under `/home`.

Upgrade-persistent printer configuration and Klipper logs are userdata. The
current Klipper integration uses
`/home/fre3nder/printer_data/config/printer.cfg` as its runtime configuration
source and `/home/fre3nder/printer_data/logs/klippy.log` for its persistent log.
The immutable system supplies
`/usr/share/fre3nder/defaults/printer.cfg` only as an initial default: it may
seed a missing userdata configuration but shall never overwrite an existing
userdata `printer.cfg`.

At minimum:

- `/run` shall provide volatile boot-session runtime state;
- `/tmp` shall provide volatile temporary storage;
- compatibility paths such as `/var/run` and `/var/lock` shall have defined
  writable behavior;
- `/var/tmp`, logs, and caches shall each have an explicit persistence policy;
- `/var/run` and `/var/lock` shall resolve to `/run` locations while `/var`
  itself remains normal system state in the OverlayFS;
- normal services shall not require writes to the SquashFS lower filesystem;
- the writable root shall be activated only after both persistence roles have
  been uniquely identified as ext4 and mounted successfully;
- unavailable, invalid, or ambiguous persistence shall retain the immutable
  root in a degraded diagnostic boot, without a RAM upper or `/home` fallback;
- persistence-dependent services shall not start in that degraded boot; and
- boot shall never run automatic filesystem repair or formatting as a response
  to a persistence error.

System persistence may be reset only when its filesystem is uniquely identified,
successfully mounted, and contains the explicit `RESET_ON_NEXT_BOOT` marker.
The reset discards and recreates only `upper` and `work`; an interrupted reset is
safe to repeat while the marker remains present. A mount or identification error
does not authorize deletion.

Acceptance requires offline validation followed by qualification of normal
reboot persistence, a marker-authorized system reset with `/home` retained, and
degraded boots for missing or invalid system and userdata backends.

### Hardware qualification status

The external Development persistence backend has been partially qualified on
the reference device.

Demonstrated on real hardware:

- successful activation of the writable OverlayFS root using `FRE3NDERSYS`;
- successful direct mounting of `FRE3NDERHOME` at `/home`;
- `/rom` remaining the immutable read-only SquashFS lower filesystem;
- persistence of normal system changes across a Fre3nder-to-Fre3nder reboot;
- persistence of userdata under `/home` across the same reboot;
- reuse of the persistent Dropbear host identity from `/home`;
- fail-closed degraded boot when persistence activation cannot be completed;
- continued diagnostic SSH availability in that degraded state; and
- no fallback to or mounting of Stock p9/p10.

The marker-authorized system-persistence reset with `/home` retained is now
qualified on the reference device. Explicit missing or invalid system- and
userdata-backend cases remain to be qualified before REQ-2026.2-001 is
complete.

## REQ-2026.2-002 - Application software and persistence

Status: **OFFLINE IMPLEMENTED / PARTIALLY HARDWARE QUALIFIED**

Fre3nder shall clearly separate reconstructible application software from
upgrade-persistent configuration and user state. A platform RootFS may contain
a qualified application baseline. Separately installed application software
belongs in the system OverlayFS, while desired state and other data that must
survive a platform replacement or system-overlay reset belong under `/home`.

The application lifecycle shall provide:

- deterministic startup through a Fre3nder-controlled service interface;
- the generic `fre3nder {install|uninstall|status|restore} <app>` management
  interface for separately installed applications;
- normal-reboot persistence for application software in the system OverlayFS;
- recovery of any qualified immutable application baseline when the system
  overlay is reset;
- retention of the application's `/home` state across that reset;
- an explicit install or restore path for a separately installed application
  after its reconstructible system-overlay payload has been reset; and
- defined failure behavior when required application software or state is
  unavailable.

Additional applications may be independently installable when their lifecycle
requires it. This requirement does not mandate one universal package manager,
version resolver, or multi-version activation mechanism for every application.

The OverlayFS and separate `/home` roles, marker-authorized system reset,
service gating, generic application dispatcher, and explicit Fluidd
install/restore/remove lifecycle are implemented. The persistence/reset
behavior is partially qualified on the reference system, and the Moonraker
baseline is integrated into the built and deployed RootFS path. Normal-reboot
persistence and explicit restore of the separately installed Fluidd payload
remain to be qualified before this requirement is complete.

Automatic desired-state reconciliation after an overlay reset and application
self-update are later lifecycle improvements, not `2026.2` acceptance criteria.

## REQ-2026.2-003 - Moonraker integration

Status: **OFFLINE IMPLEMENTED / RUNTIME PARTIALLY HARDWARE QUALIFIED**

Moonraker shall be the supported API and application-management boundary above
Klipper.

Each Fre3nder platform release shall carry a qualified stable Moonraker
baseline, its Python environment, runtime dependencies, and service integration
in the immutable RootFS.

Moonraker shall have persistent configuration and state independent of its
application code and Python environment.

Qualification shall demonstrate:

- clean service start and stop;
- expected dependency and readiness behavior relative to Klipper;
- API availability over the qualified network path;
- persistent configuration and state across a normal reboot;
- recovery of the RootFS baseline through a system-overlay reset while
  retaining `/home`; and
- defined behavior when the Moonraker baseline, environment, or persistent
  state is missing or invalid.

Failure of the Moonraker application layer shall not silently modify or replace
the Fre3nder base platform.

Reference hardware qualifies the pinned Moonraker runtime and dependency set,
real startup, local HTTP API, network discovery, volatile Moonraker UDS,
persistent configuration, ready Klippy connection, and S60 readiness through a
natural boot. It now also qualifies LAN access to `/server/info` and real
Moonraker JSON-RPC WebSocket traffic through Lighttpd while Moonraker remains
loopback-only. The fixed RootFS source and Python environment were subsequently
built and deployed as part of the Stage-D RootFS path. Qualification of the
final `2026.2` candidate, its normal-reboot state retention, and its baseline
recovery after a system-overlay reset remain open.

Moonraker self-update, dependency transitions, and automatic post-update S61
restart are not implemented as a complete lifecycle and are deferred beyond
`2026.2`.

## REQ-2026.2-004 - Update ownership boundary

Status: **OFFLINE IMPLEMENTED / PARTIALLY HARDWARE QUALIFIED**

Fre3nder shall distinguish platform updates from managed-application updates.

The application layer may manage approved persistent applications and web
frontends, including Fluidd and compatible alternatives. A future
application-level updater may manage those applications within the same
ownership boundary.

It shall not independently replace or modify:

- the Fre3nder kernel;
- the immutable Fre3nder RootFS;
- the Fre3nder-controlled Klipper host build;
- X2000 A/B selection or partition contents;
- F005 MCU firmware;
- system packages.

Those components remain under explicit Fre3nder build, deployment, and
qualification control.

A generic user-facing application install, restore, removal, or future update
action must therefore not imply a platform, boot-slot, or MCU update.

The default Moonraker configuration disables system updates. Its RootFS source
tree is a Git repository, while Fre3nder Klipper intentionally is not; the
pinned updater therefore does not create a Git deployer for Klipper. S61 has no
platform, boot-slot, MCU, or system-package update operation. The dispatcher and
Fluidd handler likewise operate only on their owned application payload,
configuration, desired state, and frontend selection. A working Moonraker or
managed-application self-update lifecycle is not required for `2026.2`.

## REQ-2026.2-005 - OctoApp integration (deferred)

Status: **DEFERRED / POST-2026.2**

This identifier is retained so historical references and requirement numbering
remain stable. OctoApp is not a `2026.2` release requirement. Fluidd is the
`2026.2` reference application that demonstrates the generic managed-
application mechanism independently of the kernel and RootFS build.

A later OctoApp integration should use the local Moonraker API and the generic
managed-application interface. Its future lifecycle should:

- install without rebuilding the RootFS;
- persist across normal reboot;
- start through the managed application/service model;
- communicate with the local Moonraker instance;
- be disableable or removable without changing the Fre3nder base platform.

No OctoApp implementation or qualification is required by REQ-2026.2-009 or the
final `2026.2` release.

## REQ-2026.2-006 - Frontend-neutral web-UI layer

Status: **OFFLINE IMPLEMENTED / PARTIALLY HARDWARE QUALIFIED**

Fre3nder shall provide a persistent frontend-neutral web-UI layer.

The immutable RootFS shall not hard-code Fluidd as the Fre3nder user
interface.

The system shall support an explicitly selected active frontend and shall allow
a compatible frontend to be replaced without rebuilding the kernel or RootFS.

Frontend application files and user-specific frontend state shall remain
outside the immutable RootFS.

The selected active frontend is a LAN web-UI concern. The native local display
is independently provided by GuppyScreen and does not consume this selection.

Partial reference-hardware evidence now demonstrates the frontend-neutral
selection file driving the generic S62 document root, a selected Fluidd payload
served over the LAN, and HTTP/WebSocket forwarding to loopback-only Moonraker.
Replacement with another compatible web frontend has not been qualified on the
reference system; hardware qualification of multiple frontends is not required
for `2026.2`.

## REQ-2026.2-007 - Fluidd reference frontend

Status: **OFFLINE IMPLEMENTED / PARTIALLY HARDWARE QUALIFIED**

Fluidd shall be the first web frontend qualified for `2026.2`.

Qualification shall demonstrate:

- installation into the persistent UI/application layer;
- access through the qualified LAN path;
- successful connection to the local Moonraker API;
- printer status and control through Moonraker;
- persistence across reboot;
- explicit restore or removal through the managed-application interface; and
- independent frontend replacement without a RootFS deployment.

Support for alternative compatible frontends is an architectural requirement;
hardware qualification of multiple frontends is not required for `2026.2`.

Partial reference-hardware evidence now demonstrates initial Fluidd bootstrap,
installation into the persistent application/UI layout, active frontend
selection, static LAN access, and real Moonraker HTTP and WebSocket connectivity.
Printer control through Fluidd, reboot persistence, explicit restore/removal,
and independent replacement without RootFS deployment are not yet qualified.
Moonraker-driven Fluidd self-update is deferred beyond `2026.2`.

## REQ-2026.2-008 - Display, touch, and local presentation

Status: **CORE LOCAL UI HARDWARE QUALIFIED / NORMAL CONTROL FLOWS OPEN**

Fre3nder shall provide an open local display path for the printer's integrated
display.

The implementation shall cover the hardware and system functions required for
normal local operation, including:

- display output;
- touch input;
- backlight control;
- required kernel and Device Tree integration;
- the native GuppyScreen Core-UI using Moonraker's API.

The local display stack shall not depend on Fluidd, a browser, or a display
server. GuppyScreen shall communicate with Moonraker; printer control shall
continue through Moonraker and Klipper.

The system shall remain administratively reachable if the local UI cannot
start.

### Hardware qualification status

The hardware and core local-UI portions of this requirement are qualified on
the investigated reference system.

Demonstrated on real hardware:

- PC22 backlight control with physical backlight response;
- Ingenic fbdev/fb_stage operation through `/dev/fb0`;
- stable 480x272 framebuffer output with correct colors;
- PB16 panel reset integration verified through successful panel bring-up;
- NS2009 enumeration on I2C4 at address `0x48`;
- static I2C4 ownership of GPC25/GPC26 with UART3 disabled;
- PC15 active-low pendown detection;
- Linux `BTN_TOUCH`, `ABS_X`, and `ABS_Y` input events;
- GuppyScreen `display_rotate: 1` with correct physical orientation;
- calibrated end-to-end touch mapping after the GuppyScreen rotation fix;
- automatic backlight enable at GuppyScreen startup;
- physical display standby after 60 seconds of inactivity;
- first-touch wake without activating the underlying UI control; and
- audible touch feedback through Linux `pwm-beeper`.

The persistent GuppyScreen integration preceding the current pin was built,
deployed to Fre3nder p8, and started successfully on the investigated reference
system. The touch-rotation correction, backlight startup correction, 60-second
standby/wake behavior, and touch-beep path are physically qualified.

The current pin `baa4f6689ac7334d240107529f6d3c42a1297319` adds the compact
272x480 portrait layouts and was cross-compiled through the normal component
path. Its Home temperatures and chart, Settings, Printer Tune, Console, Macros,
and left navigation were physically exercised in a volatile on-device test.
Persistent RootFS deployment of that exact pin remains part of qualification of
the final `2026.2` candidate.

Detailed evidence is recorded in
[`x2000-display-touch.md`](x2000-display-touch.md) and
[`guppyscreen.md`](guppyscreen.md).

REQ-2026.2-008 remains incomplete only with respect to the broader set of
normal local printer-control flows and their integrated behavior with
Moonraker/Klipper. Those flows remain part of the final usable-system
qualification rather than a display/touch hardware blocker.

## REQ-2026.2-009 - Integrated usable-system qualification

Status: **PLANNED**

A final `2026.2` candidate shall be qualified as one integrated system on the
investigated reference device.

The qualification shall demonstrate at minimum:

- normal Fre3nder boot;
- correct immutable/persistent/volatile filesystem behavior;
- retained persistent configuration across reboot;
- healthy Klipper startup and expected F005 communication;
- healthy Moonraker startup and API availability;
- successful Fluidd operation through the managed-application and frontend-
  neutral web layers from the LAN;
- successful local display and touch operation;
- successful local operation through GuppyScreen while the selected web
  frontend remains independently available over the LAN;
- normal printer status and control through the user-facing stack;
- one real print initiated and monitored through the `2026.2` user-facing
  stack;
- normal reboot followed by restoration of the usable state;
- no unintended modification of Stock A, the immutable RootFS, or
  Fre3nder-controlled MCU/platform components by managed-application
  operations.

Completion of this requirement establishes the `2026.2 Usable System`
functional milestone. Creation of the final release tag remains a separate
release action under `docs/versioning.md`.

## REQ-2026.2-010 - Componentized X2000 build architecture

Status: **OFFLINE IMPLEMENTED / BUILD CONFIRMED**

The X2000 build shall be further separated into independently maintainable
component builders.

The former `build-x2000-rootfs` responsibility was split so that
Buildroot/root-filesystem assembly and independently maintained applications
are no longer built by one monolithic component.

The intended builder structure is:

```text
scripts/build-x2000
scripts/build-x2000-buildroot
scripts/build-x2000-kernel
scripts/build-x2000-moonraker
scripts/build-x2000-guppyscreen
scripts/build-f005
```

Future independently maintained X2000 components shall follow the same model
where useful.

### Responsibilities

`build-x2000` shall be the top-level release orchestrator. It shall not contain
component-specific build implementation. It shall invoke the required component
builders, validate their artifacts and provenance, and compose the final
Fre3nder X2000 release.

`build-x2000-buildroot` shall own the generic Linux/Buildroot RootFS baseline
and final RootFS assembly. It shall consume already built and validated RootFS
component artifacts rather than implementing their build logic itself.

`build-x2000-moonraker` shall own the Moonraker-specific build inputs and
artifact creation, including the pinned upstream source, Python dependencies,
environment, RootFS payload, hashes, licenses, and component provenance.

`build-x2000-guppyscreen` shall own the GuppyScreen-specific build inputs,
cross-compilation, patches, immutable runtime payload, licenses, and component
provenance.

`build-x2000-kernel` shall continue to own only the X2000 kernel and DTB build.

`build-f005` shall continue to own only the F005 firmware build. Building the
firmware shall remain separate from flashing or otherwise modifying printer
hardware.

Builders such as `build-x2000-guppyscreen` shall produce independently
maintainable component artifacts that can be consumed by the RootFS assembly
without moving their implementation into the Buildroot builder.

### Component artifact contract

Each independently built component shall provide a deterministic artifact and
sufficient provenance for the consuming builder to validate it.

At minimum, the contract shall identify:

* the component;
* its source/version identity;
* the relevant build-input identity;
* the produced artifact hash;
* the provenance required for redistribution and reproducibility.

The exact manifest schema shall remain minimal and shall not introduce a generic
framework beyond what the real component builders require.

RootFS component artifacts shall be consumed by `build-x2000-buildroot`. The
resulting RootFS manifest shall record the identities of the component artifacts
that were incorporated.

The final `build-x2000` release composition shall in turn validate the RootFS,
kernel, F005, and any other release components and record their identities in
the final release provenance.

### Required implementation audit

Before changing the build scripts, the current build flow shall be audited to
determine the smallest coherent refactoring.

The audit shall establish:

1. which current `build-x2000-rootfs` responsibilities belong to the generic
   Buildroot/RootFS builder;
2. which Moonraker-specific responsibilities shall move to
   `build-x2000-moonraker`;
3. the minimal deterministic artifact produced by
   `build-x2000-moonraker`;
4. how `build-x2000-buildroot` consumes that artifact without containing
   Moonraker-specific build implementation;
5. which functions in `build/x2000/entrypoint.sh` must be separated;
6. how existing build-input fingerprints, component manifests, and release
   provenance remain consistent;
7. which tests belong to the individual component builders;
8. how the existing `build-x2000-rootfs` interface is migrated or removed
   without leaving two competing RootFS build paths.

### Constraints

The implementation shall follow these constraints:

* KISS;
* one clear build responsibility per component builder;
* no hardware access from build scripts;
* build and deployment remain separate;
* no automatic F005 flashing;
* component artifacts are validated fail-closed before consumption;
* no unnecessary package-manager or component-framework abstraction;
* no duplicated build logic between component builders;
* `build-x2000` remains the single entry point for producing a complete
  Fre3nder X2000 release;
* full release builds remain final validation gates rather than an iterative
  development feedback loop.

The implementation audit found that the former `build-x2000-rootfs` performed
both generic assembly and Moonraker staging. That interface has been removed.
`build-x2000-moonraker` and `build-x2000-guppyscreen` now produce deterministic
RootFS-overlay archives with minimal component manifests; the Buildroot builder
validates their source identity, build-input identity, mode, and artifact hash
before extraction. `build-x2000-buildroot` owns toolchain preparation and final
RootFS assembly, and the final RootFS manifest records both components. The
component and RootFS build completed successfully for the first Stage-D
hardware test.


## Requirement discipline

Each requirement remains `PLANNED` until implementation and the required
validation evidence exist.

Offline tests may establish `OFFLINE CONFIRMED` where appropriate but do not
authorize or imply hardware qualification.

Hardware-changing qualification remains separately authorized under
`AGENTS.md`.

Requirements may be refined when implementation evidence exposes a real
constraint, but release scope shall not expand merely because additional
features would be useful.
