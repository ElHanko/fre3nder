# GuppyScreen local Core-UI

Status: **SOURCE INTEGRATED / BUILD PENDING / HARDWARE QUALIFICATION NOT
STARTED**.

GuppyScreen is Fre3nder's native local Core-UI. It is built from source into
the immutable RootFS baseline and is neither a managed application nor a web
frontend. Fluidd remains the independently selected LAN web interface.

```text
Web:    Klipper <-> Moonraker <-> Fluidd / alternative web frontends
Local:  Klipper <-> Moonraker <-> GuppyScreen <-> fbdev / evdev
```

No X11, Wayland, Chromium, WebKit, kiosk process, target-side compiler, first
boot download, or GuppyScreen installer is part of this design.

## Pinned upstream

The inspected upstream is
[`ballaswag/guppyscreen`](https://github.com/ballaswag/guppyscreen). Its
published tags run from `0.0.11-beta` through `0.0.26-beta`, plus the moving
`nightly` tag. No non-beta release was available when inspected on 2026-09-12.
Fre3nder selects the latest published numbered release rather than unpublished
`main`:

```text
release:    0.0.26-beta
commit:     cf5c6d7539a2dca090ca71c177f57a2d96df443a
license:    GPL-3.0-only
commit date: 2024-04-28
```

The release is old and explicitly beta, but it is the narrowest published,
immutable upstream basis and contains the touch-calibration fix advertised by
that release. Later `main` changes are not silently included. A future update
requires changing and validating the exact pin.

The source uses Make, C++17, and upstream documents GCC/G++ 7.2 or newer. Its
Makefile has a real `CROSS_COMPILE` path used by upstream's MIPS release job;
Fre3nder uses the already established Buildroot GCC 13.4.0/binutils 2.43.1
MIPS32r2/O32/hard-float/FPXX/NaN2008 toolchain instead of upstream's downloadable
toolchain. Build compatibility with that newer toolchain is pending the
authorized component build.

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
pinned public source, its pinned submodules, the upstream-carried patches, the
Fre3nder runtime-path patch, and the reproducible builder.

The builder applies the pinned tree's `0001-lv_driver_fb_ioctls.patch`,
`0002-spdlog_fmt_initializer_list.patch`, and
`0003-lvgl-dpi-text-scale.patch`, followed by Fre3nder's
`patches/guppyscreen/0001-fre3nder-runtime-paths.patch`. The last patch only
adds environment-selectable configuration, theme, and input-device paths.

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
mode. The Fre3nder default sets `display_rotate` to `3`
(`LV_DISP_ROT_270`) and the component enables LVGL software rotation. No kernel
rotation or new display driver is introduced.

The service identifies exactly one Linux input event whose sysfs device name is
`ns2009_ts`, creates `/run/fre3nder-guppyscreen/input`, and passes that path to
the application. It does not depend on `/dev/input/event0` and does not access
the NS2009 I2C controller directly.

The upstream fbdev/evdev patch removes the initial fixed 0..4096 mapping so the
bundled affine calibration receives raw coordinates. With
`touch_calibrated: true` and no saved coefficients, GuppyScreen presents its
interactive calibration screen and stores the resulting six coefficients in
the persistent JSON file. It then applies those coefficients together with the
configured display rotation. The approximate raw ranges observed on the
reference device are deliberately not build-time defaults.

The exact physical rotation direction, calibration UX, and end-to-end touch
mapping remain hardware-qualification items. If rotation direction proves
wrong, change the persistent `display_rotate` value based on observed hardware
behavior; do not change the kernel geometry.

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

No `update.sh` is installed beside the binary, so upstream's UI update action
does not mutate the immutable baseline. GuppyScreen updates remain owned by the
reproducible RootFS build and deployment process.

The upstream Wi-Fi control panel, optional macros, printer actions, rotation,
touch calibration, reconnect behavior, and all normal UI flows remain
unqualified until a built artifact is run on the reference system.

## Build gate

No build has been run for this integration. The smallest complete validation is
the RootFS-only development orchestration, because it must prepare the pinned
toolchain, build both independently consumed RootFS components, and prove that
the final SquashFS incorporates their validated manifests:

```sh
scripts/build-x2000 --develop
```

Expected outputs are component artifacts under
`local/production/artifacts/x2000/{moonraker,guppyscreen}/` and a validated
`local/production/artifacts/x2000/rootfs-only/rootfs.squashfs` whose manifest
records both. A kernel build is unnecessary because the framebuffer and touch
kernel inputs are unchanged.
