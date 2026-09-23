# F005 mainline configuration

The current project-authored reference configuration is
[`configs/klipper-f005/printer-f005-mainline.cfg`](../configs/klipper-f005/printer-f005-mainline.cfg).
It applies to the investigated F005/GD32F303RET6 board; other printers need
board verification and independent calibration. The [F005 pin matrix](f005-pin-matrix.md)
is the current pin-reference summary, and the tracked configuration itself is
the source for exact active Klipper values.

The host uses passive `/dev/ttyS1` at 230400 baud. The primary MCU supports
Cartesian motion, extruder, TMC2208 software UART, X/Y endstops, BLTouch and
safe Z homing, bed mesh, heaters, thermistors, fans, and filament sensing.
The secondary Linux-process MCU at `/tmp/klipper_host_mcu` exposes ADXL345
through `/dev/spidev2.0`. The current reference `z_offset: 2.180`, PID,
mesh, and input-shaping values were qualified on the investigated printer;
they are not universal defaults. The earlier Phase-2 `z_offset: 1.900` is
historical and was superseded for that reference device.

The open first-print configuration intentionally omits Creality-only
`prtouch_v2`, `z_compensate`, `bl24c16f`, `hx711s`, `dirzctl`, `filter`,
`soft_homing`, `fan_feedback`, and dependent custom macros. The comparison
basis and classification are in [Stock Klipper analysis](klipper-stock.md).
The MCU port architecture is in [GD32F303 mainline port](gd32f303-mainline-port.md).

The staged first-print, passive runtime, Host-MCU/ADXL, and calibration
observations are preserved in
[F005 hardware validation](f005-hardware-validation.md) and the
[historical host/config milestone](../research/docs/f005-mainline-config-milestone.md).
Historical no-action and staged configurations remain under
[`research/configs/klipper-f005/`](../research/configs/klipper-f005/).
For changing the installed configuration, use the
[configuration guide](configuration.md).
