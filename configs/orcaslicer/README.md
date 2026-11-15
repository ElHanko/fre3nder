# OrcaSlicer profiles

This directory contains the Fre3nder OrcaSlicer printer and standard process
presets for the hardware-validated Ender-3 V3 KE reference configuration.

## Scope

The current preset is for the investigated F005/GD32F303RET6 reference setup
with a 0.4 mm nozzle. It inherits OrcaSlicer's built-in
`Creality Ender-3 V3 KE 0.4 nozzle` preset, so the existing Creality KE process
and filament presets remain available instead of being duplicated here.

The preferred process, `0.20mm Standard @Fre3nder Ender3V3KE`, inherits the
built-in Creality KE 0.20 mm Standard process. It reduces the seven explicit
XY jerk settings from 7 mm/s to 5 mm/s to match the Fre3nder printer preset
and avoid OrcaSlicer's maximum jerk warning.

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
- call `START_PURGE` for the original two-line start purge, sharing its XY
  path with paused filament purges in the reference Klipper configuration;
- enable Klipper's `[exclude_object]` module because OrcaSlicer emits native
  `EXCLUDE_OBJECT_DEFINE`, `EXCLUDE_OBJECT_START`, and `EXCLUDE_OBJECT_END`
  commands for sliced objects.

## Import

Enable the built-in Creality Ender-3 V3 KE with the 0.4 mm nozzle in OrcaSlicer
so both parent presets are available. Use **File -> Import -> Preset Configs**
and import both JSON files:

- `Fre3nder Ender-3 V3 KE 0.4 nozzle.json`
- `0.20mm Standard @Fre3nder Ender3V3KE.json`

Select the Fre3nder printer and verify the Fre3nder Standard process is active.
If OrcaSlicer keeps the Creality process selected, switch to the Fre3nder
process in the Process dropdown. Users with a customized Fre3nder printer
preset can import just the process and select it manually.

The files contain no physical-printer host, IP address, credentials, or other
device-specific connection settings.

The printer preset requires the reference filament-change macros, including
`START_PURGE`, to be installed first. Existing `printer.cfg` files are preserved
by RootFS updates; merge the sections explicitly as described in
[filament changes](../../docs/configuration.md#filament-changes). Previously
exported profiles with the inline purge sequence continue to work. The default
start motion and extrusion are unchanged; custom purge coordinates now belong
in `_FILAMENT_SETTINGS` in Klipper.

## Provenance

The preset was prepared against:

- Fre3nder `main` commit `0260ad37d5858d9ef78111ad0bc3937c39734dfc`,
  especially `configs/klipper-f005/printer-f005-mainline.cfg`;
- OrcaSlicer `main` commit `0a3724ed2f106dd40b8a6b6f89c6a83a546cc81c`,
  especially `resources/profiles/Creality/machine/Creality Ender-3 V3 KE 0.4 nozzle.json`;
- OrcaSlicer `v2.4.2`, [the Creality KE Standard process preset](https://github.com/OrcaSlicer/OrcaSlicer/blob/v2.4.2/resources/profiles/Creality/process/0.20mm%20Standard%20%40Creality%20Ender3V3KE.json)
  (AGPL-3.0), the runtime parent of the Fre3nder process preset.

Both Fre3nder presets are user overrides that inherit the OrcaSlicer system
presets at runtime.

## Validation boundary

These presets describe the current Fre3nder reference configuration. Calibration
values such as Z offset, PID tuning, pressure advance, input shaping, filament
flow, and temperature remain printer- or filament-specific and are therefore
not encoded as Fre3nder-wide OrcaSlicer overrides.

Before publishing a generated `.orca_printer` bundle, import both presets into
the targeted OrcaSlicer release and slice a representative model. Check that
the Fre3nder Standard process triggers no maximum jerk warning and that its
G-code emits `SQUARE_CORNER_VELOCITY=5` with the expected start/end sequence.
Check for Creality-only commands and physical-printer connection settings
before publishing the bundle.
