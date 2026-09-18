# X2000 hardware and boot contract

This contract defines the minimum X2000 host capabilities that an open
replacement must provide for the investigated Ender-3 V3 KE reference system.
It began as a Phase 3.1 analysis result. Later sections also record selected
source implementations and offline build results. A source implementation or
offline build does not by itself imply a hardware result.

Unless a source says otherwise, observations are scoped to the investigated
F005 reference system running Creality firmware V1.1.0.15. They must not be
assumed to apply to every Ender-3 V3 KE revision.

The productive kernel is now upstream Linux `v6.6.18` plus Fre3nder P01-P14,
configured by `kernel-clean-port.defconfig` and released as
`6.6.18-fre3nder`. Its Phase-5 offline integration is complete, but it has not
been hardware-qualified. Kernel-related hardware results in this contract were
obtained with the preceding `6.6.18-rt23` vendor-kernel path unless explicitly
identified as clean-port evidence; they establish required hardware behavior
but do not qualify the clean port.

## Evidence and status vocabulary

- `PROVEN`: directly observed on the reference system or established by the
  captured reference data.
- `LIKELY`: the required replacement path follows from the evidence, but its
  exact X2000 Device Tree binding or a mainline test is not yet established.
- `VENDOR-DEPENDENT`: the stock function is known, but the available evidence
  does not establish a suitable open kernel/DT path.
- `UNKNOWN`: a required technical property has not yet been established.
- `NOT REQUIRED`: observed hardware/software is not required for the selected
  Phase-3 target at this stage.
- `SOURCE IMPLEMENTED`: reproducible project inputs exist, but the resulting
  artifact has not necessarily been built or qualified on hardware.
- `BUILT`: the relevant artifacts were produced successfully from the recorded
  project inputs.
- `OFFLINE CHECKED`: generated artifacts passed the recorded build-time checks;
  this does not imply execution or qualification on the reference device.

The matrix deliberately records the stock interface rather than copying stock
software. “Open target implementation” is a required interface, not an
implementation commitment.

