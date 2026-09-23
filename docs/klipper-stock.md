# Klipper, printer configuration, Moonraker, and web stack

Unless stated otherwise, these observations come from the reference system running
Creality firmware `V1.1.0.15`. They are not asserted for every Ender-3 V3 KE
firmware revision.

## What is actually running

**Confirmed:** The running printer service is Creality's Klipper:

```text
/usr/share/klippy-env/bin/python
/usr/share/klipper/klippy/klippy.py
/usr/data/printer_data/config/printer.cfg
-l /usr/data/printer_data/logs/klippy.log
-a /tmp/klippy_uds
```

The interpreter resolves to `/usr/share/klippy-env/bin/python3`, Python 3.8.2. The
active `klippy.py` and `S55klipper_service` hash exactly match `/rom`, proving these
two active files come from the immutable Creality RootFS rather than the overlay.

**Confirmed version evidence:** Host Klipper reports `09faed31-dirty` in its log.
The packaged `/usr/share/klipper` tree has no `.git` directory, so ancestry beyond
that hash cannot be reconstructed locally. The best public content comparison
baseline used for the first mainline milestone is
`9b60daf62dd7c02164c53f2baa72e3e6c8af441f`; this records content provenance and
does not assert fork ancestry.

## Stock classification boundary

`/usr/share/klipper` is the active Creality tree in the immutable SquashFS. The
inspected device also contained Klipper-related material in writable storage, but
that material came from local experiments and is documented only in the ignored
`local-device.md`. It must not be used to characterize stock firmware.

## Creality-specific Klipper surface

Comparing module names in the reference Creality tree with an upstream baseline
produced these Creality-tree-only Python modules:

```text
bl24c16f.py       custom_macro.py    dirzctl.py
fan_feedback.py   filter.py          hx711s.py
metadata.py       prtouch.py         prtouch_v2.py
soft_homing.py    tool.py            z_compensate.py
```

In addition, the active tree has MIPS binary extensions:

```text
prtouch_v2_wrapper.cpython-38-mipsel-linux-gnu.so
z_compensate_wrapper.cpython-38-mipsel-linux-gnu.so
```

**Confirmed configured integration:** `[prtouch_v2]`, `[z_compensate]`,
`[bl24c16f]`, and `[custom_macro]` are present in the reference configuration.
The archived runtime logs used for the first mainline milestone show normal
BLTouch/`probe` bed-mesh operation, but do not establish that PR-Touch or
`z_compensate` is used during those runs. The two compiled wrappers remain tied
to the MIPS/Python 3.8 ABI and are not part of the first mainline port.

`hx711s.py`, `dirzctl.py`, `filter.py`, `fan_feedback.py`, `soft_homing.py`,
`tool.py`, and `metadata.py` are present but inactive in the examined F005 path.
They are classified `DROP` for the first milestone; automatic print/nozzle
calibration can be revisited as an optional `REIMPLEMENT` task if required.

## Printer configuration

Primary file: `/usr/data/printer_data/config/printer.cfg`, declared version
`v1.2.12`, created 2024-03-27. Includes:

```text
sensorless.cfg
gcode_macro.cfg
printer_params.cfg
```

These are the Creality configuration includes. The active reference configuration
also had an individual extra include, which is recorded only in the ignored
`local-device.md`. A factory-oriented `factory_printer.cfg` version `v1.2.4` was
also observed.

### MCU and motion

- Main MCU comment: GD32F303RET6, board firmware family `CR4NS200323C10`.
- Runtime MCU constant: `gd32f303xe`, 120 MHz.
- Connection: `/dev/ttyS1`, UART 230400, restart method `command`.
- MCU runtime build: `38d96adc-dirty-20231016_135251-longer-virtual-machine`.
- X/Y/Z: Cartesian; TMC2208 drivers on MCU UART pins PB12/PB13/PB14.
- Maximum configured velocity 500 mm/s; acceleration 8000 mm/s².

### Host MCU and sensors

- `[mcu rpi]` uses `/tmp/klipper_host_mcu` (name retained despite non-Raspberry Pi
  hardware).
- Host MCU runtime build: `v0.11.0-372-gb9ad7605`, MCU type `linux`, 50 MHz.
- ADXL345 uses Host-MCU SPI `spidev2.0`, axes map `z,y,x`.
- BL24C16F uses Host-MCU I2C bus 2 at 400 kHz.

### Probe, load sensing, Z offset

- A normal `[bltouch]` logical probe uses PC14 (sensor) and PC13 (control), offset
  X=0, Y=27.
- BLTouch is the active Z endstop and normal `probe` object in the investigated
  reference configuration. Archived logs contain complete 5x5 bed-mesh runs
  through this probe path.
- `[prtouch_v2]` uses pressure clock/data pins PA4/PC6 and PA15 swap pins.
- `[z_compensate]` implements nozzle cleaning/pressure compensation behavior.
- `prtouch_v2` and `z_compensate` are configured and initialize, but their use in
  the examined runtime logs is not demonstrated. They are therefore outside
  the first mainline milestone.
- There is no active `[load_cell]` section. Pressure/load-cell-like behavior is
  implemented by the Creality PR-Touch modules; `hx711s.py` exists but is not
  configured.
- A device-specific BLTouch Z offset was saved; its value belongs only in the
  ignored `local-device.md`.

### Extruder, heaters, fans, and sensing

- Extruder step/dir PB4/PB3, heater PA1, EPCOS 100K B57560G104F on PC5,
  0-320 °C, PID controlled, pressure advance 0.036.
