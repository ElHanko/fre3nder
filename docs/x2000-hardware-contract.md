# X2000 hardware and boot contract

This contract describes the productive Fre3nder host for the investigated
Ender-3 V3 KE / F005 reference. Other hardware/firmware revisions require
verification. The current kernel and ordered patch series are defined in
[sources.json](../configs/x2000/sources.json).

## Evidence and status vocabulary

`PROVEN` is directly observed reference evidence. `LIKELY` is an inference;
`VENDOR-DEPENDENT` means no suitable open path is established; `UNKNOWN` is
unresolved; `NOT REQUIRED` excludes a function from the selected scope.
`SOURCE IMPLEMENTED`, `BUILT` and `OFFLINE CHECKED` describe separate source,
build and offline states. `QUALIFIED ON DEVICE` applies only to the exact
hardware, source/artifact identity, slot and exercised behavior in its record.
A host-kernel result does not automatically requalify all peripherals or a new
package, byte sequence, slot or release.

| Function | Current interface / boundary | Reference status |
| --- | --- | --- |
| CPU/RAM/eMMC | X2000 SMP, 256-MiB declared RAM, MMC/GPT, immutable SquashFS plus logical SYS/HOME | Host baseline qualified; exact reservation/RPMB behavior remains bounded |
| USB | Linux host for storage, Ethernet and UVC under normal printer power; preserve external BootROM recovery separately | Bounded reference evidence; not every USB role/power mode |
| Ethernet | USB CDC-NCM administration, boot-time Ethernet-first with WLAN fallback | Reference path qualified; no runtime/hotplug failover |
| WLAN | CYW43430, regular linux-firmware/CLM and unchanged Radxa NVRAM | QUALIFIED ON DEVICE (WLAN ONLY) for recorded integration |
| F005 | Exclusive passive `/dev/ttyS1`, 230400 baud, 8N1 | Exact MCU identity gates; no inferred new print qualification |
| Display/touch | fbdev, PC22 backlight, NS2009/I2C4, evdev | Reference hardware path qualified; package boundaries in [display](display.md) |
| Camera | UVC/index-0 V4L2 capture → loopback streamer → `/webcam/` | Recorded reference camera path qualified; late insertion needs manual start |
| ADXL345/Host MCU | `/dev/spidev2.0` → Linux-process MCU PTY → upstream Klipper | Reference communication/input shaping qualified; calibration is device-specific |
| BL24C16F | No required dependency in current open-printer scope | NOT REQUIRED; preserve protected contents |
| Watchdog/reset | Keep compatible reset/recovery boundary | Broader policy/acceptance remains unresolved |

Bluetooth was not tested or qualified. The integrated Ethernet MAC is outside
the productive design. Historical measurements and qualification identities
are in [hardware evidence](../research/docs/x2000-hardware-qualification.md),
[F005 validation](../research/docs/f005-hardware-validation.md) and
[build history](../research/docs/x2000-build-history.md).

## Minimal Fre3nder backlight path

The DTS uses PC22 active-high `gpio-backlight` without `default-on`. The display
manager/app controls backlight through Linux; PC21 is not claimed or toggled.
Framebuffer, NS2009, permissions and beeper details are in [display](display.md).

## Required open-host interfaces

The selected appliance therefore needs, at minimum:

```text
X2000 SMP + DRAM + eMMC
X2000 UART -> /dev/ttyS1 @ 230400 -> Mainline F005
X2000 SPI -> /dev/spidev2.0 -> ADXL345 -> Linux Host MCU
display + touch input
SDIO WLAN with its required firmware and board data
USB CDC-NCM Ethernet with boot-time WLAN fallback
USB UVC camera -> uvcvideo -> V4L2 /dev/videoX -> localhost MJPEG streamer
               -> Lighttpd /webcam/ -> Moonraker webcam -> Fluidd
Linux USB role(s) where required by the selected appliance
reset/watchdog behavior appropriate to an unattended appliance
```

The host system must keep the F005 UART exclusively owned by Klipper. It must
not reproduce the stock updater's boot-window or firmware-update behavior.
BootROM USB recovery is a separate preserved boundary, not a dependency on a
Linux USB host implementation.

## WLAN early-firmware contract

The productive Kernel embeds the selected CYW43430 `.bin`, matching
`.clm_blob`, and unchanged Radxa AZW372 `.txt` through
`CONFIG_EXTRA_FIRMWARE`; the same files remain in the RootFS for later
requests. `CONFIG_BRCMFMAC=y` registers `brcmfmac` at device initcall time.
The KE WLAN patch exposes the SDIO card during a late initcall, which reaches
`brcmf_sdio_probe()` and `request_firmware_nowait()` before
`prepare_namespace()` mounts the real SquashFS RootFS. Firmware available
only from that RootFS cannot reliably satisfy the first probe. Exact file
hashes, licensing, and the reference-system WLAN qualification are in
[`configs/x2000/sources.json`](../configs/x2000/sources.json) and
[Buildroot maintenance](buildroot-maintenance.md).

## ADXL345 and Host-MCU contract

