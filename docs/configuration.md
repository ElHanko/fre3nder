# Fre3nder configuration

The current reference configuration is
[`configs/klipper-f005/printer-f005-mainline.cfg`](../configs/klipper-f005/printer-f005-mainline.cfg).
It targets the investigated F005/GD32F303RET6 board and must be independently
calibrated on other printers.

The F005 pin contract is summarized in
[`docs/f005-pin-matrix.md`](f005-pin-matrix.md). The current host, service,
storage, network, and boot configuration is under
[`configs/x2000`](../configs/x2000); its source and artifact invariants are
listed in [`configs/x2000/sources.json`](../configs/x2000/sources.json).

The OrcaSlicer user preset for the current 0.4 mm reference configuration is
under [`configs/orcaslicer`](../configs/orcaslicer/). It inherits OrcaSlicer's
built-in Ender-3 V3 KE profile and contains only the Fre3nder-specific G-code
and motion-limit overrides.

The host uses passive `/dev/ttyS1` at 230400 baud and starts normal Klippy only
after exact Fre3nder MCU identity classification. Stock and unknown MCU
identities leave the Fre3nder Klippy service stopped.

Creality-specific behavior and the deliberate first-milestone omissions are
described in [`docs/klipper-stock.md`](klipper-stock.md) and
[`docs/f005-mcu-switching.md`](f005-mcu-switching.md).
