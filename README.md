# Fre3nder

*An open software platform for the Ender-3 V3 KE.*

Fre3nder is an independent open-source project and is not affiliated with or
endorsed by Creality. Ender and Ender-3 are trademarks of their respective
owner.

## Current status

Current released version: [`2026.2`](CHANGELOG.md)

**`2026.2 RELEASED`** on the investigated reference system.
Fre3nder provides an open X2000 host, upstream Klipper integration for the
F005 MCU, a persistent usable-system stack, Moonraker, managed web applications,
GuppyScreen, and a documented path back to Stock. The `2026.2` usable-system
scope is hardware-qualified on the investigated reference system. See the
[changelog](CHANGELOG.md) for release history.

The important boundaries remain:

- software-only Fre3nder -> Stock: **REQUIRES QUALIFICATION**;
- power-cycle Stock recovery: **QUALIFIED ON DEVICE (2/2)**;
- physical PC22 backlight effect: **QUALIFIED ON DEVICE**;
- integrated display/backlight/touch hardware path: **QUALIFIED ON DEVICE**;
- the complete `2026.2` persistence, Moonraker, Fluidd, and GuppyScreen
  usable-system path: **HARDWARE QUALIFIED ON DEVICE**.

Observations marked as qualified apply to the investigated reference system
unless explicitly stated otherwise. Do not treat its calibration, hardware
revision, or recovery behavior as universal.

## Start here

- [What Fre3nder builds and how to build it](docs/build.md)
- [Current configuration and hardware contract](docs/configuration.md)
- [Integrated display and touch hardware](docs/x2000-display-touch.md)
- [GuppyScreen local Core-UI](docs/guppyscreen.md)
- [Installation and deployment boundary](docs/installation.md)
- [Recovery and return to Stock](docs/recovery.md)
- [Development and tests](docs/development.md)
- [Current roadmap](docs/roadmap.md)
- [Release history](CHANGELOG.md)
- [Licensing and provenance](docs/licensing-and-provenance.md)
- [Acknowledgements](ACKNOWLEDGEMENTS.md)

The current implementation is organized as follows:

```text
build/       reproducible current build recipes
configs/     current Fre3nder host and F005 configurations
patches/     patches required by current builds
scripts/     current build, deployment, recovery, and test tools
tests/       current product tests, where present
docs/        current product documentation
research/    active research, bring-up, analysis, and history
```

## Research and bring-up history

[`research/`](research/) is an active project layer, not a dead archive. It
contains reverse engineering, hardware discovery, prototypes, experiments,
historical qualification records, and rejected alternatives. New work on the
display, touch, camera, sensors, MCU protocols, or bootloader starts there.

Qualified findings may be adopted into the productive tree, but productive
code, builds, configurations, and runtime must never depend on `research/`.

## Safety and local information

Read [`AGENTS.md`](AGENTS.md) before any hardware-related work. Offline builds
do not authorize deployment or persistent printer changes. Keep device-specific
information in the ignored `docs/local-device.md`, created from
[`docs/local-device.example.md`](docs/local-device.example.md), and never store
secrets in the repository.

## License

Project-authored Fre3nder system material is licensed under
`AGPL-3.0-or-later`. Project-authored material in [`research/`](research/) is
licensed under MIT unless a file is third-party or derived material. See
[`docs/licensing-and-provenance.md`](docs/licensing-and-provenance.md) for the
path-specific licensing and provenance policy.
