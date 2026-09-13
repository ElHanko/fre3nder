# GuppyScreen local Core-UI

Status: **FORK SOURCE INTEGRATED / FORK BUILD PENDING / STAGE-D RUNTIME
PARTIALLY HARDWARE QUALIFIED**.

GuppyScreen is Fre3nder's native local Core-UI. It is built from source into
the immutable RootFS baseline and is neither a managed application nor a web
frontend. Fluidd remains the independently selected LAN web interface.

```text
Web:    Klipper <-> Moonraker <-> Fluidd / alternative web frontends
Local:  Klipper <-> Moonraker <-> GuppyScreen <-> fbdev / evdev
```

No X11, Wayland, Chromium, WebKit, kiosk process, target-side compiler, first
boot download, or GuppyScreen installer is part of this design.

## Pinned source

The productive source is the Fre3nder-maintained fork
[`ElHanko/guppyscreen`](https://github.com/ElHanko/guppyscreen), pinned to:

```text
source label: 0.0.26-beta+fre3nder.b89154d
commit:       b89154d178a45cf65ab50dc085a4df85fc7da896
license:      GPL-3.0-only
```

The fork descends from the published `ballaswag/guppyscreen` `0.0.26-beta`
baseline at commit `cf5c6d7539a2dca090ca71c177f57a2d96df443a`.
The selected fork commit is 23 commits ahead of that baseline. The pinned
native dependency submodules remain unchanged.

The source uses Make, C++17, and upstream documents GCC/G++ 7.2 or newer. Its
Makefile has a real `CROSS_COMPILE` path used by upstream's MIPS release job;
Fre3nder uses the already established Buildroot GCC 13.4.0/binutils 2.43.1
MIPS32r2/O32/hard-float/FPXX/NaN2008 toolchain instead of upstream's downloadable
toolchain. The component and RootFS build completed successfully for the first
Stage-D hardware test using the previous pre-fork source pin. The currently
pinned fork commit still requires a new authorized component build.

Pinned native/vendored dependencies are:

| Dependency | Identity | License |
| --- | --- | --- |
| LVGL | `74d0a816a440eea53e030c4f1af842a94f7ce3d3` (8.3.11) | MIT |
| lv_drivers | `71830257710f430b6d8d1c324f89f2eab52488f1` | MIT |
| libhv | `a1d81857131fe7ea499a23e333513bfb279df6b0` | BSD-3-Clause |
| spdlog | `ddce42155e67589a8b1534c4935242f759c07646` | MIT |
| vendored wpa_supplicant control client | pinned by the GuppyScreen commit | BSD-3-Clause |

The exact records are machine-readable in `configs/x2000/sources.json`.
License texts are copied into `/usr/share/licenses/guppyscreen/` in the
component payload. GuppyScreen's GPL corresponding-source boundary is the
pinned public fork source, its pinned submodules, the source-carried patches,
and the reproducible builder.

The builder applies the pinned tree's `0001-lv_driver_fb_ioctls.patch`,
`0002-spdlog_fmt_initializer_list.patch`, and
`0003-lvgl-dpi-text-scale.patch`. The generic runtime-path overrides
`GUPPYSCREEN_CONFIG`, `GUPPYSCREEN_THEME_DIR`, and `GUPPYSCREEN_INPUT` are now
carried directly by the pinned Fre3nder GuppyScreen fork. The fork also carries
the touch-rotation correction derived from the first hardware test.

## Build and RootFS contract

REQ-2026.2-010 was still only planned before this work: Moonraker staging and
generic RootFS assembly both lived in `build-x2000-rootfs`. That interface is
removed. The component flow is now:

```text
scripts/build-x2000
  ├── scripts/build-x2000-moonraker
  │     └── artifacts/x2000/moonraker/rootfs-overlay.tar
  ├── scripts/build-x2000-buildroot --toolchain
  ├── scripts/build-x2000-guppyscreen
  │     └── artifacts/x2000/guppyscreen/rootfs-overlay.tar
  └── scripts/build-x2000-buildroot --assemble
        └── artifacts/x2000/rootfs-only/rootfs.squashfs
```

Each application component archive has a minimal manifest containing its
source, license, build mode, project/build-input identity, and archive SHA256.
The Buildroot assembler rejects stale, mismatched, symlinked, malformed, or
wrongly sourced artifacts and records the consumed component identities in the
RootFS manifest. Component archives are deterministic tar files with normalized
ownership and timestamps.

The GuppyScreen component contains only:

```text
/opt/fre3nder/guppyscreen/guppyscreen
/usr/share/guppyscreen/themes/*.json
/usr/share/licenses/guppyscreen/*
```

The project RootFS overlay supplies the service and immutable initial default:

```text
/etc/init.d/S64fre3nder-guppyscreen
/usr/share/fre3nder/defaults/guppyconfig.json
```

The service seeds a missing configuration once at:

```text
/home/fre3nder/.fre3nder/guppyscreen/guppyconfig.json
```

That file contains user settings and the affine touch-calibration coefficients
written by GuppyScreen, so it survives a system-overlay reset. Existing regular
configuration is retained; symlinks and non-files fail closed. GuppyScreen logs
to `/home/fre3nder/printer_data/logs/guppyscreen.log`; early process output and
service state remain volatile under `/run/fre3nder-guppyscreen/`.

## Display, touch, and rotation

GuppyScreen uses the upstream LVGL 8.3 fbdev driver directly with `/dev/fb0`.
The qualified kernel remains at its native 480x272, 32-bpp, 1920-byte-stride
mode; fbdev reports a virtual size of 480x816 on the investigated reference
system. Hardware testing demonstrated that `display_rotate: 3` is physically
upside down and `display_rotate: 1` (`LV_DISP_ROT_90`) has the correct physical
orientation. The Fre3nder default is therefore `1`. The component enables LVGL
software rotation; no kernel rotation or new display driver is introduced.

The service identifies exactly one Linux input event whose sysfs device name is
`ns2009_ts`, creates `/run/fre3nder-guppyscreen/input`, and passes that path to
the application. It does not depend on `/dev/input/event0` and does not access
the NS2009 I2C controller directly.

The upstream fbdev/evdev patch removes the initial fixed 0..4096 mapping so the
bundled affine calibration receives raw coordinates. Input discovery and raw
touch data are confirmed on the investigated reference system: physical
left-to-right movement maps mainly to decreasing raw Y, while physical
top-to-bottom movement maps mainly to increasing raw X. GuppyScreen starts its
interactive calibration with `display_rotate: 1`, but that calibration is not
currently usable.

The observed endpoint samples were:

```text
physical left -> right: (2011,3517) -> (1924,828),  dx=-87,   dy=-2689
physical top  -> bottom: (292,2283) -> (3757,2002), dx=+3465, dy=-281
```

The first hardware test exposed an error in the historical GuppyScreen
calibration handling for rotated displays. Analysis against the pinned LVGL
pointer transformation showed that the old 90-degree path effectively used
the inverse transformation for 270 degrees, producing the observed mirrored
axes. The pinned `ElHanko/guppyscreen` fork now contains the corresponding
90/270-degree correction and the 180-degree off-by-one correction together
with a regression test. This source fix has not yet been rebuilt or qualified
on the reference printer. No kernel, DTS, `ke-touch.patch`, or service-side
coordinate workaround is introduced. End-to-end calibrated touch therefore
remains open until the next hardware test.

## Moonraker and failure behavior

The default connects by WebSocket to `ws://127.0.0.1:17126/websocket`, matching
Fre3nder's loopback-only Moonraker listener. Upstream libhv reconnects with a
bounded 200 ms to 2 s delay policy and GuppyScreen displays its initialization
state while Klipper/Moonraker is unavailable.

S64 runs after S61 by name but does not wait for or gate on Moonraker readiness.
It requires the active persistent root, the immutable binary/themes, `/dev/fb0`,
and a unique `ns2009_ts` event device. Missing prerequisites or an early process
exit produce a status under `/run/fre3nder-guppyscreen/status` and leave the
local UI stopped. Service startup checks the process for one second only.
GuppyScreen never gates system initialization, Dropbear, Klipper, Moonraker, or
Fluidd.

The first Stage-D boot exposed one integration defect: although the existing
PC22/gpio-backlight path works, its `bl_power` remained `4` after GuppyScreen
started, leaving the physical display dark. S64 now writes `0` to
`/sys/class/backlight/backlight/bl_power` after confirming that the UI process
is running. A missing or unwritable attribute is logged but does not stop the
UI or block boot. The manual `bl_power=0` hardware effect is confirmed; this
S64 source correction still awaits its next build and deployment.

No `update.sh` is installed beside the binary, so upstream's UI update action
does not mutate the immutable baseline. GuppyScreen updates remain owned by the
reproducible RootFS build and deployment process.

The built RootFS deployed and booted successfully on Fre3nder p8. GuppyScreen
reached `active`, produced physical fbdev output, found NS2009 through evdev,
started touch calibration, and attempted its Moonraker WebSocket connection at
`ws://127.0.0.1:17126/websocket`. Calibrated touch and the wider set of normal
printer-control flows remain unqualified.

## First Stage-D hardware result

On the investigated reference system:

```text
Component and RootFS build       PASS
RootFS deployment to p8         PASS
Fre3nder B boot                  PASS
Persistent root                 PASS
GuppyScreen service/process     PASS
ingenicfb physical output       PASS
NS2009 evdev discovery/raw data PASS
Display rotation value 1        PASS
Backlight automatic start       SOURCE FIXED / RETEST REQUIRED
Touch calibration/rotation      OPEN
```

Stage D is therefore not fully hardware-qualified. The next qualification step
is to build the updated S64/default configuration together with the pinned
GuppyScreen fork under the normal build gate. After an authorized RootFS
deployment, verify automatic backlight enable, display orientation, touch
calibration, and end-to-end pointer mapping on the reference printer.
