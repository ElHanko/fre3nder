# F005/GD32F303 reference hardware validation

This report records one controlled validation sequence on the investigated
Ender-3 V3 KE F005 board with GD32F303RET6, using upstream Klipper commit
`0499b30374315f2a9f49fc12808527fc7d0f5cfa` and the project F005 port. It is a
reference-system result, not a guarantee for other KE revisions or a substitute
for independent calibration.

## MCU and host contract

The Mainline MCU identified as `gd32f303xe` at 120 MHz over `/dev/ttyS1` at
230400 baud. The intended architecture is:

```text
X2000 host / print computer
    -> UART 230400
Mainline F005 / GD32F303 MCU
    -> validated printer hardware
```

Only the main MCU and the existing host runtime were required. A separate
nozzle-MCU instance, Creality PR-Touch modules, or the private PTY feeder are
not part of the production architecture. The feeder was temporary test
scaffolding and accepted only a sanitized G-code stream after removing
unsupported slicer/UI commands (`EXCLUDE_OBJECT_*`,
`SET_GCODE_VARIABLE MACRO=PRINTER_PARAM`, `ACCEL_TO_DECEL`, and `M73`).

## Staged results

The following results are from the single staged bring-up sequence. Commands
were issued only within their stated gate.

| Stage | Result | Observed scope |
| --- | --- | --- |
| A | PASS | PC5 hotend and PC4 bed thermistors returned plausible passive readings. |
| B | PASS | TMC2208 X/Y/Z communication; IFCNT reached 6; X/Y endstops; bounded X/Y/Z motion and direction; positive Z moved physically upward. |
| C | PASS | BLTouch deploy, retract, query, deliberate manual trigger, XYZ homing, and `PROBE_CALIBRATE`. |
| D | PASS | Part fan, hotend heater/sensor, bed heater/sensor, temperature-controlled hotend fan, and mainboard-fan command path. |
| E | PASS | Filament detected, `M109 S240`, and 50 mm controlled hot extrusion. |
| F | PASS after one controlled retry | Full configuration, G28, heated 5x5 mesh, and complete PLA Benchy. |

Stage C produced a historical `PROBE_CALIBRATE` result of 1.800 mm while the
session's homing origin was `-0.100`. In the pinned upstream Klipper semantics,
`Z_OFFSET_APPLY_PROBE` computes the permanent value as
`z_offset - homing_origin.z`; the value used for the successful Phase-2 print
was therefore `1.800 - (-0.100) = 1.900`. This records the mechanical state of
that run; it is neither a universal value nor the currently qualified reference
calibration.

On 2026-08-29, after an aborted integrated test print, the reference device was
calibrated again. An initial `PROBE_CALIBRATE` with residual heat and an active
mesh produced `z_offset: 2.177`. The controlled cold repetition raised the
toolhead, used `BED_MESH_CLEAR` (which reported no probed bed), observed a
26.4 C bed and 27.7 C hotend, homed, and probed contact at
`110,110,z=0.030000`. Paper was trapped at Z=-0.300 and moved with light,
even resistance at Z=-0.250; `ACCEPT` produced `z_offset: 2.180`.
The 0.003 mm difference supports the following reference-device result:
**`z_offset: 2.180` is QUALIFIED ON DEVICE by a paper test.**

Consequently, `z_offset: 1.900` is **WIDERLEGT as the current reference value**,
but not as a description of the historical successful Phase-2 print. It was
still the tracked value during the first 2026-08-29 integration attempt, not a
current calibration recommendation; the later successful repeat and separate
configuration update are recorded below. The successful Benchy start sequence
creates a fresh 5x5 mesh with `BED_MESH_CALIBRATE PROBE_COUNT=5,5`; no previously
stored mesh is relied on.

The validated reference bed-mesh settings are speed 350, bounds
`5,10` to `215,215`, 5x5 points, fade start 1, fade end 10, fade target 0, and
horizontal move height 8. The observed contact values ranged from -0.1625 to
+0.3200; these are measurements from this run, not a universal mesh.

The reference PID baseline used by the successful run is:

```text
extruder:   Kp=20.584  Ki=1.737  Kd=60.981
heater_bed: Kp=70.652  Ki=1.798  Kd=694.157
```

These values are derived from known F005/Creality configuration evidence and
were exercised during the run. They are reference values only; PID refinement
and recalibration remain appropriate if hardware or sensor conditions differ.

