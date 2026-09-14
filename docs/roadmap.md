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
- `2026.2` — usable-system milestone reached on 2026-09-14. It is not yet
  released; final release-mode packaging, validation, and tagging remain.

## Current release work

No functional or hardware-acceptance blocker remains for `2026.2`. The current
work is limited to reviewing and committing the source state, producing and
validating final release-mode artifacts from that exact state, and creating the
matching release tag.

## Next

### User-facing installation and releases

Define a reproducible public release-artifact and download boundary, including
how a user selects an exact release and sees the installed version through the
normal UI or API. Turn the established development deployment into a guided
Stock-to-Fre3nder installation flow with model checks, Point-of-Return backup,
safe deployment, and a clear return-to-Stock path. Minimize required SSH and
developer-only steps without choosing an installer technology prematurely.

### GuppyScreen project boundary

Define how the Fre3nder-maintained GuppyScreen work becomes an independently
maintained project with its own repository boundary, versioning, and releases.
Fre3nder should eventually consume a clearly pinned GuppyScreen release instead
of treating UI development as part of the platform, while the exact project and
upstream relationship remains to be decided.

### Managed applications

Extend the simple managed-application model beyond the qualified Fluidd path as
real applications require it. Complete a coherent generic install, remove,
status, restore, update, version/pin, dependency, and user-management experience.
Keep catalog or discovery work demand-driven and avoid introducing a general
package-manager framework without a concrete need.

## Later

### Platform updates (OTA) and rollback

Design a safe release-to-release update path for the Fre3nder platform. It must
respect the immutable RootFS, A/B and recovery boundaries, persistent `/home`,
and the separation between platform and application updates. Updates must retain
a usable fallback and must never imply silent F005 firmware flashing.

### Mainline Linux

Move toward a kernel based as far as practical on mainline Linux. Identify the
required X2000 and printer-hardware support, isolate the current vendor patches,
reduce remaining Ingenic dependencies, and upstream suitable work where
possible. Select a concrete kernel only after this investigation, then qualify
the resulting path on hardware.

### Internal persistence backend

Provide an installation-oriented internal backend for the existing system and
userdata persistence roles, which currently use external Development storage.
The design must preserve the logical role abstraction, avoid assuming ownership
of Stock data, and define migration and recovery before changing partitions.

### Operational resilience

Complete runtime and hotplug network failover, late-camera recovery, and the
uninterrupted software-only Fre3nder-to-Stock handoff. These are useful product
improvements but are not missing `2026.2` acceptance work.

## Exploratory

- Qualify broader Ender-3 V3 KE hardware and firmware revisions before treating
  reference-system results as universal.
- Consider additional applications, web frontends, and peripherals only when a
  concrete user need justifies product integration and maintenance cost.
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