The canonical configuration uses `[mcu rpi]` at `/tmp/klipper_host_mcu`,
ADXL345 on `spidev2.0` at 2 MHz and `axes_map: z,y,x`. The DTS uses software SPI:
SCK GPE16, MOSI GPE17, MISO GPE18 active-high, CS GPE21 active-low. `spi2` and
one chip select expose `/dev/spidev2.0`; `rohm,dh2228fv` supplies the allowlisted
spidev binding, not the physical sensor identity. SPI, spi-gpio and spidev are
built in; the unrelated Ingenic hardware-SPI driver is disabled.

The wiring provenance is the [OpenKE/NebulaOS qualified implementation](https://github.com/coreflake1/NebulaOS-firmware/blob/95f770a858a1076f7ffdb6b4541181034862f57e/scripts/build/accelerometer-eeprom-bus-enable-variant.sh).
It is external hardware evidence, not imported runtime code or qualification of
other Fre3nder artifacts. Original comparison and independent qualification are
preserved in [hardware evidence](../research/docs/x2000-hardware-qualification.md#adxl345-and-host-mcu-contract).

S59 requires spidev, starts `/usr/bin/klipper_mcu -r -I /tmp/klipper_host_mcu`,
checks exact process identity and waits for the PTY. S60 refuses Klippy when
that prerequisite is missing. PTY creation alone does not prove an ADXL sensor:
Klippy config opens SPI, while sensor identity is checked when sampling begins.
Existing HOME configuration is retained; newly supplied sections need deliberate
manual integration. Shaper/calibration values in the reference configuration
are not universal. BL24C16F is not part of this required path; do not access or
modify it as an incidental sensor task.

## Camera contract

The required path is USB UVC → `uvcvideo` → V4L2 capture → `mjpg-streamer` at
`127.0.0.1:8080` → Lighttpd `/webcam/` → Moonraker → frontend.
S63 scans sysfs for an index-0 character device bound to `uvcvideo`; neither
Stock `video4` nor any other fixed `videoN` index is an API. Standard UVC/V4L2
support is retained; Ingenic ISP, Halley5 camera and OV2735A paths are excluded.

[S63](../configs/x2000/rootfs-overlay/etc/init.d/S63fre3nder-camera) currently
passes resolution `1920x1080` and frame rate `30` to the input plugin. These
are service defaults, not proof that every camera supports them or a new hardware
qualification. Camera environment overrides are not a supported public contract.
Buildroot supplies the streamer and plugins under `/usr/lib/mjpg-streamer/`.

Lighttpd strips the `/webcam/` prefix and proxies to loopback. The platform
`fre3nder/camera.conf` fragment advertises `/webcam/?action=stream` and
`/webcam/?action=snapshot`; existing Moonraker configuration needs the include.
There is no automatic restart after late attachment/reconnection. Inspect the
status first; a bounded manual S63 start is the current administrative path.
Creality cam_app/WebRTC/AI middleware is outside scope.

## Boot contract

The board DTS embeds no `/chosen/bootargs` or slot-specific root. The existing
boot chain supplies the selected kernel's command line and matching RootFS.
[Storage](storage-layout.md#current-ab-mapping) defines the system pairs.
Qualified B-side slot-neutral-kernel evidence and separately recorded B→A
Factory-app deployment evidence retain their own exact identities; neither
establishes that an arbitrary current image was exercised from both slots.
No unrecorded fallback, BootROM sequencing or loader commands are guaranteed.

## Stock-compatibility constraints

Gate 1 is **SATISFIED** by the current evidence review. The vendor
Windows/Cloner process is vendor-documented, Linux-independent, and its required
material is preserved and offline validated, but recovery execution remains
documented and not personally rehearsed on the reference board.

The current A/B design uses the existing p1 selector and p5/p7, p6/p8 system
pairs only through defined, authorized deployment or OTA operations. This
does not make the other stock structures free space. The remaining
constraints are:

- Preserve the stock pre-p1 loader area. Do not treat unused bytes or an
  inactive A/B side as free open-system storage outside the defined update
  operation.
- Preserve p2 `sn_mac` as protected factory/identity data. It is not an
  open-system configuration store and must never be cloned or overwritten.
- Do not alter eFuses, RPMB, eMMC boot configuration, boot0/boot1, or factory
  identity material without separate explicit authorization. RPMB use is still
  UNKNOWN.
- The vendor recovery package overwrites the user-area boot payload, p3, p5,
  and p7; its configured erase map also erases p1, the inactive system side,
  p9, and part of p10, while p2 lies outside its configured ranges. Actual
  preservation remains unverified until an actual Cloner execution and post-boot
  identity check are authorized and completed.
- Stock first boot can recreate p9 and p10. Fre3nder currently keeps SYS and
  HOME on separate external backends; internal persistence needs a separate
  location and migration decision.
- Keep BootROM recovery reachable and do not depend on a permanent undocumented
  special state.

Historical Stock boot reconstruction and kernel selection are preserved in
[hardware evidence](../research/docs/x2000-hardware-qualification.md#boot-contract)
and [kernel feasibility](../research/docs/x2000-kernel-dt-feasibility.md).
