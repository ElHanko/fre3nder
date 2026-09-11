# OrcaSlicer profile

This directory contains the Fre3nder OrcaSlicer printer preset for the
hardware-validated Ender-3 V3 KE reference configuration.

## Scope

The current preset is for the investigated F005/GD32F303RET6 reference setup
with a 0.4 mm nozzle. It inherits OrcaSlicer's built-in
`Creality Ender-3 V3 KE 0.4 nozzle` preset, so the existing Creality KE process
and filament presets remain available instead of being duplicated here.

The inherited mechanical limits already match the Fre3nder reference
configuration: 220 x 220 x 245 mm printable volume, 500 mm/s X/Y maximum
velocity, 8000 mm/s^2 X/Y maximum acceleration, 30 mm/s Z maximum velocity,
and 300 mm/s^2 Z maximum acceleration.

Fre3nder-specific overrides are intentionally limited to settings where the
stock OrcaSlicer KE preset conflicts with current upstream Klipper or the
Fre3nder configuration:

- remove the Creality-specific `PRINTER_PARAM` start-G-code dependency;
- remove the obsolete `SET_VELOCITY_LIMIT ACCEL_TO_DECEL=...` command;
- keep X/Y maximum jerk at 5 mm/s to match Fre3nder's
  `square_corner_velocity: 5.0` reference setting;
- use plain `M84` at print end because Klipper does not implement the
  axis-selective semantics implied by `M84 X Y E`;
- use `PAUSE` for slicer-requested filament changes because the current
  Fre3nder baseline does not define an `M600` macro;
- enable Klipper's `[exclude_object]` module because OrcaSlicer emits native
  `EXCLUDE_OBJECT_DEFINE`, `EXCLUDE_OBJECT_START`, and `EXCLUDE_OBJECT_END`
  commands for sliced objects.

## Import

In OrcaSlicer, use **File -> Import -> Preset Configs** and select:

`Fre3nder Ender-3 V3 KE 0.4 nozzle.json`

The preset depends on OrcaSlicer's built-in
`Creality Ender-3 V3 KE 0.4 nozzle` parent preset. No physical-printer host,
IP address, credentials, or other device-specific connection settings are
stored in this file.

## Provenance

The preset was prepared against:

- Fre3nder `main` commit `0260ad37d5858d9ef78111ad0bc3937c39734dfc`,
  especially `configs/klipper-f005/printer-f005-mainline.cfg`;
- OrcaSlicer `main` commit `0a3724ed2f106dd40b8a6b6f89c6a83a546cc81c`,
  especially `resources/profiles/Creality/machine/Creality Ender-3 V3 KE 0.4 nozzle.json`.

The Fre3nder preset is a user override that inherits the OrcaSlicer system
preset instead of vendoring a copy of the upstream profile. This keeps the
repository material small and makes the Fre3nder-specific differences explicit.

## Validation boundary

This preset describes the current Fre3nder reference configuration. Calibration
values such as Z offset, PID tuning, pressure advance, input shaping, filament
flow, and temperature remain printer- or filament-specific and are therefore
not encoded as Fre3nder-wide OrcaSlicer overrides.

Before publishing a generated `.orca_printer` bundle, import this preset into
the targeted OrcaSlicer release, slice a representative model, and inspect the
resulting G-code for the expected start/end sequence and absence of
Creality-only commands. Do not include OrcaSlicer physical-printer connection
settings in a repository bundle.