| Function | Reference hardware | Attachment | Stock driver/software | Kernel/DT dependency | Open target implementation | Status | Scope/evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CPU / SMP | Ingenic X2000-family, two XBurst II V2 cores | SoC | Linux 4.4.94 SMP | X2000 CPU, clocks, SMP bring-up | Linux LTS with both cores available | PROVEN REQUIREMENT / CLEAN PORT OFFLINE | Reference inventory and the former vendor-kernel runtime report two CPUs. The upstream-v6.6.18 clean-port implementation is offline-integrated but not hardware-qualified. |
| RAM | 256 MiB declared by command line | SoC DRAM | Stock kernel | DDR initialization and memory reservation | Kernel/DT memory and reserved-memory suitable for the appliance | PROVEN | `mem=256M@0x0`; exact reservation map remains UNKNOWN. |
| eMMC | DG4008 eMMC, user area plus boot0/boot1/RPMB | X2000 MMC | Stock MMC and GPT/A/B updater | X2000 MMC, GPT, SquashFS, ext4 | Linux MMC and immutable system/persistent-data separation | PROVEN | Reference capture validates layout; RPMB use remains UNKNOWN. |
| USB | Linux USB host path is hardware-verified under normal printer power; a separate physical BootROM USB recovery entry is observed | X2000 USB/OTG | Stock kernel | X2000 USB/OTG node, PHY, role/power wiring | Linux USB role(s) only where required by the appliance | PROVEN ON LEGACY KERNEL | On the investigated reference system, the former Develop kernel (`6.6.18-rt23`) enumerated the root hub, internal USB hub, AX88179B, and a USB mass-storage device when the pad was powered through the printer. Powering only through the internal Micro-USB brought up DWC2/root hub but produced no children; this is a power-path limitation, not a GPC9 causality proof. The bounded result does not inventory every Linux USB role or qualify the clean port. Preserve BootROM USB recovery independently. [^usb-power] |
| Ethernet | External AX88179B adapter presenting CDC-NCM interfaces | Linux USB host | Not required for the observed stock path | USB host plus `usbnet`, `cdc_ether`, and `cdc_ncm` | Boot-time Ethernet-first administration path with WLAN fallback | PROVEN | On the investigated reference system, `cdc_ncm` bound the adapter, created the Ethernet interface, detected carrier, and obtained a DHCP lease. Production leaves WLAN down after Ethernet success and falls back to WLAN only when Ethernet fails during boot. Runtime/hotplug failover is not implemented. [^usb-power] |
| WLAN | Broadcom/Cypress SDIO device on `mmc1` | SDIO | `bcmsdh_sdmmc`, `cywdhd` | MMC/SDIO, power/reset GPIO, Broadcom firmware/NVRAM | Standard Linux WLAN stack | QUALIFIED ON LEGACY KERNEL (WLAN ONLY) | The production firmware/NVRAM inputs remain linux-firmware `20250211` firmware `7.45.98.118 (7d96287 CY)` / FWID `01-32059766`, its matching CLM, and the unchanged BSD-3-Clause Radxa AZW372 NVRAM. On 2026-09-14 those exact inputs were built with the then-productive vendor kernel, passed p6/p8 write readback and Fre3nder B boot from `/dev/mmcblk0p8`, exposed the pinned NVRAM at runtime, and passed WPA association, DHCP, and 10/10 gateway ICMP packets on the investigated reference system. Stock p5/p7 and the Ethernet default path remained unchanged; the final selector was `STOCK_A`. This evidence does not qualify the clean-port SDIO path. Bluetooth was not tested or qualified. [^phase32] [^radxa-nvram] |
| UART -> F005 | Main MCU F005/GD32F303 | `/dev/ttyS1`, 230400 baud | `ingenic-uart`; Stock Klipper; Phase-2 Mainline Klippy | UART controller, pinmux, clock, stable tty node | Upstream Klipper owns the same UART exclusively at 230400, 8N1 | PROVEN | `ttyS1` is stock node `10031000.serial` with compatible `ingenic,8250-uart`. The Mainline F005 first print passed on this reference; an LTS X2000 UART/clock board route remains unproven. |
| Display | 480x272 framebuffer at 60 Hz on the portrait-mounted panel; `fb0` through `fb3` | X2000 display path | `jzfb` stock framebuffer/display stack | Display controller, panel, clocks, power/backlight, reserved memory | X2000 framebuffer/panel path with GuppyScreen Core-UI | QUALIFIED ON LEGACY KERNEL / CLEAN PORT OFFLINE | The former vendor-kernel project kernel/DTS/RootFS path produced physical framebuffer output with correct panel colors on the investigated reference system. GPC22 backlight control, automatic startup, 60-second standby, and first-touch wake are physically demonstrated. The current GuppyScreen pin was persistently deployed and qualified through normal printer control and a complete real print. The P13/P14 clean-port implementation is offline-integrated but not hardware-qualified. See [x2000-display-touch.md](x2000-display-touch.md) and [guppyscreen.md](guppyscreen.md). [^phase32] |
| Touch | NS2009 at I2C address `0x48` on bus 4 | I2C 4, evdev input | Stock touchscreen driver | I2C controller, NS2009 node, `pendown-gpios`/pinctrl | Project-carried GPL NS2009 driver through evdev into GuppyScreen | QUALIFIED ON LEGACY KERNEL / CLEAN PORT OFFLINE | On the former vendor-kernel path, the investigated reference system enumerated the controller, identified it dynamically as `ns2009_ts`, emitted raw X/Y events, and demonstrated calibrated touch mapping with `display_rotate: 1`, first-touch wake, and audible touch feedback. The P11 clean-port implementation is offline-integrated but not hardware-qualified. See [x2000-display-touch.md](x2000-display-touch.md) and [guppyscreen.md](guppyscreen.md). [^phase32] |
| Camera | One active Stock alias resolves to `video4`; nodes `video0` through `video4` exist | USB UVC endpoint | `uvcvideo`, `cam_app`, `mjpg_streamer`, MJPEG TCP 8080 | Qualified USB host path plus UVC/V4L2 | USB UVC -> `uvcvideo` -> V4L2 capture node -> `mjpg-streamer` on localhost -> Lighttpd `/webcam/` -> Moonraker -> Fluidd | QUALIFIED ON DEVICE | On the investigated reference system, Fre3nder selected the index-0 `uvcvideo` capture node, served JPEG snapshot and multipart MJPEG data only on loopback, proxied the external `/webcam/` path through Lighttpd, published the config-sourced webcam through Moonraker, and displayed the real image in Fluidd. Camera insertion after a camera-absent boot still requires a manual S63 start. [^phase32] |
| ADXL345 | ADXL345 accelerometer | `spidev2.0`, chip select 0 | Klipper Linux Host MCU | `spi-gpio` GPIO/pinmux/CS, `spidev` child node | Upstream Klipper Linux-process MCU using `/dev/spidev2.0` | INPUT SHAPING QUALIFIED ON DEVICE | On the investigated reference device, the complete path through NumPy, `SHAPER_CALIBRATE` X/Y, the extended 100-Hz X sweep, and `SAVE_CONFIG` succeeded. The measured reference baseline is MZV at 62.4 Hz for X and MZV at 39.8 Hz for Y; it is not universal across printers. [^klipper-host-mcu] [^openke-adxl] |
| Linux Host MCU | X2000 Linux process | `/tmp/klipper_host_mcu` | `/usr/bin/klipper_mcu -r` | Linux process, Unix PTY, required SPI character device | Upstream Klipper Linux-process MCU before Klippy | QUALIFIED ON DEVICE | On the investigated reference device, the built binary ran on the X2000, created the PTY, and exchanged real traffic with Klippy `[mcu rpi]`. This result is scoped to that reference device. [^klipper-host-mcu] |
| BL24C16F | 2-KiB I2C EEPROM | I2C 2, addresses `0x50`--`0x57`, 400 kHz | Creality `bl24c16f` Klipper module | I2C 2 only if a retained function needs it | No target dependency currently identified | NOT REQUIRED | It is configured on the reference, but the Phase-2 complete print did not require it. The available module exposes generic EEPROM read/write commands; no evidence shows that normal open Host-MCU/ADXL operation needs its contents. |
| Watchdog / reset | Boot/Reset controls and SoC recovery entry | board-specific | `ingenic-watchdog`; stock boot chain | Reset source and, if used, watchdog DT node/driver | A demonstrable non-destructive reset/watchdog path | LIKELY | Stock node `10002000.watchdog` uses `ingenic,watchdog`. The selected SDK has this path and NebulaOS supplies a bounded watchdog fix; reset policy and reference-board acceptance remain open. [^phase32] |

