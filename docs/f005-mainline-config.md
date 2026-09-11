# F005 mainline host/config milestone

**HOST/CONFIG AND FIRST-PRINT VALIDATION COMPLETE**
**PRIMARY MCU PASSIVE RUNTIME CONFIG/FINALIZE: PASS**
**REFERENCE F005 PRINT: PASS**

This document describes the investigated F005/GD32F303RET6 reference only. It
does not claim support for every Ender-3 V3 KE revision. The fixed upstream
basis is Klipper commit
`0499b30374315f2a9f49fc12808527fc7d0f5cfa`, together with the small GD32F303
port documented in [`gd32f303-mainline-port.md`](gd32f303-mainline-port.md).

## Offline and hardware result

The current project-authored mainline configuration is published under
[`configs/klipper-f005/`](../configs/klipper-f005/). The historical minimal
first-bring-up candidate and staged candidates remain under
[`research/configs/klipper-f005/`](../research/configs/klipper-f005/) and were
used for the earlier offline validation. The then-current primary-MCU
configuration was run through Klipper's own `scripts/test_klippy.py` in
debugoutput/dictionary mode with the exact dictionary from the final GD32F303
build. That historical run predates the new secondary Linux-MCU/ADXL sections;
it must not be read as their offline dictionary validation. The F005 dictionary
identifies the MCU as `gd32f303xe`, uses a 120 MHz clock, and models PA3/PA2 at
230400 baud; Klippy loaded 88 commands.

The offline run reported no unknown sections, options, or pins and no missing
MCU commands. The complete mainline configuration was subsequently validated
on the investigated reference through the staged bring-up and one complete
PLA Benchy. The evidence and exact validation boundary are in
[`f005-hardware-validation.md`](f005-hardware-validation.md).

## Passive MCU runtime result

After the separate controlled F005 MCU flash and identify validation, a single
passive Mainline Klippy runtime test completed on the investigated reference
system with exit code `0`. It used `kinematics: none` at `/dev/ttyS1`, 230400
baud, loaded the real `gd32f303xe` dictionary, completed ClockSync, and sent
`allocate_oids count=0` followed by `finalize_config`. The MCU then reported
`is_config=1` and `is_shutdown=0`, and Klippy exited cleanly through the
`/dev/null` EOF path without a firmware restart.

The initial `get_config` response was not separately printed. The reviewed
private gate requires `is_config=0` and `is_shutdown=0` before configuration
send; reaching the configuration-send line proves that this gate allowed the
observed run. The pinned code registers `/dev/null` input only after READY, so
the clean EOF exit also establishes that READY was reached.

This establishes **MAINLINE KLIPPY ↔ MAINLINE F005 MCU PASSIVE RUNTIME
CONFIG/FINALIZE: PASS**. It does not validate printer peripherals or printing.

## First-mainline hardware surface

The first-mainline target retains the ordinary upstream paths for Cartesian
X/Y/Z, the extruder, TMC2208 software UART, physical X/Y endstops, BLTouch and
`probe:z_virtual_endstop`, `safe_z_home`, 5x5 `bed_mesh`, hotend and bed heaters
with EPCOS 100K B57560G104F thermistors, part/hotend/mainboard fans, and the
filament switch. The pin mapping is listed in
[`f005-pin-matrix.md`](f005-pin-matrix.md).

The BLTouch uses sensor PC14, control PC13, and offsets X=0/Y=27. The tracked
`z_offset: 2.180` is **QUALIFIED ON DEVICE** for this reference device by the
2026-08-29 cold paper test and successful Fre3nder-B repeat print. The
historical Phase-2 print value was 1.900, calculated from a 1.800
`PROBE_CALIBRATE` result and `homing_origin.z=-0.100`; it is **WIDERLEGT as the
current reference value**. Other printers must calibrate independently. The bed
uses PB2/PC4 and the hotend PA1/PC5. The vendor `temp_offset_flag` is
intentionally omitted.

The reference PID baselines are now published in the mainline configuration
because they were exercised during the controlled bring-up and print:
extruder Kp 20.584 / Ki 1.737 / Kd 60.981 and bed Kp 70.652 / Ki 1.798 /
Kd 694.157. They are reference values, not universal calibration. Pressure
advance and calibrated input-shaper values remain intentionally absent.

The minimal bring-up remains deliberately limited to primary-MCU
communication configuration, printer limits, the three rails, and BLTouch
object loading. It excludes host-MCU/ADXL, heaters, fans, filament, TMC, mesh,
`safe_z_home`, macros, and any motion, homing, probing, or calibration actions.
The required rail/endstop and `probe:z_virtual_endstop` definitions are present
for configuration loading; no action is issued by this file. It remains a
deliberately limited no-action bring-up surface. The separate full mainline
reference configuration is hardware validated on the investigated board.

