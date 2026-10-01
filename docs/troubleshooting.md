# Troubleshooting Fre3nder

Read actual status and logs before changing state. These paths and state names
describe current diagnostic implementation, not a general stable status-file
API. A service start can exit successfully while reporting a refused/degraded
state. Hardware, selector, filesystem and firmware writes are not routine fixes.

## Writable runtime or persistence is missing

Read `/run/fre3nder-root/status`, `/proc/cmdline` and `/proc/mounts`; inspect
label/type discovery with `blkid` if available. Normal writable operation
requires uniquely identified ext4 SYS and HOME backends, not Stock p9/p10.
Missing/ambiguous/wrong-type inputs fail closed. Do not format a device, relabel
arbitrary storage, create reset markers or force a mount as a diagnostic step.
The immutable degraded runtime is not equivalent to `active`.
See [storage](storage-layout.md) and [recovery](recovery.md). If Linux is not
reachable, use the bounded recovery decision path rather than assuming SSH.

## Klipper or Moonraker is unavailable

Read `/run/fre3nder-klipper/status`, `/run/fre3nder-klipper-mcu/status` and
`/run/fre3nder-moonraker/status`. Inspect persistent logs under
`/home/fre3nder/printer_data/logs/`. Check that required sockets/PTYs exist and
that their owning processes match the expected service; do not delete a PID or
kill an unrelated process to bypass an identity check.

Klipper can report `degraded-root`, `host-mcu-unavailable`, `startup-timeout`,
`startup-failed` or an F005 gate state. Moonraker needs active persistence,
active Klipper/UDS, its immutable baseline and Python environment.
`baseline-invalid` is not repaired by a first-boot download. Existing config
is retained; verify required includes/sections instead of replacing user files.
See [Moonraker](moonraker.md), [F005](f005.md) and
[hardware](x2000-hardware-contract.md#adxl345-and-host-mcu-contract).

## F005 state prevents Klipper startup

Use S60's diagnostic state and existing logs. `stock-mcu` means the exact
supported Stock MCU is present without an accepted opt-in;
`f005-update-required` means a recognized Qualified predecessor needs an
explicit update. `unknown-mcu` and `mcu-transition-failed` fail closed.
Do not weaken identity matching, retry a failed flash or enable the Stock
auto-transition marker merely to make the service start. Follow
[F005 switching](f005-mcu-switching.md) and its authorization/recovery boundaries.

## Display or touch is missing

Inspect `fre3nder app display list` and `fre3nder app display status`, then
`/run/fre3nder-display/status`. `disabled` is a valid user choice;
`selection-invalid`, `framebuffer-unavailable`, `touch-unavailable` or a
permission failure identifies a missing prerequisite. Inspect `/sys/class/graphics`,
`/proc/bus/input/devices` and the selected app's data/log directory; do not
hardcode an observed `eventN` or directly drive arbitrary GPIOs.
Missing UI does not authorize a Factory-marker reset or block the other services.
See [display](display.md) and [app CLI](api/cli.md#display-selection).

## Camera is missing

Read `/run/fre3nder-camera/status` and, when present,
`/run/fre3nder-camera/mjpg_streamer.log`; inspect `/sys/class/video4linux/`.
`camera-unavailable` means no eligible index-0 UVC capture node was found;
`baseline-invalid` or permission/runtime errors describe different prerequisites.
After late attachment, a manual `/etc/init.d/S63fre3nder-camera start` is the
current administrative action once prerequisites are checked. It starts a
service; it is not automatic hotplug recovery. Do not force Stock `video4`.
For a healthy service, compare the loopback snapshot with the proxied
`/webcam/?action=snapshot` path and the Moonraker include.
See [camera contract](x2000-hardware-contract.md#camera-contract).

## OTA is blocked

Preserve CLI errors and read `/run/fre3nder-root/status`, `/proc/cmdline` and
`/proc/mounts`. `verify`, `preflight` and `backup-plan` are diagnostic stages
that do not write slots. Check signature/trust, logical storage, backup selection
and the exact package/transaction pairing before retrying a permitted stage.
Pending and persistent activation records are internal; inspect them only to
retain evidence, never edit/delete them to bypass state or partition guards.

Postboot diagnostics are under `/run/fre3nder/ota/`; the persistent activation
and known-good records belong to SYS. No record alone substitutes for observing
the actual booted runtime. A failure may follow partial writes or selector
activation; stop and use [updates](updates.md), [OTA](ota.md) and
[recovery](recovery.md). Automatic rollback is not implied.

## An app does not start

Inspect `fre3nder app list` and `fre3nder app status <app>`, its HOME data/logs
and the relevant platform service status. App status may invoke the app's
service; it is not a guaranteed pure read or pure-JSON channel. For display apps,
also inspect explicit selection. Verify a retained package with
`fre3nder app verify <package.fre3app>` and inspect trusted publisher keys.
Do not replace trust anchors or edit manager metadata as a repair shortcut.
After a SYS reset, the boot restore path re-verifies the cached signed package;
missing/invalid cache or trust is a visible failure, not permission to download
an arbitrary replacement. See [apps](apps.md) and [package format](fre3app.md).
