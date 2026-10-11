This is a historical documentation snapshot from `docs/fre3nderscreen.md` at project
commit `a3a3cb263ab845a5590136545911b02306ada35b`. Statements and status labels describe that
recorded scope, not the current build or every hardware revision. The preserved
text remains `AGPL-3.0-or-later`; see `REUSE.toml`.

The snapshots below retain their historical build and qualification status.
The later [2026-10-11 Linux VT qualification](#2026-10-11-linux-vt-integration-qualification)
records the tested VT integration; current operation is documented in
[the display guide](../../docs/display.md).

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

## Display and touch hardware snapshot

This is a historical documentation snapshot from `docs/x2000-display-touch.md` at project
commit `a3a3cb263ab845a5590136545911b02306ada35b`. Statements and status labels describe that
recorded scope, not the current build or every hardware revision. The preserved
text remains `AGPL-3.0-or-later`; see `REUSE.toml`.

# X2000 integrated display and touch hardware

This document records the productive Fre3nder hardware implementation and
qualification of the integrated Ender-3 V3 KE display, backlight, and
touchscreen on the investigated reference system.

The hardware path was qualified on real hardware on 2026-09-12 using the
then-productive kernel baseline. On 2026-09-24 the productive runtime path was
re-exercised on Linux stable `v6.6.157` while qualifying Fre3nderScreen
`589275a7c3a7fd904184bb5f15b058b7c0376911`. The live system confirmed
`ingenicfb` framebuffer operation, NS2009 input and calibrated touch, physical
backlight standby, and touch wake on that kernel baseline.

The 2026-09-12 qualification covers the Linux kernel, Device Tree, framebuffer,
backlight, I2C touchscreen, pendown detection, and Linux input-device path.

It does not qualify a local printer UI. Local presentation is a separate
application-layer concern above this hardware interface.

## Qualified architecture

The productive Fre3nder display hardware path is:

~~~text
X2000 DPU
  |
  +-- Ingenic fb_stage
  |     |
  |     `-- /dev/fb0
  |          480x272 logical framebuffer
  |
  +-- PC22
  |     `-- gpio-backlight
  |
  `-- PB16
        `-- panel reset

I2C4 on GPC25/GPC26
  |
  `-- NS2009 @ 0x48
        |
        +-- ABS_X / ABS_Y
        +-- BTN_TOUCH
        +-- PC15 active-low pendown
        |
        `-- /dev/input/event0
~~~

UART3 is disabled in the productive Device Tree because UART3 and I2C4 share
GPC25/GPC26 on this hardware. Static ownership is assigned to I2C4 for the
touchscreen.

Bluetooth or another future UART3 user would require an explicit runtime
pinmux hand-off and is outside this qualification.

## Backlight

The integrated backlight is controlled by PC22:

~~~dts
backlight {
        compatible = "gpio-backlight";
        gpios = <&gpc 22 GPIO_ACTIVE_HIGH INGENIC_GPIO_NOBIAS>;
};
~~~

The kernel exposes:

~~~text
/sys/class/backlight/backlight
~~~

with:

~~~text
type=raw
max_brightness=1
brightness=1
actual_brightness=1
~~~

Physical qualification demonstrated that changing `bl_power` changes the
integrated display backlight.

PC22 active-high control is therefore hardware-qualified on the investigated
reference system.

## Display panel

Fre3nder uses the Ingenic vendor fbdev/fb_stage display path rather than DRM.

The productive panel identity is:

~~~text
fre3nder,ender3-v3-ke-480x272
~~~

with panel reset on PB16.

The qualified mode is:

~~~text
resolution:       480x272
refresh:          60 Hz
pixel clock:      approximately 10.7568 MHz
panel interface:  parallel RGB565
framebuffer bpp:  32
~~~

Runtime qualification produced:

~~~text
/dev/fb0
name=ingenicfb
modes=U:480x272p-60
virtual_size=480,816
bits_per_pixel=32
stride=1920
~~~

The 480x816 virtual framebuffer is the driver's triple-buffered 480x272
framebuffer.

A direct framebuffer pixel test produced stable red, green, and blue regions
with correct colors.

The physical panel is mounted in portrait orientation while the native panel
and framebuffer coordinate system are 480x272 landscape. Rotation belongs to
the later presentation/input layer and is not implemented in the kernel.

### LCD power-enable boundary

PC21 is not driven by Fre3nder.

Stock-system investigation did not establish a requirement to drive that GPIO
and observed it in the input-low state. Fre3nder therefore does not claim or
toggle PC21 without evidence that it is necessary.

## NS2009 touchscreen

The integrated resistive touchscreen uses a Nsiway NS2009 controller on I2C4:

~~~dts
&i2c4 {
        status = "okay";
        pinctrl-names = "default";
        pinctrl-0 = <&i2c4_pc>;

        touchscreen@48 {
                compatible = "nsiway,ns2009";
                reg = <0x48>;
                pendown-gpios = <&gpc 15 GPIO_ACTIVE_LOW INGENIC_GPIO_NOBIAS>;
        };
};
~~~

The physical bus assignment is:

~~~text
I2C4 SDA/SCL: GPC25/GPC26
NS2009:       address 0x48
pendown:      PC15, active-low
~~~

The effective kernel configuration contains:

~~~text
CONFIG_INPUT_TOUCHSCREEN=y
CONFIG_TOUCHSCREEN_NS2009=y
~~~

The driver is built into the kernel.

Runtime qualification produced:

~~~text
/sys/bus/i2c/devices/4-0048
name=ns2009
~~~

and:

~~~text
N: Name="ns2009_ts"
H: Handlers=mouse0 event0
~~~

The kernel registered the device as:

~~~text
input: ns2009_ts as /devices/platform/apb/10054000.i2c/i2c-4/4-0048/input/input0
~~~

`/dev/input/event0` reports:

- `BTN_TOUCH`
- `ABS_X`
- `ABS_Y`

Real touch testing demonstrated correct touch-down and touch-release events:

~~~text
TOUCH 1
...
TOUCH 0
~~~

and stable X/Y measurements across the panel.

Observed raw values during qualification were approximately:

~~~text
X: 330 .. 3680
Y: 540 .. 3560
~~~

The later GuppyScreen rotation check recorded these endpoint samples on the
same reference system:

~~~text
physical left -> right: (2011,3517) -> (1924,828),  dx=-87,   dy=-2689
physical top  -> bottom: (292,2283) -> (3757,2002), dx=+3465, dy=-281
~~~

These values are qualification observations, not a universal calibration
contract. Exact scaling, axis transformation, inversion, and rotation belong
to the local presentation/input layer; see [Fre3nderScreen](../../docs/display.md).

## UART3 / I2C4 pin ownership

The X2000 pinctrl definitions assign both UART3 and I2C4 to GPC25/GPC26 using
different mux functions.

The productive Fre3nder Device Tree therefore disables UART3:

~~~dts
&uart3 {
        status = "disabled";
};
~~~

and statically assigns GPC25/GPC26 to I2C4.

Runtime qualification confirmed that I2C4 registered successfully and that
UART3 was not registered.

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

## Provenance

The productive kernel baseline is official Linux stable:

~~~text
linux stable v6.6.157
commit 79643295eba17affbd16ca97f3ef04c90266b28c
Fre3nder result: 6.6.157-fre3nder
~~~

Display and touch are explicit layers in the ordered Fre3nder kernel patch
series. Their source provenance is retained from the public
`coreflake1/NebulaOS-kernel` reference at commit
`88a0e1ecc6ace7c9e4ad99d6fa49e272180fd5a9`, with exact source paths,
revisions, roles, and licenses recorded in `configs/x2000/sources.json`.

The display-derived source material is recorded as `GPL-2.0-only`. The
NS2009-derived source material is recorded as `GPL-2.0-or-later`.

The historical Ingenic X2000 kernel at commit
`a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b` remains migration provenance for
the surrounding X2000 platform integration; it is not a productive kernel
source.

No proprietary Creality display or touchscreen binary is part of this
productive implementation.

## Qualification evidence

The kernel-only build completed successfully with:

~~~text
build-manifest.json: OK
kernel.uImage: OK
ender3-v3-ke.dtb: OK
effective-kernel-config: OK
~~~

Offline inspection confirmed:

- the required framebuffer configuration
- the required NS2009 configuration
- compiled `ns2009.o`
- linked NS2009 probe, poll, OF-match, and driver symbols
- `touchscreen@48` in the generated DTB
- PC15 active-low pendown in the generated DTB
- I2C4 enabled with the expected pinctrl
- UART3 disabled

The kernel was then deployed through the established Fre3nder kernel-only
deployment path.

Deployment qualification reported:

~~~text
KERNEL_P6=PASS
ROOTFS_P8=SKIPPED
SYSTEM_PERSISTENCE_RESET=SKIPPED
FINAL_ACTIVE_ROOT=/dev/mmcblk0p8
FINAL_SELECTOR=STOCK_A
DEPLOY_X2000=PASS
~~~

Stock p5 and p7 remained unchanged.

Real-hardware runtime qualification demonstrated:

- working physical backlight control
- stable framebuffer output with correct colors
- successful NS2009 probe at I2C address 0x48
- Linux input-device registration
- working PC15 touch-down and release detection
- plausible and stable X/Y coordinates across the panel
- no UART3 registration conflicting with I2C4

## Qualification status

On the investigated reference system:

~~~text
Backlight / PC22          HARDWARE QUALIFIED
Display / fbdev           HARDWARE QUALIFIED
480x272 panel output      HARDWARE QUALIFIED
Panel reset / PB16        BOOT VERIFIED
NS2009 / I2C4             HARDWARE QUALIFIED
Pendown / PC15            HARDWARE QUALIFIED
ABS_X / ABS_Y             HARDWARE QUALIFIED
BTN_TOUCH                 HARDWARE QUALIFIED
UART3 disabled            VERIFIED
~~~

The integrated display/backlight/touch hardware path is therefore
**HARDWARE QUALIFIED ON DEVICE**.

## Stage-D GuppyScreen follow-up

GuppyScreen was subsequently built from the pinned Fre3nder fork, assembled
into the RootFS, deployed to Fre3nder p8, and booted on the investigated
reference system. GuppyScreen reached `active`, used `/dev/fb0` through
`ingenicfb`, and found NS2009 through dynamic evdev discovery.

`display_rotate: 1` is physically correct. The historical rotated-touch
transformation defect was corrected in the pinned GuppyScreen fork; the fixed
90/270-degree handling and 180-degree off-by-one correction were rebuilt and
deployed. End-to-end physical testing confirmed correct calibrated left/right
and up/down pointer mapping.

The initial Stage-D image left `bl_power=4` after GuppyScreen startup. The S64
service correction enabled the PC22 gpio-backlight after successful UI
startup, and that behavior was physically qualified. This remains evidence
of the earlier development state, before the kernel boot-default change below.

The GuppyScreen fork used for Stage-D also controlled physical standby through
the same Linux backlight interface. On the investigated reference printer:

~~~text
automatic backlight startup     PASS
display_rotate: 1               PASS
calibrated touch mapping        PASS
60-second physical standby      PASS
first-touch wake                PASS
touch-beep via pwm-beeper       PASS
~~~

The touch-beep uses the generic Linux `pwm-beeper` input interface backed by
X2000 PWM3 / PC03. The physically accepted click parameters are 260 Hz for
4 ms with a 120 ms debounce. GuppyScreen emits `EV_SND` / `SND_TONE`; it does
not require a `/dev/mem` PWM helper.

Stage D qualified the physical display, touch, backlight, and beep path on the
investigated reference system. Later normal printer control and a complete
print through GuppyScreen were qualified separately; see
[Fre3nderScreen qualification boundary](display-qualification.md#qualification-boundary).
Neither result establishes support across other hardware revisions.

### Kernel backlight boot default (2026-10-11)

The current board DTS adds `default-on` to the PC22 `gpio-backlight` node.
In Linux stable `v6.6.157`,
[`gpio_backlight_probe()`](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/video/backlight/gpio_backlight.c?h=v6.6.157)
reads this boolean, selects `FB_BLANK_UNBLANK` for a node without a phandle,
and drives the GPIO with initial brightness 1. Our backlight node has no label,
reference or explicit phandle, so this path applies. With a phandle, the driver
instead derives initial power from the existing GPIO value. `default-on` is
defined by the standard
[`gpio-backlight` binding](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/Documentation/devicetree/bindings/leds/backlight/gpio-backlight.yaml?h=v6.6.157).

This enables the backlight during kernel initialization and makes tty1
visible during the later boot sequence independently of Fre3nderScreen startup.
S64's existing startup enable and Fre3nderScreen's runtime control, including
standby/wakeup, remain unchanged. **Offline checked and hardware-validated on
the investigated reference system.** The operator reported that the changed
kernel built successfully and that the boot screen and tty1 console are now
visible. This validates the new boot initial state; it does not establish a
new standby/wakeup qualification or support across other hardware revisions.

## 2026-10-11 Linux VT integration qualification

This section records the operator-reported hardware results supplied for the
documentation review on 2026-10-11. They apply to the investigated Ender-3 V3 KE
reference system and the Development artifacts below. No hardware operation or
new build was performed as part of this documentation review.

| Component | Tested identity |
| --- | --- |
| Fre3nder | `2026.5.a` |
| Kernel SHA256 | `01986371514bdb1aba27f7166f9fe58083b252017e0d02fed1d39ef478384efa` |
| RootFS SHA256 | `a05efd5d284e51ae4269d3d88dff7c0756d0f57dd7dd8157df823a9f386ccaf5` |
| Build-input SHA256 | `d2b923a30d0105f2284bbdb70155599f24416ecd8908419ad00bb5a185984bb7` |
| Signed Fre3nderScreen app | `2026.2.b13627b-fre3nder.0.20e072f`, development serial `0` |

Read-only local artifact inspection during this review confirmed that the
Kernel and RootFS bytes and their manifests match the supplied hashes and
build-input identity. The local signed package has the supplied version,
contains the corrected app service, and matches the Factory-seed SHA256 in the
RootFS manifest. This corroborates artifact identity; the physical observations
below remain the operator's hardware evidence.

### Exercised hardware behavior

| Check | Reported result |
| --- | --- |
| Complete X2000 Development build, including MIPS compilation | PASS |
| Kernel and RootFS deployment | PASS |
| Automatic Screen start after a regular reboot, without manual display-manager start | PASS; display manager `active` |
| Screen execution and VT ownership | Unprivileged `fre3nder` on tty7; `console check` confirmed `VT_PROCESS` and `KD_GRAPHICS` |
| Linux framebuffer text console on tty1 | Usable |
| USB keyboard Ctrl+Alt+F1/F7 and return to graphics | PASS; UI restored correctly |
| Touchscreen and standby/wakeup | PASS |
| Local root shell without the opt-in | Access refused |
| Local root shell with a regular `root:root`, `0600` opt-in file | Access granted |
| Local root shell after removing the opt-in | New access refused |
| Klipper after reboot | `active` |

First activation exposed a documentation defect: `/etc/fre3nder/` was absent on
the fresh installation, so creating only `console.enabled` failed. The current
[activation instructions](../../docs/display.md#optional-passwordless-local-root-shell)
create the directory with `root:root`, mode `0755`, before the single-link
regular opt-in file with mode `0600`.

### Startup investigation and offline evidence

The local app-service investigation reproduced a premature failure when child
`exec` was delayed by 200 ms. The old `while running` condition treated the
launching shell's temporary `/proc` identity as a failed app, removed its PID
marker and could leave a subsequently started process untracked. The corrected
service keeps waiting while the launched child is alive; readiness still
requires the validated app identity and first-frame marker. S64 separately
polls service status and tty7's VT/graphics modes instead of checking them once.

Existing host tests cover delayed process identity, delayed readiness, immediate
success, missing-process and missing-VT timeouts, partial-start cleanup, and
console mode/ownership restoration. These are fixture/mock results, distinct
from the successful physical boot and interactive checks above. In particular,
they do not qualify every forced crash, timeout or recovery path on hardware.

### Historical implementation references

The earlier VT configuration review cited
[NebulaOS-kernel commit 4ade16b5139ca6706137f94466397e2d801ad051](https://github.com/coreflake1/NebulaOS-kernel/commit/4ade16b5139ca6706137f94466397e2d801ad051)
as an fbcon configuration comparison. That citation remains provenance for the
configuration investigation, not a runtime dependency or an imported VT
controller. Fre3nder's console and app handoff use Linux fbcon, VT, HID, evdev
and TTY ownership. Existing display/touch driver derivation remains documented
in the [hardware provenance](#provenance) above and the source manifest.

Two implementation details explain the current boot-output path. Deferred
fbcon takeover is scheduled asynchronously: writing `rotate_all` before binding
can have no effect, so the helper waits for actual attachment. Capturing rcS
through a pipe/tee could wait on stdout inherited by long-lived services;
the helper instead captures to a volatile file and replays it after rcS exits.

### Remaining boundaries and implementation finding

Forced SIGKILL/crash, hung live VT-controller recovery and timeout/failure
cleanup were not comprehensively exercised on hardware. The reported boot
does not establish a repeated-boot reliability count, a complete print with
this VT app package, or support across other hardware revisions. It also does
not qualify an independently built release artifact at the prepared release
pin. Automatic recovery from a still-live hung VT controller is not implemented.

The initial source review found a difference from the requested `root:root` opt-in
policy: `root_owned()` in the [console helper](../../configs/x2000/rootfs-overlay/usr/libexec/fre3nder/console)
checked `st_uid == 0`, but not `st_gid == 0`. A file or parent directory with
UID 0 and a different GID could therefore pass when its other checks passed.
Mode `0600` still denied group access to the file; the finding was a
policy-enforcement gap, not evidence of an authentication bypass.

**Resolved in source; offline validated, not deployed.** The subsequent
correction requires UID 0 and GID 0 for `/etc`, `/etc/fre3nder` and
`/etc/fre3nder/console.enabled`. All existing file-type, permission, symlink and
hardlink checks remain, including exact mode `0600` and one hard link for the
opt-in. `/run/fre3nder-root/status` retains its UID-0 ownership contract without
a fixed GID. The correction passed 14 Console/Displaymanager tests and the
Display-Service fixtures offline. The hardware results above describe the
preceding implementation; the new GID check has not been deployed to or tested
on the physical printer.