The mainline reference uses PID control with the values listed above. Heater
behavior was exercised in the controlled bring-up and complete print; PID
refinement remains a future calibration task and these values must not be
treated as universal.

## Removed or deferred Creality surface

The first mainline milestone does not carry `prtouch_v2`, `z_compensate`,
`bl24c16f`, `hx711s`, `dirzctl`, `filter`, `soft_homing`, or `fan_feedback`.
Creality custom macro/tool/metadata integration, UI/cloud coupling, the
nozzle-MCU path, `temperature_sensor mcu_temp`, `temp_offset_flag`, saved
calibration, and macros dependent on those objects are also omitted. PR-Touch
and Z compensation remain optional future open reimplementation work, not a
first-mainline dependency.

The tracked full reference configuration now includes the upstream secondary
`[mcu rpi]` at `/tmp/klipper_host_mcu`, the ADXL345 on `spidev2.0` at 2 MHz
with `axes_map: z,y,x`, and resonance-test limits `accel_per_hz: 50`, point
`117.5,117.5,100`, and `max_freq: 80`. `[input_shaper]` is intentionally empty:
no calibration result is invented or inherited from another system.

The matching kernel/DTS, reproducible Linux-process MCU build, and S59-before-
S60 service path are **SOURCE IMPLEMENTED / STATICALLY CHECKED / BUILT /
OFFLINE CHECKED** against Klipper commit
`0499b30374315f2a9f49fc12808527fc7d0f5cfa`. The manual 2026-09-11 development
build produced and checked the kernel and decoded DTB, built `klipper_mcu` and
validated its MIPS32r2/O32/NaN2008/hard-float ELF ABI and interpreter, and
confirmed the binary, service ordering, PTY/SPI endpoints, and canonical
configuration in the built RootFS. The full artifacts were assembled and their
generated `SHA256SUMS` passed verification.

This build evidence is distinct from the historical F005 dictionary/
`test_klippy.py` validation described above and does not claim that test covered
the secondary MCU or ADXL sections.

On the investigated reference device, the deployed development build has now
qualified the runtime `/dev/spidev2.0` character device, Linux-process
`klipper_mcu`, `/tmp/klipper_host_mcu` PTY, Klippy `[mcu rpi]` communication,
physical ADXL345 SPI communication, and `ACCELEROMETER_QUERY`. The existing
persistent `printer.cfg` was correctly retained during deployment; the four
new sections were copied from the RootFS default for this controlled test
because S60 seeds that default only when no persistent configuration exists.
No automatic configuration migration is implied.

The subsequent RootFS-only development build included Buildroot-native NumPy.
On the investigated reference device, Python 3.12.14 imported NumPy 1.25.0
from the system package path, and `MEASURE_AXES_NOISE` completed with
159.113215 (x), 95.617217 (y), and 90.125327 (z). This is a qualified noise
measurement, not a completed input-shaper calibration. `TEST_RESONANCES`,
`SHAPER_CALIBRATE`, derived shaper frequencies/types, and input-shaping
`SAVE_CONFIG` remain unperformed. The configured `axes_map: z,y,x` remains the
qualified reference mapping, and `[input_shaper]` remains intentionally empty.

OpenKE/NebulaOS provides exact external hardware evidence for the
GPE16/17/18/21 wiring and polarity, but no external binary or service is used;
Fre3nder's hardware result is independently scoped to the investigated
reference device. The BL24C16F/EEPROM/PLR path remains outside this
integration. Exact source provenance and the startup boundary are recorded in
[`x2000-hardware-contract.md`](x2000-hardware-contract.md#adxl345-and-host-mcu-contract).

## What remains open

The staged reference validation established passive thermistors, TMC2208
communication, X/Y endstops, X/Y/Z motion and direction, BLTouch deploy/retract
and probing, XYZ homing, both heaters and thermistors, fans, filament sensing,
50 mm hot extrusion, and a complete heated 5x5-mesh PLA Benchy. Exact scope,
one recoverable Timer-too-close startup shutdown, and remaining calibration
limits are recorded in [`f005-hardware-validation.md`](f005-hardware-validation.md).

This milestone alone does not establish Gate 1 and does not make persistent
recovery or flashing safe. Gate 1 is separately satisfied by the current
evidence review; recovery execution remains documented but not personally
rehearsed. Gate 2 is addressed for the required first-print behavior by
using upstream/keep/drop/deferred classifications; optional Creality
PR-Touch/Z-compensation remains future reimplementation work. No vendor
firmware, binary, private path, or device identity data is redistributed.