The validated Ethernet path is the external USB CDC-NCM adapter, not the X2000
integrated MAC. The integrated-MAC physical path remains outside the current
Production design. [^linux-dwmac]

## Minimal Fre3nder backlight path

The project DTS contains the minimal project-authored `gpio-backlight` node
using GPC22/PC22, active high, and no `default-on`. The source is **OFFLINE
IMPLEMENTED**. A kernel-only offline build passed with
`CONFIG_BACKLIGHT_CLASS_DEVICE=y` and `CONFIG_BACKLIGHT_GPIO=y`; its generated
DTB contains exactly one `gpio-backlight` node. Its decompiled GPIO cells are
`<0x08 0x16 0x00 0x00>`: the generated DTB resolves phandle `0x08` uniquely to
`gpc`, and `0x16` is pin 22. Thus GPC22 active-high without `default-on` is
**OFFLINE CONFIRMED**. Subsequent reference-hardware testing demonstrated the
physical backlight effect, automatic UI startup, 60-second standby, and
first-touch wake. The complete documented framebuffer, NS2009 evdev, calibrated
touch, and GuppyScreen Core-UI path is qualified on that reference system.

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

## ADXL345 and Host-MCU contract

The stock reference configuration declares `[mcu rpi]` on
`/tmp/klipper_host_mcu`, then uses `spidev2.0` with an ADXL345 at 2 MHz and axes
map `z,y,x`. This establishes the required interface chain:

```text
ADXL345 -> software SPI GPIO / CS 0 -> /dev/spidev2.0
        -> Klipper Linux-process MCU -> upstream ADXL345 support
        -> ACCELEROMETER_QUERY / SHAPER_CALIBRATE
```

The pinned upstream Klipper source confirms that its Linux-process MCU uses the
ordinary `/dev/spidev<bus>.<cs>` interface. Its `linuxprocess.config` seed is
used without interactive menu configuration, and `klipper_mcu` is compiled
with the same Buildroot-internal MIPS32r2/O32/hard-float/FPXX/NaN2008 compiler
as the rest of userspace. The RootFS installs it as `/usr/bin/klipper_mcu`.
This is an upstream implementation and introduces no Creality or NebulaOS
runtime component.