## Complete print

One complete PLA Benchy was printed with bed 55 °C and hotend 220 °C. The
archived run started at `2026-08-20 21:50:25` local time and completed at
`22:38:46` (about 48 minutes 21 seconds), processing more than 128,000
G-code commands. It included G28 and a heated 5x5 bed mesh. Heaters, fans,
extrusion, motion, and the filament path all operated during the print. The
end commands set both heater targets to zero.

The hotend briefly overshot to approximately 224.5 °C before settling. No MCU
shutdown, communication failure, lost step, layer shift, or command error was
observed during the successful print. The result was a complete, usable
Benchy. The overshoot is a future PID-refinement item, not a Phase-2 blocker.

## 2026-08-29 integrated Fre3nder-B requalification

The historical Benchy stream and sanitizer output were reproduced for a
Fre3nder-B end-to-end test after the B host, Fre3nder MCU, Klippy, complete
configuration, PTY/UART ownership, and an armed Stock-A recovery selector were
observed. The operator aborted the first layer after hearing a scraping or
dragging sound. The feeder performed its safe stop and set hotend, bed, and fan
targets to zero; no UART or MCU communication failure was observed.

The earlier possible nozzle-to-bed-collision interpretation is **WIDERLEGT / not
supported by the later measurements**. The G-code requests Z=0.200 for both the
purge line and first layer (0.20 mm layer height, 0.50 mm first-layer width).
With the then-persistent 1.900 configuration instead of the newly measured
approximately 2.180 offset, the nozzle baseline was approximately 0.280 mm
higher than Klipper assumed. Ignoring the local bed-mesh correction, requested
Z=0.200 therefore corresponds to a baseline physical gap of approximately
0.480 mm.
A too-high first layer is strongly supported; that the sound was dragged,
poorly adhered filament remains an **INFERENCE**.

No `SAVE_CONFIG` was issued for the successful repeat. At that time the image
configuration still contained `z_offset: 1.900`; the session-only
`SET_GCODE_OFFSET Z=-0.280`, with base and homing Z confirmed as `-0.280000`,
emulated the approximately 2.180 probe offset. Klipper's semantics for this
runtime offset were checked against the exactly pinned upstream source before
the print.

The complete repeat print then finished successfully. The 2.177 / 2.180 paper
tests, the temporary effective offset, and that completed print establish
**`z_offset: 2.180`: QUALIFIED ON DEVICE** for this reference device. The
separate tracked configuration was subsequently updated to 2.180. The aborted
first attempt remains a historical controlled abort; its explanation as dragged
poorly adhered filament remains an **INFERENCE**, not a demonstrated cause.
The **FRE3NDER-B END-TO-END PRINT: QUALIFIED ON DEVICE** closes this
requalification.

## One startup shutdown and retry

During the first full-configuration finalization, Klipper reported one
`Timer too close` MCU shutdown. The archived host evidence contains no concrete
overload diagnosis. The shutdown was cleared by exactly one controlled MCU
reset, followed by one deliberate manual retry; the retry completed the full
validation and print successfully. This event is retained as an observed
runtime fact, not hidden as a clean first attempt and not treated as an
unresolved project blocker.

## Scope and boundaries

This demonstrates the required first-print hardware surface on the investigated
reference: the upstream MCU port, the primary UART, thermistors, TMC2208
software UART, endstops, motion, BLTouch/probe, homing, mesh, heaters, fans,
filament sensing, extrusion, and a complete print.

The following remained outside this historical milestone: Host-MCU/ADXL and
input shaping, Creality PR-Touch and `z_compensate`, automatic nozzle/pressure
calibration, vendor UI/cloud integration, and any persistent recovery or
rollback claim.
PR-Touch/Z compensation are optional future open reimplementation work, not
required for the validated first print.

## 2026-09-11 Host-MCU/ADXL source integration

After the hardware-validation milestones above, Fre3nder added a reproducible
upstream Linux-process MCU and onboard-ADXL345 source path. The project DTS
models software SPI as SCK GPE16 active high, MOSI GPE17 active high, MISO
GPE18 active high, and CS GPE21 active low, with one chip select and a stable
`spi2` alias for `/dev/spidev2.0`. The values are attributable to OpenKE/
NebulaOS commit `95f770a858a1076f7ffdb6b4541181034862f57e`, where this wiring and
polarity were hardware-qualified. Fre3nder verified the binding, GPIO polarity,
bus-alias, and spidev behavior statically against its exactly pinned Linux
6.6.18 SDK source.

