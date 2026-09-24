# Fre3nderScreen local Core-UI

Status: **CURRENT DEVELOPMENT INTEGRATION CANDIDATE; NEW PIN NOT YET
HARDWARE-QUALIFIED**.

Fre3nderScreen is Fre3nder's dedicated native local Core-UI for the Ender-3 V3
KE. It is built from source into the immutable RootFS baseline and is neither a
managed application nor a web frontend. Fluidd remains the independently
selected LAN web interface.

```text
Web:    Klipper <-> Moonraker <-> Fluidd / alternative web frontends
Local:  Klipper <-> Moonraker <-> Fre3nderScreen <-> fbdev / evdev
```

No X11, Wayland, Chromium, WebKit, kiosk process, target-side compiler,
first-boot download, or standalone screen installer is part of this design.

## Source identity and provenance

The productive source is the Fre3nder-maintained fork
[`ElHanko/guppyscreen`](https://github.com/ElHanko/guppyscreen), pinned to:

```text
source label: 0.0.26-beta+fre3nder.589275a
commit:       589275a7c3a7fd904184bb5f15b058b7c0376911
license:      GPL-3.0-only
```

The repository name remains `guppyscreen` for source-history continuity.
The application at this pin identifies as **Fre3nderScreen** and is specialized
for one Fre3nder / Ender-3 V3 KE target, one local Moonraker endpoint, and the
272x480 portrait UI.

The fork descends from the published `ballaswag/guppyscreen` `0.0.26-beta`
baseline at commit `cf5c6d7539a2dca090ca71c177f57a2d96df443a`. Its native
submodule identities remain:

| Dependency | Identity | License |
| --- | --- | --- |
| LVGL | `74d0a816a440eea53e030c4f1af842a94f7ce3d3` (8.3.11) | MIT |
| lv_drivers | `71830257710f430b6d8d1c324f89f2eab52488f1` | MIT |
| libhv | `a1d81857131fe7ea499a23e333513bfb279df6b0` | BSD-3-Clause |
| spdlog | `ddce42155e67589a8b1534c4935242f759c07646` | MIT |
| vendored wpa_supplicant control client | pinned by the Fre3nderScreen commit | BSD-3-Clause |

The exact records are machine-readable in `configs/x2000/sources.json`.
License texts are copied into `/usr/share/licenses/fre3nderscreen/` in the
component payload. The GPL corresponding-source boundary is the pinned public
fork source, its pinned submodules, the source-carried patches, and the
reproducible builder.

The component builder applies the three dependency patches shipped by the
pinned source tree. It builds with the Fre3nder Buildroot GCC 13.4.0 /
binutils 2.43.1 MIPS userspace toolchain. Because libhv embeds `__DATE__` and
`__TIME__`, `SOURCE_DATE_EPOCH` is derived from the pinned source commit.

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

The component flow is:

```text
scripts/build-x2000
  ├── scripts/build-x2000-moonraker
  │     └── artifacts/x2000/moonraker/rootfs-overlay.tar
  ├── scripts/build-x2000-buildroot --toolchain
  ├── scripts/build-x2000-fre3nderscreen
  │     └── artifacts/x2000/fre3nderscreen/rootfs-overlay.tar
  └── scripts/build-x2000-buildroot --assemble
        └── artifacts/x2000/rootfs-only/rootfs.squashfs
```

The Fre3nderScreen component contains only:

```text
/opt/fre3nder/fre3nderscreen/fre3nderscreen
/usr/share/fre3nderscreen/themes/*.json
/usr/share/licenses/fre3nderscreen/*
```

The project RootFS overlay supplies:

```text
/etc/init.d/S64fre3nderscreen
/usr/share/fre3nder/defaults/fre3nderscreen.json
```

The service seeds a missing configuration once at:

```text
/home/fre3nder/.fre3nder/fre3nderscreen/fre3nderscreen.json
```

The new path intentionally starts a clean Fre3nderScreen configuration rather
than importing the obsolete nested GuppyScreen schema. `/home` still owns the
persistent user configuration. Logs go to
`/home/fre3nder/printer_data/logs/fre3nderscreen.log`; early process output and
service state remain volatile under `/run/fre3nderscreen/`.

The service discovers exactly one Linux input event named `ns2009_ts`, exposes
that event to the application, provides the backlight power path and optional
`pwm-beeper`, and never waits for Moonraker readiness. Missing local-UI
prerequisites stop only the local UI; they do not gate Dropbear, Klipper,
Moonraker, or Fluidd.

## Qualification boundary

The previous integration pin

```text
0.0.26-beta+fre3nder.baa4f66
baa4f6689ac7334d240107529f6d3c42a1297319
```

was built, persistently deployed, and hardware-qualified on the investigated
reference system as part of the recorded `2026.2.a` candidate path. That
evidence includes fbdev output, NS2009 touch discovery and calibrated pointer
mapping, `LV_DISP_ROT_90`, automatic backlight start, 60-second standby/wake,
touch-beep feedback, the compact portrait UI, and one complete print initiated
through the local UI.

That qualification evidence remains valid for the recorded old pin; it is not
silently transferred to `589275a7c3a7fd904184bb5f15b058b7c0376911`. The new Fre3nderScreen pin keeps the same
qualified hardware direction and dependency identities but changes application
scope, binary/config/runtime names, and configuration architecture. It therefore
requires a new component build and subsequent hardware qualification before it
can be described as hardware-qualified.

Historical release evidence remains in `CHANGELOG.md` and the repository
history. Building the new pin alone does not qualify or authorize deployment.