The project DTS implements the software bus as follows: SCK GPE16 active high,
MOSI GPE17 active high, MISO GPE18 active high, and CS GPE21 active low. A
single chip select and the `spi2` alias make the child appear as
`/dev/spidev2.0`. These values and polarities come from externally
hardware-qualified OpenKE/NebulaOS evidence at exact commit
`95f770a858a1076f7ffdb6b4541181034862f57e`; Fre3nder independently confirmed
their interpretation against the pinned Linux 6.6.18 `spi-gpio` and SPI-core
sources. The child uses the pinned kernel's allowlisted `rohm,dh2228fv`
compatible solely to obtain the generic spidev binding; it does not describe
the fitted sensor identity. Generic SPI, `spi-gpio`, and spidev are built in,
while the unrelated Ingenic hardware-SPI driver remains disabled. [^openke-adxl]

At boot, `S59fre3nder-klipper-mcu` first requires `/dev/spidev2.0`, then starts
`/usr/bin/klipper_mcu -r -I /tmp/klipper_host_mcu`, verifies that its PID
belongs to that exact command, and waits a bounded interval for the PTY.
`S60fre3nder-klipper` refuses to start if that PTY is unavailable. Pinned-source
inspection establishes a more precise boundary: `klipper_mcu` creates the PTY
during process setup; Klippy's MCU configuration then opens
`/dev/spidev2.0`; the ADXL345 identity/register transaction begins only when a
measurement command such as `ACCELEROMETER_QUERY` starts sampling. A missing
host MCU or missing spidev node therefore prevents Klippy readiness; with a
usable spidev node but an absent or wrong sensor, the ADXL identity failure is
expected at measurement time.

On 2026-09-11, a manual development build completed the kernel, DTB, Linux MCU,
RootFS, and full-artifact path. Its build gates checked the effective SPI
kernel configuration, decoded ADXL-related DTB properties, the stripped
`klipper_mcu` ELF/ABI/interpreter/libc contract, and the binary, services,
endpoints, and canonical configuration in the built RootFS. The resulting
development manifest identifies a dirty worktree; all entries in the generated
full-artifact `SHA256SUMS` passed verification. This established **SOURCE
IMPLEMENTED / STATICALLY CHECKED / BUILT / OFFLINE CHECKED** status; the
separate device result follows below.

The development artifacts were subsequently deployed through the established
full X2000 path. Kernel and RootFS readback passed, Stock p5 and p7 remained
unchanged, the system booted from p8, and the selector was restored to
`STOCK_A`. On the investigated reference device, `/dev/spidev2.0` was a
character device, `klipper_mcu` ran with `-r -I`, its PTY resolved to
`/dev/pts/0`, and Klippy reported real `[mcu rpi]` traffic. The physical ADXL345
responded successfully to `ACCELEROMETER_QUERY`. These results qualify the
Fre3nder Host-MCU and ADXL communication chain on that device.

The RootFS default already contained the four Host-MCU/ADXL sections, but S60
correctly preserved the existing persistent `printer.cfg` instead of replacing
it. The sections were copied into that file for this controlled qualification;
this is not a deployment or ADXL failure and does not establish an automatic
configuration-migration policy.

A subsequent RootFS-only development build included Buildroot-native NumPy and
validated both the legacy-output `ADOPTED` and following fingerprint-matched
`HIT` paths. Its idempotent Moonraker post-build step and final RootFS
checks completed successfully. Deployment replaced and verified only p8; p6
and the existing kernel were unchanged, the system booted from p8, and the
selector ended at `STOCK_A`.

On the investigated reference device, Python 3.12.14 imported NumPy 1.25.0
from the system RootFS, a repeated `ACCELEROMETER_QUERY` returned
`8580.269578, -296.082377, 592.164754`, and `MEASURE_AXES_NOISE` completed with
159.113215 (x), 95.617217 (y), and 90.125327 (z). This qualifies the complete
Host-MCU/ADXL/NumPy noise-measurement path on that device.

`SHAPER_CALIBRATE` later passed for X and Y, including a successful repeated X
sweep through 100 Hz. The original 80-Hz X sweep produced a technically valid
3hump_ei fit at 88.6 Hz, above its actually excited range; the extended sweep
instead recommended MZV at 62.4 Hz. Y recommended MZV at 39.8 Hz. `SAVE_CONFIG`
successfully persisted those four values. The tracked configuration retains
the qualified `axes_map: z,y,x`, uses `max_freq: 100`, and publishes this
reference-device shaper baseline.

