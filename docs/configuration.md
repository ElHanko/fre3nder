# Configuring Fre3nder

The repository contains generic build inputs and a hardware-validated
**reference** printer configuration. On a running Fre3nder system, user
configuration lives primarily under persistent `/home`; an existing user file
is retained when a new RootFS is installed. Values measured on the
investigated F005/GD32F303RET6 printer, including probe offset, PID, mesh,
and input shaping, require independent calibration on another printer.

## Find the setting to change

| Purpose | Runtime path or input | Owner and persistence |
| --- | --- | --- |
| Klipper printer configuration | `/home/fre3nder/printer_data/config/printer.cfg` | Userdata in HOME; seeded once from the RootFS default if missing |
| Moonraker main configuration | `/home/fre3nder/printer_data/config/moonraker.conf` | Userdata in HOME; seeded once, existing file retained |
| Fre3nder Moonraker fragments | `/home/fre3nder/printer_data/config/fre3nder/*.conf` | Platform/app fragments in HOME; main config needs `[include fre3nder/*.conf]` |
| Fre3nderScreen settings and touch calibration | `/home/fre3nder/.local/share/fre3nderscreen/fre3nderscreen.json` | App data; initialized once from the old regular Fre3nderScreen config if present, otherwise from the signed package default |
| Web frontend selection and installed packages | `/home/.fre3nder/frontend/active` and `/home/.fre3nder/packages/` | Root-managed persistent package state; managed through `fre3nder app` |
| SSH host identity | `/home/fre3nder/.fre3nder/ssh/` | Persistent host identity when persistent root is active |
| Optional local root shell | `/etc/fre3nder/console.enabled` | Root-controlled SYS opt-in; survives ordinary reboots, removed by SYS reset; independent of SSH |
| WLAN and SSH boot provisioning | FAT32 USB root: `wpa_supplicant.conf`, `authorized_keys`, `enable_ssh` | Boot-local inputs copied to volatile `/run`; not baked into a build |
| System code and application payloads | `/opt`, `/usr`, and the writable SYS overlay | Reconstructible system state; reset exposes the immutable RootFS baseline |

The logical HOME/SYS roles and current external ext4 backends are specified in
[storage layout](storage-layout.md). `FRE3NDERHOME` backs `/home`;
`FRE3NDERSYS` backs the writable system OverlayFS. Internal Stock p9/p10 are
not current Fre3nder persistence backends. `/run` and `/tmp` are volatile.

## Configure the printer

1. Start from the installed `printer.cfg` and compare it with the current
   tracked reference
   [`printer-f005-mainline.cfg`](../configs/klipper-f005/printer-f005-mainline.cfg).
   The RootFS default seeds only a missing file; an update does not merge new
   sections into an existing persistent file.
