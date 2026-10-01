# Fre3nder

*An open software platform for the Ender-3 V3 KE.*

Fre3nder is an independent open-source project and is not affiliated with or
endorsed by Creality. Ender and Ender-3 are trademarks of their respective
owner.

## Current status

Current released version: [`2026.3`](CHANGELOG.md)

**`2026.3 RELEASED`** on the investigated reference system.
Fre3nder provides an open X2000 host, upstream Klipper integration for the
F005 MCU, a persistent usable-system stack, Moonraker, managed web applications,
and a documented path back to Stock. The released `2026.3` line retains the
previously qualified GuppyScreen local-UI evidence. The current Development
line integrates Fre3nderScreen as a signed Factory `.fre3app`; this path was
hardware-qualified on the investigated reference system with package
`2026.1.14cd415-fre3nder.0.4796448`. The prepared Fre3nderScreen release source
pin is `2026.2`, commit `63e7ecb9fff980b53f4987ef9994675aecf9e0a2`.
Only documentation changed after the qualified `14cd415` source; the
`2026.2` release binary has not yet been built or hardware-qualified.

The `2026.3` **Independent Kernel Stack** release completes the transition away
from the vendor kernel. Its host kernel is official Linux stable `v6.6.157`
plus an ordered five-patch Fre3nder X2000 hardware-support series with explicit
provenance and no RT23 dependency. The released series reproduces the source
tree exercised on the investigated reference system. The checkout may already
contain a later development version; its current source identity is defined by
[`VERSION`](VERSION) and [`configs/x2000/sources.json`](configs/x2000/sources.json).

The `2026.3` kernel qualification covers the exercised host boot, network, and
SSH path. Previously qualified display/touch, camera, ADXL/Input Shaper,
GuppyScreen, and complete-print flows remain documented qualification evidence
but were not automatically re-run on `6.6.157-fre3nder`. See the
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

Start with [the current documentation index](docs/README.md) for usage,
operations, development, API reference and troubleshooting.

- [Build Fre3nder](docs/build.md)
- [Configure Fre3nder](docs/configuration.md)
- [Back up HOME and SYS](docs/backup.md)
- [Display, touch and Fre3nderScreen](docs/display.md)
- [Install or update Fre3nder](docs/installation.md)
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
licensed under MIT unless a specific assignment preserves another license or
the file is third-party/derived material. See
[`docs/licensing-and-provenance.md`](docs/licensing-and-provenance.md) for the
path-specific licensing and provenance policy.