The tracked `max_accel: 4500` is conservatively below Klipper's theoretical
smoothing-based suggestion of `max_accel <= 4700 mm/s²` for the limiting Y/MZV
result. It is not a mechanical maximum, and all values remain specific to the
investigated reference device. `TEST_RESONANCES` remains an optional raw-data
diagnostic, not an unmet qualification gate after the completed
`SHAPER_CALIBRATE` runs.

OpenKE's hardware result remains external evidence for the board wiring. The
Fre3nder qualification above is an independent result limited to the
investigated reference device and is not a general claim for other hardware
revisions.

The BL24C16F is on the same host-MCU class of interface but is not part of the
observed ADXL345 path. Its stock module stores/reads generic EEPROM data and
offers diagnostic/write commands. No retained evidence establishes a required
calibration or identity dependency for the selected open-host scope. Do not
read, copy, or overwrite it as part of Phase 3.1; retain its contents in the
protected private backup and defer further classification until a concrete
function requires it.

## Camera contract

The reference system exposes five V4L2 nodes and maps the active Creality camera
alias to `video4`. `cam_app` and `mjpg_streamer` provide an MJPEG service on TCP
8080. The active camera endpoint is an observed USB UVC device using
`uvcvideo`; this proves a standard V4L2 transport on the reference. The Linux
USB host path has since been qualified independently on the investigated
reference system. Stock's `video4` index is not a stable Fre3nder interface.

The required replacement contract is therefore deliberately narrow:

```text
USB UVC -> uvcvideo -> V4L2 /dev/videoX -> mjpg-streamer
        -> 127.0.0.1:8080 -> Lighttpd /webcam/
        -> Moonraker [webcam fre3nder_camera] -> Fluidd
```

The camera/runtime leg is **QUALIFIED ON DEVICE** on the investigated reference
system. Fre3nder exposed the UVC capture endpoint as `/dev/video0` with
`index=0` and the companion metadata endpoint as `/dev/video1` with `index=1`.
S63 selected `/dev/video0` from sysfs, and `mjpg_streamer` served a valid JPEG
snapshot plus a multipart MJPEG stream at `127.0.0.1:8080`; a bounded run did
not produce new kernel USB/UVC errors. The corresponding kernel and RootFS
inputs were built, deployed, and checked on that system. This result remains
scoped to the investigated reference device and camera revision.

The productive clean-port defconfig retains only the standard UVC/V4L2 capture
path and excludes the Ingenic ISP, Halley5 camera-board, and OV2735A paths. S63 scans
`/sys/class/video4linux/video*`, follows each node's real driver link, and uses
an index-0 character device bound to `uvcvideo`; it does not assume `video4` or
select an accompanying UVC metadata node. Buildroot supplies
`/usr/bin/mjpg_streamer` and the required plugins under
`/usr/lib/mjpg-streamer/`. S63 supplies no resolution or frame-rate override and
keeps port 8080 loopback-only.

The Lighttpd/Moonraker/Fluidd leg is also **QUALIFIED ON DEVICE**. Lighttpd
exposes `/webcam/` on its existing port 80 listener, proxies only that prefix to
`127.0.0.1:8080`, and strips `/webcam/` before forwarding.
Moonraker's platform-owned
`/home/fre3nder/printer_data/config/fre3nder/camera.conf` advertises
`/webcam/?action=stream` and `/webcam/?action=snapshot`; the existing
`[include fre3nder/*.conf]` loads it. On the investigated reference system,
Moonraker returned the enabled `fre3nder_camera` with `source: config`, the
external snapshot returned a valid JPEG, and Fluidd displayed the real camera
image without separate frontend configuration. Port 8080 remained loopback-only.

The resulting qualification is:

| Camera leg | Status |
| --- | --- |
| USB UVC | QUALIFIED ON DEVICE |
| `uvcvideo` / V4L2 | QUALIFIED ON DEVICE |
| Dynamic index-0 `/dev/videoX` selection | QUALIFIED ON DEVICE |
| `mjpg-streamer` | QUALIFIED ON DEVICE |
| Localhost HTTP/JPEG | QUALIFIED ON DEVICE |
| Lighttpd `/webcam/` | QUALIFIED ON DEVICE |
| Moonraker webcam configuration/API | QUALIFIED ON DEVICE |
| Fluidd camera display | QUALIFIED ON DEVICE |

