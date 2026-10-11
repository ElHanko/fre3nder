# Display, touch and Fre3nderScreen

Fre3nderScreen is the dedicated native local Core-UI, packaged as a signed
display `.fre3app`. Fluidd or another web frontend remains independently selected.
The local path is Klipper → Moonraker → Fre3nderScreen → fbdev/evdev; no browser,
X11, Wayland, first-boot download or standalone installer is required.

## Source identity and provenance

Release source, submodules and licenses are recorded in
[sources.json](../configs/x2000/sources.json) and
[licensing and provenance](licensing-and-provenance.md#fre3nderscreen-application-artifact).
A source pin or unchanged application source is not hardware qualification of
a new release binary or signed package.

## Dedicated Fre3nder contract

Fre3nderScreen has a fixed production contract:

- Ender-3 V3 KE / X2000;
- one local Moonraker endpoint;
- Linux fbdev and evdev;
- 272x480 logical portrait UI;
- LVGL software rotation `LV_DISP_ROT_90`;
- calibrated NS2009 touch input;
- touch feedback and physical backlight standby;
- one small-screen Material asset set.

The application configuration is flat. There is no `default_printer`,
`printers` map, or runtime `display_rotate` setting. The immutable Fre3nder
default connects to `127.0.0.1:17126`.

The SDL host simulator is a development tool for this UI.

## Build and RootFS contract

Fre3nder builds the native app artifact; `fre3nder-apps` packages and signs it.
RootFS assembly verifies the finished package with the package core and official
publisher key, then embeds it unchanged at
`/usr/share/fre3nder/factory-apps/fre3nderscreen.fre3app`. Platform and app release
modes are independent: a development platform uses the prepared release seed
unless `--fre3nderscreen-app` explicitly requests a development app build.
[Building](build.md#complete-x2000-build) describes local sources, package
identity, release requirements, and full versus RootFS-only builds.

On a fresh persistent system, `S63fre3nder-factory-app` installs this seed
through the package core and explicitly selects it. The persistent
`/home/.fre3nder/factory-apps/fre3nderscreen` marker records `pending` or
`complete`. A completed bootstrap is never rerun after OTA, removal, or a
different display choice. A new RootFS seed therefore does not update an
already installed app; follow the [explicit app-update procedure](installation.md#update-the-installed-display-app).
`S64fre3nder-display` manages VT, framebuffer, touch, optional backlight, and
optional beeper access; S65 skips display frontends.

The unprivileged app service stores its settings at
`$FRE3NDER_APP_DATA_DIR/fre3nderscreen.json`. On first setup it copies an
existing regular legacy config from
`/home/fre3nder/.fre3nder/fre3nderscreen/fre3nderscreen.json`; otherwise it
uses the packaged default. It never deletes the legacy file. The old nested
GuppyScreen schema is not imported. App logs and PID live under the app data
directory. Missing local UI prerequisites do not gate Dropbear, Klipper,
Moonraker, or Fluidd.

## Hardware interface

The investigated Ender-3 V3 KE uses the Ingenic fbdev/fb_stage path with a
480x272 landscape framebuffer and portrait-mounted panel. Fre3nderScreen
provides the 272x480 logical portrait presentation with `LV_DISP_ROT_90`.
fbcon rotates only the text console; the framebuffer geometry and app rotation
remain unchanged. A stable input `eventN` number is not part of this contract.
The platform discovers the NS2009 `ns2009_ts` device and supplies paths through
[Display Frontend API v1](fre3app.md#display-frontend-api-v1).

| Function | Current reference wiring / interface |
| --- | --- |
| Framebuffer/panel | `ingenicfb`, `/dev/fb0`, 480x272 at 60 Hz, RGB565 panel, 32-bpp framebuffer |
| Panel reset | PB16 |
| Backlight | PC22 active-high `gpio-backlight`, `/sys/class/backlight/backlight/bl_power` |
| LCD power-enable | PC21 is not claimed or driven |
| Touch | NS2009 at I2C4 address `0x48`, GPC25/GPC26, PC15 active-low pendown |
| Input | `BTN_TOUCH`, `ABS_X`, `ABS_Y`; discover the device rather than hardcode `event0` |
| Pin ownership | I2C4 owns GPC25/GPC26; UART3 is disabled; no runtime handoff implemented |
| Beeper | Linux `pwm-beeper`, X2000 PWM3/PC03, `EV_SND`/`SND_TONE`; no `/dev/mem` helper |

Calibration, axis mapping and presentation rotation belong to the app/input
layer. Reference measurements are not universal calibration values. S64 manages
framebuffer/input and optional backlight/beeper permissions and supplies the
selected unprivileged service with the relevant paths and supplementary groups.

## Build integration

The productive X2000 kernel build carries display and touch support through the
ordered kernel patch series, specifically:

~~~text
patches/kernel/0002-ender3-v3-ke-display-v6.6.157.patch
patches/kernel/0003-ns2009-touch-v6.6.157.patch
patches/kernel/0005-fre3nder-ender3-v3-ke-integration-v6.6.157.patch
configs/x2000/kernel-fre3nder.defconfig
configs/x2000/kernel.fragment
~~~

The board DTS is carried inside the applied kernel tree as
`module_drivers/dts/x2000/ender3-v3-ke.dts`.

`build/x2000/entrypoint.sh` verifies each ordered patch hash and the final
result tree, applies the series to the pinned Linux-stable baseline, and
validates the display/touch configuration and generated DTB during kernel
preparation.

The effective kernel configuration is checked fail-closed for:

~~~text
CONFIG_FB=y
CONFIG_FB_INGENIC=y
CONFIG_FB_INGENIC_STAGE=y
CONFIG_STAGE_ENDER3_V3_KE_480X272=y
CONFIG_INPUT_TOUCHSCREEN=y
CONFIG_TOUCHSCREEN_NS2009=y
~~~

## Configuration and qualification boundary

Select, inspect or disable a display through
[`fre3nder app display`](api/cli.md#display-selection). Keep valuable settings
in HOME and calibrate the actual panel through the app. The flat Screen schema
and legacy-file initialization are described above; this repository does not
promise compatibility for arbitrary JSON keys from the external application.

Automatic boot startup, VT switching, touch, standby/wakeup and the optional
local root shell have been exercised on the investigated reference system.
Exact artifacts, dated results and untested failure scenarios are recorded in
[display qualification](../research/docs/display-qualification.md#2026-10-11-linux-vt-integration-qualification).
Missing local UI does not block SSH, Klipper, Moonraker or the web frontend.

## Linux virtual terminals

Fre3nder uses the Linux framebuffer console (`fbcon`) on tty1 and
Fre3nderScreen on tty7. A USB HID keyboard switches to tty1 with Ctrl+Alt+F1
and back to the UI with Ctrl+Alt+F7. The application keeps running during the
switch; returning to tty7 redraws the UI and restores touch input.

The kernel enables VT, fbcon, console rotation, deferred takeover and USB HID.
The platform console helper sets `rotate_all=3` after fbcon binds, with a
bounded wait for deferred takeover. Rotation applies only to text output;
`/dev/fb0` remains 480x272 and Fre3nderScreen retains LVGL software rotation.

### Boot output

The board Device Tree sets `default-on` for the PC22 `gpio-backlight` so the
Linux driver enables the backlight during kernel initialization. This makes
tty1 visible during the later boot sequence independently of Fre3nderScreen
startup. Fre3nderScreen retains runtime backlight control, including standby
and wakeup; S64's existing enable after successful app startup is unchanged.
The operator confirmed a successful build and visible boot screen and tty1
console on the investigated reference system; see
[backlight qualification](../research/docs/display-qualification.md#kernel-backlight-boot-default-2026-10-11).

After the persistent-root switch, `console boot` initializes tty1 and replays
available `dmesg` output without clearing the kernel ring buffer. The
`console services` action runs rcS, captures output in `/run/fre3nder-boot.log`,
and replays it to tty1 and the inherited serial console when rcS returns.
These helper actions exit after their work; there is no permanent log follower.

Early kernel output still uses the existing serial console
(`console=ttyS4,115200n8`). tty1 shows a later replay, not continuous kernel
output or private application logs. Overwritten ring-buffer entries cannot be
recovered. Missing tty1/fbcon produces a diagnostic without gating the other
printer services.

### Optional passwordless local root shell

Init provides a guarded `askfirst` entry on tty1. Pressing Enter opens a local
root shell only when the opt-in is valid and persistent root is active;
otherwise it reports that local access is disabled. Enabling this switch grants
anyone with physical keyboard access a passwordless root shell and full system
control. It does not enable SSH or alter SSH authentication.

For first activation, run as root on a healthy writable Fre3nder runtime.
Create the directory as well as the file; `/etc/fre3nder/` may be absent on a
fresh installation:

```sh
test "$(cat /run/fre3nder-root/status)" = active &&
  test ! -L /etc/fre3nder &&
  install -d -o root -g root -m 0755 /etc/fre3nder &&
  test ! -e /etc/fre3nder/console.enabled &&
  test ! -L /etc/fre3nder/console.enabled &&
  install -o root -g root -m 0600 /dev/null /etc/fre3nder/console.enabled
```

Then use Ctrl+Alt+F1 and press Enter. Type `exit` to end the shell; use
Ctrl+Alt+F7 to return to Fre3nderScreen. Switching VTs does not end an open
shell. No reboot or display restart is needed to enable or disable access.

Disable future shell starts with:

```sh
rm -f /etc/fre3nder/console.enabled
```

Exit any already open root shell separately. Removing the file prevents new
shell starts but does not terminate an existing session.

Keep `/etc/fre3nder/` owned by `root:root`, without group/other write access,
and `console.enabled` a `root:root` regular file with exact mode `0600` and one
hard link. Symlinks and other file types are rejected. The helper checks UID 0
and GID 0 for the opt-in and both parent directories, `/etc` and `/etc/fre3nder`.
`/run/fre3nder-root/status` must be a regular file with UID 0, without group/other
write access, containing `active`; its GID is not restricted.

The opt-in lives in the SYS overlay under `/etc`. It survives ordinary reboots,
but a SYS reset removes it; the immutable RootFS contains no enabled marker.
The file is not migrated into HOME. SSH provisioning remains governed by
[networking](networking.md#ssh).

### Graphics ownership and terminal handoff

The startup chain is S64 → package-core → selected app service →
Fre3nderScreen. The root-owned console helper prepares tty7 and grants only
`fre3nder:fre3nder` access, mode `0600`. Package-core runs the app service as
`fre3nder`, with the existing `video`, `input` and `beep` groups, and supplies
`FRE3NDER_DISPLAY_VT=/dev/tty7` through [Display API 1](fre3app.md#display-frontend-api-v1).
The app creates its own session and opens tty7 as its controlling terminal with
`TIOCSCTTY`; these Linux TTY permissions allow its VT operations without root,
setuid or added capabilities.

Fre3nderScreen uses `VT_PROCESS` release/acquire signals and `KD_GRAPHICS`.
On release it suspends framebuffer writes and touch dispatch, restores the
backlight, stops touch feedback and acknowledges the handoff. LVGL timers and
Moonraker callbacks continue while tty1 is foreground. On acquisition it wakes
the panel, resets touch processing and standby timing, and redraws the UI.
Touches on tty1 are drained without UI actions; UI standby cannot blank tty1.

After initialization, the app activates tty7, waits for activation, draws its
first frame and writes its readiness marker. The app service checks process
identity and that marker every 100 ms, with at most 100 retry sleeps. Child
liveness keeps the startup wait open until `exec` establishes the app's `/proc`
identity; success still requires both identity and marker.

S64 checks app service status and tty7's `VT_PROCESS` / `KD_GRAPHICS` immediately,
then at 100-ms intervals with at most 50 retry sleeps. Both waits end as soon as
readiness succeeds; there is no fixed boot delay. Check execution adds to the
ten-second app and five-second manager sleep budgets. A failed start or timeout
makes S64 request app stop, remove runtime device links, release tty7 and report
`startup-failed`. Diagnostics distinguish a missing app process from missing
VT readiness. A missing framebuffer console reports `console-unavailable`.

Normal shutdown and handled failures restore `VT_AUTO` / `KD_TEXT`, returning
to tty1 if tty7 was foreground. S64 stop also returns tty7 to `root:root`, mode
`0600`. There is no supervision daemon or automatic respawn. Automatic recovery
from a hung, still-live VT controller is not implemented.

### Diagnosis

Read the display state, service-start log and VT modes before changing state:

```sh
ssh -o BatchMode=yes <printer-host> '
  cat /run/fre3nder-root/status /run/fre3nder-display/status
  cat /sys/class/tty/tty0/active
  /etc/init.d/S64fre3nder-display status
  /usr/libexec/fre3nder/console check
  cat /run/fre3nder-boot.log
'
```

`console check` verifies graphics ownership of tty7, not which VT is currently
foreground or whether Moonraker is connected. It can succeed while tty1 is
visible. App service output and UI logs are under
`/home/fre3nder/.local/share/fre3nderscreen/logs/`. A display-manager start can
return zero while its status file reports a refused or failed start; inspect
both the status and the logged reason. For general service failures, see
[troubleshooting](troubleshooting.md#display-or-touch-is-missing).