2. Confirm board identity and pin mapping against the
   [F005 pin matrix](f005.md#pin-matrix) before changing pins, motor directions,
   heaters, fans, probe, or the `[mcu]` serial path. The current F005 host
   path is passive `/dev/ttyS1` at 230400 baud. Normal Klippy starts only after
   exact Fre3nder MCU identity classification; a Stock or unknown MCU leaves
   it stopped.
3. Calibrate probe/Z offset, heater PID, bed mesh, and resonance/input-shaper
   values on the actual printer. The reference `z_offset: 2.180` and shaper
   baseline are evidence for one investigated unit, not factory defaults for
   every Ender-3 V3 KE. Preserve a copy of valuable configuration before
   changing it; [backup](backup.md) covers HOME and SYS archives.
4. Validate the edited configuration through Klipper/Moonraker before relying
   on motion or heat. If a new RootFS added default sections, merge only the
   required sections manually into the persistent file; inspect the relevant
   release and [F005 configuration](f005.md) documentation.

The OrcaSlicer preset and its import instructions are in
[`configs/orcaslicer/README.md`](../configs/orcaslicer/README.md). It inherits
OrcaSlicer's built-in KE profile and supplies Fre3nder-specific G-code and
motion-limit overrides.

## Filament changes

The reference configuration provides `PAUSE`, `LOAD`, `UNLOAD`, `PURGE`, and
`RESUME` for Fluidd and the upstream filament switch. The sensor's existing
`pause_on_runout: True` calls the same `PAUSE` as the UI and slicer. Inserting
filament never resumes automatically. The normal workflow is:

`PAUSE` → change filament (`UNLOAD` / `LOAD`) → optional `PURGE` → `RESUME`.

The operator reported successful reference-hardware tests of pause/park, normal
resume, the 300-second heater/motor shutdown, retained print state, recovery
homing, reheating and warm Z remeasurement, mesh/reference restoration, and
completion of a Benchy. Those recovery tests used the former front point,
nozzle X10/Y-12 (BLTouch X10/Y15). A visible seam at the restart is accepted
for this development state. **The new rear point and simplified macro workflow
still require hardware validation; the front-point result does not qualify them.**

The RootFS stages the project-owned `fre3nder_filament_recovery.py` as a
Klipper extra; it does not patch Klipper core. For an existing installation,
manually merge the macro sections, `[fre3nder_filament_recovery]`,
`[idle_timeout]`, and `[delayed_gcode _FILAMENT_POWER_OFF]` from the reference
configuration, and replace the old `CANCEL_PRINT` macro. Keep `[pause_resume]`,
`[virtual_sdcard]` with `on_error_gcode: CANCEL_PRINT`, and the filament sensor.
Do not duplicate sections or overwrite calibration and other user settings.
A RootFS update preserves an existing `printer.cfg`; it does not perform this
merge. Import the updated OrcaSlicer profile only after `START_PURGE` is
available in the installed configuration. If upgrading the preliminary recovery
configuration, replace its `[fre3nder_filament_recovery]` settings with the
current section (remove `required_clearance` and `front_lift`). Replace the
`RESUME` macro and remove the old `RECOVER_PRINT` and `RECOVERY_RESUME` macro
sections. `RECOVER_HOMING` is now a diagnostic command supplied by the extra,
not an additional macro needed for ordinary operation.

During a print:

1. Use `PAUSE`, or let the filament sensor pause the print. Upstream Klipper
   saves the print position and G-code state. The macro retracts 1 mm if hot,
   raises Z by up to 50 mm, and parks left of the print at the start-purge X/Y.
   Repeated `PAUSE` commands keep the original saved state and deadline.
2. Use `UNLOAD` to retract the remaining filament. Release the extruder lever
   for manual removal/insertion; do not disable the motors. The stock board
   shares the stepper-enable signal, so disabling the extruder can also lose
   the axis reference.
3. Insert replacement filament and use `LOAD`. The defaults are 60 mm unload
   and 50 mm load at 5 mm/s. Override the positive distance, for example
   `LOAD LENGTH=40` or `UNLOAD LENGTH=70`. These commands wait for the saved
   print temperature; `TEMPERATURE=<degrees>` selects another suitable
   temperature for that operation. A cold manual pause without a saved heater
   target requires an explicit temperature.
4. Use `PURGE`, optionally `PURGE LENGTH=20 TEMPERATURE=210`. `LENGTH` is the
   total filament length, split equally between the two strokes. Repeat as
   needed and remove the hanging filament at the parked nozzle before resume.
   The print remains paused throughout.
5. Use `RESUME`. It checks the pause, axis reference and enabled filament
   sensor, restores and waits for the original print temperature, unretracts
   in the purge area, returns in XY at clearance height, then lets upstream
   `RESUME` restore the print Z position and G-code/extrusion state. It never
   runs recovery homing while the original reference is valid. After motor
   release or loss of axis reference, `RESUME` selects the two-stage recovery
   path below instead of returning blindly to the object.

The original start purge was inline in the OrcaSlicer preset's
`machine_start_gcode`: X -2.0 / -1.7, Y20 to Y145 and back to Y30, with two
15-mm extrusion strokes at Z0.2 after approaching at Z0.3. The updated preset
calls `START_PURGE TEMPERATURE=...`; the reference configuration's
`_PURGE_LINE` contains the shared strokes. The default start sequence retains
the original positions, feed rates, heating wait and E resets. Existing
exported profiles with the old inline sequence still work unchanged.

Paused `PURGE` reuses that XY area while staying above the paused print by the
configured lift, and at least 5 mm above nominal bed Z. It does not descend to
the old start line. Repeated purges retain the same clearance height rather
than adding another lift each time. The nozzle finishes at X -1.7 / Y30 for
filament removal. All XY travel lifts first; if less than the configured
minimum 2-mm clearance is available near maximum Z, travel is refused and
the print stays paused. Cancel if safe clearance cannot be obtained.

Adjust `_FILAMENT_SETTINGS` in the installed configuration for modified
printers: purge coordinates, extrusion lengths/speeds, Z lift/minimum
clearance, and travel speeds live there. New start-purge and filament-purge
commands share these coordinates. Older inline slicer profiles must be
updated separately if their purge coordinates need to change. Keep the
purge path outside the printed object's area and within configured axis limits.

For the first 300 seconds, the original heater targets and motor reference
remain active. A one-shot timer then turns off **both heaters and all motors**,
without moving the parked head, closing the SD file or cancelling the print.
The normal idle handler also performs this complete shutdown while paused.
The one-shot deadline is measured from the first `PAUSE`; filament operations
and repeated `PAUSE` do not extend it. Configure the positive `pause_timeout`
in `_FILAMENT_SETTINGS` if another interval is needed.

The paused SD file/cursor, upstream `PAUSE_STATE`, original heater targets and
a copy of the active mesh remain in RAM without a pause-duration limit. This
does not survive a Klippy restart, reboot or loss of power. After motor release,
saved coordinates cannot establish the physical position. `LOAD`, `UNLOAD` and
`PURGE` then require successful recovery homing first. An inactive timer
never cancels the job. Only explicit `CANCEL_PRINT` or an actual print error
invokes cancellation. `CLEAR_PAUSE` refuses to discard an active filament pause.

The final `RESUME` and `CANCEL_PRINT` restore the
previous normal idle timeout and cancel the one-shot timer. Cancellation turns
off heaters and motors immediately. Normal idle/print-end shutdown remains
available. Cooling the bed may release or shift the part; no recovery command
can establish adhesion from the saved coordinates.

`CANCEL_PRINT` uses upstream `CANCEL_PRINT_BASE` to close the virtual-SD job and
clear pause. It deliberately omits `SDCARD_RESET_FILE`: virtual-SD error
handling still runs inside the SD command context, where that command is
forbidden. Thus `on_error_gcode` can cancel without masking the original
print error with a second abort error.

### Recovery after heater/motor shutdown

The normal interface uses Fluidd's existing `PAUSE` and `RESUME` actions.
There are no extra recovery buttons, coordinates or confirmation flags.
`RESUME` distinguishes three cases:

- A captured active pause with XYZ still referenced and no recorded motor
  release follows the existing normal reheat/return/resume path in one action.
- A lost reference or recorded motor release requires recovery homing. Once
  automatic recovery has been qualified and enabled as described below, the
  **first `RESUME`** performs that homing and leaves the print paused.
- Missing or inconsistent state, an unqualified automatic recovery path or a
  failed homing sequence refuses continuation with an English console error.

For a long pause on a qualified setup:

1. **Before the first `RESUME`, inspect the print.** It must still adhere to
   the bed without shifting. Check actual clearance under the entire X gantry,
   including possible sag or tilt after motor release. The full X-homing path,
   Y-homing/bed sweep, travel to the probe point, and nozzle/BLTouch descent
   must clear the part, brim, skirt and clips. Otherwise keep the print paused
   or use `CANCEL_PRINT`.
2. Press **`RESUME`**. It runs the existing `RECOVER_HOMING` implementation:
   check the retained software state, home X → Y → Z at the configured point,
   lift locally, restore and wait for the original bed/hotend temperatures,
   then measure Z again while warm. It restores the original Z frame and mesh
   and raises Z at that point to the saved park height. **It does not resume
   the print or return to the object.** The console requests a visual check:
   `Recovery homing completed. Check print adhesion, print position and toolhead
   clearance along the return path, then press RESUME again to continue.`
3. If needed, use `UNLOAD`, `LOAD` and optional `PURGE` in the existing purge
   area. **Inspect adhesion and print position again after reheating, and check
   the entire return path**, including the eventual descent onto the print.
4. Press **`RESUME` again**. This separate action confirms the requested visual
   inspection. Software rechecks the pause, XYZ reference, unchanged mesh,
   original stable heater targets and enabled filament sensor, then uses the
   existing return/unretract and upstream resume sequence. The paused SD file
   continues at its saved cursor with its original extrusion and G-code state.

The software cannot detect adhesion, a shifted part, sag, obstructions or
collision freedom. Neither a command nor a qualified configuration establishes
unknown mechanical conditions for a particular print. No measured-clearance
value or technical confirmation parameter is required during ordinary use.

Another motor release or loss of XYZ reference invalidates recovery readiness.
The next `RESUME` must home again and still leaves the print paused; it cannot
reuse stale success or bypass recovery through an ordinary `G28`. A failed
homing attempt latches an error: further `RESUME` calls **do not retry its
motion automatically**. The snapshot remains available as far as Klipper can
retain it. Inspect and diagnose explicitly with `RECOVER_HOMING`, or use
`CANCEL_PRINT`. A successful diagnostic retry clears that failure. `RESUME`
without an active captured pause is rejected; repeated presses after a print
has resumed do not restore a discarded snapshot or start another homing cycle.

There is no fixed 50-mm recovery-clearance requirement. `PAUSE` still requests
its configured lift (default 50 mm), capped by Z maximum. Software requires a
recorded raised park with at least the existing `min_lift` (default 2 mm) and
a return height above the newly probed position. These are commanded-coordinate
checks, **not a measurement of actual clearance after motor release**. A partial
lift may be usable only when the actual complete path is clear. A refused or
insufficient park blocks recovery.

### Recovery point and validation boundary

The default in `[fre3nder_filament_recovery]` is:

```ini
home_xy_position: 10, 178
automatic_recovery: False
probe_lift: 8
travel_speed: 20
```

`home_xy_position` specifies the **nozzle** position. With the reference
BLTouch X0/Y+27 offsets, nozzle X10/Y178 puts the probe at **X10/Y205, rear
left on the plate**, bringing the bed far forward. This candidate **has not
been validated on hardware**. Validate its physical reach, bed/gantry sweep, probe
contact, repeatability after reheating, and return path before relying on it.
Adapt the position for modified printers and requalify it. The previously
tested front point can be configured as `10, -12`; neither point is guaranteed
clear for every printed object.

**Automatic recovery is disabled by default**, even though the candidate passes
software geometry checks. Enable `automatic_recovery: True` in the installed
configuration only after hardware validation of the selected point, the complete
homing/bed/return paths and warm Z/mesh restoration. Reset it to `False` when
changing the point or modifying the machine until that setup is requalified.
Without this qualification, an ordinary `RESUME` after reference loss refuses
before any homing or return movement; it explains that automatic recovery is
disabled pending hardware validation. Ordinary pauses with valid references
continue to work.

`RECOVER_HOMING` remains separately callable for deliberate, supervised
hardware qualification and diagnosis. It can run while automatic recovery is
disabled, so inspect and clear the complete paths before calling it. It uses
the same technical checks and homing implementation as `RESUME`, leaves the
print paused and requests the same inspection before a later `RESUME`. Calling
it is not itself evidence of hardware qualification and is not part of the
normal user workflow.

The software checks both nozzle coordinates against the configured axis limits
and the offset-adjusted BLTouch point against the saved measured mesh rectangle
(reference X5–215/Y10–215). The old front-only `y < 0` restriction is replaced
by the full Y-axis bounds. These checks permit the rear candidate without
removing the mesh, probe-offset, finite-coordinate or X-axis checks. They do
not establish that the probe is physically on unobstructed bed.

Normal `G28` and `safe_z_home` are unchanged. Recovery invokes the pinned
upstream native homing handler for each axis to avoid the ordinary unreferenced
Z hop and centre move. It moves only X/Y while Z is unreferenced; no guessed Z
or `SET_KINEMATIC_POSITION` is used. A normal `G28` after motor
release does not establish recovery readiness. Only the recovery sequence can
restore the saved mesh frame before a later `RESUME` continues the print.

Missing snapshots, changed SD files/cursors or saved print state, missing or
changed meshes, configured zero-normalization, shifted meshes, changed probe
offsets or fade settings, unsupported geometry, and unsuitable saved print
temperatures block recovery. Homing failures turn heaters/motors off and retain
the paused snapshot. The original unshifted 5x5 mesh must still belong to this
job and its original homing/thermal frame; retaining identical data does not
prove unchanged physical geometry. A Klippy restart, reboot or power loss
removes the in-memory recovery state.

For this reference, `probe_finalize()` stores already calibrated `bed_z` values
in the original raw homing frame because no `zero_reference_position` is set.
Let `M` be the saved interpolated mesh and `R` the **probe** position at the
edge. After real warm edge homing, the coordinate conversion is:

```text
delta = M(R.x, R.y)
original_raw_Z = edge_homed_raw_Z + delta
```

Native probe homing has already accounted for BLTouch `z_offset`; it is not
subtracted again. The implementation calls upstream `ZMesh.calc_z()` on the
original interpolated table. It does not use the nearest 5x5 cell or assume
that the centre sample is the normal reference: mesh rows are Y10, 61.25,
112.5, 163.75 and 215, whereas the normal probe home is at Y110. Subtracting
`M(110,110)` would incorrectly shift the retained raw frame whenever the
interpolated value there is nonzero. A zero-normalized mesh has lost the raw
constant needed here and is deliberately unsupported.

Mesh compensation is disabled during raw homing. The native Z coordinate is
translated only after actual probing, then the original mesh/fade is restored
for motion. Neither `SET_GCODE_OFFSET Z` nor `PAUSE_STATE` is changed, avoiding
double compensation. This follows the pinned upstream
[`probe_finalize`/`ZMesh`](https://github.com/Klipper3d/klipper/blob/7bc4d09465d31cd30fc0822e8d0abe02cc8c547f/klippy/extras/bed_mesh.py),
[`ProbeResult`](https://github.com/Klipper3d/klipper/blob/7bc4d09465d31cd30fc0822e8d0abe02cc8c547f/klippy/extras/manual_probe.py)
and [native homing](https://github.com/Klipper3d/klipper/blob/7bc4d09465d31cd30fc0822e8d0abe02cc8c547f/klippy/extras/homing.py)
semantics. Interpolation is still an approximation. Reheating does not prove
that the bed, probe offset, gantry or part returned to its original geometry;
measure that repeatability during hardware qualification.

## Configure services and access

Moonraker's main configuration must include the exact line
`[include fre3nder/*.conf]` for platform and managed-app fragments to load.
Newly seeded defaults include it; older persistent files are **not** rewritten.
The [app guide](apps.md) explains package and web ownership. A legacy
`fre3nder/fluidd.conf` needs a separate, controlled one-time removal during
device migration; new Fluidd packages do not create that updater fragment.
[Moonraker runtime](moonraker.md) describes its baseline
and the current updater limit.

Fre3nderScreen uses its own persistent JSON settings, while framebuffer, NS2009
input discovery, and backlight are platform hardware paths. See
[display integration](display.md) for runtime behavior and physical interfaces.
The [local root console](display.md#optional-passwordless-local-root-shell) is
disabled until explicitly enabled. Its setup creates `/etc/fre3nder/` when
missing and establishes the required ownership and permissions.

The boot-local FAT32 provisioning path can provide WLAN configuration and
public-key SSH access without storing credentials in the repository. The
`enable_ssh` marker is separate from `authorized_keys`; WLAN setup alone does
not enable SSH. Existing provisioned inputs are copied under `/run` for that
boot. The [X2000 architecture](x2000-open-host-architecture.md#provisioning-and-administrative-access)
explains the access boundary; [networking](networking.md) specifies the current
input checks and paths. Keep credentials and device-specific values out
of public documentation and build artifacts.

Source identities and build-time versions live in
[`configs/x2000/sources.json`](../configs/x2000/sources.json); they are build
inputs, not user calibration files. Do not alter the F005 firmware manifest,
boot selector, partition layout, factory identity, or the RootFS trust anchor
as a routine configuration change. Refer to [installation](installation.md),
[storage](storage-layout.md), and [recovery](recovery.md) for those boundaries.
