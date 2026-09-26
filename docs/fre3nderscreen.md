# Fre3nderScreen local Core-UI

Status: **RELEASE 2026.1 PINNED; NEW ROOTLESS INTEGRATION NOT YET HARDWARE-QUALIFIED**.

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
[`ElHanko/fre3nderscreen`](https://github.com/ElHanko/fre3nderscreen), pinned to:

```text
release:      2026.1
commit:       4da29a130d3ac82572e5d86ea55420d2998bf31f
license:      GPL-3.0-only
```

The repository retains the original GuppyScreen Git history and upstream provenance.
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

Release 2026.1 was validated in the Fre3nderScreen repository. Its DejaVu font
and Material Design Icons asset license texts are packaged with the existing
component licenses. The inherited DejaVu font's exact version is not established.

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
/etc/init.d/S30fre3nder-user
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

After the persistent root is active, S30 ensures the locked `fre3nder` account
(UID/GID 1000), its home and screen paths, and membership in `video`, `input`,
and `beep`. S64 retains root control of its PID, status, and input link; it
grants only the selected framebuffer, touch, optional beeper, and backlight
nodes to those groups and starts Fre3nderScreen as `fre3nder`. The screen can
read the input link and write only its volatile output log under
`/run/fre3nderscreen`. The G-code directory remains root-owned with group
read/traverse access for `fre3nder` and no group write access.

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

The previous Fre3nderScreen pin

```text
0.0.26-beta+fre3nder.589275a
589275a7c3a7fd904184bb5f15b058b7c0376911
```

was built into the Fre3nder `2026.4.a` development artifact from project commit
`ae0a11f1fe339246aff4d20c936ceb2e40914f2d`, deployed as a matched Kernel and
RootFS pair, and hardware-qualified on the investigated reference system on
2026-09-24.

The qualification confirmed Fre3nderScreen service autostart, framebuffer
output and portrait presentation, NS2009 touch discovery and calibrated pointer
mapping, persisted calibration across restart, touch-beep feedback, local
Moonraker connectivity, normal UI operation, 60-second backlight standby, and
touch wake.

The complete print-start path was already hardware-qualified on the older
`baa4f66` pin. The qualification of `589275a` remains historical evidence; it
does not qualify release 2026.1 in the new Fre3nder integration. A separately
authorized target build and hardware test must validate the rootless service,
its supplementary groups, device access, local UI, and print path.

Historical qualification evidence remains in `CHANGELOG.md` and the repository
history.
