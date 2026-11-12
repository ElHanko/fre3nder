# F005 mainline configuration

`printer-f005-mainline.cfg` is the current hardware-validated reference
configuration for the investigated F005/GD32F303RET6 board. It includes the
stock-derived TMC2208 software UARTs, extruder, heaters, thermistors, fans,
filament switch, safe Z homing, and 5x5 bed mesh.

The operator reported successful reference-hardware tests of filament change,
300-second heater/motor shutdown, retained pause state, and recovery through
completion of a Benchy at the former front probe point. The simplified Fluidd
workflow is `PAUSE` → change filament → optional `PURGE` → `RESUME`; after motor
shutdown, inspect the print and paths, use `RECOVER_PRINT`, inspect again, then
use `RECOVERY_RESUME`. Paused jobs have no automatic cancellation timer.

The new configurable rear recovery point defaults to nozzle X10/Y178 (reference
BLTouch X10/Y205) and **still requires hardware validation**, as does the new
macro interface. Normal `G28`/`safe_z_home` is unchanged and `RESUME` never
recovers a lost reference automatically. See
[filament changes](../../docs/configuration.md#filament-changes) for operation,
visual checks, the shared start-purge area, configuration and the explicit
merge required for existing installations.

The configuration's pin mapping and qualification scope are documented in
[F005 pin matrix](../../docs/f005.md#pin-matrix) and
[F005 hardware evidence](../../research/docs/f005-hardware-validation.md).
Its calibration values are reference-device values and must be independently
verified on every other printer.

The current host-side passive UART option is part of the `[mcu]` section. The
X2000 host configuration, identity manifest, and runtime overlay live under
[`configs/x2000`](../x2000/).

Earlier no-action, bring-up, and staged candidates remain available under
[`research/configs/klipper-f005`](../../research/configs/klipper-f005/); they
are historical validation inputs, not current production configuration.