On 2026-09-11, the manual development build
`scripts/build-x2000 --develop --kernel-build` completed successfully. Its
manifest records version `2026.2.a`, development artifact mode, a dirty project
worktree, Linux `6.6.18-rt23`, Buildroot `2025.02.17`, and pinned upstream
Klipper commit `0499b30374315f2a9f49fc12808527fc7d0f5cfa`. This is development
evidence, not a clean release qualification.

The build gates confirmed the effective SPI kernel configuration and decoded
the generated DTB to check the `spi2` alias, `spi-gpio`, the spidev-compatible
child, and 2 MHz maximum frequency. The pipeline built and stripped the
Linux-process `klipper_mcu` with the Buildroot userspace toolchain and checked
its 32-bit little-endian MIPS32r2/O32/NaN2008/hard-float ABI, interpreter, and
`libc.so.6` dependency. RootFS checks confirmed the executable at
`/usr/bin/klipper_mcu`, mode `0755`, the S59-before-S60 service path,
`/dev/spidev2.0`, `/tmp/klipper_host_mcu`, the `-r -I` launch, and the canonical
configuration containing `[mcu rpi]` and the ADXL/resonance sections. Kernel,
DTB, RootFS, and full artifacts were produced, and every entry in the generated
full-artifact `SHA256SUMS` passed `sha256sum -c`.

The source and build state is therefore **SOURCE IMPLEMENTED / STATICALLY
CHECKED / BUILT / OFFLINE CHECKED**. No printer was accessed for that build
qualification.

The resulting development kernel and RootFS were subsequently installed on the
investigated reference system through the established `scripts/deploy-x2000`
path. It reported `KERNEL_P6=PASS`, `ROOTFS_P8=PASS`,
`SYSTEM_PERSISTENCE_RESET=PASS`, and `DEPLOY_X2000=PASS`. Complete readback and
SHA-256 verification passed for p6 and p8, and Stock p5 and p7 remained
unchanged. After boot, `/run/fre3nder-root/status` was `active`, the active root
was `/dev/mmcblk0p8`, and the final selector was `STOCK_A`.

On that system, `/dev/spidev2.0` existed as a character device,
`/usr/bin/klipper_mcu -r -I /tmp/klipper_host_mcu` was running, and
`/tmp/klipper_host_mcu` linked to `/dev/pts/0`. After the new `[mcu rpi]`,
`[adxl345]`, `[resonance_tester]`, and `[input_shaper]` sections were copied
from the built-in default into the already-existing persistent `printer.cfg`,
Klippy reported real Host-MCU traffic. `ACCELEROMETER_QUERY` then returned:

```text
accelerometer values (x, y, z):
8886.707777, 0.000000, 740.205942
```

This qualifies the Fre3nder `spi-gpio` path, `/dev/spidev2.0`, Linux-process
MCU, host PTY, Klippy `[mcu rpi]` connection, physical ADXL345 SPI
communication, and `ACCELEROMETER_QUERY` **ON THE INVESTIGATED REFERENCE
DEVICE**. It is not a result for other hardware revisions.

A subsequent RootFS-only development build included Buildroot's native
`python-numpy` package. The first incremental run adopted the compatible
markerless Buildroot output (`ADOPTED`), the next reported a fingerprint-matched
cache hit (`HIT`), and the idempotent Moonraker post-build path completed
successfully. The final
artifact checks reported `build-manifest.json: OK`, `buildroot.config: OK`, and
`rootfs.squashfs: OK`.

The RootFS-only deployment kept the existing kernel (`KERNEL_P6=SKIPPED`),
wrote and verified p8 (`ROOTFS_P8=PASS`), reset system persistence while
retaining the qualified userdata boundary (`SYSTEM_PERSISTENCE_RESET=PASS`),
booted from `/dev/mmcblk0p8`, restored `STOCK_A`, and ended with
`DEPLOY_X2000=PASS`. On the investigated reference device, Python 3.12.14 then
imported NumPy 1.25.0 from
`/usr/lib/python3.12/site-packages/numpy/__init__.pyc`.

The subsequent sensor query returned:

```text
accelerometer values (x, y, z):
8580.269578, -296.082377, 592.164754
```

