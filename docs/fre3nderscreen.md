# Fre3nderScreen local Core-UI

Status: **Factory `.fre3app` integration hardware-qualified on the investigated
reference system with the Development package identified below**.

Fre3nderScreen is Fre3nder's dedicated native local Core-UI for the Ender-3 V3
KE. It is cross-built from source into a neutral artifact, then packaged as a
normal signed display `.fre3app`. The immutable RootFS carries only its signed
factory seed. Fluidd remains the independently selected LAN web interface.

```text
Web:    Klipper <-> Moonraker <-> Fluidd / alternative web frontends
Local:  Klipper <-> Moonraker <-> Fre3nderScreen <-> fbdev / evdev
```

No X11, Wayland, Chromium, WebKit, kiosk process, target-side compiler,
first-boot download, or standalone screen installer is part of this design.

## Source identity and provenance

The release-mode source pin in the Fre3nder-maintained fork
[`ElHanko/fre3nderscreen`](https://github.com/ElHanko/fre3nderscreen) is:

```text
release:      2026.2
commit:       63e7ecb9fff980b53f4987ef9994675aecf9e0a2
license:      GPL-3.0-only
```

This prepares release `2026.2`; no release tag or binary has been produced yet.
Its application code, patches, and submodules match the hardware-qualified
`14cd41599f1ee8dec659b282e54762fd61552c5a` source. The only subsequent commit
changes `README.md` and `DEVELOPMENT.md`. The planned package is
`2026.2-fre3nder.2`, with `release_serial = 2`; its release binary has not
been hardware-qualified.

The repository retains the original GuppyScreen Git history and upstream provenance.
The application at this release pin identifies as **Fre3nderScreen** and is specialized
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

The release records are machine-readable in `configs/x2000/sources.json`.
The neutral artifact contains the byte-exact qualified license texts, which
`fre3nder-apps` imports unchanged into the signed package payload. The GPL
corresponding-source boundary is the public fork source, its recorded
submodules, source-carried patches, and the reproducible builder.

DejaVu font and Material Design Icons notices accompany the package payload.
The inherited DejaVu font's exact version is not established.

The artifact builder applies the three dependency patches shipped by the
resolved source tree. It builds with the Fre3nder Buildroot GCC 13.4.0 /
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

## Factory-app Development qualification

The Factory-app path was validated on the investigated reference printer with
this historical Development identity, separate from the prepared `2026.2`
release pin above:

| Input | Qualified identity |
| --- | --- |
| Fre3nder | `41df7e7029607908a7287c9492bf28df643aaf17` |
| fre3nder-apps | `4796448` |
| Fre3nderScreen source | `14cd41599f1ee8dec659b282e54762fd61552c5a` |
| Signed package | `2026.1.14cd415-fre3nder.0.4796448`, `release_serial = 0` |

The complete Kernel and RootFS A/B deployment from slot B to slot A passed,
including Kernel p5 and RootFS p7 readback, reboot, and runtime checks. The
Factory marker reached `complete`; the package core installed the `.fre3app`
and selected Fre3nderScreen as the display frontend. Its process ran as
`fre3nder:fre3nder`, and the old `/opt/fre3nder/fre3nderscreen` path was absent.
The legacy configuration and calibration were functionally carried into the
new app data path. Physical display output, touch, calibration, Moonraker
connectivity, and beeper output through `/run/fre3nder-display/beeper` passed.
These results qualify the listed Development package and Factory-app path;
they do not establish hardware qualification of the unbuilt `2026.2` release
binary or a complete print with this package.

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
does not qualify release 2026.1 in the new Fre3nder integration or establish a
complete print with the Development Factory-app package described above.

Historical qualification evidence remains in `CHANGELOG.md` and the repository
history.
