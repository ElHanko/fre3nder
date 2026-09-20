# Fre3nder roadmap

Fre3nder has a qualified open printer stack and usable-system baseline for the
investigated Ender-3 V3 KE. The project now moves from proving that platform to
making releases easier to maintain, install, update, and extend.

Completed release work and historical milestones are documented in the project
[`CHANGELOG.md`](../CHANGELOG.md). This roadmap intentionally focuses on future
work.

## Reached milestones

- `2026.1` — open printer stack and first qualified real print, released on
  2026-08-29.
- `2026.2` — usable-system, released on 2026-09-14.
- `2026.3` — independent-kernel-stack, released on 2026-09-20.

## Next

### User-facing installation and releases

Define a reproducible public release-artifact and download boundary, including
how a user selects an exact release and sees its installed version and update
state through the normal UI or API. Turn the established development deployment
into a guided Stock-to-Fre3nder installation flow with model checks,
Point-of-Return backup, safe deployment, understandable recovery and rollback,
and a clear return-to-Stock path. Minimize required SSH and project-specific
knowledge without removing expert SSH administration or choosing an installer
technology prematurely.

### GuppyScreen project boundary

Define how the Fre3nder-maintained GuppyScreen work becomes an independently
maintained project with its own repository boundary, versioning, and releases.
Fre3nder should eventually consume a clearly pinned GuppyScreen release instead
of treating UI development as part of the platform, while the exact project and
upstream relationship remains to be decided.

### Local UI product experience

Continue optimizing the GuppyScreen product experience for the small 480x272
display. Improve remaining quality-of-life workflows and local administration
so normal printer use depends less on the web UI or SSH. Larger layout or UX
redesigns remain optional until a concrete scope is selected; this product work
is separate from the GuppyScreen project and ownership boundary above.

### Managed applications

Extend the simple managed-application model beyond the qualified Fluidd path as
real applications require it, and prove that the generic layer works for more
than one useful application or frontend. Improve install, remove, status,
restore, version/pin, dependency, discovery, and user-management behavior while
keeping catalog work demand-driven. Avoid introducing a general package-manager
framework without a concrete need.

### Platform updates (OTA) and rollback

Add a safe release-to-release update path for the Fre3nder platform.

The update architecture should use the existing X2000 A/B system slots so that
the currently active system remains untouched while a new system is written and
verified on the inactive side.

Platform updates should preserve the logical `HOME` role while resetting the
logical `SYS` system overlay for the newly installed release. OTA must operate on
these logical storage roles rather than depending on their physical backing.
Physical assignment of `SYS` and `HOME` remains an installation/storage-policy
responsibility.

The initial implementation is intended for the currently supported external
Fre3nder persistence backend. Internal persistence and migration are separate
future work and may require corresponding extensions to OTA.

The same OTA core should eventually be usable through SSH/CLI, the web interface,
and the local display. Local upload and removable USB storage are the initial
planned update sources.

A deliberate return to compatible Creality Stock firmware should also be
supported without requiring a permanently preserved Stock A/B slot. Normal
Fre3nder platform updates remain separate from F005 firmware updates.

## Later

### Application update lifecycle

Integrate Moonraker self-update and Fluidd or other managed-application updates
with explicit version ownership, dependency handling, and defined service
restarts. Restore desired applications automatically after a system-overlay
reset when that can be done safely. Application updates must remain separate
from platform ownership and must never implicitly replace the kernel, RootFS,
F005 firmware, or A/B state.

### Platform updates (OTA) and rollback

Design a safe release-to-release update path for the Fre3nder platform. It must
respect the immutable RootFS, A/B and recovery boundaries, persistent `/home`,
and the separation between platform and application updates. Updates must retain
a usable fallback, fit normal user-facing installation and recovery workflows,
and must never imply silent F005 firmware flashing.

### Kernel upstreaming

The productive kernel is already independently maintainable from official Linux
stable. Reduce the remaining Fre3nder X2000 hardware-support series over time
and upstream suitable support where practical. Upstreaming is a maintenance
improvement, not a prerequisite for the current kernel path.

### Internal persistence backend

Provide an installation-oriented internal backend for the existing system and
userdata persistence roles, which currently use external Development storage.
The design must preserve the logical role abstraction, avoid assuming ownership
of Stock data, and define migration and recovery before changing partitions.

### Network resilience

Add runtime Ethernet/WLAN failover, predictable hotplug behavior, and bounded
reconnect and recovery after link loss so administrative access normally
restores itself. Define the required behavior without selecting a network-
manager implementation prematurely.

### Stock/Fre3nder transitions

Complete the software-controlled Fre3nder-to-Stock handoff and qualify the
remaining coordinated F005 and Stock-host transitions. Reduce manual recovery
and power-cycle steps while preserving the current safety and recovery
boundaries; Stock and Fre3nder are alternative operating states, not concurrent
systems.

### Peripheral workflows

Recover the camera service automatically after late attachment, failure, or
reconnection. Improve the already qualified ADXL345/input-shaping path with a
more integrated calibration workflow and fewer maintenance or SSH steps,
potentially through the normal UI, without redesigning its working hardware
path.

## Exploratory

- Consider OctoApp as an application and Mainsail or other compatible web
  frontends as candidates when a concrete use case justifies expanding and
  validating the managed-application model. They are not promised release
  contents.
- Consider Bluetooth qualification and integration only if a concrete use case
  emerges; current WLAN qualification does not cover Bluetooth.
- Qualify broader Ender-3 V3 KE hardware, board, and Stock-firmware revisions
  before treating reference-system results as universal.
- Consider larger GuppyScreen layout or UX redesigns and additional local
  functions only after a product scope is selected.
- Evaluate HTTPS/TLS for the web UI when the deployment and threat model
  justify the additional lifecycle and certificate ownership.
- Evaluate which remaining Klipper, kernel, and UI changes can be contributed
  upstream after their long-term ownership boundaries are clear.

No future version numbers or delivery dates are assigned until a scope is
actually selected.

## Standing project gates

Gate 1, **POINT OF RETURN**, and Gate 2, **CREALITY DELTA UNDERSTOOD**, are
satisfied for the current scope. That status does not authorize persistent or
hardware-changing operations; those remain explicit WARNING / RED ZONE work
under `AGENTS.md`.

Gate 2 uses the classifications `UPSTREAM`, `KEEP`, `REIMPLEMENT`, `DROP`, and
`UNKNOWN`. Current classifications are documented in
[`klipper-stock.md`](klipper-stock.md); historical gate evidence remains in
[`research/docs/roadmap-history.md`](../research/docs/roadmap-history.md).