`MEASURE_AXES_NOISE` also completed successfully:

```text
Axes noise for xy-axis accelerometer:
159.113215 (x), 95.617217 (y), 90.125327 (z)
```

This qualifies native RootFS NumPy import and `MEASURE_AXES_NOISE` **ON THE
INVESTIGATED REFERENCE DEVICE**. `TEST_RESONANCES`, `SHAPER_CALIBRATE`, derived
input-shaper frequencies and types, and input-shaping `SAVE_CONFIG` remain
unperformed and unqualified. The tracked `[input_shaper]` section remains empty;
no shaper result has been determined or saved.

The prior isolated `Timer too close` event belongs to the historical
primary-MCU startup described above; there is no evidence connecting it to the
now-qualified Host-MCU communication path.

Exact external-source links and the inspected upstream startup semantics are
recorded in
[`x2000-hardware-contract.md`](x2000-hardware-contract.md#adxl345-and-host-mcu-contract).

Gate 1 / Point of Return is **SATISFIED** by the current evidence review. The
vendor recovery path is documented and the Boot-ROM entry is known, but
destructive recovery and a complete return to Stock have not been personally
rehearsed on this device. The recovery route is not guaranteed, and this report
does not authorize persistent work.

For the F005 MCU, `FIRMWARE_RESTART` -> actual release of `/dev/ttyS1` ->
immediate `mcu_util -c`/`-g` and the exact bootloader/app identity
`mcu0_001_G32-mcu0_004_000` are **QUALIFIED ON DEVICE**. Actual UART release is
the qualified bootloader-window trigger; process exit or a particular log line
is not. The Stock-to-Fre3nder updater path is also **QUALIFIED ON DEVICE**:
exact Stock identity `mcu0_001_G32-mcu0_005_000`, one project-initiated
`mcu_util -u -f` invocation with `app_run`, followed by an independent exact
Fre3nder identity `mcu0_001_G32-mcu0_004_000` and successful Mainline Klippy
configuration.

The earlier 2026-08-27 project-controlled Stock-image restoration remains a
historical successful observation. It does not qualify the current full
software-only Fre3nder-B -> Stock return. In the 2026-08-29 attempt, the
Stock-A selector, p7 boot, original `S13mcu_update`, and hash-valid original
Stock image were all correct, but Stock Klipper reported `Lost communication
with MCU 'mcu'`, Moonraker shut down, and reconnects timed out before `Printer
is ready`. Therefore that complete software-only path **REQUIRES
QUALIFICATION**.

A manual full power-cycle subsequently recovered Stock A on p7 with the exact
Stock MCU, 116 commands, complete Stock configuration, and `Printer is ready`.
This was observed twice on the investigated reference system:
**POWER-CYCLE STOCK RECOVERY: QUALIFIED ON DEVICE (2/2)**. It is the presently
qualified complete Stock recovery boundary, not a guarantee for other devices;
the missing software-only qualification does not block current development
while that recovery boundary is retained.

## 2026-08-30 open bidirectional F005 product path

The following F005-only sequence is **QUALIFIED ON DEVICE** on the investigated
reference system. It used the open production helper and flasher; no
`mcu_util` process was observed. The new product files were supplied
non-persistently from `/run` for this test.

```text
previously qualified Fre3nder 004
-> open Fre3nder -> Stock path
-> independent exact Stock 005 identity
-> product-helper dry run (no reset, no flash)
-> product-helper --write
-> Stock dictionary reset and UART close
-> one-second wait
-> open bootloader handshake, identity, sector query, one transfer, app_start
-> independent exact new Fre3nder identity
```

The write run used the exact Stock runtime identity
`38d96adc-dirty-20231016_135251-longer-virtual-machine`, then the bootloader
identity `mcu0_001_G32-mcu0_005_000`. It completed with the new Fre3nder image:

```text
runtime:  ?-20260830_120730-cde6ec7a76a4
identity: mcu0_004_000
size:     22528 bytes
SHA-256:  7035a193779dc070eed540052eadd9db064fd48cee9e45dedc0cb0de73711aec
```

The helper performed no automatic retry or recovery. This qualifies the bounded
F005 transitions, including the open Stock -> Fre3nder path. At this stage, the
test did not yet qualify installation or boot of a newly built complete
Fre3nder RootFS/release image; that later qualification is recorded below.
Historical `mcu_util` evidence above remains a record of the earlier path; any
existing persistent vendor tool was not modified by this run.

## 2026-08-30 current-main RootFS installation qualification

After the open F005 product path was qualified, the complete current-main
RootFS integration was built and deployed separately on the investigated
reference system.

The tested source state was commit
`c4c6fa18e659a82ada32c708720202a5ad6592ac`, described as
`2026.1-1-gc4c6fa1`, with embedded `VERSION=2026.1`. It was therefore an
untagged current-main test build, not another public `2026.1` release.

The tested xz-compressed SquashFS artifact was 31760384 bytes with SHA-256
`5ac3a01985789476f0db73fbb2091f3b7fbfcce98578392c6c7c1f14abfbddf2`.
Offline inspection confirmed the expected F005 product helper, MCU helper,
open bootloader module, release manifest, persistence integration, and Klipper
startup gate. `mcu_util` was absent from the immutable RootFS, and no product
runtime dependency on `research/` or `local/` was present.

The then-established `scripts/deploy-x2000-rootfs` path changed the selector
from DEVELOP_B to STOCK_A, booted Stock A from p7, wrote the new RootFS to p8,
performed a complete artifact-length readback with an exact SHA-256 match,
selected DEVELOP_B, booted the newly written Fre3nder B from p8, and finally
restored the selector to STOCK_A.

The deployment helper reported `B->A->B deployment: PASS`. The final running
root was `/dev/mmcblk0p8`, while the selector was deliberately left at
`STOCK_A` as the established fallback state for the next boot.

Post-boot inspection confirmed a read-only SquashFS root on p8,
`VERSION=2026.1`, active `/persist/system` and `/persist/userdata`, the exact
expected F005 product-file hashes, absence of `mcu_util` from the immutable
RootFS, `KLIPPER_STATUS=active`, a live Klippy process, and active persistence.

The installed F005 manifest retained runtime
`?-20260830_120730-cde6ec7a76a4`, firmware size 22528 bytes, firmware SHA-256
`7035a193779dc070eed540052eadd9db064fd48cee9e45dedc0cb0de73711aec`,
and bootloader identity `mcu0_001_G32-mcu0_004_000`.

`/run/fre3nder-klipper/mcu-state.log` existed but was empty after this boot, so
no new direct post-boot MCU-version read is claimed from that file. Immediately
before deployment, the MCU had independently identified as that exact qualified
Fre3nder runtime. The RootFS deployment did not write the MCU, and the normal
fail-closed Klipper startup gate subsequently completed with Klipper active and
its process alive. These observations remain separate evidence statements.

No motion, heater operation, MCU firmware write, or additional full print was
required for this RootFS installation gate because the printer hardware and
configuration path had already been qualified separately and were unchanged.

**FULL CURRENT-MAIN ROOTFS INSTALL: QUALIFIED ON DEVICE.**

At this qualification stage the hostname remained `(none)`. Host naming was
therefore recorded as a separate open product requirement. That historical
observation remains valid for this specific RootFS build; the requirement was
implemented and qualified in the later full kernel-plus-RootFS installation
record below.

## 2026-08-30 full current-main kernel and RootFS installation qualification

A later complete X2000 build was produced from clean project commit
`833cbd43132e5a818a422f25d9478cd6b3f76123`, described by Git as
`2026.1-4-g833cbd4`. Its embedded canonical project version remained `2026.1`,
so this was an untagged current-main qualification build rather than a new
public release.

The build manifest recorded that exact project commit and a clean worktree.
All generated checksums passed before hardware installation.

The installed Slot-B artifacts were:

- `kernel.uImage`: 4878400 bytes, SHA-256
  `5d350222ae07efb710aaeb4f43f8753180d0e04ea6f74ab687089fd07fdc7e6f`;
- `rootfs.squashfs`: 31760384 bytes, SHA-256
  `6cecb56bafd931874d296d81089d20596632cb342a0bd605e723bddfe83b7b62`.

The kernel was Linux `6.6.18-rt23`. The built DT selected the Ender-3 V3 KE
platform and the explicit Slot-B command line
`root=/dev/mmcblk0p8 rootwait rootfstype=squashfs ro`.

Installation began from Stock A on p7 with the exact Stock-A selector and with
p6 and p8 unmounted. The new kernel was written only to p6 and the new RootFS
only to p8. Both writes were followed by complete artifact-length readback and
exact SHA-256 verification. Stock p5 and p7 were read before and after the
operation and remained byte-for-byte unchanged.

After selecting DEVELOP_B and rebooting, the reference system booted the new
p6 kernel and p8 RootFS successfully. Post-boot acceptance confirmed:

- active root p8 with the expected read-only SquashFS command line;
- Linux `6.6.18-rt23`;
- `VERSION=2026.1`;
- hostname `fre3nder`, including the active kernel hostname;
- active persistence;
- active Klipper.

The selector was then restored from DEVELOP_B to the exact STOCK_A state while
Fre3nder remained running from p8.

This qualifies the full current-main kernel-plus-RootFS installation and the
hostname requirement on the investigated reference system. It does not by
itself constitute a new complete print qualification of this exact kernel
artifact.

**FULL CURRENT-MAIN KERNEL + ROOTFS INSTALL: QUALIFIED ON DEVICE.**

**HOSTNAME `fre3nder`: QUALIFIED ON DEVICE.**

## 2026-09-11 resilient startup and automatic Stock-to-Fre3nder qualification

A development RootFS containing passive-UART v2, bounded Moonraker process
cleanup, and the opt-in automatic Stock-to-Fre3nder F005 startup path was built
and installed on the investigated reference system.

The deployed RootFS was 58085376 bytes with SHA-256
`2f0760d69531ff2417ca8c6295e6b730350e77e7297da003696470ea7b5c2bde`.
It was written from Stock A on p7 to inactive p8. Artifact readback passed,
Stock p5 and p7 remained unchanged, Fre3nder booted from p8, and the selector
was restored to `STOCK_A`. `deploy-x2000` reported `DEPLOY_X2000=PASS`.

### Passive UART v2

Exactly one `FIRMWARE_RESTART` was issued. Three passive identify attempts
timed out before a later automatic attempt identified the exact qualified
Fre3nder MCU and returned the printer to ready without a manual Klippy restart.

**X2000 PASSIVE UART V2 AUTOMATIC RECONNECT: QUALIFIED ON DEVICE.**

### Moonraker startup cleanup

The installed RootFS ran exactly one Klippy process and exactly one Moonraker
process. Moonraker reached `active`, and no new SQLite insertion errors were
observed.

**MOONRAKER BOUNDED STARTUP/CLEANUP: QUALIFIED ON DEVICE.**

### Opt-in automatic Stock -> Fre3nder transition

The persistent opt-in marker was a regular seven-byte file containing exactly
`enabled` without a trailing newline. The RootFS itself did not pre-create the
marker.

After a complete power-cycle, unchanged Stock `S13mcu_update` successfully
handshook with `/dev/ttyS1`, reported `mcu0_001_G32-mcu0_004_000`, selected
`mcu0_001_G32-mcu0_005_000.bin`, and completed `fw_update`.

Stock Klipper then identified the expected runtime
`38d96adc-dirty-20231016_135251-longer-virtual-machine`.

Fre3nder B was then selected and booted without manual MCU or service
intervention. S60 recognized the supported Stock runtime and valid opt-in.
The transition log reported:

    f005-stock-to-fre3nder: transition-complete

After the transition:

- Klipper service status was `active`;
- Moonraker service status was `active`;
- Klipper reported `Printer is ready`;
- MCU version was `?-20260830_120730-cde6ec7a76a4`;
- `bytes_retransmit` was 0;
- `bytes_invalid` was 0;
- `retransmit_seq` was 0.

**AUTOMATIC OPT-IN STOCK -> FRE3NDER HOST/MCU TRANSITION:
QUALIFIED ON DEVICE.**

### Remaining warm-reboot boundary

A separate warm X2000 reboot into Stock did not reset the F005 into a state in
which unchanged Stock successfully replaced the Fre3nder application. On the
following Fre3nder boot, the exact qualified Fre3nder MCU was still
identifiable but was in firmware shutdown. Klipper reported
`Can not update MCU 'mcu' config as it is shutdown`.

A subsequent complete power-cycle allowed unchanged Stock `S13mcu_update` to
perform the successful 004 -> 005 update described above.

The full-power-cycle Stock recovery boundary therefore remains qualified. The
software-only Fre3nder -> Stock warm-reboot handoff remains
**REQUIRES QUALIFICATION**. The shutdown state is recorded without assigning an
unproven cause.
