# Reproduce the Phase-2 F005 first-print result

This is the compact reproduction runbook for the investigated Ender-3 V3 KE
F005 board with a GD32F303RET6 MCU. It records a controlled reference result,
not a general conversion procedure. Every persistent or live operation requires
the operator's own authorization, backup set, and recovery decision.

## Scope and boundary

The validated source basis is Klipper
`0499b30374315f2a9f49fc12808527fc7d0f5cfa`. The target contract is:

```text
Stock X2000 userspace -> Mainline Klippy -> /dev/ttyS1 at 230400
    -> Mainline F005/GD32F303 MCU -> printer hardware
```

This applies only to the reference-style F005/GD32F303RET6 hardware described
in [f005-pin-matrix.md](../../docs/f005.md#pin-matrix). Gate 1 / Point of Return is
**SATISFIED** by the current evidence review. Only the separate full-device
vendor / Ingenic / Cloner recovery path remains execution-unverified, not
personally rehearsed, and not guaranteed.

For the F005 MCU, the transition from `FIRMWARE_RESTART` through actual
`/dev/ttyS1` release to immediate `mcu_util -c`/`-g` and exact bootloader/app
identity `mcu0_001_G32-mcu0_004_000` is **QUALIFIED ON DEVICE**. UART release,
not process exit or a particular log line, is the qualified bootloader-window
trigger. The controlled Stock-F005 -> Fre3nder-F005 updater path is also
**QUALIFIED ON DEVICE**: exact Stock identity `mcu0_001_G32-mcu0_005_000`, one
project-initiated `mcu_util -u -f` invocation returning `app_run`, then exact
Fre3nder identity and successful Mainline Klippy configuration.

The project-controlled Stock-image restoration observed on 2026-08-27 remains
historical evidence. It does not qualify the current complete software-only
Fre3nder-B -> Stock return: on 2026-08-29, Stock A booted p7 with its original
`S13mcu_update` and hash-valid Stock image, but Moonraker shut down and Stock
Klipper reported `Lost communication with MCU 'mcu'` and timed out before
`Printer is ready`. That path **REQUIRES QUALIFICATION**. A complete manual
power-cycle recovery to Stock A, exact Stock MCU, 116 commands, complete Stock
configuration, and `Printer is ready` was observed twice on this reference
device: **POWER-CYCLE STOCK RECOVERY: QUALIFIED ON DEVICE (2/2)**.

Reproducibility here means rebuilding the documented source, applying the
published patches, using the operator's own Stock X2000 installation and
recovery material, and repeating the Mainline runtime and staged validation
once the Mainline F005 image is running. MCU source/build/packaging and that
runtime-to-first-print path are reproducible from this public tree. The
historical Stock-to-first-flash bootstrap is not fully copy-paste reproducible,
because its temporary early-boot init/one-shot bridge was not retained. The
actual project-initiated `mcu_util` update invocation and its successful result
are documented. This does not require a bit-identical future build, publication of a tested binary,
vendor firmware or binaries, private backups/identity, Host-MCU/ADXL/input
shaping, or PR-Touch/Z compensation.

## Build the two Mainline components

Follow [build/klipper-f005/README.md](../../build/klipper-f005/README.md) to check
out the pinned source, apply
`patches/klipper/0001-gd32f303-f005-mainline.patch`, build the MCU, and package
the resulting `klipper.bin` with
`scripts/package_f005_firmware.py`. The package is the F005 updater image; do
not substitute an arbitrary raw Klipper image.

The validated historical session used the archived GCC 7.2/NaN2008
`c_helper.so` recorded with the Phase-2 runtime evidence. The current
`build-x2000-chelper` command intentionally produces a
Buildroot/Fre3nder-userspace helper with a legacy-NaN ABI and must not be
substituted into this Stock-X2000 reproduction. The old compiler is no longer a
productive or automatically downloaded build input. Do not overwrite the
Stock Klipper tree.

Apply the passive-UART patch to that working copy:

```sh
git apply <project-root>/research/patches/klipper/0002-x2000-passive-uart-attach.patch
```

`0002` is required for the validated Stock-X2000 UART attach. It opens only
`/dev/ttyS1` at 230400, takes `flock`, requests `TIOCEXCL` while accepting only
`ENOTTY`, configures 8N1 with `CREAD`/`CLOCAL`, disables flow control and
`HUPCL`, and starts Klipper's normal serial queue with fd type `b'u'`. It does
not manipulate RTS/DTR, switch baud, run `stk500v2_leave()`, reconnect, or
probe a bootloader. The ordinary upstream `connect_uart()` path was not the
validated path on the Stock X2000.

Apply `0003-f005-bltouch-no-auto-retry-test.patch` only before Stage C or a
later bring-up stage that loads `[bltouch]`. `0003` is test-only. It changes
the two BLTouch retry guards in
`klippy/extras/bltouch.py` from `retry >= 2` to `retry >= 0`: one in
`_verify_raise_probe()` and one in `_test_sensor()`. Thus a failed validation
stops after its first failed attempt instead of issuing an automatic reset/retry.
Do not treat this patch as a production baseline.

Use the Stock Python environment already present on the X2000 to run the
separate Mainline tree. The reference used the Stock Klippy Python environment,
`/usr/share/klippy-env/bin/python`, not a host package installation. Before
starting it, ensure that no Stock
Klippy or updater process owns `/dev/ttyS1`; the Mainline log must identify
`gd32f303xe`, `CLOCK_FREQ=120000000`, and `SERIAL_BAUD=230400`. On the
reference Stock image, the relevant boot scripts are `S13mcu_update` and
`S55klipper_service`; an operator must prevent both from running for the
temporary Mainline session and verify exclusive UART ownership before launch.
This is temporary runtime isolation, not a permanent host-service install.

For the passive Runtime gate, use `-i /dev/null` with
[`f005-runtime-passive.cfg`](../configs/klipper-f005/f005-runtime-passive.cfg):

```sh
<stock-python> <mainline-tree>/klippy/klippy.py \
  f005-runtime-passive.cfg -i /dev/null -d <klipper.dict> -l <log-file>
```

The Phase-2 passive result was dictionary load, ClockSync,
`allocate_oids count=0`, `finalize_config`, `is_config=1`, `is_shutdown=0`,
READY, and a clean exit. A later full runtime must instead use Klipper's input
PTY option (`-i <pty-path>`); Klipper creates that PTY path and the test feeder
opens it once. For example, a Stage configuration can be launched as:

```sh
<stock-python> <mainline-tree>/klippy/klippy.py \
  <stage-config> -i <pty-path> -d <klipper.dict> -l <log-file>
```

The PTY is an input transport only; no Moonraker or `virtual_sdcard` service is
needed for this Phase-2 test path.

## First flash: documented boundary

The reference first flash used a temporary Mainline image on the X2000, a
controlled disable of the Stock MCU updater and Stock Klippy, a temporary
init/one-shot change to reach the early bootloader window, and exactly one
Stock `mcu_util` flash attempt. The observed updater sequence was:

```text
mcu_util -i /dev/ttyS1 -c
mcu_util -i /dev/ttyS1 -g
mcu_util -i /dev/ttyS1 -u -f <mainline-f005-image>
```

It reported `update:0` followed by `app_run`. There was no automatic retry.
The Stock image header is `mcu0_005_000`; the Mainline updater header is
`mcu0_004_000`.

On 2026-08-27 an initial no-write test stopped Stock Klipper, verified
`/dev/ttyS1` free, and attempted `mcu_util -c`, `-g`, and `-s` directly against
the running Mainline application. Those operations timed out because no reset
into the bootloader had occurred.

A subsequent separately authorized no-write test used Moonraker
`FIRMWARE_RESTART`, released `/dev/ttyS1`, and successfully reached the
Creality bootloader. `mcu_util -c` returned 0, `mcu_util -g` returned
`mcu0_001_G32-mcu0_004_000`, and `mcu_util -s` returned `app_run` with return
code 0. Stock Klipper then reconnected to the unchanged Mainline MCU and
returned to the same known `read_swap_prtouch` error. No erase or firmware
upload occurred.

The Mainline-to-bootloader-to-Mainline roundtrip is therefore qualified on the
reference device. At this intermediate point the Stock firmware write itself
was not yet qualified. Later on 2026-08-27, under separate explicit
authorization, one project-initiated `mcu_util` update invocation restored the
preserved Stock image and Stock Klipper subsequently reached `Printer is ready`,
completing the F005 Mainline-to-Stock qualification. This does not imply
exactly one internal transfer attempt.

**Retained-evidence limitation:** the exact private init/one-shot file contents
and command ordering that opened the first-flash window were not retained in
the available Phase-2 artifacts. This repository deliberately does not publish
a replacement first-flash script: doing so would invent a persistent procedure
that was not independently revalidated. A matching operator must reconstruct
and review that board's Stock-init arrangement locally before using `mcu_util`.
This is the one remaining public reproducibility gap.

After a successful single flash, do not add a separate low-level retry or reset
probe. The post-flash identity check is the passive Mainline Runtime gate: its
log must report `gd32f303xe`, `CLOCK_FREQ=120000000`, and
`SERIAL_BAUD=230400` before any staged hardware action.

## Stage A--F validation

Use [printer-f005-bringup.cfg](../configs/klipper-f005/printer-f005-bringup.cfg)
for no-action parser/connection preparation, the published
[Stage A--E configurations](../configs/klipper-f005/stages/), and
[printer-f005-mainline.cfg](../../configs/klipper-f005/printer-f005-mainline.cfg)
as the successful reference baseline. The historical per-command transcripts
for Stages A--E were not retained; the sequence below is the smallest
reproduction workflow derived from the validated configuration and result, not
a claim that every command is a verbatim historical transcript. Stop on the
first unexpected result; do not automatically retry a stage.

### A. Passive thermistors

Load `stage-a-passive-thermistors.cfg` before enabling motion or outputs.
Use `STATUS` and inspect `hotend_thermistor` and `bed_thermistor` in the Klippy
status/log; PC5 (hotend) and PC4 (bed) must show plausible, stable ambient
values. Stop for an ADC range error, implausible temperature, MCU shutdown, or
any unexpected output command.

### B. TMC, endstops, and bounded motion

Load `stage-b-steppers-endstops-tmc.cfg`. Use `DUMP_TMC STEPPER=stepper_x`,
`stepper_y`, and `stepper_z`; each reference driver reached IFCNT 6. Use
`QUERY_ENDSTOPS` to confirm the active-low X/Y physical endstop polarity, then
perform only one short bounded X, Y, and Z movement at a time with manual
`G91`/`G1` commands. Confirm direction before the next axis; positive Z must
move the toolhead physically upward. PC14 is only the historical raw
configuration placeholder in this stage; its polarity and mechanical meaning
were not yet validated, so Z homing is prohibited. No probe, heater, or
automatic retry belongs to this stage.

### C. BLTouch, homing, and Z calibration

Load `stage-c-bltouch-homing.cfg` with `0003` applied, exercise one
deploy/retract pair with `BLTOUCH_DEBUG`, use `QUERY_PROBE`, and perform the
deliberate manual trigger check. Then run `G28` and `PROBE_CALIBRATE`. The
historical Phase-2 `PROBE_CALIBRATE` result was 1.800. The exact historical Stage-C
pre-calibration value was not retained; the published Stage-C file uses only a
neutral parser placeholder (`z_offset: 0`) and is not printable as-is. Its
first print was initially high; two runtime corrections of -0.05 produced a
cumulative `homing_origin.z=-0.100`. Pinned upstream
`Z_OFFSET_APPLY_PROBE` calculates `new_calibrate = z_offset - offset`, so the
value used by that print was `1.800 - (-0.100) = 1.900`.

That value was retained in `printer-f005-mainline.cfg` for the historical
Phase-2 print; it is not the currently qualified calibration. A
2026-08-29 cold, mesh-cleared paper-test repetition produced `z_offset: 2.180`
after a first residual-heat/active-mesh result of 2.177 (difference 0.003 mm).
`z_offset: 2.180` is **QUALIFIED ON DEVICE** by that reference-device paper test,
and 1.900 is **WIDERLEGT as the current reference value**, not as the then-valid
Phase-2 setting. A complete Fre3nder-B repeat print on 2026-08-29 used the
then-unmodified 1.900 image value plus session-only
`SET_GCODE_OFFSET Z=-0.280` and completed successfully, qualifying the effective
2.180 behavior. The tracked configuration was subsequently updated to 2.180.
For the successful repeat, the Benchy start code creates a fresh mesh with
`BED_MESH_CALIBRATE PROBE_COUNT=5,5`; no previously stored mesh is relied on.

### D. Fans and heaters

Load `stage-d-fans-heaters.cfg`. Confirm each path separately: part fan,
temperature-controlled hotend fan, and mainboard-fan output. Then use stepped,
manually observed hotend and bed
setpoints; return both targets to zero after each observation. The reference
validated the PC5/PA1 hotend and PC4/PB2 bed paths. It does not establish a
universal thermistor calibration or PID tuning.

### E. Filament and extrusion

Load `stage-e-extruder.cfg`. Confirm the filament sensor reports filament.
Heat the hotend with `M109 S240`, then issue one controlled 50 mm relative
extrusion and check direction and
material flow. Stop for a sensor, temperature, slip, direction, or current
anomaly.

### F. Full configuration and first print

Load the complete reference configuration, home with `G28`, and run a heated
5x5 `BED_MESH_CALIBRATE`. The reference print used 55 C bed and 220 C hotend.
It exercised heaters, fans, extrusion, motion, and the filament path. The
complete-print details and reference PID/mesh values are in
[f005-hardware-validation.md](f005-hardware-validation.md).

The initial full-config finalization once produced `Timer too close`, leaving
`is_config=1` and `is_shutdown=1`. There was no concrete host-overload proof.
The reference used one controlled dictionary `reset` from shutdown, waited
10 seconds, and made one deliberate manual retry; that retry and the print
passed. No automatic recovery/retry is part of this runbook. If, and only if,
that exact shutdown state is observed, run the test-only helper once:

```sh
<stock-python> research/scripts/f005_reset_from_shutdown_once.py \
  --klippy-dir <mainline-tree>/klippy
```

It identifies the MCU, checks `is_config=1` and `is_shutdown=1`, permits a
single normal dictionary `reset`, and confirms only that serialqueue submitted
the command. It does not reconnect or wait for a reset response. Wait 10
seconds, then make one deliberate manual runtime retry. Any other state is a
fail-closed stop, not a reason to use `config_reset`, `emergency_stop`, or an
automatic retry.

## Test-only print transport

The first print did not use Moonraker or `virtual_sdcard`. Use
`research/scripts/f005_phase2_sanitize_gcode.py` on a copy of the slicer output,
then hash the sanitized file and use `research/scripts/f005_phase2_pty_feeder.py` against the
Klipper-created input PTY. The feeder checks READY and filament presence, sends
one real command at a time, waits for `ok`, uses longer timeouts for G28,
mesh, M109, and M190, and stops on the first error. It never reconnects or
resends. On abort it attempts `M104 S0`, `M140 S0`, and `M106 S0` even if the
abort signal caused the failure.

```sh
python3 research/scripts/f005_phase2_sanitize_gcode.py <slicer-input.gcode> <stage-f.gcode>
sha256sum <stage-f.gcode>
<stock-python> research/scripts/f005_phase2_pty_feeder.py \
  --port <pty-path> --gcode <stage-f.gcode> --sha256 <printed-sha256>
```

The sanitizer removes only these Stage-F-unsupported commands:

- `EXCLUDE_OBJECT_DEFINE`, `EXCLUDE_OBJECT_START`, `EXCLUDE_OBJECT_END`;
- `SET_GCODE_VARIABLE` with `MACRO=PRINTER_PARAM`;
- `SET_VELOCITY_LIMIT` carrying `ACCEL_TO_DECEL=`; and
- `M73`.

It permits only `BED_MESH_CALIBRATE`, G1, G21, G28, G90, G92, M104/M106/M109,
M140/M190, M220/M221, M83, M84, and ordinary `SET_VELOCITY_LIMIT` unchanged.
`[exclude_object]`, Creality's `PRINTER_PARAM` macro integration,
`display_status`, and the legacy `ACCEL_TO_DECEL` parameter were intentionally
not part of the Stage-F baseline. No Benchy G-code or third-party model is
stored in this repository.

## After reboot and deferred work

The historical Mainline image state must not be generalized into an automatic
return procedure. The 2026-08-29 software-only Fre3nder-B -> Stock handoff
**REQUIRES QUALIFICATION**; the manually power-cycled Stock recovery is the
current **QUALIFIED ON DEVICE** boundary for the reference device. This runbook
still does not provide host-service installation or automatic startup management
and defers Host-MCU/ADXL/input shaping, PR-Touch, Z compensation, UI/cloud
integration, and general printer tuning.