Automatic hotplug restart remains open: when S63 runs at boot without a camera,
later insertion does not trigger another start. A manual
`/etc/init.d/S63fre3nder-camera start` works; automatic retry is a separate QoL
item and is not a blocker for the qualified normal path.
Reimplementing `cam_app`, Creality WebRTC, or AI middleware is outside scope.
The 2023-08-03 X2000 community-kernel status matrix recorded display and camera
as unsupported. It is historical community feasibility evidence only, not a
definitive assessment of later X2000 kernel trees; the same README separately
states that Ingenic later ported Linux 6.6 LTS to XBurst2 processors.
[^ingenic-community]

## Boot contract

The following reconstruction is only as strong as the available capture. It
does not claim the exact X2000 BootROM sequence or U-Boot environment.

| Stage | Observed/inferred source and handoff | Replacement classification | Evidence/status |
| --- | --- | --- | --- |
| X2000 BootROM | Boot/Reset reaches Ingenic USB Boot mode; normal-media selection is not directly observed. | SHOULD KEEP FOR STOCK COMPATIBILITY | BootROM itself is not a project replacement target. Normal selection is UNKNOWN. |
| Stage 1 / SPL | Vendor SPL/U-Boot-style material begins at user-area LBA 0 before p1. The recovery package contains an X2000 SPL and loads its recovery Stage 2 to RAM. | SHOULD KEEP FOR STOCK COMPATIBILITY | Persistent placement is PROVEN; its normal boot sequencing is UNKNOWN. |
| U-Boot / second-stage loader | The same pre-p1 payload contains vendor-style loader material. The captured Linux image is a U-Boot legacy `uImage`. | SHOULD KEEP FOR STOCK COMPATIBILITY | It is LIKELY to load the selected kernel and command line; commands/environment are UNKNOWN. |
| RTOS A/B | p3/p4 are stock update payloads. Their runtime role in the Linux boot path is not established. | UNKNOWN | Preserve/reserve for stock compatibility; do not assign to the open design. |
| Kernel A/B | p5/p6 contain legacy Linux images; the selected stock system boots a 4.4.94 kernel. | MUST REPLACE | Open appliance needs an LTS-oriented kernel, but no version is selected in Phase 3.1. |
| Device Tree | Reference compatible strings identify X2000; no separate reference DTS/DTB has been retained. | MUST REPLACE | Exact load location and node contents are UNKNOWN. |
| RootFS A/B | p7/p8 are stock SquashFS images; command line selects p7 on the captured A side. | MUST REPLACE | An immutable Buildroot root filesystem is the target. |
| Writable system data | p9 is the stock overlay; p10 is stock `/usr/data`. | UNKNOWN / RESERVED | Reuse or replacement is deferred to the persistent-storage/update design. Phase 3.1 grants no ownership of p9 or p10. |

The captured command line is:

```text
console=ttyS4,115200n8 mem=256M@0x0 mem=0M@0x30000000 lcm_id=0
init=/linuxrc root=/dev/mmcblk0p7 rootwait rootfstype=squashfs ro
```

Together with the `ota` selector and paired kernel/rootfs partitions, this
supports the inference that the stock loader selects an A/B kernel and passes a
matching root device. It does not prove the loader implementation, the DTB
load address, or the fallback behavior for a damaged selector.

## Stock-compatibility constraints

Gate 1 is **SATISFIED** by the current evidence review. The vendor
Windows/Cloner process is vendor-documented, Linux-independent, and its required
material is preserved and offline validated, but recovery execution remains
documented and not personally rehearsed on the reference board.

The future design must preserve these constraints:

- Reserve the stock pre-p1 loader area and p1--p10 until a separately
  authorized design can prove otherwise. Do not treat unused bytes or an
  inactive A/B side as free open-system storage.
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
- Stock first boot can recreate p9 and p10. Open configuration and persistent
  user data therefore need a later, separately designed location and migration
  policy.
- Keep BootROM recovery reachable and do not depend on a permanent undocumented
  special state.

Consequently, Phase 3.1 makes no open partition, A/B, installer, rollback, or
bootloader decision. A valid later outcome remains: stock structures are kept
reserved and the open appliance uses a separate image/update strategy only
after stock-return effects are understood.

## LTS and Buildroot selection criteria

Phase 3.2 must compare pinned, maintained candidates rather than selecting a
kernel or Buildroot release for novelty. A candidate must be evaluated in this
order:

