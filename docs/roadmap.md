# Fre3nder roadmap

Fre3nder has a qualified open printer stack and usable-system baseline for the
investigated Ender-3 V3 KE. The project now moves from proving that platform to
making releases easier to maintain, install, update, and extend.

Completed release work and historical milestones are documented in the project
[`CHANGELOG.md`](../CHANGELOG.md). This roadmap intentionally focuses on future
work.

## Next

### User-facing installation and releases

Define a reproducible public release-artifact and download boundary, including
how a user selects an exact release and sees its installed version and update
state through the normal UI or API. Turn the documented
[expert installation](installation.md) into a guided Stock-to-Fre3nder flow
with model checks, Point-of-Return backup, safe deployment, understandable recovery and rollback,
and a clear return-to-Stock path. Minimize required SSH and project-specific
knowledge without removing expert SSH administration or choosing an installer
technology prematurely.

### Local UI product experience

Improve local printer and administration workflows on the 272x480
Fre3nderScreen display so fewer tasks require the web UI or SSH.

### Managed applications

Extend the signed `.fre3app` model beyond the previously qualified Fluidd path as
real applications require it, and prove that the generic layer works for more
than one useful application or frontend. Improve install, remove, status,
restore, version/pin, dependency, discovery, and user-management behavior while
keeping catalog work demand-driven. Avoid introducing a general package-manager
framework without a concrete need.

### Platform updates and rollback

Expand hardware validation of release-to-release A/B updates on the supported
USB and eMMC backends. Improve recovery when a newly activated system does not
boot, and evaluate additional update sources when needed. The current
[OTA workflow](updates.md) covers the CLI, Maintenance and Fre3nderScreen.

## Later

### Application update lifecycle

Improve signed-package updates, recovery and dependency handling as concrete
apps require them. Moonraker already uses the platform system-app lifecycle.
Keep app updates independent of the Kernel, RootFS, F005 firmware and A/B
state. See [applications](apps.md).

### Kernel upstreaming

The productive kernel is already independently maintainable from official Linux
stable. Reduce the remaining Fre3nder X2000 hardware-support series over time
and upstream suitable support where practical. Upstreaming is a maintenance
improvement, not a prerequisite for the current kernel path.

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
[F005](f005.md#current-stock-and-gate-2-classification); historical gate evidence remains in
[`research/docs/roadmap-history.md`](../research/docs/roadmap-history.md).
