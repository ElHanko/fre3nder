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

The current Fre3nderScreen source deliberately removes the old generic
GuppyScreen product matrix. The production contract is fixed:

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

The SDL host simulator remains a development tool. Android, K1/CR-10/Nebula
product matrices, Debian/Raspberry Pi production packaging, multi-printer
selection, Z-Bolt, generic landscape layouts, and the GuppyScreen self-updater
are not part of the Fre3nderScreen production scope.

## Build and RootFS contract

The separate `scripts/build-x2000-fre3nderscreen` cross-build produces
`local/production/artifacts/x2000/fre3nderscreen/app/` with the binary, themes,
licenses, manifest, and checksums. `fre3nder-apps` imports it, builds, and signs
the `.fre3app`. After explicit build/signing authorization,
`scripts/build-x2000-fre3nderscreen-release` orchestrates these release-only
steps through the existing cross-builder and the sibling apps release wrapper.
It atomically replaces `local/production/factory-apps/fre3nderscreen.fre3app`
with a byte-identical copy of the resulting package, mode `0644`, and verifies
SHA256. Its defaults are `../fre3nder-apps` and the existing
`local/production/keys/apps/private.pem`; `--apps-repo` and `--key` override them.
It runs no RootFS build or deployment. The RootFS assembly takes that
finished package through `FRE3NDER_FACTORY_FRE3NDERSCREEN_APP`, verifies it with
the package core and official publisher key, and embeds it unchanged at
`/usr/share/fre3nder/factory-apps/fre3nderscreen.fre3app`.

Platform and app release modes are independent. Both `scripts/build-x2000` and
`scripts/build-x2000 --develop` use the prepared release Factory seed without
rebuilding Screen. Only `scripts/build-x2000 --develop --fre3nderscreen-app`
(also with `--rootfs-only`, optionally `--f005-build`) builds current remote
Screen `main` through the existing cross-builder's `--develop` path. The sibling
`fre3nder-apps/scripts/build-fre3nderscreen-development` imports and signs it as
`<artifact.source.release>-fre3nder.0.<apps-commit>`, using the apps commit's short
Git identity and `release_serial = 0`. Tracked apps changes block this path;
generated untracked/ignored files do not.

The returned package is supplied through `FRE3NDER_FACTORY_FRE3NDERSCREEN_APP`
only for that RootFS build, with `FRE3NDER_FACTORY_FRE3NDERSCREEN_MODE=development`.
The canonical release seed is not copied, replaced, or deleted. Without the app
flag the expected mode is `release` (`release_serial >= 1`), including for a
development platform. The app flag requires `--develop` and a full or RootFS
scope; a release platform cannot contain a development Factory app. Errors stop
the requested app path without falling back to the release seed. Building and
signing require separate explicit authorization; no deployment is performed.

On a fresh persistent system, `S63fre3nder-factory-app` installs this seed
through the package core and explicitly selects it. The persistent
`/home/.fre3nder/factory-apps/fre3nderscreen` marker records `pending` or
`complete`. A completed bootstrap is never rerun after OTA, removal, or a
different display choice. `S64fre3nder-display` remains a generic manager of
framebuffer, touch, optional backlight, and optional beeper access; S65 skips
display frontends.

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
Kernel rotation and a stable input `eventN` number are not part of this contract.
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

The recorded hardware path and one exact Development Factory-app package were
qualified on the investigated reference system. The prepared release binary
and a complete print with that Factory-app package are not established by those
records. Earlier standalone Screen/GuppyScreen results remain separate evidence.

Complete source/package identities, slots, hashes, measured endpoints and
qualification boundaries are retained in
[display qualification](../research/docs/display-qualification.md). Missing
local UI does not block SSH, Klipper, Moonraker or the web frontend.