1. X2000 CPU/SMP, DRAM, eMMC, UART, SPI, I2C, display/touch, SDIO WLAN, camera,
   USB as required, and reset/watchdog needs;
2. maintainable LTS/security and bug-fix support;
3. upstream support before vendor patches, with each unavoidable patch scoped;
4. reproducible, pinned source and toolchain inputs;
5. practical boot time and memory footprint for 256 MiB RAM; and
6. a read-only image, separate persistent data, controlled image activation,
   and rollback design that does not consume stock structures by assumption.

Buildroot must likewise be a stable, pinned release used to construct an
appliance, not a rolling general-purpose distribution.

## Phase-3.2 feasibility result

The authorized sanitized binding capture and the public source reconciliation
are complete. [x2000-kernel-dt-feasibility.md](../research/docs/x2000-kernel-dt-feasibility.md)
records the historical selection of the pinned Ingenic Linux 6.6.18 X2000 SDK
mirror for the first qualified implementation. The productive source basis is
now upstream Linux v6.6.18 plus P01-P14. NebulaOS remains attributable KE prior
art rather than an adopted distribution.

[^klipper-host-mcu]: [Upstream Klipper Linux-process MCU documentation](https://github.com/Klipper3d/klipper/blob/master/docs/RPi_microcontroller.md) and source paths `src/linux/spidev.c` / `src/linux/i2c.c`, inspected at the Phase-2 upstream comparison basis `0499b30374315f2a9f49fc12808527fc7d0f5cfa`.
[^openke-adxl]: [OpenKE/NebulaOS hardware-qualified ADXL `spi-gpio` implementation at commit `95f770a858a1076f7ffdb6b4541181034862f57e`](https://github.com/coreflake1/NebulaOS-firmware/blob/95f770a858a1076f7ffdb6b4541181034862f57e/scripts/build/accelerometer-eeprom-bus-enable-variant.sh), plus its [later known-good configuration reconciliation at commit `40a9ff6161bad1363279cd3f516b2d48bb25dea1`](https://github.com/coreflake1/NebulaOS-firmware/blob/40a9ff6161bad1363279cd3f516b2d48bb25dea1/docs/adxl-known-good-reconciliation.md). These are external hardware evidence, not imported runtime code or Fre3nder qualification.
[^linux-dwc2]: [Upstream Linux DWC2 parameters](https://github.com/torvalds/linux/blob/v6.12/drivers/usb/dwc2/params.c), Linux v6.12, inspected 2026-08-21.
[^linux-dwmac]: [Upstream Linux Ingenic DWMAC implementation](https://github.com/torvalds/linux/blob/v6.12/drivers/net/ethernet/stmicro/stmmac/dwmac-ingenic.c), Linux v6.12, inspected 2026-08-21. It defines `ID_X2000` and the `ingenic,x2000-mac` compatible.
[^ingenic-community]: [Ingenic-community Linux README at commit `91fe78280ac7dd0dae0f58cb271e821bd39ba97e`](https://github.com/Ingenic-community/linux/tree/91fe78280ac7dd0dae0f58cb271e821bd39ba97e), inspected 2026-08-21. Its X2000 status matrix is dated 2023-08-03; its separate current note says Ingenic later ported Linux 6.6 LTS to XBurst2 processors. This is community-maintained historical feasibility evidence, not an upstream-Linux support claim or a definitive assessment of later X2000 kernel trees.
[^phase32]: [Phase-3.2 kernel and Device Tree feasibility](../research/docs/x2000-kernel-dt-feasibility.md), including the public Ingenic release identity, pinned public source mirror, and separately scoped NebulaOS hardware prior art.
[^radxa-nvram]: [Unmodified Radxa/rkwifibt AZW372 NVRAM at commit `3d93dbcf5ff6e04fa760a56a0dad9f6077394072`](https://github.com/radxa/rkwifibt/blob/3d93dbcf5ff6e04fa760a56a0dad9f6077394072/firmware/infineon/CYW43438/cyw43438_azw372.txt), qualified with the official linux-firmware `.bin` and `.clm_blob` and the resulting Fre3nder Kernel/RootFS on the investigated reference system on 2026-09-14. This evidence covers WLAN, not Bluetooth.
[^usb-power]: [X2000 A/B bring-up and development plan](../research/docs/x2000-ab-bringup-plan.md), bounded USB host power-path qualification on the investigated reference system.
