# F005 mainline configuration

`printer-f005-mainline.cfg` is the current hardware-validated reference
configuration for the investigated F005/GD32F303RET6 board. It includes the
stock-derived TMC2208 software UARTs, extruder, heaters, thermistors, fans,
filament switch, safe Z homing, and 5x5 bed mesh.

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
