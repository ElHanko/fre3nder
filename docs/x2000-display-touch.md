# X2000 integrated display and touch hardware

This document records the productive Fre3nder hardware implementation and
qualification of the integrated Ender-3 V3 KE display, backlight, and
touchscreen on the investigated reference system.

The hardware path was qualified on real hardware on 2026-09-12.

This qualification covers the Linux kernel, Device Tree, framebuffer,
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

These values are qualification observations, not a universal calibration
contract. Exact scaling, axis transformation, inversion, and rotation belong
to the local presentation/input layer.

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

The productive X2000 kernel build contains:

~~~text
configs/x2000/ke-display.patch
configs/x2000/ke-touch.patch
configs/x2000/ender3-v3-ke.dts
configs/x2000/kernel.fragment
~~~

`build/x2000/entrypoint.sh` applies and validates the display and touch patches
during kernel preparation.

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

The kernel base used by these patches is the pinned public Ingenic SDK:

~~~text
Llixuma/ingenic-linux-kernel6.6-x2000-v1.0-20250221
commit a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b
Linux 6.6.18-rt23
~~~

The open display and touchscreen reference material was inspected from:

~~~text
coreflake1/NebulaOS-kernel
commit 88a0e1ecc6ace7c9e4ad99d6fa49e272180fd5a9
~~~

The exact source paths, revisions, roles, and licenses are recorded in
`configs/x2000/sources.json`.

The display-derived kernel material is recorded as GPL-2.0-only.

The NS2009-derived kernel material is recorded as GPL-2.0-or-later.

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

The following remain outside this qualification:

- local printer UI
- display/UI rotation
- touch calibration and coordinate transformation for the final UI
- application startup and recovery behavior
- broader qualification across other hardware revisions