- Bed heater PB2, same sensor type on PC4, 0-120 °C, PID controlled.
- Part fan `fan0` on PA0; nozzle heater fan on PC1; mainboard fan on inverted PB1.
- Filament switch on inverted PC15.

### Mesh and input shaping

- Bed mesh: 5x5, X 5..215, Y 10..215, travel 350 mm/s.
- A device-specific saved default mesh is present in `printer.cfg`.
- Device-specific input-shaper calibration values were present and are recorded
  only in the ignored `local-device.md`.
- Resonance tester uses ADXL345, test point 117.5/117.5/100, max 90 Hz.

## MCU firmware and update behavior

**Confirmed current MCU updater state:** `mcu0` on `/dev/ttyS1` reports
`mcu0_001_G32-mcu0_005_000`. The matching F005 image exists at:

```text
/usr/share/klipper/fw/F005/mcu0_001_G32-mcu0_005_000.bin
```

An F005 nozzle image also exists, but this board's updater selected only `mcu0`;
use of that nozzle image on this printer is **unconfirmed**. Only the main MCU
and Host MCU are loaded by the active Klipper path; use of a separate nozzle
MCU is not evidenced in that path and is not required by the first mainline
port. The boot-time
`S13mcu_update` script can handshake, compare versions, upload firmware through
`mcu_util`, and start the MCU application. It was read, not run.

Offline static analysis of the inspected p7/p8 Stock artifacts now establishes
the version/image decision for the known Fre3nder/Mainline identity. If the
Creality bootloader is reachable and reports
`mcu0_001_G32-mcu0_004_000`, `S13mcu_update` uses the hardware prefix to select
`mcu0_001_G32-mcu0_005_000.bin`; its numeric inequality check treats
`004 != 005` as an update request. This is not an upgrade-order comparison, and
the Stock selection does not use a release manifest or SHA-256 verification.

Neither `S13mcu_update` nor `mcu_util` resets a running application into the
bootloader. The reliable bootloader handoff during a normal reboot from Fre3nder
to unchanged Stock and the complete automatic roundtrip therefore remain
unqualified. Stock remains unchanged. See `f005-mcu-switching.md` for the
detailed evidence, including the bounded internal retry behavior of the inspected
`mcu_util`.

There is no USB, ACM, or CAN MCU node. `/dev/ttyS0`..`ttyS7` exist; only ttyS1 is
opened by Klipper for the printer MCU in the captured process state.

## Moonraker

- Installation: `/usr/data/moonraker/moonraker`.
- Python: 3.8.2 in `/usr/data/moonraker/moonraker-env`.
- Git: branch `master`, commit `1ed102edfb34906115bfeb02712d4c839b93a7a9`.
- Reported version: `v0.10.0-19-g1ed102e`.
- Config: `/usr/data/printer_data/config/moonraker.conf`.
- Klipper connection: `/tmp/klippy_uds`.
- API: `0.0.0.0:7125`; also creates
  `/usr/data/printer_data/comms/moonraker.sock`.
- Database: `/usr/data/printer_data/database/moonraker-sql.db`.

The active Moonraker config contained persistent local additions. Their concrete
names and settings are recorded only in the ignored `local-device.md` and must not
be treated as the original Creality Moonraker config.

## Web/UI components

- Creality binary `web-server` listens on TCP 80 as part of the
  master/app/display/upgrade stack.
- The MJPEG camera service listens on TCP 8080.
- Additional web interfaces and integrations were supplied from writable storage
  on the inspected device. They are local modifications, not stock-firmware
  findings.

## Mainline MCU milestone

The investigated GD32F303RET6/F005 board is covered by a minimal upstream port,
classified as **SMALL MCU PORT**. It reuses the current upstream STM32F1 and
generic ARM paths; no complete `src/gd32/` backend is needed. The exact source
patch, configuration, and offline Docker build recipe are documented in
[`gd32f303-mainline-port.md`](gd32f303-mainline-port.md).

## First mainline host/config result

The investigated F005 reference has a current first-mainline configuration
under [`../configs/klipper-f005/`](../configs/klipper-f005/) and historical
minimal offline/no-action candidates under
[`../research/configs/klipper-f005/`](../research/configs/klipper-f005/).
They are described in [`f005-mainline-config.md`](f005-mainline-config.md). Current
upstream Klippy accepted both with the exact GD32 dictionary; the mainline
target was then validated through the staged hardware sequence and one complete
PLA Benchy. The exact historical Phase-2 `z_offset: 1.900`, current 2.180
paper-test requalification, PID baseline, and remaining boundaries are in
[`f005-hardware-validation.md`](f005-hardware-validation.md).
The bring-up file remains an offline/no-action candidate. `temp_offset_flag`
is intentionally absent.

## Risks and open questions

- **Risk:** Creality binary Python extensions cannot simply be copied to a newer
  Python/architecture and expected to load.
- **Risk:** The stock service can overwrite/update config files at startup based on
  config version and preserves only the `SAVE_CONFIG` tail.
- **Risk:** Klipper logs can consume substantial persistent storage. Check local
  usage before backup or migration work.
- **Open:** The exact historical upstream ancestor of Creality hash `09faed31`
  was not reconstructed. The public source comparison uses the recorded public
  baseline and makes no ancestry claim.
- **Open:** Complete behavior of the binary PR-Touch/Z-compensation wrappers;
  these are optional future reimplementation work, not a blocker for the first
  MCU port.
