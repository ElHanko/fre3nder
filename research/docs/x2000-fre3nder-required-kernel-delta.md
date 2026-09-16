## Fre3nder hardware and kernel requirements

This inventory is limited to the Fre3nder inputs in
`configs/x2000/kernel.fragment`, `configs/x2000/ender3-v3-ke.dts`, the three
`configs/x2000/ke-*.patch` files, and `configs/x2000/sources.json`. The source
basis recorded there is Linux `6.6.18-rt23` from the pinned X2000 SDK commit
`a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`. Existing effective kernel
configuration artifacts were used only to identify the immediate controller
symbols selected by the base defconfig. This first inventory does not enumerate
their transitive implementation; the following section does. It includes only
the later clean-port decisions needed to prevent the current vendor
configuration from being mistaken for a requirement.

| Function | DTS reference | `compatible` | Relevant enabled Kconfig | Presumed responsible driver |
| --- | --- | --- | --- | --- |
| X2000 board identity and 256 MiB DRAM | `/`, `/memory@0` | `creality,ender-3-v3-ke`, fallback `ingenic,x2000`; none for memory | `CONFIG_DT_ENDER3_V3_KE` (added by the build integration) | MIPS XBurst2/X2000 platform and the selected built-in DTB; memory is a standard DT declaration |
| Kernel scheduling and immutable/persistent root support | `/chosen` selects `/dev/mmcblk0p8`, SquashFS, and read-only root; no separate peripheral node | none | `CONFIG_PREEMPT`, `CONFIG_FILE_LOCKING`, `CONFIG_BLK_DEV_INITRD`, `CONFIG_OVERLAY_FS`, `CONFIG_SQUASHFS`, `CONFIG_SQUASHFS_XZ` | Kernel scheduler, VFS/OverlayFS, block-initrd support, and SquashFS/XZ. `CONFIG_INITRAMFS_SOURCE=""` means that no built-in initramfs content is named here |
| eMMC system storage | `&msc0`, `&msc0_8bit`; 8-bit, non-removable, high-speed/HS200 declaration | inherited `ingenic,sdhci` | `CONFIG_MMC`, `CONFIG_MMC_BLOCK`, `CONFIG_MMC_SDHCI`, `CONFIG_MMC_SDHCI_INGENIC` | `sdhci-ingenic.c` plus the MMC/SDHCI core |
| Main printer MCU transport | `&uart1`, `&uart1_pin`, child `uart1_pc_txrx`; GPC23/GPC24 | inherited `ingenic,8250-uart` | `CONFIG_SERIAL_INGENIC_UART`, `CONFIG_SERIAL_INGENIC_CONSOLE` | `ingenic_uart.c`; provides the Fre3nder `/dev/ttyS1` path used by Klipper for the F005 MCU |
| USB controller, PHY, role and board power | current `&otg`, `&otg_phy`; GPD17 active-low VBUS detect and GPC9 active-high VBUS drive | current vendor tree inherits `ingenic,x2000-dwc2-hsotg`, `ingenic,usbphy-x2000`; the clean port uses upstream `ingenic,x2000-otg`, `ingenic,x2000-phy` | the current vendor configuration enables DWC2 dual-role, external-VBUS detect and role switching; the clean-port requirement is DWC2 host only | The demonstrated functions are USB mass storage, CDC-NCM Ethernet and UVC camera. The clean port models GPC9 as a fixed-regulator-backed DWC2 `vbus-supply` and omits GPD17; no Device/Gadget, dual-role, role-switch, HNP or SRP requirement is established. |
| Boot-local USB provisioning | no static child node; device enumerates below `&otg` | supplied by the attached USB mass-storage device | `CONFIG_USB_STORAGE`, `CONFIG_FAT_FS`, `CONFIG_VFAT_FS` | USB mass-storage, SCSI/block, FAT/VFAT; Fre3nder mounts the selected FAT32 provisioning medium read-only |
| External USB Ethernet | no static child node; device enumerates below `&otg` | supplied by USB interface descriptors | `CONFIG_USB_NET_DRIVERS`, `CONFIG_USB_USBNET`, `CONFIG_USB_NET_CDC_NCM`; effective selection also has `CONFIG_USB_NET_CDCETHER` | `usbnet`, `cdc_ether`, and `cdc_ncm`. The observed AX88179B presents CDC-NCM interfaces and binds `cdc_ncm` |
| Optional alternate mode of the same USB Ethernet adapter | no static child node | supplied by USB interface descriptors | `CONFIG_USB_NET_AX88179_178A` | `ax88179_178a`; enabled and retained, but it did not bind to the currently observed CDC-NCM presentation and is not the demonstrated runtime path |
| USB camera capture | no static child node; camera enumerates below `&otg` | supplied by USB UVC descriptors | `CONFIG_MEDIA_SUPPORT`, `CONFIG_MEDIA_SUPPORT_FILTER`, `CONFIG_MEDIA_CAMERA_SUPPORT`, `CONFIG_VIDEO_DEV`, `CONFIG_MEDIA_CONTROLLER`, `CONFIG_MEDIA_USB_SUPPORT`, `CONFIG_USB_VIDEO_CLASS` | `uvcvideo` and V4L2; provides the `/dev/videoX` capture endpoint consumed by `mjpg_streamer` |
| SDIO WLAN | `&msc1`, `&msc1_4bit`, RTC32K in its known working enabled state, `/wifi-bt-power`; GPD4 WLAN_REG_ON and GPA1 fixed-supply control | inherited `ingenic,sdhci`; `regulator-fixed` for the supply; future `mmc-pwrseq-simple` for WLAN_REG_ON | `CONFIG_MMC`, `CONFIG_MMC_SDHCI`, `CONFIG_MMC_SDHCI_INGENIC`, `CONFIG_REGULATOR_FIXED_VOLTAGE`, `CONFIG_WLAN_VENDOR_BROADCOM`, `CONFIG_BRCMFMAC`, `CONFIG_BRCMFMAC_SDIO`, `CONFIG_CFG80211`, `CONFIG_FW_LOADER` | The qualified current runtime uses patched `sdhci-ingenic.c`/`ingenic_sdio.c`; the clean-port architecture instead uses generic MMC pwrseq (`CONFIG_PWRSEQ_SIMPLE`), fixed regulator, normal first rescan, and `brcmfmac` SDIO. The firmware, CLM, and AZW372 NVRAM recorded in `sources.json` remain part of the WLAN path. |
| ADXL345 accelerometer for input shaping | `/spi-gpio-adxl345`, `/spi-gpio-adxl345/spidev@0`, `&aliases` (`spi2`); SCK GPE16, MOSI GPE17, MISO GPE18, CS GPE21 | `spi-gpio`; child `rohm,dh2228fv` | `CONFIG_SPI`, `CONFIG_SPI_GPIO`, `CONFIG_SPI_SPIDEV`; immediate effective selections include `CONFIG_SPI_MASTER` and `CONFIG_SPI_BITBANG` | `spi-gpio.c` and `spidev.c`; exposes `/dev/spidev2.0` to the Klipper Linux-process MCU. The child compatible is only the pinned kernel's spidev allow-list token, not the fitted chip identity |
| 480x272 parallel-RGB display output | `&dpu`, `/fre3nder-panel`; reset PB16 | inherited `ingenic,dpu`; panel `fre3nder,ender3-v3-ke-480x272` | `CONFIG_FB`, `CONFIG_FB_INGENIC`, `CONFIG_FB_INGENIC_STAGE`, `CONFIG_FB_INGENIC_DISPLAYS_STAGE`, `CONFIG_STAGE_ENDER3_V3_KE_480X272` | Ingenic `fb_stage`/`ingenicfb.c` plus the panel driver added by `ke-display.patch`; provides `/dev/fb0` as a 480x272, 32-bpp BGRX/RGB888-compatible framebuffer. The DPU reduces that input in hardware to the physical parallel RGB565 panel output at 60 Hz. |
| Display backlight | `/backlight`; GPC22 active-high | `gpio-backlight` | `CONFIG_BACKLIGHT_CLASS_DEVICE`, `CONFIG_BACKLIGHT_GPIO` | Generic `gpio_backlight.c`; its sysfs interface is used by GuppyScreen for startup, standby, and wake |
| Resistive touchscreen | `&i2c4`, `&i2c4_pc`, `/.../touchscreen@48`; I2C address `0x48`, GPC25/GPC26, pendown GPC15 active-low | inherited controller `ingenic,x2000-i2c`; child `nsiway,ns2009` | `CONFIG_I2C`, `CONFIG_I2C_INGENIC`, `CONFIG_INPUT`, `CONFIG_INPUT_EVDEV`, `CONFIG_INPUT_TOUCHSCREEN`, `CONFIG_TOUCHSCREEN_NS2009` | `i2c-ingenic.c` plus `ns2009.c` added by `ke-touch.patch`; supplies ABS_X/ABS_Y and BTN_TOUCH through evdev |
| Touch-feedback beeper | `/beeper`, `&pwm`, `&pwm3_pc`; PWM3 on PC03 | `pwm-beeper`; inherited controller `ingenic,x2000-pwm` | `CONFIG_PWM`, `CONFIG_PWM_INGENIC_V2`, `CONFIG_INPUT_MISC`, `CONFIG_INPUT_PWM_BEEPER` | GuppyScreen emits `EV_SND`/`SND_TONE`; the productive path uses PWM3 at 260 Hz, normal polarity and 50% duty cycle through generic `pwm-beeper` and a small ordinary X2000 PWM provider. |
| Shared GPIO and pin multiplexing for the above devices | `&gpa`, `&gpb`, `&gpc`, `&gpd`, `&gpe` and the named pinctrl groups above | inherited parent `ingenic,x2000-pinctrl` | `CONFIG_PINCTRL`, `CONFIG_PINCTRL_INGENIC`, `CONFIG_PINCTRL_INGENIC_V2`, `CONFIG_GPIOLIB`, `CONFIG_OF_GPIO` | Ingenic X2000 pinctrl/GPIO implementation and the GPIO consumer API |
| SoC watchdog exposure | `&watchdog` | inherited `ingenic,watchdog` | `CONFIG_WATCHDOG`, `CONFIG_INGENIC_WDT` | `ingenic_wdt.c`; the node and driver are enabled in the current vendor-based configuration, but no Fre3nder userspace watchdog consumer is referenced by the inspected inputs. The later watchdog retention decision drops this watchdog-class path from the future upstream port; only the independent WDT-based platform restart primitive remains required. |

The complete board-DTS node inventory is: root `/`; `/chosen`; `/backlight`;
`/beeper`; `/fre3nder-panel`; `/memory@0`; `/wifi-bt-power`;
`/spi-gpio-adxl345` and its `/spi-gpio-adxl345/spidev@0` child; reopened
`&aliases`;
reopened `&uart1_pin` and its new `uart1_pc_txrx` child; `&uart1`; `&msc0`;
`&msc1`; `&otg`; `&otg_phy`; `&uart3`; `&i2c4` and its
`touchscreen@48` child; `&watchdog`; and `&dpu`. The references from those
nodes are `&gpa`, `&gpb`, `&gpc`, `&gpd`, `&gpe`, `&pwm`, `&pwm3_pc`,
`&msc0_8bit`, `&msc1_4bit`, `&rtc32k_enable`, `&rtc32k_disable`,
`&wifi_bt_power`, `&i2c4_pc`, `&otg_phy`, and the locally defined
`&adxl_spi` and `&uart1_pc_txrx` labels.

The current board file's complete explicit compatible set is
`creality,ender-3-v3-ke`, `ingenic,x2000`, `gpio-backlight`, `pwm-beeper`,
`fre3nder,ender3-v3-ke-480x272`, `regulator-fixed`, `spi-gpio`,
`rohm,dh2228fv`, and `nsiway,ns2009`. The immediately referenced controller
nodes inherit `ingenic,8250-uart`, `ingenic,sdhci`,
`ingenic,x2000-dwc2-hsotg`, `ingenic,usbphy-x2000`,
`ingenic,x2000-i2c`, `ingenic,watchdog`, `ingenic,dpu`, and
`ingenic,x2000-pwm` from `x2000.dtsi`; GPIO references are children of the
`ingenic,x2000-pinctrl` node.

The fragment also deliberately excludes unrelated paths: Ingenic hardware
SPI and IIO are disabled because ADXL345 uses GPIO SPI plus spidev; the
integrated Ingenic MAC is disabled because networking uses USB Ethernet or
SDIO WLAN; platform/ISP camera support is disabled because the camera is USB
UVC; sound/ASoC is disabled because the beeper uses PWM input; and the legacy
BCMDHD and GT9XX paths are disabled in favor of `brcmfmac` and NS2009.

Remaining boundaries and uncertainties are:

- `CONFIG_BLK_DEV_INITRD` is enabled, but `CONFIG_INITRAMFS_SOURCE=""` names
  no built-in initramfs and the selected root is the p8 SquashFS. Actual use of
  an external initrd is not established by the inspected inputs.
- `&uart3` is explicitly disabled because it shares GPC25/GPC26 with I2C4.
  Despite the fixed regulator's `wifi_bt_power` name and the SDIO clock pin
  states, only WLAN is a current qualified consumer; Bluetooth is not a
  Fre3nder requirement established by these inputs.
- `/chosen` supplies the productive kernel command line
  `console=ttyS4,115200 root=/dev/mmcblk0p8 rootwait rootfstype=squashfs ro`.
  It contains neither an `earlyprintk` nor an `earlycon` argument. The inherited
  UART4 node is disabled in `x2000.dtsi` and is not enabled or assigned a
  pinctrl group by the board DTS. No Getty, productive service, recovery path,
  or debug path uses `ttyS4`; its `console=` argument was carried forward from
  the captured Stock command line and is stale for the clean port.
- The display patch can optionally consume `ingenic,vdd-en-gpio`, but the
  Fre3nder panel node does not provide it. The current qualified path uses
  PB16 reset and the separate PC22 backlight and deliberately does not drive
  PC21.
- The watchdog node and driver are enabled in the current vendor-based image,
  but later analysis establishes that Fre3nder has no productive `/dev/watchdog`
  consumer. For the future upstream port the watchdog-class driver and DT node
  are dropped; only the independent WDT-based platform restart primitive remains.
  The exact Creality bootloader state can still be checked later with an early
  read-only WDT/reset-cause observation if desired.
- The board-level `creality,ender-3-v3-ke` compatible identifies the DTB; the
  inspected inputs do not contain or require a separate driver bound to that
  board string.

## Required Ingenic kernel components

This section traces only the proven Fre3nder functions above through the pinned
Linux `6.6.18-rt23` source at SDK commit
`a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`. Paths are relative to
`sdk/kernel/kernel-6.6`. The effective Fre3nder kernel configuration is the
selection basis. Unless stated otherwise, a component originates in that SDK;
the board DTS, NS2009 and panel drivers, and the WLAN edits originate in the
corresponding Fre3nder inputs named in the first section. A symbol or object
appearing in an SDK defconfig or an unconditional vendor directory alone is
not evidence that Fre3nder needs its behavior.

The classifications used here are exact:

- **REQUIRED**: directly implements a demonstrated Fre3nder hardware path.
- **CURRENT VENDOR TREE — TRANSITIVE REQUIRED**: is not itself a demonstrated
  peripheral function, but the selected board, a required driver, or the
  current vendor link layout cannot operate or link without it. This
  classification describes dependencies of the current vendor build, not
  requirements that a future clean port must retain in the same form.
- **CURRENT VENDOR CONFIG/LINK DEPENDENCY ONLY**: is selected or referenced by
  the current vendor configuration but implements no demonstrated productive
  requirement and must not be carried into the clean port.
- **UNCLEAR**: enabled and reachable, but actual Fre3nder use is not proven.
- **NOT REQUIRED**: no path from a demonstrated Fre3nder function reaches it.

The dependency walk stops when it reaches generic Linux subsystems such as
MMC, USB, networking, V4L2, framebuffer, input, SPI, PWM, regulator, or GPIO
consumer APIs. Such generic code is named where it identifies the concrete
endpoint, but is not expanded into a complete Linux dependency inventory.

### XBurst2/X2000 boot and DT infrastructure

| Classification | Exact component files | Kconfig and Makefile selection | Origin and required chain | Reason |
| --- | --- | --- | --- | --- |
| **REQUIRED** | `module_drivers/dts/x2000/ender3-v3-ke.dts` (staged from `configs/x2000/ender3-v3-ke.dts`) | `CONFIG_DT_ENDER3_V3_KE`; added to `arch/mips/xburst2/soc-x2000/Kconfig.DT` and `module_drivers/dts/Makefile` by the X2000 build integration | Fre3nder board selection -> built-in DTB | This is the concrete board description that enables every controller in the first section. |
| **CURRENT VENDOR TREE — TRANSITIVE REQUIRED** | `arch/mips/xburst2/core/prom.c`, `arch/mips/xburst2/soc-x2000/setup.c`, `arch/mips/xburst2/soc-x2000/include/soc/base.h`, `arch/mips/xburst2/soc-x2000/include/soc/ddr.h` | `CONFIG_MACH_XBURST2`, `CONFIG_SOC_X2000`, `CONFIG_INGENIC_BUILTIN_DTB`; `arch/mips/xburst2/Makefile`, `core/Makefile`, and `soc-x2000/Makefile` | selected built-in board DTB -> `get_fdt_addr()` -> `__dt_setup_arch()` -> `plat_of_populate()`; boot -> `of_clk_init()`, `timer_probe()`, `irqchip_init()` | Supplies the XBurst2 firmware/DT handoff and X2000 OF platform creation needed before any DT-described device can probe. The two headers supply the directly used X2000 address and DDR definitions. |
| **CURRENT VENDOR TREE — TRANSITIVE REQUIRED** | `arch/mips/xburst2/core/sc.c`, `arch/mips/xburst2/core/smp.c`, `arch/mips/xburst2/core/include/core_base.h`, `arch/mips/xburst2/core/include/ccu.h`, `arch/mips/xburst2/core/include/mxuv3.h`, `arch/mips/xburst2/soc-x2000/include/cpu-feature-overrides.h` | `CONFIG_BOARD_SCACHE`, `CONFIG_XBURST2_CPU_SCACHE`, `CONFIG_SMP`, `CONFIG_NR_CPUS=2`; `core/Makefile` | X2000 CPU selection -> secondary-cache DMA operations and XBurst2 SMP setup -> per-CPU IRQ/timer initialization; generic MIPS context-switch header -> XBurst2 `mxuv3.h` | The cache/SMP code and its register headers are active properties of the selected two-core X2000 platform. `mxuv3.h` remains a compile-time architecture header, but X2000's feature override makes its runtime calls disappear; this does not make `common/mxuv3.c` required. |
| **CURRENT VENDOR CONFIG/LINK DEPENDENCY ONLY** | `arch/mips/xburst2/soc-x2000/serial.c` | built unconditionally by `soc-x2000/Makefile`; its `prom_putchar()` is consumed because `CONFIG_EARLY_PRINTK=y` | config-enabled generic MIPS early printk -> vendor X2000 `prom_putchar()` | The command line does not request `earlyprintk`, no productive early serial console is required, and no other necessary X2000 function depends on this file. Do not port it. |
| **CURRENT VENDOR TREE — TRANSITIVE REQUIRED** | `module_drivers/dts/x2000/x2000.dtsi`, `module_drivers/dts/x2000/x2000-pinctrl.dtsi`; `module_drivers/include/dt-bindings/{interrupt-controller/x2000-irq.h,clock/ingenic-tcu.h,clock/ingenic-x2000.h,sound/ingenic-baic.h,gpio/ingenic-gpio.h,net/ingenic_gmac.h,dma/ingenic-pdma.h,pinctrl/ingenic-pinctrl.h}` | included by the selected board DTS; no independent runtime Kconfig | board DTS -> base SoC nodes, phandles, constants, and pin groups | These are mandatory DT inputs. Inclusion of the sound, GMAC, and PDMA constant headers is only a preprocessing dependency and does not make those controllers required at runtime. |
| **CURRENT VENDOR TREE — TRANSITIVE REQUIRED** | `arch/mips/xburst2/soc-x2000/reset.c` — only the normal `reset_init()` / `jz_wdt_restart()` path | `reset.o` is built by `soc-x2000/Makefile`; with `CONFIG_HIBERNATE_RESET` unset, `reset_init()` assigns `_machine_restart = jz_wdt_restart` | normal Linux reboot -> `_machine_restart` -> direct TCU/WDT programming | The later watchdog retention decision establishes that the WDT hardware is still needed as a one-shot platform reset source even though the watchdog-class driver is dropped. Port only this minimal restart primitive; vendor proc/debug or unrelated reset/power-management surface is not required. |
| **NOT REQUIRED** | `arch/mips/xburst2/common/get-cpu-features.c`, `arch/mips/xburst2/common/mxuv3.c`, `arch/mips/xburst2/common/initrd-check.c`; `arch/mips/xburst2/soc-x2000/gpio.c`, `pm.c`, `pm_sleep.c`, `pm_fastboot.c`, `regs_save_restore.S` | several are unconditionally listed by vendor Makefiles; `initrd-check.o` is commented out; `CONFIG_XBURST2_CPU_TEST` and `CONFIG_FASTBOOT` are off | no call from a proven function; X2000 overrides make `cpu_has_mxuv3` false; the legacy exported GPIO helper has no required caller | Proc diagnostics, unused MXUv3 context code, the unused vendor initrd check, legacy GPIO API, suspend, and fastboot behavior are not needed merely because the vendor directory builds some of them. |

### Clock, interrupt, timer, and pin control

| Classification | Exact component files | Kconfig and Makefile selection | Origin and required chain | Reason |
| --- | --- | --- | --- | --- |
| **CURRENT VENDOR TREE — TRANSITIVE REQUIRED** | `module_drivers/drivers/clk/ingenic-v2/clk.c`, `clk-div.c`, `clk-bus.c`, `power-gate.c`, `clk-pll-v1.c`, `clk-x2000.c`; private headers `clk.h`, `clk-div.h`, `clk-bus.h`, `power-gate.h`, `clk-pll-v1.h`; `module_drivers/include/dt-bindings/clock/ingenic-x2000.h` | `CONFIG_CLK_X2000` selects `CONFIG_COMMON_CLK_INGENIC`; the X2000 branch of `module_drivers/drivers/clk/ingenic-v2/Makefile` sets its local `CLK_PLL_V1 := y` and selects the six objects | `ingenic,x2000-clocks` -> clocks for CPU/buses, INTC, OST, UART1, MSC0/1, OTG/PHY, DPU/LCD, I2C4, and PWM | `clk-x2000.c` directly uses the common clock, divider, bus, PLL-v1, gate, and power-gate helpers. Those six objects are therefore mandatory for the required consumers. `CONFIG_INGENIC_CLK_DEBUG_FS` only adds diagnostics and is not itself required. |
| **CURRENT VENDOR TREE — TRANSITIVE REQUIRED** | `module_drivers/drivers/irqchip/irq-ingenic-cpu.c`, `module_drivers/drivers/irqchip/irq-ingenic-chip.c`, `arch/mips/xburst2/core/include/irq_cpu.h`, `arch/mips/xburst2/soc-x2000/include/irq.h` | `CONFIG_IRQ_INGENIC_CPU`, `CONFIG_INGENIC_INTC_CHIP`; `module_drivers/drivers/irqchip/Makefile` | `ingenic,cpu-interrupt-controller` -> `ingenic,core-intc` -> interrupts for the required devices | Provides the CPU and SoC interrupt domains selected by `CONFIG_SOC_X2000`; the two XBurst2 headers provide their private interrupt definitions and interfaces. |
| **CURRENT VENDOR TREE — TRANSITIVE REQUIRED** | `module_drivers/drivers/clocksource/ingenic_core_ost.c` | `CONFIG_CLKSRC_INGENIC_CORE_OST`; `module_drivers/drivers/clocksource/Makefile` | `ingenic,core-ost` -> global clocksource and per-CPU clockevents; XBurst2 SMP calls its per-CPU initializer | This is the selected X2000 system timer. |
| **REQUIRED** | `module_drivers/drivers/pinctrl/pinctrl-ingenic.c`, `module_drivers/drivers/pinctrl/pinctrl-ingenic.h`; `module_drivers/include/dt-bindings/pinctrl/ingenic-pinctrl.h` | `CONFIG_PINCTRL_INGENIC_V2`; `module_drivers/drivers/pinctrl/Makefile` | `ingenic,x2000-pinctrl` -> UART1, MSC0/1, I2C4, PWM3 and GPIO-backed reset/power/backlight/touch/USB/SPI signals | One driver supplies both X2000 pin muxing and the five GPIO banks/IRQ domains used by the board. `CONFIG_PINCTRL_DUMP` is diagnostic only and not required. |
| **NOT REQUIRED** | `module_drivers/drivers/irqchip/irq-ingenic.c`, `module_drivers/drivers/clocksource/ingenic_sysost.c`, non-X2000 clock implementations and `clk-pll.c`/`clk-pll-v2.c`, `module_drivers/drivers/pinctrl/multi-vgpio.c` | not selected by the effective symbols or not matched by the active compatibles | no required board node or consumer reaches these alternatives | They implement older/different interrupt, timer, clock, PLL, or virtual-GPIO paths. |

### eMMC, SDIO WLAN, and UART1

| Classification | Exact component files | Kconfig and Makefile selection | Origin and required chain | Reason |
| --- | --- | --- | --- | --- |
| **REQUIRED IN CURRENT VENDOR TREE** | `module_drivers/drivers/mmc/host/sdhci-ingenic.c`, `module_drivers/drivers/mmc/host/ingenic_sdio.c`, `module_drivers/drivers/mmc/host/sdhci-ingenic.h`; `arch/mips/xburst2/soc-x2000/include/soc/cpm.h` | `CONFIG_MMC_SDHCI_INGENIC`; `mmc_sdhci_ingenic-objs := sdhci-ingenic.o ingenic_sdio.o` in `module_drivers/drivers/mmc/host/Makefile` | `&msc0` and `&msc1` -> `ingenic,sdhci` -> generic SDHCI/MMC; current Fre3nder WLAN patch -> MSC1 REG_ON and RTC32K pin states -> generic `brcmfmac` SDIO | The current composite object is shared by eMMC and WLAN. Its `ingenic_sdio.c` sequencing glue is required by the qualified vendor-based runtime, but **NOT REQUIRED IN THE CLEAN PORT**. The clean port retains X2000 SDHCI controller support and uses generic MMC/pwrseq for the board sequence. The Broadcom endpoint remains generic in-tree `brcmfmac`, not BCMDHD. |
| **REQUIRED** | Generic `drivers/net/wireless/broadcom/brcm80211/brcmfmac/`: base objects `cfg80211.c`, `chip.c`, `fwil.c`, `fweh.c`, `p2p.c`, `proto.c`, `common.c`, `core.c`, `firmware.c`, `fwvid.c`, `feature.c`, `btcoex.c`, `vendor.c`, `pno.c`, `xtlv.c`; BCDC `bcdc.c`, `fwsignal.c`; SDIO `sdio.c`, `bcmsdh.c`; OF `of.c`; built-in vendor cores `wcc/core.c`, `cyw/core.c`, `bca/core.c`; generic `drivers/regulator/fixed.c` | `CONFIG_BRCMFMAC=y`, `CONFIG_BRCMFMAC_PROTO_BCDC=y`, `CONFIG_BRCMFMAC_SDIO=y`, `CONFIG_OF=y`, `CONFIG_REGULATOR_FIXED_VOLTAGE=y`; brcmfmac and regulator Makefiles | MSC1/SDIO -> detected WLAN function -> `brcmfmac` -> firmware/CLM/NVRAM from `configs/x2000/sources.json`; `/wifi-bt-power` -> `regulator-fixed` | This is the exact generic WLAN composite at the dependency boundary. Its unconditionally included `btcoex.c` is coexistence support inside the WLAN driver and does not establish a Fre3nder Bluetooth device or Bluetooth stack requirement. |
| **REQUIRED** | `module_drivers/drivers/tty/serial/ingenic_uart.c`, `module_drivers/drivers/tty/serial/ingenic_uart.h` | `CONFIG_SERIAL_INGENIC_UART`; `module_drivers/drivers/tty/serial/Makefile` | `&uart1` -> `ingenic,8250-uart` -> `/dev/ttyS1` -> Klipper printer MCU | Implements the clocked/interrupt-driven UART1 controller. The board supplies no DMA properties, so no Ingenic PDMA driver is in this path. The enabled `CONFIG_SERIAL_INGENIC_CONSOLE`, `CONFIG_SERIAL_INGENIC_LARGE_BAUDRATE`, and `CONFIG_SERIAL_INGENIC_MAGIC_SYSRQ` only alter this same object and are not independently established requirements. |
| **NOT REQUIRED** | `module_drivers/drivers/mmc/host/ingenic_mmc.c`, `ingenic_mmc.h`, `ingenic_mmc_reg.h`; the BCMDHD driver tree | old MMC controller selection and disabled BCMDHD configuration | no match to `ingenic,sdhci`/generic `brcmfmac` path | These are alternative implementations. `CONFIG_MMC_INDEX_MATCH_CONTROLLER` is also off. Bluetooth and the disabled UART4 node have no demonstrated runtime path. |

### USB host, PHY, and attached generic devices

| Classification | Exact component files | Kconfig and Makefile selection | Origin and required chain | Reason |
| --- | --- | --- | --- | --- |
| **UPSTREAM — REQUIRED HOST PATH** | upstream `drivers/usb/dwc2/` | host-only DWC2 selection; no Fre3nder need for dual-role, external-VBUS detect or role switching | `ingenic,x2000-otg` -> upstream X2000 match/parameter data -> generic `phys`/`phy-names` linkage -> upstream DWC2 host core | Linux v6.6.18 already supplies X2000 HS host operation, UTMI 16-bit configuration, 16 host channels and 1024-word host FIFO data. No additional X2000-specific Fre3nder DWC2 function is statically established. |
| **UPSTREAM — REQUIRED PHY PATH** | upstream `drivers/phy/ingenic/phy-ingenic-usb.c` | generic PHY framework selection | `ingenic,x2000-phy` -> upstream X2000 PHY initialization and host-mode programming | This is the clean-port PHY base. No additional Fre3nder-specific PHY function is statically established; vendor SRBC reset, SPENDN0, TX-strength, wake handling and legacy USB-PHY callbacks remain qualification subjects rather than automatic port requirements. |
| **FRE3NDER BOARD DATA — REQUIRED** | board DTS only | `regulator-fixed` and DWC2 `vbus-supply` | GPC9 active-high -> GPIO-backed fixed regulator -> DWC2 port VBUS lifecycle | GPC9 is the hardware-required VBUS enable. Raw GPIO control from the vendor PHY is not required. GPD17 is omitted from the host-only clean port. |
| **CURRENT VENDOR TREE — TRANSITIVE REQUIRED** | `module_drivers/drivers/usb/phy/phy-ingenic-x1000.c`, `phy-ingenic-x1600.c`, `phy-ingenic-x2500.c`, `phy-ingenic-x2600.c`, `phy-ingenic-ad100.c` | all are added by the same `CONFIG_INGENIC_USB_PHY` Makefile branch | common `phy-ingenic.c` OF match table -> externally defined per-family data symbols -> final link | These five non-X2000 implementations are not runtime hardware requirements, but the current source/Makefile topology makes them link dependencies of the selected common PHY driver. |
| **NOT REQUIRED IN CLEAN PORT** | DWC2 Device/Gadget/DRD, HNP/SRP and vendor OTG/VBUS-detect glue; `drivers/net/usb/ax88179_178a.c` for the observed runtime | the current tree enables alternatives that have no demonstrated consumer | all demonstrated USB devices use the host path; the observed adapter binds CDC-NCM | Enabled alternatives are not promoted to requirements. USB mass storage, CDC-NCM and UVC remain the required generic endpoint paths. |

The generic USB boundary reached here is concrete: DWC2 builds `core.o`,
`core_intr.o`, `platform.o`, `drd.o`, `params.o`, host objects `hcd.o`,
`hcd_intr.o`, `hcd_queue.o`, `hcd_ddma.o`, dual-role `gadget.o`, and (because
debugfs is enabled) `debugfs.o`. This describes the current build, not the
clean-port requirement: only the host side is demonstrated as a Fre3nder
function, and no productive function requires a role change.

| Proven USB function | Exact generic driver files | Kconfig and Makefile selection |
| --- | --- | --- |
| Mass-storage provisioning | `drivers/usb/storage/{scsiglue.c,protocol.c,transport.c,usb.c,initializers.c,sierra_ms.c,option_ms.c,usual-tables.c}` | `CONFIG_USB_STORAGE`; `usb-storage-y` in `drivers/usb/storage/Makefile` |
| CDC-NCM Ethernet | `drivers/net/usb/usbnet.c`, `drivers/net/usb/cdc_ether.c`, `drivers/net/usb/cdc_ncm.c` | `CONFIG_USB_USBNET`, `CONFIG_USB_NET_CDCETHER`, `CONFIG_USB_NET_CDC_NCM`; `drivers/net/usb/Makefile` |
| UVC camera | `drivers/media/usb/uvc/{uvc_driver.c,uvc_queue.c,uvc_v4l2.c,uvc_video.c,uvc_ctrl.c,uvc_status.c,uvc_isight.c,uvc_debugfs.c,uvc_metadata.c,uvc_entity.c}` | `CONFIG_USB_VIDEO_CLASS`, with `uvc_entity.o` added by `CONFIG_MEDIA_CONTROLLER=y`; `drivers/media/usb/uvc/Makefile` |

### Display and framebuffer

| Classification | Exact component files | Kconfig and Makefile selection | Origin and required chain | Reason |
| --- | --- | --- | --- | --- |
| **REQUIRED** | Required subsets of `module_drivers/drivers/video/fbdev/ingenic/fb_stage/ingenicfb.c` and `dpu_ctrl.c`; private headers `dpu_reg.h`, `dpu_ctrl.h`, `dpu_dma_desc.h`; `module_drivers/drivers/video/fbdev/ingenic/include/ingenicfb.h`, `lcd_panel.h` | `CONFIG_FB_INGENIC`, `CONFIG_FB_INGENIC_STAGE`; the current vendor build also selects three framebuffer pages and four composer layers | `&dpu` -> `ingenic,dpu` -> one DMA-addressable framebuffer -> one direct RDMA descriptor/channel -> TFT timing and parallel RGB output -> `/dev/fb0` | Only the standard fbdev, direct-RDMA and TFT-output subsets implement the demonstrated primary display path. The complete vendor files are references, not wholesale port units. |
| **REQUIRED** | `module_drivers/drivers/video/fbdev/ingenic/displays/panel-ender3-v3-ke-480x272.c` | `CONFIG_FB_INGENIC_DISPLAYS_STAGE`, `CONFIG_STAGE_ENDER3_V3_KE_480X272`; entry added to the display Kconfig/Makefile by `configs/x2000/ke-display.patch` | `/fre3nder-panel` -> `fre3nder,ender3-v3-ke-480x272` -> LCD panel registration -> DPU TFT mode | This project-added panel driver supplies the 480x272 parallel-RGB timings and PB16 reset. No PC21 supply GPIO exists in the Fre3nder node. |
| **NOT REQUIRED** | `arch/mips/xburst2/soc-x2000/libdmmu.c`, `arch/mips/xburst2/soc-x2000/include/libdmmu.h`, `arch/mips/xburst2/common/proc.c`, `arch/mips/xburst2/core/include/ingenic_proc.h` | Unconditionally built or referenced by the current vendor architecture/composer layout | primary framebuffer DMA handle -> RDMA `FrameBufferAddr`; no DMMU mapping in this chain | DMMU is used only for optional composer layers and vendor DMMU UAPI. Its initialization and proc helper are vendor link/runtime ballast for the direct primary framebuffer. |
| **CURRENT VENDOR TREE — TRANSITIVE REQUIRED** | `module_drivers/drivers/video/fbdev/ingenic/jz_mipi_dsi/jz_mipi_dsi.c`, `jz_mipi_dsi_lowlevel.c`, `jz_mipi_dsih_hal.c`, `jz_mipi_dsi_phy.c`; private headers `jz_mipi_dsi_lowlevel.h`, `jz_mipi_dsih_hal.h`, `jz_mipi_dsi_phy.h`, `jz_mipi_dsi_regs.h` | entering `jz_mipi_dsi/` under `CONFIG_FB_INGENIC` unconditionally adds all four objects | selected DPU objects -> unconditional MIPI function references -> MIPI implementation objects -> final link | The Fre3nder panel runs parallel TFT/RGB and does not exercise MIPI at runtime. These files are nevertheless mandatory under the present vendor link layout, so this is a link dependency, not a MIPI hardware requirement. |
| **NOT REQUIRED** | `fb_stage/hw_composer.c`, `hw_composer_fb.c`, `sysfs.c`, `hw_composer_v4l2.c`; `fb_stage_wip/`, other panel drivers, and the X2600 rotation path | several are forced into the current composite object or enabled as vendor control infrastructure; V4L2/experimental/rotation alternatives are off | the productive framebuffer selects `DATA_CH_RDMA` and starts before optional composer export/sysfs handling | Composer layers and UAPI, dynamic sysfs controls, V4L2/writeback, experimental paths, and unrelated panels are outside the established primary framebuffer requirement. |

### I2C4/touch, PWM/beeper, GPIO SPI, and backlight

| Classification | Exact component files | Kconfig and Makefile selection | Origin and required chain | Reason |
| --- | --- | --- | --- | --- |
| **REQUIRED** | `module_drivers/drivers/i2c/busses/i2c-ingenic.c` | `CONFIG_I2C_INGENIC`; `module_drivers/drivers/i2c/busses/Makefile` | `&i2c4` -> `ingenic,x2000-i2c` -> generic I2C core -> NS2009 child | Implements the I2C4 controller and consumes its X2000 clock and interrupt; it has no additional private Ingenic helper object. |
| **REQUIRED** | `drivers/input/touchscreen/ns2009.c` | `CONFIG_TOUCHSCREEN_NS2009`; Kconfig/Makefile entries added by `configs/x2000/ke-touch.patch` | `nsiway,ns2009` at I2C address `0x48` -> input/evdev; pendown -> GPIO consumer API | This project-added generic I2C input driver is the demonstrated touchscreen endpoint. GT9xx is not on this path. |
| **REQUIRED FUNCTIONAL SUBSET** | ordinary PWM behavior from `module_drivers/drivers/pwm/pwm-ingenic-v2.c` | `CONFIG_PWM_INGENIC_V2`; `module_drivers/drivers/pwm/Makefile` | `ingenic,x2000-pwm` -> PWM3 -> generic `drivers/input/misc/pwm-beeper.c` | Fre3nder needs a small X2000 provider with `.apply()` for PWM3. The complete vendor file is only a register/sequence reference; its DMA, IRQ, debug and test surfaces are not port requirements. |
| **REQUIRED** | generic `drivers/spi/spi-gpio.c`, `drivers/spi/spi-bitbang.c`, `drivers/spi/spidev.c`; generic `drivers/video/backlight/gpio_backlight.c`; generic `drivers/input/misc/pwm-beeper.c` | `CONFIG_SPI_GPIO`, `CONFIG_SPI_BITBANG`, `CONFIG_SPI_SPIDEV`, `CONFIG_BACKLIGHT_GPIO`, `CONFIG_INPUT_PWM_BEEPER` | board GPIO/pinctrl -> software SPI and backlight; Ingenic PWM -> beeper | These are the exact generic endpoint drivers. They require the X2000 pinctrl/GPIO or PWM provider above, but no additional Ingenic SPI, IIO, backlight, or input driver. |
| **NOT REQUIRED** | Ingenic hardware-SPI and IIO/ADXL drivers, PWM v1/v3 alternatives, GT9xx touchscreen drivers | disabled or unmatched alternatives | the board uses GPIO SPI plus spidev, PWM v2, and NS2009 | None lies on a proven Fre3nder path. |

### Watchdog

| Classification | Exact component files | Kconfig and Makefile selection | Origin and required chain | Reason |
| --- | --- | --- | --- | --- |
| **NOT REQUIRED** | `module_drivers/drivers/watchdog/ingenic_wdt.c`, `module_drivers/drivers/watchdog/ingenic_wdt.h` | `CONFIG_INGENIC_WDT`; `module_drivers/drivers/watchdog/Makefile` | enabled `&watchdog` -> `ingenic,watchdog` -> generic watchdog core, but no productive Fre3nder consumer | The later watchdog retention decision is `DROP`: no productive service opens or feeds `/dev/watchdog`, the available X2000-v12 SPL source disables the counter during normal boot, and the independent Linux reboot path uses WDT hardware directly without this driver. The driver, `CONFIG_INGENIC_WDT`, and the DT watchdog node are not future-port requirements. |
| **NOT REQUIRED** | `module_drivers/drivers/watchdog/ingenic_wdt_v1.c` and other SoC watchdog variants | alternative Kconfig selections/compatibles | no match from the selected X2000 watchdog node | They are not implementations of the active compatible. |

### Classification summary

- **REQUIRED — direct X2000/board paths:** the board DTB; X2000 pinctrl/GPIO;
  the Ingenic SDHCI composite for eMMC and SDIO WLAN; Ingenic UART1; the
  upstream X2000 DWC2/USB PHY host path plus GPC9 VBUS board data; the DPU/framebuffer
  subset and Fre3nder RGB panel; Ingenic I2C4 and NS2009; Ingenic PWM v2;
  and the generic GPIO-SPI/spidev, GPIO-backlight, PWM-beeper, USB storage,
  CDC-NCM, and UVC endpoints. These functional groups, rather than a fragile
  source-file count, define the direct requirement. For USB, the retained
  requirement is the upstream X2000 DWC2/PHY host path plus the Fre3nder GPC9
  VBUS board data, not the vendor dual-role or legacy-PHY integration.
- **CURRENT VENDOR TREE — TRANSITIVE REQUIRED — platform/link infrastructure:** XBurst2 DT boot,
  secondary-cache/SMP providers; the minimal WDT-based platform
  restart primitive; the X2000 base DTS and binding headers; the Ingenic-v2
  clock implementation; the interrupt-controller implementation; the core OST
  timer; non-X2000 PHY data objects forced by the common PHY match table; and
  MIPI objects forced by the current framebuffer link
  layout. The non-X2000 PHY and MIPI groups are build/link necessities only, not
  Fre3nder hardware functions.
- **Retain/drop and architecture decisions:** no unresolved decision remains for
  PREEMPT_RT, the watchdog, early print/ttyS4, UART, I2C, MSC1 WLAN sequencing,
  the USB host/PHY/VBUS model, the PWM provider scope, DPU/fbdev, DPU DMA
  mapping, or the DPU IRQ model. Remaining checks are hardware qualification,
  including the final clean-port PWM clock/DT binding, not architecture questions.
- **NOT REQUIRED — major excluded areas:** Bluetooth; the Ingenic Ethernet MAC;
  platform camera/ISP; ASoC; hardware SPI and IIO ADXL drivers; GT9xx; BCMDHD;
  the AX88179 driver as the current runtime path; UART4 runtime use; PC21 panel
  power; external initrd use; old MMC/IRQ/timer/PWM/watchdog alternatives; the
  watchdog-class driver itself; the vendor X2000 early-print path and stale
  `console=ttyS4,115200` boot argument; non-selected display paths; XBurst2
  diagnostics/MXUv3; and X2000 power-management/fastboot plus reset proc/debug
  surface beyond the required minimal WDT-based restart primitive. Their presence in a defconfig,
  DTS include, or unconditional vendor Makefile is not evidence of a Fre3nder
  requirement.

## Minimal delta against Linux v6.6.18

This comparison uses the exact upstream commit
[`d8a27ea2c98685cdaa5fa66c809c7069a4ff394b`](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/commit/?id=d8a27ea2c98685cdaa5fa66c809c7069a4ff394b)
and the exact Ingenic SDK commit
[`a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`](https://github.com/Llixuma/ingenic-linux-kernel6.6-x2000-v1.0-20250221/commit/a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b).
It covers only the `REQUIRED` and `CURRENT VENDOR TREE — TRANSITIVE REQUIRED`
components identified above. “Port” below means the smallest functionality
that has to be represented in an upstream-based tree; it does not mean copying
the complete vendor file.

### A. Architecture infrastructure

Upstream v6.6.18 contains some declarative X2000 knowledge, but not a complete
X2000 platform. `arch/mips/generic/board-ingenic.c` recognizes
`ingenic,x2000`, `ingenic,x2000e`, and `ingenic,x2000h`, and generic MIPS code
knows the XBurst2 processor ID. However, `arch/mips/ingenic/Kconfig` stops at
`MACH_X1830`: it neither defines nor selects `MACH_X2000`. There is no upstream
`arch/mips/xburst2/` implementation and no upstream X2000 SoC DTS. The root
compatible alone is therefore not a bootable X2000 port.

| Vendor component | v6.6.18 comparison | Transitive kind | Minimal port consequence |
| --- | --- | --- | --- |
| `arch/mips/xburst2/core/prom.c`; `soc-x2000/setup.c`; `base.h`, `ddr.h` | **FULLY VENDOR-SPECIFIC**. Upstream's generic Ingenic board is the natural base, but lacks the vendor firmware/built-in-DTB handoff and X2000 platform setup. | **ARCHITECTURAL DEPENDENCY** | Add X2000 machine selection and the necessary DT handoff/population behavior to the upstream MIPS/Generic model. Do not import unrelated reset, PM, fastboot, or diagnostic code. |
| `core/sc.c`, `core/smp.c`; `core_base.h`, `ccu.h`; X2000 `cpu-feature-overrides.h` | **FULLY VENDOR-SPECIFIC**. No equivalent XBurst2 secondary-cache and two-core SMP/CCU implementation exists upstream. | **ARCHITECTURAL DEPENDENCY** | New XBurst2 cache/SMP support is required. Port only the cache maintenance, secondary-core bring-up, IPI and per-CPU initialization reached by this configuration. |
| `core/include/mxuv3.h` | **FULLY VENDOR-SPECIFIC**, but used as an architecture compile-time header; the selected X2000 feature override suppresses its MXUv3 runtime calls. | **ARCHITECTURAL DEPENDENCY** in the current architecture layout | Either provide the minimal definitions required by the XBurst2 context-switch path or restructure that path. `common/mxuv3.c` remains unnecessary. |
| `soc-x2000/serial.c` | **FULLY VENDOR-SPECIFIC** provider for `prom_putchar()` under the current config-enabled `EARLY_PRINTK` setup. | **CURRENT VENDOR CONFIG/LINK DEPENDENCY ONLY** | Do not port this file, `prom_putchar()`, the vendor X2000 early-print integration, or `CONFIG_EARLY_PRINTK` solely for this path. No replacement earlycon is required. |
| `module_drivers/dts/x2000/x2000.dtsi`, `x2000-pinctrl.dtsi`, and X2000 binding headers | **FULLY VENDOR-SPECIFIC** as files. Upstream has only `include/dt-bindings/dma/x2000-dma.h`, not the required SoC description and vendor binding constants. | **ARCHITECTURAL DEPENDENCY** | Add an upstream-style X2000 DTSI and only the binding constants used by the retained nodes. Drop disabled sound, GMAC, PDMA and other unused nodes/constants from the minimal board path where practical. |
| Ingenic-v2 clocks: `clk-x2000.c` plus `clk.c`, `clk-div.c`, `clk-bus.c`, `power-gate.c`, `clk-pll-v1.c` | **UPSTREAM BASE + X2000 ADDITION** at the subsystem level. Upstream has `drivers/clk/ingenic/{cgu.c,cgu.h,...}` and older SoC data, but no X2000 clock provider. The vendor framework is a separate implementation, not a small diff against those files. | **ARCHITECTURAL DEPENDENCY** | X2000 clock topology, PLL/divider/bus/gate and power-gate data are required. Implement them on the upstream CGU framework where it can express the hardware; do not assume all five vendor common-helper files must become new upstream files. |
| `irq-ingenic-cpu.c`, `irq-ingenic-chip.c` and private IRQ headers | **FULLY VENDOR-SPECIFIC** XBurst2/per-CPU implementation. Upstream `irq-ingenic.c` is an older single Ingenic interrupt-controller design and does not implement the `cpu-intc-map` XBurst2 SMP topology. | **ARCHITECTURAL DEPENDENCY** | Add the XBurst2 CPU interrupt dispatch and X2000 per-CPU core INTC/domain behavior; omit vendor diagnostics and unrelated wake/PM extensions unless proven necessary. |
| `ingenic_core_ost.c` | **FULLY VENDOR-SPECIFIC**. Upstream `drivers/clocksource/ingenic-ost.c` supports the older OST design, not this global-counter plus per-CPU `cpu-ost-map` implementation. | **ARCHITECTURAL DEPENDENCY** | Add the X2000 global clocksource and per-CPU clockevent implementation, including the bounds fix recorded below. |
| `libdmmu.c`, `libdmmu.h`; `common/proc.c`, `ingenic_proc.h` | **FULLY VENDOR-SPECIFIC**, but reached only by optional composer-layer address translation, vendor DMMU UAPI, and diagnostics. The direct RDMA framebuffer uses the DMA handle without DMMU. | **VENDOR LINK-LAYOUT DEPENDENCY** | Do not port DMMU or its proc wrapper for the minimal primary framebuffer. Reconsider address translation only if a future requirement deliberately adds user-virtual composer layers. |

#### Early-print clean-port decision

```text
EARLY PRINT DECISION:
DROP VENDOR EARLY PRINT
```

The productive kernel command line comes from `/chosen/bootargs` and is:

```text
console=ttyS4,115200 root=/dev/mmcblk0p8 rootwait rootfstype=squashfs ro
```

The current state is:

```text
earlyprintk:
config-enabled only

earlyprintk bootarg:
absent

earlycon:
absent

ttyS4 productive runtime use:
not established
```

`CONFIG_EARLY_PRINTK=y` activates the generic MIPS early-print path in the
current vendor configuration without an `earlyprintk` command-line argument.
`arch/mips/xburst2/soc-x2000/serial.c` supplies its `prom_putchar()` provider
and is therefore classified as:

```text
arch/mips/xburst2/soc-x2000/serial.c:

CURRENT VENDOR CONFIG/LINK DEPENDENCY ONLY
```

No other necessary X2000 function depends on this file. The clean-port rule is:

```text
Do not port:
- soc-x2000/serial.c
- prom_putchar()
- vendor X2000 early-print integration
- CONFIG_EARLY_PRINTK solely for this path
```

Do not add a replacement earlycon. There is no current productive requirement
for an early serial console.

The inherited UART4 node is disabled in the X2000 DTSI and the Fre3nder board
DTS neither enables it nor selects one of its pinctrl groups. No Getty,
productive service, recovery path, or debug path uses `ttyS4`. The console
argument was historically carried forward from the captured Stock command
line and is therefore classified as:

```text
console=ttyS4,115200:
STALE / REMOVE IN CLEAN PORT
```

This records a future clean-port action only; the current boot argument is not
changed here.

```text
UART1 / F005:
unaffected
```

The productive `/dev/ttyS1` path for the F005 MCU is a separate normal-UART
requirement and needs no early-print path. It remains subject to the independent
UART divisor decision below.

It remains unqualified which already bootloader-initialized UART, if any, the
vendor early-print scanner could physically reach. That uncertainty does not
establish a productive port requirement.

### B. Required X2000 controllers

| Function and exact files | v6.6.18 comparison | Reached difference and minimal port boundary |
| --- | --- | --- |
| eMMC/SDIO: `sdhci-ingenic.c`, `ingenic_sdio.c`, `sdhci-ingenic.h`, `soc/cpm.h` | **FULLY VENDOR-SPECIFIC** glue over the upstream SDHCI/MMC core. v6.6.18 has no Ingenic SDHCI platform driver. | Port the X2000 clock/tuning/reset/ADMA controller behavior needed by MSC0/MSC1. The generic SDHCI/MMC core is not a port item. Do not port the manual MSC1 card-detect/power sequence; the clean-port board sequence uses generic regulator, GPIO, MMC pwrseq, non-removable startup/rescan, and brcmfmac enumeration. |
| UART1: vendor `ingenic_uart.c/.h` versus upstream `drivers/tty/serial/8250/8250_ingenic.c` | **UPSTREAM BASE + X2000 ADDITION**. Upstream already implements the Ingenic register shift, UME/RTOIE handling, clocks, FIFO data, console and 8250 registration, but has no X2000 match and uses different compatibles/clock names. | Extend the upstream 8250 driver and use an upstream-style compatible/clock description. The board supplies no DMA properties, so the vendor DMA engine, custom standalone `uart_driver`, debug proc code and most of the large vendor file are not needed. The later UART divisor decision establishes that only a small X2000-specific UMR setup is additionally required for 230400 baud; nonzero UACR and the full vendor algorithm are not required. |
| DWC2: `drivers/usb/dwc2/{params.c,platform.c,core.c,core.h,hcd.c}` | **UPSTREAM X2000 SUPPORT ALREADY PRESENT; VENDOR INTEGRATION DIFFERS**. v6.6.18 already provides the `ingenic,x2000-otg` match, X2000 parameter data, HS host operation, UTMI 16-bit configuration, 16 host channels, 1024-word host FIFO data and generic PHY linkage. | Use upstream DWC2 unchanged for the host-only architecture. The vendor `INCR16` AHB value is not a demonstrated functional requirement and must not be carried for speculative performance. Legacy PHY hookup, external-VBUS detection/override, raw VBUS GPIO control and Device/Gadget/DRD integration are not clean-port requirements. The vendor early-connect check remains **UNRESOLVED / qualification item** and must not be carried preemptively. |
| USB PHY: vendor `phy-ingenic.c/.h`, `phy-ingenic-x2000.c` | **UPSTREAM X2000 SUPPORT ALREADY PRESENT**. v6.6.18 has `drivers/phy/ingenic/phy-ingenic-usb.c`, including `x2000_usb_phy_init()` and `ingenic,x2000-phy`; the vendor driver instead uses the legacy USB-PHY API and owns both board VBUS GPIOs. | Use upstream `ingenic,x2000-phy` as the clean-port base. No additional Fre3nder-specific PHY function is statically established. Vendor SRBC reset, SPENDN0, TX-strength, wake handling and legacy callbacks are hardware-qualification subjects only. Model GPC9 separately through a fixed regulator and DWC2 `vbus-supply`; omit GPD17. |
| DPU/framebuffer: required subsets of `fb_stage/{ingenicfb.c,dpu_ctrl.c}` and private register/descriptor headers | **FULLY VENDOR-SPECIFIC** for the X2000 DPU. Upstream's older Ingenic DRM/IPU files contain no X2000 DPU match or equivalent direct-RDMA descriptor implementation. | Add a clean minimal X2000 standard-fbdev driver with one DMA-addressable 32-bpp framebuffer, one direct RDMA descriptor/channel, TFT timing, parallel RGB565 output and blanking. The later `yoffset=0` pan call is non-critical and may be handled as a trivial frame-0 reselect or successful no-op. Composer, DMMU and vendor control surfaces are not part of this port boundary. |
| I2C4: `i2c-ingenic.c` | **UPSTREAM BASE + X2000 ADDITION**. Upstream `i2c-jz4780.c` implements the same X1000-style register, explicit-STOP and 64-entry-FIFO model; the later I2C decision finds no additional X2000 controller quirk required by NS2009. | Let the X2000 compatible select the existing upstream X1000 data and provide its APB-derived gate plus explicit 100 kHz bus rate in DT. Do not port the divergent vendor driver or its debug/config surface. |
| PWM3: `pwm-ingenic-v2.c` | **FULLY VENDOR-SPECIFIC** X2000 16-channel PWM block. Upstream `pwm-jz4740.c` drives TCU channels through a parent regmap and is not the controller at `0x134c0000`. | Add a reduced X2000 PWM provider. Fre3nder needs only ordinary `.apply` behavior for channel 3; DMA waveform support, debug sysfs, test allocation and unrelated M300 support are not demonstrated requirements. |
| Pinctrl/GPIO: vendor `pinctrl-ingenic.c/.h` | **UPSTREAM BASE + X2000 ADDITION**, with an important integration defect. Upstream v6.6.18 already contains X2000/X2000E pin, function, GPIO and IRQ data—including UART1 PC23/PC24, MSC0/1, I2C4 and PWM3—but its match data is guarded by undefined `CONFIG_MACH_X2000`, making the X2000 match unusable in that tree. | Reuse the upstream driver, make the existing X2000 data selectable/reachable, and translate the vendor pinctrl DTS to upstream group/function bindings. A wholesale vendor pinctrl driver is not needed. |
| Generic endpoints: fixed regulator, SPI GPIO/bitbang/spidev, GPIO backlight, PWM beeper, USB storage, CDC Ethernet/NCM, UVC and the selected brcmfmac base/BCDC/SDIO/OF/vendor-core files listed above | **IDENTICAL TO UPSTREAM** file-for-file at the two exact comparison commits. | No driver code port is needed. Only their Kconfig selection, board description, firmware inputs and X2000 providers must remain. |

The watchdog-class path is **NOT REQUIRED** for the future Fre3nder port. The
later retention analysis establishes `DROP`: no productive Fre3nder service
uses `/dev/watchdog`, and the available X2000-v12 SPL source disables the
counter during normal boot. Therefore neither upstream `jz4740_wdt.c` nor the
vendor `ingenic_wdt.c/.h` needs an X2000 port for Fre3nder. The separate normal
Linux reboot path remains a real X2000 platform requirement: retain or
reimplement only the minimal WDT-based one-shot restart primitive from
`soc-x2000/reset.c`, without registering a watchdog-class device.

### C. Fre3nder-specific components

These belong above a generic X2000 port and must remain reviewable separately:

| Component | Classification | Minimal content |
| --- | --- | --- |
| `configs/x2000/ender3-v3-ke.dts` plus its DTB Kconfig/Makefile entry | **FRE3NDER-SPECIFIC** | Board identity, memory/root choice, UART1, eMMC, SDIO WLAN power/pins, GPC9 active-high USB VBUS enable, I2C4/NS2009, DPU/panel, PWM3/beeper, backlight and GPIO-SPI ADXL345. It must be translated to the bindings chosen for the clean X2000 port; GPD17 is omitted from the host-only USB model. |
| `configs/x2000/ke-display.patch` | **FRE3NDER-SPECIFIC** | The KE panel compatible, 480x272 timings, PB16 reset and hardware-confirmed parallel RGB565 mode. The generic X2000 DPU is section B; PC21 power is deliberately not claimed. |
| `configs/x2000/ke-touch.patch` | **FRE3NDER-SPECIFIC** | NS2009 I2C input driver and Kconfig/Makefile entry, including the KE's GPC15 `pendown-gpios` path. v6.6.18 has no NS2009 driver. |
| MSC1 WLAN board data in `configs/x2000/ender3-v3-ke.dts` | **FRE3NDER-SPECIFIC — REQUIRED** | GPA1 shared-supply enable and polarity, GPD4 WLAN_REG_ON and polarity, the required delay, `non-removable`, and RTC32K in its known working enabled state. Translate these facts to generic clean-port bindings. |
| `configs/x2000/ke-wlan.patch` | **CURRENT RUNTIME WORKAROUND — NOT REQUIRED IN CLEAN PORT** | The patch's late manual insertion, detect-work cancellation, extra MMC power cycle, software card-present/SDHCI flag changes, manual rescan, direct raw GPD4 control, and vendor WLAN/RTC32K glue are not clean-port architecture requirements. The patch itself remains unchanged while the current vendor-based runtime depends on it. |

`regulator-fixed`, `brcmfmac`, `spi-gpio`, `spi-bitbang`, `spidev`,
`gpio-backlight`, `pwm-beeper`, USB storage, CDC-NCM and UVC are not
Fre3nder-specific source deltas because their selected v6.6.18 files are
identical.

#### MSC1 WLAN clean-port decision

```text
MSC1 WLAN INTEGRATION:
GENERIC LINUX MODEL SUFFICIENT
```

The future clean port needs no Fre3nder-specific MMC/SDHCI sequencing code for
the WLAN board sequence. This does not remove or reclassify the separate
generic X2000 SDHCI controller requirement.

The generic target model is:

```text
GPA1
  -> regulator-fixed
  -> active-low
  -> regulator-boot-on / regulator-always-on
  -> MSC1 vmmc-supply

GPD4 / WLAN_REG_ON
  -> mmc-pwrseq-simple
  -> active-low reset-gpios

MSC1
  -> non-removable
  -> normal MMC host startup and first rescan
  -> SDIO enumeration
  -> brcmfmac bind
```

The required GPD4 sequence is `assert low -> wait at least 100 ms -> deassert
high -> SDIO enumeration`. The selected delay must run while GPD4 remains
asserted. In Linux v6.6.18, the MMC-host `post-power-on-delay-ms` is positioned
between pwrseq assertion and deassertion and can express that hold. The
`mmc-pwrseq-simple` node's own `post-power-on-delay-ms` runs only after reset
deassertion and therefore must not be used as the 100-ms low hold.

Dynamic RTC32K switching: **not required**. The clean port must initially
preserve the known working enabled RTC32K state. The independent electrical
necessity of RTC32K was not isolated, so this conclusion does not classify the
clock itself as unnecessary.

The following current behavior is removable from the clean port:

- the WLAN `late_initcall` and vendor WLAN/RTC32K sequencing glue;
- manual software card-present, `SDHCI_DEVICE_DEAD` manipulation, and
  `SDHCI_QUIRK_BROKEN_CARD_DETECTION` for this purpose;
- cancellation of the competing detect work;
- the extra `mmc_power_off()` / `mmc_power_up()` cycle;
- manual `mmc_detect_change()` and vendor-core changes used only to permit a
  repeated rescan;
- the `wlan-reg-on-gpios` SDHCI property and raw GPD4 control in the host
  driver.

This architecture decision is not yet hardware-qualified. The minimal later
test must demonstrate:

1. GPA1 supply is active.
2. `mmc-pwrseq-simple` physically drives GPD4 low.
3. GPD4 remains low for at least 100 ms.
4. GPD4 subsequently goes high.
5. The normal first MMC rescan enumerates the SDIO device.
6. `brcmfmac` binds without manual card insertion or an additional rescan.

An earlier OpenKE pwrseq attempt executed its callback without physically
moving GPD4. This remains a hardware-qualification warning for the generic
GPIO/pwrseq integration, but it is not evidence that the vendor workaround is
an architectural prerequisite.

#### USB host clean-port decision

```text
USB ROLE:
HOST ONLY
```

The only demonstrated productive Fre3nder USB functions are USB mass storage,
CDC-NCM Ethernet, and a UVC camera. There is no demonstrated requirement for
USB Device/Gadget, dual-role operation, OTG role switching, HNP, or SRP.

```text
X2000 DWC2:

upstream Linux v6.6.18 already provides:
```

- the `ingenic,x2000-otg` compatible and match;
- X2000 parameter data;
- high-speed host operation;
- UTMI 16-bit configuration;
- 16 host channels;
- 1024-word host RX, non-periodic TX, and periodic TX FIFO data;
- generic `phys` / `phy-names` linkage.

No mandatory X2000-specific Fre3nder DWC2 extension beyond that upstream
support was found. The vendor `INCR16` AHB value is not a demonstrated
functional requirement and must not be carried solely for possible
performance.

```text
X2000 USB PHY:

upstream ingenic,x2000-phy is the clean-port base
```

No additional Fre3nder-specific PHY function is statically established. The
vendor SRBC reset, SPENDN0, TX-strength, wake-handling, and legacy USB-PHY
callback sequences are not automatic port requirements; they remain hardware-
qualification subjects if a concrete failure later points to them.

```text
GPC9:
hardware-required active-high VBUS enable

raw GPIO control from vendor PHY:
not required
```

The clean board model is:

```text
board:
  GPC9 active-high
    -> regulator-fixed
    -> DWC2 vbus-supply

DWC2:
  compatible = "ingenic,x2000-otg"
  dr_mode = "host"
  phys / phy-names
  -> upstream DWC2 host core

PHY:
  compatible = "ingenic,x2000-phy"
  -> upstream X2000 PHY implementation

GPD17:
  omitted
```

The generic regulator integration owns the DWC2 port-VBUS lifecycle.

```text
GPD17 external VBUS detect:
DEVICE/OTG ONLY for the demonstrated Fre3nder use case
```

The vendor code uses GPD17 for gadget VBUS state, gadget connect/disconnect,
and OTG notification. The productive host path detects attached devices
through DWC2 and does not require this input.

```text
HOST EARLY-CONNECT QUIRK:
UNRESOLVED / qualification item

Do not carry this quirk preemptively.
```

The workaround avoids a possible suspend/power-saving transition that would
remove VBUS after a connection is detected but before the host port is enabled.
This has not been established as X2000-specific hardware behavior; upstream
has no exactly equivalent check, and no evidence shows that Fre3nder's
productive devices require it. Re-evaluate it only if hardware qualification
produces a reproducible failure.

The following vendor functionality is removable from the host-only clean port:

- Dual-role/DRD and Gadget support as Fre3nder requirements;
- HNP/SRP and external-ID handling;
- Gadget FIFO/DMA configuration;
- GPD17 GPIO/IRQ/workqueue glue;
- the external-VBUS-detect parameter and GOTGCTL external-VBUS override;
- the external-VBUS resume workaround;
- legacy `ingenic,usbphy` integration;
- raw GPC9 control through `usb_phy_set_vbus()`;
- vendor USB-PHY OTG callbacks and role-state glue.

This architecture decision is not yet hardware-qualified. Later qualification
must cover:

1. cold boot with USB mass storage;
2. mass-storage hotplug;
3. CDC-NCM Ethernet;
4. the UVC camera;
5. suspend/resume if used productively;
6. a USB device attached very early during host startup;
7. upstream PHY initialization versus the vendor SRBC/SPENDN0/TX-strength
   sequence;
8. the `INCR16` value only if a real performance problem is observed.

None of these open checks is a reason to carry vendor code preemptively.

### D. Vendor link ballast

The following current build dependencies are not hardware port requirements:

- **CURRENT VENDOR CONFIG/LINK ONLY — X2000 early print:**
  `arch/mips/xburst2/soc-x2000/serial.c`, its `prom_putchar()` provider, and
  the vendor X2000 early-print integration are reached only because the current
  configuration enables `CONFIG_EARLY_PRINTK`. No productive early serial
  console is required, so this path is omitted without adding an upstream
  earlycon replacement.
- **VENDOR LINK-LAYOUT ONLY — other USB PHY families:**
  `phy-ingenic-x1000.c`, `phy-ingenic-x1600.c`, `phy-ingenic-x2500.c`,
  `phy-ingenic-x2600.c`, and `phy-ingenic-ad100.c`. The vendor Makefile places
  all family objects behind the single `CONFIG_INGENIC_USB_PHY`, while the
  common match table directly references every family's exported data object.
  A clean build can select common + X2000 only by putting each match/data entry
  behind its SoC Kconfig symbol or by making per-SoC composite drivers. None of
  the five files must be carried into a minimal Fre3nder port.
- **VENDOR LINK-LAYOUT ONLY — MIPI:**
  `jz_mipi_dsi.c`, `jz_mipi_dsi_lowlevel.c`, `jz_mipi_dsih_hal.c`, and
  `jz_mipi_dsi_phy.c`. `module_drivers/drivers/video/fbdev/ingenic/Makefile`
  always enters `jz_mipi_dsi/` when `CONFIG_FB_INGENIC` is set, and that
  subdirectory links all four objects. The DPU headers and `sysfs.c` also expose
  unconditional MIPI declarations/calls even though their runtime branches are
  selected only for MIPI/LVDS panels. A clean RGB-only port can guard or split
  those includes, sysfs calls and objects; the parallel-RGB timing/descriptor
  path does not require MIPI hardware.
- **VENDOR LINK-LAYOUT ONLY — DMMU proc wrapper:** `common/proc.c` and
  `ingenic_proc.h` are pulled into this path by optional DMMU diagnostics. They
  can be removed with that proc interface without changing address translation.

The vendor clock helper files are not placed in this list: their literal file
layout is replaceable, but they currently supply required clock behavior. The
early-print provider is listed as current configuration/link ballast above.

### E. NebulaOS findings

The [`openke` branch](https://github.com/coreflake1/NebulaOS-kernel/tree/openke)
is used as corroborating evidence only. Its `main` base is the same
`a98c2e1` SDK revision. Diagnostic-only commits are omitted from the port
inventory.

| Area | Classification | Relevant finding |
| --- | --- | --- |
| MSC1/SDIO WLAN | **CONFIRMS CURRENT VENDOR WORKAROUND; NOT A CLEAN-PORT REQUIREMENT** | OpenKE's bring-up established why the current late manual-insert path must avoid racing pending generic detect work. It does not establish manual insertion as a hardware property of the fixed SDIO device. With the board sequence attached to normal host startup through generic pwrseq, the first rescan replaces the late insertion and repeated-rescan workaround. See [`858509a4a`](https://github.com/coreflake1/NebulaOS-kernel/commit/858509a4a0387d4f181a01e3679213b93bbd6863), [`0494e1df7`](https://github.com/coreflake1/NebulaOS-kernel/commit/0494e1df7), and [`2947aa10f`](https://github.com/coreflake1/NebulaOS-kernel/commit/2947aa10f536afd61ad96d7801b15acdedaa1da6). |
| MSC1 clock selection | **KNOWN VENDOR FIX RELEVANT** | In the low-speed path, vendor `sdhci_ingenic_set_clock()` writes the MSC0 clock register literal even for MSC1 instead of its already-computed `cpm_msc`. OpenKE corrects that in [`858509a4a`](https://github.com/coreflake1/NebulaOS-kernel/commit/858509a4a0387d4f181a01e3679213b93bbd6863). This fix is not in the current Fre3nder WLAN patch and must be evaluated when extracting generic MSC support. |
| WLAN power DTS | **CONFIRMS FRE3NDER BOARD DATA** | OpenKE identified the active-low PA1 shared supply and PD4 WLAN_REG_ON behavior. These polarities and the low/100-ms/high requirement remain required board data, but direct raw GPIO control does not. An earlier pwrseq attempt did not physically move GPD4 despite callback execution; retain that result as a qualification warning for the clean generic GPIO/pwrseq path, not as a reason to preserve manual host-driver sequencing. See [`1143ecb97`](https://github.com/coreflake1/NebulaOS-kernel/commit/1143ecb977bc2cd361177e781172dbcaeb5c9614) and [`c12ca7cb8`](https://github.com/coreflake1/NebulaOS-kernel/commit/c12ca7cb824784fe04d557c4cf72ae858d0917fa). |
| UART1/pinctrl | **CONFIRMS FRE3NDER** | OpenKE enabled the actual printer-MCU UART, removed conflicting pin ownership, and finally restricted UART1 to TX/RX. Fre3nder uses the same PC23/PC24 pair through its own group. See [`4905cb23e`](https://github.com/coreflake1/NebulaOS-kernel/commit/4905cb23e60ce200f9969503a6b6259e731ed660), [`c60cf4d67`](https://github.com/coreflake1/NebulaOS-kernel/commit/c60cf4d67ec2f50496715efa871d5123f978b4cb), and [`970bd6b83`](https://github.com/coreflake1/NebulaOS-kernel/commit/970bd6b834ea3d0af195b6281a0deacdafff4506). |
| USB VBUS | **CONFIRMS FRE3NDER BOARD DATA** | GPC9 as the active-high VBUS enable was recovered from the stock DTB and is already cited in the Fre3nder board DTS: [`c902097d1`](https://github.com/coreflake1/NebulaOS-kernel/commit/c902097d1a79c21ef6717d7e4ecc1db2a9233990). This establishes the board signal, not a requirement for the vendor PHY's raw GPIO API; the clean port uses a fixed regulator and DWC2 `vbus-supply`. |
| OST | **KNOWN VENDOR FIX RELEVANT** | [`2d507671c`](https://github.com/coreflake1/NebulaOS-kernel/commit/2d507671c4aff8f424cbc90e7c0fb7ae525606a1) checks the `cpu-ost-map` pair index before writing. The original post-increment test emits a false overflow for exactly `NR_CPUS` pairs and could allow an out-of-bounds write for oversized data. |
| Core IRQ | **KNOWN VENDOR FIX RELEVANT** | [`e123bb14f`](https://github.com/coreflake1/NebulaOS-kernel/commit/e123bb14fd8e3fd03a5550cf187a5a9f64faf281) fixes the identical pre-write bounds error in `cpu-intc-map`. |
| TCU | **KNOWN VENDOR FIX NOT REQUIRED FOR CURRENT FRE3NDER PATH** | [`5ac124ac6`](https://github.com/coreflake1/NebulaOS-kernel/commit/5ac124ac6015d4b0c51f549cb7cd5835ccd8a97b) only downgrades a message about the optional trigger-mode IRQ. Fre3nder's dedicated X2000 PWM block and core OST do not require that optional IRQ; the watchdog-class driver is dropped, and the independent WDT-based restart primitive does not establish a need for this trigger IRQ either. |
| Watchdog | **KNOWN VENDOR FIX NOT REQUIRED FOR CURRENT PORT** | OpenKE's initial KE commit stops the hardware counter unconditionally at probe before clearing mask/flag state: [`8e97319a1`](https://github.com/coreflake1/NebulaOS-kernel/commit/8e97319a1754e264580ac39400a0c41139d2deb4). The later retention analysis classifies the watchdog-class driver as `DROP`: no productive Fre3nder consumer exists and the available X2000-v12 SPL source disables the counter during normal boot. The OpenKE probe-stop hunk is therefore not part of the current port; only the independent WDT-based platform restart primitive remains required. |
| Display/DPU | **CONFIRMS FRE3NDER** | [`4af473b43`](https://github.com/coreflake1/NebulaOS-kernel/commit/4af473b43475344c74f1718f0e9970384b9a332b) records the hardware-confirmed parallel RGB565 bus mode used by the Fre3nder panel. [`41fec9840`](https://github.com/coreflake1/NebulaOS-kernel/commit/41fec9840ceaf661fea8eb5606d4b49b25dd0bae) merely changes an error to debug output for absent optional compositor layer sizes; it is **KNOWN VENDOR FIX NOT REQUIRED FOR CURRENT FRE3NDER PATH**. The MIPI mutex cleanup in `295b7101d` is likewise irrelevant to RGB. |
| NS2009 touch | **CONFIRMS FRE3NDER** | OpenKE found that GPC15 pendown, rather than the generic Z1 threshold, is the usable touch-present signal; Fre3nder carries the cleaned optional-GPIO form. See [`713d4d196`](https://github.com/coreflake1/NebulaOS-kernel/commit/713d4d19619a62cbbb866c0d60ca4ce3eb542ac9) and cleanup [`f7ff80a8a`](https://github.com/coreflake1/NebulaOS-kernel/commit/f7ff80a8aa21886a32783dab167e451298c60a8d). |
| PWM | **CONFIRMS HARDWARE PATH; NO PROVIDER CORRECTION** | OpenKE uses the same X2000 PWM controller for the board but contains no controller-driver correction. This confirms PWM3/PC03 as the selected path, not the correctness or minimality of the vendor PWM implementation. The clean-port decision independently requires only a small ordinary provider. |

### Compact port inventory

```text
NEW FILES NEEDED FROM VENDOR (as reduced/reworked implementations):
- XBurst2 SMP/secondary-cache/CCU support and the necessary private definitions
- minimal X2000 WDT-based platform restart primitive (no watchdog-class device)
- X2000 SoC DTSI plus only required binding definitions
- X2000 clock topology/data not expressible by existing tables alone
- X2000 per-CPU core interrupt controller and core/global OST
- X2000 SDHCI platform glue for MSC0/MSC1
- minimal X2000 direct-RDMA fbdev and parallel-RGB display support
- small ordinary X2000 PWM provider; only PWM3 is a productive Fre3nder channel

UPSTREAM FILES NEEDING X2000 CHANGES:
- arch/mips Kconfig/generic Ingenic board integration and DTB wiring
- drivers/clk/ingenic/* (preferred base for X2000 clocks)
- drivers/pinctrl/pinctrl-ingenic.c (make its existing X2000 data reachable)
- drivers/tty/serial/8250/8250_ingenic.c (X2000 match/data and binding)
- drivers/i2c/busses/i2c-jz4780.c (X2000 compatible selecting existing X1000 data)

UPSTREAM USB SUPPORT USED WITHOUT A FRE3NDER DRIVER DELTA:
- drivers/usb/dwc2/*: ingenic,x2000-otg host match and parameter data
- drivers/phy/ingenic/phy-ingenic-usb.c: ingenic,x2000-phy

FRE3NDER-SPECIFIC FILES:
- Ender-3 V3 KE board DTS and DTB selection
- 480x272 parallel-RGB565 panel driver/Kconfig/Makefile entry
- NS2009 driver/Kconfig/Makefile entry with GPC15 pendown support
- MSC1 WLAN board data in the board DTS: GPA1/GPD4 wiring and polarity,
  at-least-100-ms asserted delay, non-removable, and enabled RTC32K state
- USB board data in the board DTS: GPC9 active-high fixed regulator connected
  as the DWC2 vbus-supply; host-only role; GPD17 omitted

REMOVABLE CURRENT WLAN WORKAROUNDS:
- ke-wlan.patch manual insert/power sequencing; vendor late_initcall,
  card-present/SDHCI flag manipulation, detect-work cancellation, extra MMC
  power cycle, manual rescan, raw host-driver GPD4 control, WLAN/RTC32K glue,
  and vendor-core repeated-rescan changes needed only by that path

REMOVABLE CURRENT USB/OTG FUNCTIONALITY:
- Dual-role/DRD, Gadget, HNP/SRP, external-ID and Gadget FIFO/DMA configuration
- GPD17 GPIO/IRQ/workqueue glue and external-VBUS-detect handling
- GOTGCTL external-VBUS override and external-VBUS resume workaround
- legacy ingenic,usbphy integration, raw GPC9 usb_phy_set_vbus() control, and
  vendor USB-PHY OTG callbacks/role-state glue

USB HOST EARLY-CONNECT QUALIFICATION:
- unresolved; do not carry the vendor quirk preemptively
- reassess only after a reproducible hardware failure

REMOVABLE CURRENT PWM FUNCTIONALITY:
- DMA waveform and arbitrary-waveform support
- DMA IRQ/status/retrigger and the IRQ resource/handler used for that path
- capture, complementary output, dead-time and multi-channel synchronization
- debug sysfs, test interfaces, M300-specific extras and vendor-special
  suspend/resume behavior

DROPPED VENDOR EARLY-PRINT PATH:
- soc-x2000/serial.c, prom_putchar(), vendor X2000 early-print integration, and
  CONFIG_EARLY_PRINTK solely for this path
- no replacement earlycon; no productive early serial console requirement
- console=ttyS4,115200 is stale and must be removed in the clean port
- UART1 / F005 remains unaffected as the separate productive /dev/ttyS1 path

LIKELY REMOVABLE VENDOR LINK DEPENDENCIES:
- phy-ingenic-{x1000,x1600,x2500,x2600,ad100}.c
- all four jz_mipi_dsi/*.c objects for the RGB-only configuration
- libdmmu.c/.h, common/proc.c and ingenic_proc.h with composer/DMMU UAPI removed

DROPPED VENDOR FUNCTIONALITY:
- module_drivers/drivers/watchdog/ingenic_wdt.c/.h, CONFIG_INGENIC_WDT, and the
  watchdog DT node; retain only the independent WDT-based platform restart
  primitive from the X2000 reset path

KNOWN RELEVANT VENDOR BUGS/FIXES:
- MSC low-speed clock write must use the selected controller's cpm_msc register
- cpu-ost-map and cpu-intc-map must bounds-check the pair index before writing
- the OpenKE watchdog probe-stop workaround is not part of the current port
  because the watchdog-class driver is dropped; retain only the independent
  WDT-based restart primitive
- retain hardware-confirmed UART1 PC23/PC24, USB VBUS GPC9 board data, WLAN polarities,
  NS2009 GPC15 pendown, and display RGB565 findings

DISPLAY USERSPACE SURFACE:
- resolved: standard fbdev only; composer, DMMU and vendor JZFB surfaces are not required

DISPLAY IMPLEMENTATION CONSTRAINTS:
- one framebuffer from dma_alloc_coherent(), mapped to userspace with
  dma_mmap_coherent(); no custom cache mapping or driver-side PFN remap
- one self-linked direct-RDMA descriptor/channel with continuous static scanout
- all unnecessary DPU interrupt sources masked; no functional DPU IRQ handler;
  use status polling for quick-stop where necessary
- no unresolved DPU retain/drop or implementation-architecture decision;
  hardware qualification remains
```

## PWM/beeper decision

This decision is limited to the demonstrated touch-feedback beeper on X2000
PWM3 / PC03. The complete vendor PWM driver is not a clean-port unit.

```text
PWM DECISION:
SMALL X2000 PWM PROVIDER REQUIRED
```

### Productive path and PWM-core contract

```text
GuppyScreen
  -> EV_SND / SND_TONE
  -> pwm-beeper
  -> Linux PWM API
  -> X2000 PWM3
  -> PC03
```

The demonstrated output is 260 Hz with normal polarity and a 50% duty cycle.
Generic `pwm-beeper` also maps `SND_BELL` to 1000 Hz by default, but that is not
a demonstrated productive Fre3nder use case.

The reached consumer API is `devm_pwm_get()`, `pwm_init_state()`,
`pwm_get_state()`, `pwm_set_relative_duty_cycle(..., 50, 100)`, and
`pwm_apply_state()`. Disabling changes the enabled state and reaches the same
provider `.apply()` path. Functionally, `.apply()` is therefore the only
provider callback required by Fre3nder; no additional callback is a product
requirement.

### Provider boundary

```text
drivers/pwm/pwm-jz4740.c:
NOT SUFFICIENT FOR X2000
```

The upstream JZ4740 driver is a child of the Ingenic TCU and uses its parent
regmap, per-channel timer clocks, and TCU register model. The X2000 instead has
an independent 16-channel PWM block with its own registers and shared PWM
clocks. Adding an X2000 `compatible` to `pwm-jz4740.c` is therefore not
sufficient.

The minimal X2000 provider must:

- map the PWM MMIO registers;
- enable the functional equivalent of `gate_pwm` and provide the functional
  equivalent of `div_pwm`;
- configure channel 3, including its prescaler, period counter and duty
  counter;
- select the normal output level and enable the output;
- enable and disable the channel; and
- route PWM3 to PC03 through the X2000 pinctrl description.

Only one channel, PWM3, is a productive Fre3nder requirement. A normal Linux
PWM chip may expose more hardware channels when that simplifies the provider,
but Fre3nder does not require extra channel or synchronization logic. Normal
polarity is sufficient; inverted-polarity support is not a Fre3nder
requirement.

The demonstrated vendor setup supplies a 50 MHz PWM clock and selects a `/4`
prescaler. The 260-Hz, 50%-duty signal fits comfortably in that counter model.
These values are a known functional reference, not a requirement to preserve
that exact clock architecture in the clean port.

### IRQ, DMA, and removable vendor scope

```text
IRQ required:
no

DMA required:
no
```

Ordinary PWM output runs autonomously after the channel is started. The vendor
IRQ handler belongs to DMA waveform status/retrigger handling and is not needed
for the beeper. The following vendor functionality is outside the clean-port
requirement: DMA waveform and arbitrary-waveform support; DMA IRQ/status/
retrigger; capture; complementary output; dead-time; multi-channel
synchronization; debug sysfs; test interfaces; M300-specific extras;
vendor-special suspend/resume behavior; and an IRQ resource or handler for
ordinary beeper operation.

Hardware qualification remains for:

1. the reduced register sequence on real hardware;
2. the correct idle and active output levels;
3. the clean-port PWM clock binding; and
4. 260-Hz output through PWM3 / PC03.

These qualification items do not justify carrying DMA, IRQ, debug, test, or
other unused vendor functionality preemptively.

## DPU and framebuffer decision

This decision is limited to the productive 480x272 parallel-RGB display path.
It identifies the behavior that a clean X2000 port must provide; it does not
make any complete vendor source file a port unit.

```text
DPU DECISION:
MINIMAL DIRECT-RDMA FBDEV PATH SUFFICIENT
```

### Productive fbdev contract

The demonstrated userspace endpoint is a single standard `/dev/fb0` device.
GuppyScreen's hard requirements are `open(O_RDWR)`, `FBIOGET_FSCREENINFO`,
`FBIOGET_VSCREENINFO`, `FBIOBLANK(FB_BLANK_UNBLANK)`, a writable shared
`mmap()`, and visibility of userspace CPU writes to RDMA. Its productive
sleep/wakeup path also calls `FBIOPAN_DISPLAY` with `yoffset = 0`, but an error
from that later call is non-critical. It does not use a vendor JZFB ioctl,
`FBIO_WAITFORVSYNC`, DMA-BUF, DRM/KMS, or a composer device.

The demonstrated vendor memory and scanout chain is:

```text
one dma_alloc_coherent() framebuffer
  -> one self-linked direct-RDMA descriptor
  -> DATA_CH_RDMA
  -> TFT timing/output block
  -> 480x272 parallel RGB565 panel
```

```text
DMA MAPPING:
STANDARD DMA API SUFFICIENT
```

The clean driver allocates its one framebuffer with
`dma_alloc_coherent(dev, size, &dma_addr, GFP_KERNEL)` and maps that same
allocation to userspace with
`dma_mmap_coherent(dev, vma, cpu_addr, dma_addr, size)`. No additional
`DMA_ATTR_*` is required for the demonstrated path. The coherent-DMA contract
is the relevant abstraction:

```text
CPU/userspace writes
      ↕
coherent framebuffer
      ↕
X2000 RDMA scanout
```

Explicit cache flushes, `msync()`, custom cache maintenance, and custom page
protections are not clean-port requirements. The generic DMA API supplies the
architecture-correct userspace mapping. The vendor `io_remap_pfn_range()` plus
`_CACHE_CACHABLE_WA` path is dropped, and direct driver-side
`io_remap_pfn_range()` is not required.

```text
Vendor _CACHE_CACHABLE_WA mapping:
DROP

direct driver-side io_remap_pfn_range():
NOT REQUIRED
```

Continuous CPU writes while RDMA scans the coherent buffer are permitted. With
one framebuffer, RDMA can observe a partially updated frame and visible tearing
can result. That is a consequence of the deliberately selected single-buffer
model, not a cache-coherency failure, and does not introduce a pageflip or VSYNC
requirement.

The framebuffer is 480x272 at 32 bits per pixel with a 1920-byte stride. Its
little-endian byte order is B, G, R, X/A: blue occupies bits 0--7, green bits
8--15, red bits 16--23, and the upper byte is ignored by direct RDMA. One frame
therefore occupies 522240 bytes. The RDMA descriptor uses the DMA/bus handle
returned for that allocation directly; the CPU mapping and scanout refer to the
same storage, with no software copy or format-conversion buffer.

The RDMA input is configured as 32-bpp RGB888/BGRX while the independent TFT
output is configured for parallel RGB565. The X2000 DPU performs this reduction
in hardware; neither the CSC path nor a software conversion is reached. The
exact bit reduction used with dithering disabled is not documented by the
available sources, but the vendor Fre3nder path already uses this combination.

### Minimum runtime behavior

| Area | Minimum clean-port requirement |
| --- | --- |
| Framebuffer allocation | Allocate one 480x272x4 buffer with `dma_alloc_coherent()`, expose its size and DMA address through standard fbdev information, and map it writable with `dma_mmap_coherent()`. No additional DMA attribute, cache maintenance, or custom page protection is required. The current three-frame allocation is pageflip capacity, not a requirement. |
| fbdev registration | Allocate and register one `struct fb_info` as `/dev/fb0`, with fixed 480x272, 32-bpp BGRX/RGB888-compatible geometry and a 1920-byte stride. |
| Direct RDMA | Build one self-linked descriptor for framebuffer 0, select one direct RDMA channel, program format/address/stride, and start continuous scanout. No composer layer is active. |
| TFT output | Enable the LCD and pixel clocks, program the demonstrated 480x272@60 timing, select TFT output, and configure parallel RGB565 with the established RGB channel order. |
| Blank/unblank | `FB_BLANK_UNBLANK` must leave clocks, TFT timing and direct RDMA scanout active. Other blank modes may quick-stop RDMA and gate the display clocks, provided unblank restores the path. Repeating the vendor panel reset on every unblank is not established as a DPU requirement. |
| Pan | The productive sleep/wakeup path calls `FBIOPAN_DISPLAY` for the fixed frame at `xoffset = 0`, `yoffset = 0`, but treats failure as non-critical. A minimal driver may reselect descriptor 0 or return success as a no-op when already active. Multi-frame panning, pageflip and VSYNC synchronization are unnecessary. |
| Panel integration | Retain the Fre3nder panel timings and PB16 reset behavior from `panel-ender3-v3-ke-480x272.c`. Backlight remains the separate generic GPIO-backlight device. |
| IRQ handling | Continuous static RDMA scanout needs no functional interrupt. Keep unnecessary sources masked, disable descriptor interrupt control, omit the DPU IRQ handler, and use status polling for quick-stop where necessary. No VSYNC timestamp or wait queue is required. |

The direct primary framebuffer does not use DMMU. DMMU mappings occur only for
optional composer layers with `tlb_en` and for vendor DMMU ioctls. Likewise,
the hardware composer is surrounded by a vendor software abstraction, but the
productive `/dev/fb0` path selects `DATA_CH_RDMA` and does not submit a composer
layer. The minimum is therefore one framebuffer, one direct RDMA channel, and
zero composer layers.

### DPU interrupt boundary

```text
DPU IRQ:
NO FUNCTIONAL IRQ REQUIRED
```

The direct RDMA start is performed by register programming and does not depend
on interrupt-driven progress. `SRD_START` is notification only: the current
handler acknowledges it and updates the vendor VSYNC timestamp, while disabled
descriptor-change code has no productive effect. In the minimal port,
`SRD_START` remains masked and descriptor interrupt control is disabled.

```text
SRD_START:
notification only
```

The TFT-underflow IRQ is diagnostic only. The vendor handler acknowledges the
event and increments statistics but performs no required recovery. Keep this
source masked; if it is deliberately enabled later for diagnosis, its event
must be acknowledged correctly.

```text
TFT underflow IRQ:
diagnostic only
```

SRD/display-end notifications, VSYNC timestamp events, composer and layer
interrupts, writeback completion/overrun, TFT-underflow notification, and
general event/debug interrupts are not required by the productive minimal path.
Clear stale status before start and keep those sources masked. Quick-stop may
continue to use the existing status/polling model.

The resulting minimal display port is:

```text
1 coherent DMA framebuffer
1 direct RDMA descriptor/channel
dma_alloc_coherent()
dma_mmap_coherent()
32-bpp framebuffer input
parallel RGB565 output
continuous static scanout
all unnecessary DPU IRQ sources masked
no DPU IRQ handler required
polled stop where necessary
```

### Vendor-code boundary

`PORT REQUIRED` below means that the named behavior must be represented in a
new reduced driver. `REFERENCE ONLY` means that the complete vendor file is an
implementation reference but must not be copied wholesale. `DROP` means that
no behavior from the group is required by the productive display path.

| Vendor file or functional group | Classification | Port consequence |
| --- | --- | --- |
| `fb_stage/ingenicfb.c` as a complete file | **REFERENCE ONLY** | Extract only standard fbdev setup, one-frame coherent DMA allocation/mapping, fixed mode reporting, blank/unblank, probe/remove and the calls needed to operate direct RDMA. Use `dma_mmap_coherent()` rather than the vendor `_CACHE_CACHABLE_WA`/`io_remap_pfn_range()` path. The non-critical `yoffset=0` pan call may be handled as a trivial frame-0 reselect or successful no-op. Drop its DMMU hooks, vendor ioctls, VSYNC waits, multi-frame policy, composer integration and debug paths. |
| Minimal fbdev behavior identified in `ingenicfb.c` | **PORT REQUIRED** | Reimplement the productive contract above in a small clean driver; do not preserve unused configurability merely because it is present in the vendor file. |
| `fb_stage/dpu_ctrl.c` as a complete file | **REFERENCE ONLY** | Use it for the X2000 register definitions and proven clock, TFT, direct-RDMA descriptor, start, quick-stop and status sequences. Do not port its composer, writeback, MIPI, LVDS, DMMU, CSC, colorbar or broad interrupt machinery. |
| Direct-RDMA/TFT behavior identified in `dpu_ctrl.c` | **PORT REQUIRED** | Retain one descriptor/channel, 32-bpp input, address/stride programming, TFT timing, RGB565 output selection, register-driven start and polled quick-stop. No functional IRQ handler is required. |
| `fb_stage/hw_composer.c` | **DROP** | Vendor wrapper for optional composer operations; direct RDMA does not call it. |
| `fb_stage/hw_composer_fb.c` | **DROP** | Exported layer/writeback framebuffer and composer update surface are not productive endpoints. |
| `fb_stage/sysfs.c` | **DROP** | Runtime composer, videomode, RDMA, MIPI and debug controls are not needed for the fixed display. |
| `arch/mips/xburst2/soc-x2000/libdmmu.c` and `libdmmu.h` | **DROP** | The primary descriptor already receives a DMA address; no user-virtual composer layer is retained. |
| DPU register/descriptor definitions | **REFERENCE ONLY**, then reduce | Carry only definitions referenced by the retained direct-RDMA and TFT sequences into the clean implementation. |
| `panel-ender3-v3-ke-480x272.c` and its board wiring | **PORT REQUIRED** | Preserve the product-specific mode, parallel RGB565 selection and PB16 reset integration separately from the generic X2000 DPU driver. |

The minimal implementation is expected to be substantially smaller than the
vendor implementation because it excludes the dropped surfaces. Functional
groups, not a line-count estimate, define its scope.

No unresolved DPU retain/drop or implementation-architecture decision remains.
The precise hardware rule for RGB888-to-RGB565 reduction with dithering
disabled is not documented, but the established mode remains unchanged and
does not expand the port boundary.

Remaining work is hardware qualification only:

1. Map the single framebuffer to userspace with `dma_mmap_coherent()`.
2. Write alternating full-screen patterns.
3. Verify that no stale or cache-induced image regions occur.
4. Accept visible tearing as valid for this single-buffer test.
5. Run scanout with all DPU interrupt sources masked.
6. Verify blank/unblank.
7. Verify that no interrupt storm occurs.

Explicit minimal-port `DROP` list: framebuffer pages 1 and 2; every composer
layer and exported layer framebuffer; pageflip and VSYNC waits/timestamps;
composer, DMMU and JZFB vendor ioctls; `hw_composer.c`, `hw_composer_fb.c`,
`sysfs.c`, `libdmmu.c/.h`, DMMU proc support, MIPI DSI and its IRQ, LVDS, CSC,
V4L2/writeback integration, dynamic videomode/RDMA/composer sysfs controls,
register dumps, color bars, and unrelated panel drivers.

`GUPPYSCREEN SIMPLIFICATION: not required for minimal kernel architecture`.
The existing GuppyScreen fbdev behavior fits the single-buffer direct-RDMA
contract, so no application simplification is needed to justify or enable this
minimal kernel design.

## PREEMPT_RT separation

This separation compares the same exact source bases as the preceding section:
Linux v6.6.18 at `d8a27ea2c98685cdaa5fa66c809c7069a4ff394b` and the
Ingenic SDK at `a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`. The RT
reference is Kernel.org's official
[`patch-6.6.18-rt23.patch.xz`](https://cdn.kernel.org/pub/linux/kernel/projects/rt/6.6/older/patch-6.6.18-rt23.patch.xz),
SHA-256 `685b8ba0d388d05dcc2262a307a684683bef77e9ada25e54b78f69cc6305250d`.
The comparison was made at hunk and function level without applying the patch.

Only the files already inside the minimal port inventory were considered. In
that scope the official patch has 89 hunks in seven files: three in
`kernel/Kconfig.preempt`, 38 in the selected serial core
(`serial_core.c`, `serial_port.c`, and `serial_core.h`), and 48 in the currently
unselected 8250 core (`8250_core.c`, `8250_port.c`, and `serial_8250.h`). It has
no diff for `arch/mips`, the X2000 clock, IRQ, OST, MMC, DWC2, USB PHY,
pinctrl/GPIO, DPU/DMMU, I2C, or PWM files in the inventory, and no diff for
`8250_ingenic.c`. The matching serial changes were checked by function, not
inferred merely from the file names.

Here, **MIXED** means an official RT23 change and an X2000-required change occur
in the same listed file/function. A file containing X2000 code plus unrelated
vendor RT enablement that is absent from the official patch is instead split
into **X2000 ONLY** and **VENDOR OTHER** rows.

| File / function | Vendor difference | RT23 involvement | X2000 involvement | Classification | Minimal-port consequence |
| --- | --- | --- | --- | --- | --- |
| `kernel/Kconfig.preempt` | Adds `PREEMPT_BUILD_AUTO`, `HAVE_PREEMPT_AUTO`, `PREEMPT_AUTO`, the `PREEMPT_RT` auto-build selection, and the `PREEMPT_DYNAMIC` exclusion. | These are the three official RT23 hunks and match semantically. | None. The selected `CONFIG_PREEMPT=y` already exists in plain v6.6.18; `CONFIG_PREEMPT_RT` and `CONFIG_PREEMPT_AUTO` are unset. | **RT ONLY** | Do not carry these additions merely to preserve Fre3nder's selected non-RT preemption model. |
| `drivers/tty/serial/serial_core.c`, `serial_port.c`; `include/linux/serial_core.h` — UART port locking | Replaces direct `port->lock` operations with `uart_port_lock*()` wrappers and adds the nbcon acquire/release integration in those wrappers. | All 38 scoped official RT23 hunks are represented semantically; vendor-wide restyling is separate below. | No X2000 register, compatible, clock, or pin behavior is added. The files are reached by the selected standalone Ingenic UART through `CONFIG_SERIAL_CORE=y`. | **RT ONLY** | Plain v6.6.18 retains the serial-core functionality needed by UART1; the RT-aware locking layer is not an X2000 port item while `CONFIG_PREEMPT_RT=n`. |
| `drivers/tty/serial/8250/8250_core.c`, `8250_port.c`; `include/linux/serial_8250.h` — 8250 locking and console | Adds RT-aware port locking, legacy-console gating, nbcon atomic/thread console writers, console state fields, and the split IER helpers. | All 48 scoped official RT23 hunks are represented semantically. | None; the official patch does not touch `8250_ingenic.c`. In the effective Fre3nder configuration `CONFIG_SERIAL_8250` is unset. | **RT ONLY** | These changes are dormant in the current vendor-driver path and need not accompany an X2000 addition to upstream `8250_ingenic.c`. |
| The same six generic serial files — remaining vendor diff | Large indentation/brace restyling plus non-matching generic serial drift outside the named RT23 functions/hunks. | No concrete correspondence with the official scoped RT23 hunks. | No X2000-specific identifiers or behavior were found in this remainder. | **VENDOR OTHER** | Do not copy the bulk vendor diff; start from the upstream serial core/8250 files. |
| `arch/mips/Kconfig` — `ARCH_SUPPORTS_RT`, `HAVE_PREEMPT_AUTO`, `HAVE_POSIX_CPU_TIMERS_TASK_WORK` selections | Enables RT/automatic-preemption prerequisites for MIPS generally. | These lines are absent from the official RT23 patch, which has no `arch/mips` hunk. | They are not X2000-specific and are unnecessary for the selected `CONFIG_PREEMPT=y`, `CONFIG_PREEMPT_RT=n` configuration. | **VENDOR OTHER** | Do not carry this vendor MIPS RT enablement as part of the minimal X2000 port. |
| `arch/mips/Kconfig`, `arch/mips/Makefile`, `arch/mips/xburst2/**` — XBurst2 machine, boot, SMP, secondary cache, current early print, minimal restart | Adds the XBurst2/X2000 architecture selection and its implementation/integration. The later watchdog decision additionally retains only the normal `reset_init()` / `jz_wdt_restart()` platform-reset primitive from `soc-x2000/reset.c`; the early-print subpath is only a current configuration/link dependency. | No official RT23 hunk in these paths. | The platform, SMP/cache, DT handoff, and independent WDT-based reboot mechanism are required X2000 support. The vendor early-print subpath has no productive requirement. | **X2000 ONLY** for the retained platform support; **CURRENT VENDOR CONFIG/LINK DEPENDENCY ONLY** for early print | Port the necessary platform, SMP/cache, DT handoff, and minimal restart integration independently of RT23. Omit `soc-x2000/serial.c`, `prom_putchar()`, and the vendor early-print integration; do not add a replacement earlycon. |
| `module_drivers/dts/x2000/{x2000.dtsi,x2000-pinctrl.dtsi}` and required binding headers | Supplies the X2000 SoC nodes, phandles, pins, and constants used by the board DTS. | No official RT23 hunk. | Entirely X2000 DT description/integration. | **X2000 ONLY** | Provide an upstream-style X2000 DTSI and only the bindings needed by retained nodes. |
| `module_drivers/drivers/clk/ingenic-v2/**` and clock Kconfig/Makefiles | Adds the X2000 clock, PLL, divider, bus, gate, and power-gate topology. | No official RT23 hunk. | Supplies clocks for all retained X2000 controllers. | **X2000 ONLY** | Implement the required X2000 clock data/behavior on an appropriate upstream clock framework; RT23 is irrelevant to it. |
| `module_drivers/drivers/irqchip/irq-ingenic-{cpu,chip}.c` and integration | Adds the XBurst2 CPU dispatch and per-CPU X2000 interrupt-controller/domain topology. | No official RT23 hunk. | Required by SMP and all retained device interrupts; the known map-bounds fix is likewise non-RT. | **X2000 ONLY** | Port the X2000 interrupt topology and bounds fix without importing diagnostics or unrelated PM extensions. |
| `module_drivers/drivers/clocksource/ingenic_core_ost.c` and integration | Adds the X2000 global counter and per-CPU clockevents. | No official RT23 hunk. | Required X2000 timer behavior; the known `cpu-ost-map` bounds fix is non-RT. | **X2000 ONLY** | Port the X2000 OST implementation and bounds fix independently of RT23. |
| `module_drivers/drivers/mmc/host/{sdhci-ingenic.c,ingenic_sdio.c,sdhci-ingenic.h}` and integration | Adds X2000 SDHCI clock/tuning/reset/ADMA glue and the current MSC1 manual-card/power path. | No official RT23 hunk. | X2000 controller support remains required for eMMC and SDIO WLAN; the manual WLAN path is a removable vendor/Fre3nder workaround. The MSC-register fix is X2000 controller logic. | **X2000 ONLY** for controller behavior; **NOT REQUIRED IN CLEAN PORT** for manual WLAN sequencing | Port only the MSC0/MSC1 controller behavior. Express Fre3nder WLAN board sequencing with generic regulator, pwrseq, GPIO, non-removable startup/rescan, and brcmfmac mechanisms. |
| `module_drivers/drivers/tty/serial/ingenic_uart.c/.h` and integration | Adds the selected standalone Ingenic UART driver, including X2000 register/FIFO/clock behavior. Its locking remains direct `spin_lock*()` rather than the RT23 UART wrappers. | The file does not exist in the official patch, so none of its code can be attributed to RT23. | The core UART1 path is X2000-specific. DMA, proc/debug, and the separate vendor-driver architecture are not required by the current no-DMA board node. | **X2000 ONLY** for the core path; unused portions are **VENDOR OTHER** | Prefer a small X2000 extension to upstream `8250_ingenic.c`; do not import the standalone driver wholesale. The later UART divisor decision limits the required addition to X2000 match/clock/FIFO data and a small divisor-register hook. |
| `drivers/tty/serial/8250/8250_ingenic.c` | Vendor file is byte-identical to exact upstream v6.6.18. | No official RT23 hunk. | It has no vendor X2000 addition; such an addition is the proposed clean-port direction, not an existing vendor diff. | No vendor difference | Add X2000 match/data only as a separate X2000 port change if this upstream driver is used. |
| `drivers/usb/dwc2/{params.c,platform.c,core.c,core.h,hcd.c}` — vendor X2000/OTG/VBUS hunks | Adds a vendor compatible/parameter path, legacy PHY hookup, external-VBUS detection/drive and host connect-state changes. | No official RT23 hunk in DWC2. | Upstream v6.6.18 already provides the required X2000 host match/parameters and generic PHY/regulator integration. The vendor `INCR16` value is not a demonstrated functional requirement; the early-connect check is an unresolved qualification item. | **VENDOR OTHER / NOT REQUIRED IN CLEAN PORT** for the legacy/OTG/VBUS integration; **UNRESOLVED** for the early-connect check | Use upstream DWC2 host-only and generic `vbus-supply`. Do not carry the early-connect check preemptively; reassess it only after a reproducible failure. |
| DWC2 remaining vendor hunks | Adds a read-only mode sysfs file and gadget wrappers while deleting or changing broader generic clock/regulator/power handling, plus formatting churn. | No official RT23 involvement. | Not needed by the demonstrated host path. | **VENDOR OTHER** | Leave these hunks out of the minimal port. |
| `module_drivers/drivers/usb/phy/phy-ingenic.c/.h`, `phy-ingenic-x2000.c` | Adds the legacy-API X2000 PHY implementation and owns the KE VBUS GPIO behavior. | No official RT23 hunk in the scoped USB PHY paths. | Upstream `ingenic,x2000-phy` is the clean-port base and no additional Fre3nder PHY function is statically established. GPC9 is separate board data for a generic DWC2 VBUS supply; GPD17 is Device/OTG-only for the demonstrated use. | **VENDOR OTHER / NOT REQUIRED IN CLEAN PORT** | Use the upstream PHY. Treat vendor SRBC/SPENDN0/TX-strength/wake sequences only as hardware-qualification subjects, not as code to port preemptively. |
| `phy-ingenic-{x1000,x1600,x2500,x2600,ad100}.c` | Linked only because the vendor common match table references every SoC family's data. | No official RT23 involvement. | No retained X2000 runtime path reaches these implementations. | **VENDOR OTHER** | Split or guard the match/data entries; do not port these family drivers. |
| `drivers/pinctrl/pinctrl-ingenic.c` and vendor pinctrl integration | Vendor uses its own binding/driver path; upstream already has X2000 pin/function data but leaves its match unreachable behind an undefined selection. | No official RT23 hunk in pinctrl/GPIO. | Making the existing upstream X2000 data reachable and translating the DTS binding are X2000 requirements. | **X2000 ONLY** | Use the upstream driver/data with a small X2000 reachability/binding change; do not import the vendor driver wholesale. |
| Required subsets of `fb_stage/{ingenicfb.c,dpu_ctrl.c}` — primary RGB framebuffer path | Adds standard fbdev registration/mapping, one direct RDMA descriptor/channel, TFT timing, start/stop, and the 32-bpp-input to parallel-RGB565 output configuration. | No official RT23 hunk in the DPU path. | Required for the demonstrated parallel-RGB `/dev/fb0` path. | **X2000 ONLY** | Implement the minimal direct-RDMA fbdev path independently of RT23; use the vendor files as register/sequence references rather than porting them wholesale. |
| `hw_composer.c`, `hw_composer_fb.c`, `sysfs.c`, `libdmmu.c/.h`, DPU vendor ioctls and debug surface | Vendor-only compositor, address-translation, export/control and diagnostic interfaces surround the direct path. | No official RT23 involvement. | Productive userspace uses only standard fbdev, and primary RDMA uses a direct DMA handle. | **VENDOR OTHER** | Drop these groups from the minimal display port. |
| `jz_mipi_dsi/**`; `common/proc.c`, `ingenic_proc.h` | Pulled in by unconditional vendor link layout or optional DMMU diagnostics. | No official RT23 involvement. | Neither MIPI hardware nor DMMU proc diagnostics is required by the established RGB path. | **VENDOR OTHER** | Remove these link-only dependencies in a clean port. |
| `module_drivers/drivers/i2c/busses/i2c-ingenic.c` and integration | Adds a divergent X2000-capable controller implementation and vendor debug/config surface. | No official RT23 hunk in I2C. | An X2000 I2C4 compatible/clock/DT path is required for NS2009; the later controller decision shows the existing upstream X1000 data is sufficient and finds no required controller quirk. | **X2000 ONLY** for controller enablement; the standalone implementation is **VENDOR OTHER** | Use upstream `i2c-jz4780.c`, select its X1000 data for X2000, and omit the vendor implementation. |
| `module_drivers/drivers/pwm/pwm-ingenic-v2.c` and integration | Adds the X2000 16-channel PWM controller; also contains DMA waveform, debug sysfs, and test support. | No official RT23 hunk in PWM. | Ordinary channel-3 `.apply` behavior is required for the beeper; the extra surfaces are not. | **X2000 ONLY** for ordinary PWM; extras are **VENDOR OTHER** | Port a reduced ordinary X2000 PWM provider only. |
| `module_drivers/drivers/watchdog/ingenic_wdt.c/.h` | Adds a standalone X2000-style watchdog-class device unlike upstream's TCU-regmap driver. | No official RT23 hunk in this path. | The later retention analysis establishes no productive Fre3nder `/dev/watchdog` consumer; the required normal reboot path programs WDT hardware independently from `soc-x2000/reset.c`. | **VENDOR OTHER** | Do not port the watchdog-class driver, `CONFIG_INGENIC_WDT`, or its DT node. Retain or reimplement only the separate minimal X2000 WDT-based restart primitive. |
| Fixed regulator, SPI GPIO/bitbang/spidev, GPIO backlight, PWM beeper, selected USB storage/network/UVC, and selected brcmfmac files | The files identified in the previous section are byte-identical between the two exact commits. | No vendor difference to attribute to RT23. | They remain generic endpoints of X2000-provided buses/GPIO/PWM. | No vendor difference | Keep upstream files unchanged and retain only configuration and DT wiring. |
| Fre3nder board DTS, panel, NS2009, and WLAN changes | These are the four Fre3nder-specific components in section C, not SDK-versus-upstream RT deltas. | None; they are not classified as RT. | Board/product-specific behavior above the generic X2000 port. | **FRE3NDER-SPECIFIC** | Keep them separate from both the official RT patch and the generic X2000 delta. |

The compact result, counting coherent change groups rather than every source
file in a vendor-only subsystem, is:

```text
RT ONLY:
- 3 groups / 7 files / 89 official scoped hunks:
  kernel preemption Kconfig (3 hunks), selected serial core (38 hunks),
  and currently unselected generic 8250 support (48 hunks)

X2000 ONLY:
- required functional groups:
  XBurst2 platform, SoC DTS/bindings, clocks, core IRQ, OST, MMC/SDHCI,
  UART, pinctrl/GPIO reachability, DPU, I2C, and ordinary PWM
- the associated minimal Kconfig/Makefile integration belongs to its group

MIXED:
- none found: no official RT23 hunk also carries required X2000 behavior

VENDOR OTHER:
- generic serial restyling/non-RT drift
- vendor MIPS RT enablement absent from the official RT23 patch
- unused standalone-UART DMA/debug surface
- vendor DWC2 dual-role/Gadget/external-VBUS/legacy-PHY integration and
  unrelated sysfs/general-power churn
- vendor legacy USB-PHY/OTG glue and other-SoC USB PHY link ballast
- composer, DMMU, MIPI and display proc/sysfs/debug link ballast
- PWM DMA/debug/test surface
- standalone watchdog-class driver and its DT/Kconfig exposure

RETAIN/DROP ARCHITECTURE DECISIONS:
- no unresolved decision remains for PREEMPT_RT, the watchdog, early
  print/ttyS4, UART, I2C, MSC1 WLAN sequencing, the USB host/PHY/VBUS model,
  the PWM provider scope, DPU/fbdev, DPU DMA mapping, or the DPU IRQ model

IMPLEMENTATION AND HARDWARE QUALIFICATION:
- PWM implementation work remains limited to later hardware qualification and
  the final clean-port clock/DT binding
- USB early-connect behavior and PHY qualification remain hardware-qualification
  items
- DPU DMA mapping and IRQ architecture are resolved; standard coherent DMA and
  no functional DPU IRQ are selected, with hardware qualification remaining
```

**Would a Fre3nder port to plain Linux v6.6.18 lose X2000-relevant code solely
by omitting RT23?** No, according to the present static comparison. None of the
official RT23 hunks in the scoped inventory implements X2000 hardware behavior,
and plain v6.6.18 already supports the selected `CONFIG_PREEMPT=y` model. This
does not mean that unmodified v6.6.18 supports the printer: the listed X2000
groups and the separate Fre3nder-specific components still have to be added. It
means only that those additions do not depend on applying the official RT23 patch.
The RT-aware serial locking/console changes are present in the vendor tree even
with `CONFIG_PREEMPT_RT=n`, but no static X2000 requirement for them was found.

## Watchdog retention decision

This decision concerns the watchdog-class device selected by
`CONFIG_INGENIC_WDT` and the `ingenic,watchdog` DT node. It separately accounts
for the X2000 platform's use of the same hardware block as a one-shot restart
mechanism. The latter does not require a registered `/dev/watchdog` device.

### Userspace findings

| Candidate consumer | Installed or present | Started or used by Fre3nder | Finding |
| --- | --- | --- | --- |
| BusyBox `watchdog` | The effective BusyBox configuration has `CONFIG_WATCHDOG=y`, and the built RootFS contains `/sbin/watchdog` as a BusyBox link. This comes from the base BusyBox configuration; `configs/x2000/busybox.fragment` does not select it. | No. `BR2_PACKAGE_BUSYBOX_WATCHDOG` is unset, so Buildroot does not install `S15watchdog`; no Fre3nder init script or `inittab` entry invokes the applet. The separate `watchdog` and `watchdogd` packages are also unset. | Installed capability only, not a configured runtime consumer. |
| systemd watchdog settings | None. The effective image selects `BR2_INIT_BUSYBOX=y` and explicitly does not select systemd. | No `RuntimeWatchdogSec`, `RebootWatchdogSec`, `KExecWatchdogSec`, or `WatchdogDevice` setting exists in the productive inputs. | Not applicable to this SysV-style BusyBox init image. |
| Klipper Linux-process MCU | Its upstream `src/linux/watchdog.c` is compiled and the `-w` command-line option would open `/dev/watchdog` and periodically write to it. | No. `S59fre3nder-klipper-mcu` starts `klipper_mcu` with `-r -I <host-tty>` and does not pass `-w`. | Code capability exists but is deliberately not activated by the production service. |
| Klippy / printer MCU | Klipper contains MCU-local watchdog implementations and protocol timeout/shutdown handling. | No X2000 `/dev/watchdog` open, write, or ioctl is present in the selected host-side Klippy path. | MCU safety/communication behavior is not a Linux SoC watchdog consumer. |
| Moonraker | `proc_stats.py` has a class named `Watchdog`; the lockfile also contains a Python package with that name through documentation tooling. | The `proc_stats` watchdog is an event-loop timer that logs blocked-loop intervals. It never opens a watchdog device. No Moonraker configuration references `/dev/watchdog`. | Naming and dependency text only; not a hardware watchdog consumer. |
| Direct consumers | No productive Fre3nder file contains `/dev/watchdog`, `WDIOC_*`, or another direct watchdog ioctl. | None found. | No runtime consumer is established. |

Thus the presence of the BusyBox applet and the optional Klipper `-w` code must
not be confused with use: both are installed/compiled capabilities, but neither
is started in the productive Fre3nder configuration.

### Vendor driver behavior

The unchanged SDK implementation is
`module_drivers/drivers/watchdog/ingenic_wdt.c`, selected by
`CONFIG_INGENIC_WDT` through the adjacent Kconfig and Makefile. Its probe path:

1. requires the DT IRQ resource even though it does not request the IRQ;
2. maps the `0x10002000` register range;
3. obtains and enables `mux_wdt` and the shared `gate_tcu` clock;
4. registers the watchdog-class device; and
5. clears the watchdog interrupt mask and flag state.

The original `probe()` neither starts nor stops the counter and does not read
the counter-enable register. It also never calls `watchdog_set_hw_running()` or
otherwise marks a boot-enabled watchdog. Consequently the selected generic
`CONFIG_WATCHDOG_HANDLE_BOOT_ENABLED=y` support cannot recognize or take over an
already running counter through this driver. The `.start` callback starts the
counter only when the watchdog core calls it, normally after `/dev/watchdog` is
opened; `.stop`, `.ping`, and `.set_timeout` are likewise consumer-driven.

The apparent restart support in this driver is inactive: both
`ingenic_restart_handler()` and `register_restart_handler()` are inside
`#if 0`, and `ingenic_wdt_ops` supplies no `.restart` callback. Similarly,
`IRQ_SWITCH` is defined as zero, so `ingenic_wdt_interrupt()` and
`request_irq()` are compiled out. The driver nevertheless requires an IRQ
number at probe and writes the mask/flag registers. No in-kernel consumer other
than the generic watchdog character-device framework was found. The clock and
TCU providers are dependencies of the driver; they do not depend on it.

### OpenKE evidence

OpenKE commit
[`8e97319a1754e264580ac39400a0c41139d2deb4`](https://github.com/coreflake1/NebulaOS-kernel/commit/8e97319a1754e264580ac39400a0c41139d2deb4)
adds exactly one functional watchdog operation: an unconditional
`writeb(0x0, ... + INGENIC_REG_WDT_COUNTER_ENABLE)` in `probe()`, before the
existing mask/flag clears. It does not add a watchdog service, takeover state,
restart handler, or IRQ handler.

The commit's stated observation was an OpenKE boot attempt that reached
`Run /linuxrc as init process` and then reset without a panic message or the
configured panic delay. Its author described a hardware-level reset, and an
inherited SPL/U-Boot watchdog specifically, as "very likely". No read of the
watchdog enable/counter registers, reset-cause register, or controlled A/B test
is recorded in that change. The observation therefore motivates a plausible
defensive measure but does not prove either the reset cause or bootloader
retention. The change has no effect when the watchdog driver is not selected or
its DT node does not probe.

### Bootloader/SPL evidence

The locally archived SDK U-Boot tree contains the corresponding X2000-v12 and
Halley5 sources. In
[`arch/mips/cpu/xburst2/x2000_v12/soc.c`](https://github.com/coreflake1/NebulaOS-kernel/blob/a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b/u-boot/arch/mips/cpu/xburst2/x2000_v12/soc.c),
`board_init_f()` unconditionally writes zero to `WDT_TCER` near its beginning,
explicitly labelled as disabling the watchdog. The available
[`x2000_halley5.h`](https://github.com/coreflake1/NebulaOS-kernel/blob/a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b/u-boot/include/configs/x2000_halley5.h)
and X2000 base configuration do not enable `CONFIG_JZ_WATCHDOG` or
`CONFIG_HW_WATCHDOG`; the SPL Makefile links the generic watchdog support only
when `CONFIG_JZ_WATCHDOG` is set.

The same tree's generic XBurst2 `do_reset()` path deliberately programs and
starts the watchdog, but only to execute an explicit U-Boot reset and then wait
for that reset. No X2000-v12 normal-boot path was found that re-enables the
counter after the early disable and before Linux entry. These sources therefore
argue against a normal running-counter handoff.

This is relevant SDK source, not a source-to-binary proof for the exact Creality
SPL/U-Boot installed on every Ender-3 V3 KE revision. No exact Creality
bootloader build configuration or matching source tree was found locally. The
static evidence establishes the intended X2000-v12 behavior, but cannot exclude
an unpublished Creality change.

### Kernel and restart dependency

There is one real dependency on the watchdog *hardware*, but not on the
watchdog-class driver. `arch/mips/xburst2/soc-x2000/Makefile` unconditionally
builds `reset.o`. With `CONFIG_HIBERNATE_RESET` unset, its `reset_init()` assigns
`_machine_restart = jz_wdt_restart`; that function directly enables the TCU/WDT
clock source, programs a four-millisecond timeout, and starts the counter. The
productive image exposes ordinary reboot paths through `inittab`, and the
deployment tooling also uses `reboot` in authorized workflows.

This restart implementation accesses the WDT/TCU registers and clocks directly.
It neither calls `ingenic_wdt.c` nor depends on `CONFIG_INGENIC_WDT`, the
`ingenic,watchdog` DT node, `/dev/watchdog`, or the watchdog core. A future port
therefore needs a clean X2000 restart implementation, which may still use the
hardware watchdog as a one-shot reset source, but does not need to expose or
port the vendor watchdog device driver. This finding supersedes the earlier
blanket treatment of `soc-x2000/reset.c` as unnecessary: its vendor proc/debug
surface remains unnecessary, while its normal restart function is a separate
minimal platform requirement.

```text
WATCHDOG DECISION:
DROP

Evidence:
- no productive Fre3nder service opens, configures, or feeds /dev/watchdog
- the installed BusyBox applet is not configured or started
- Klipper's Linux watchdog support is optional and Fre3nder does not pass -w
- Moonraker's namesake watchdog only monitors its event loop
- the vendor driver has no active restart or IRQ handler and no other consumer
- available X2000-v12 SPL source explicitly disables the counter before boot
- OpenKE's inherited-watchdog explanation is plausible but explicitly not proven
- normal kernel reboot uses the WDT directly, independently of the device driver

Remaining uncertainty:
- the available SDK SPL/U-Boot source is not proven byte-for-byte equivalent to
  the exact Creality bootloader on every hardware/firmware revision
- no earliest-Linux read of WDT_TCER/reset-cause state was made; such a read
  before any watchdog driver probes would be the smallest later observation if
  bootloader retention must be closed empirically

Port consequence:
- CONFIG_INGENIC_WDT may be dropped from the future Fre3nder kernel
- the ingenic,watchdog DT node may be disabled or omitted
- module_drivers/drivers/watchdog/ingenic_wdt.c/.h and the OpenKE probe-stop
  hunk do not need to be ported
- retain or reimplement only the independent X2000 WDT-based platform restart
  primitive; it must not expose /dev/watchdog unless a future runtime policy
  deliberately adds a consumer
- if an early read later proves a running bootloader handoff, revisit this as
  RETAIN FOR BOOT SAFETY and decide whether bootloader-side disable or a minimal
  early-kernel stop is the cleaner correction
```

## UART divisor decision

This decision is limited to the productive X2000 UART1 path. The requested
partial `linux-upstream` checkout does not contain `8250_ingenic.c`; the
comparison therefore uses the byte-equivalent file in the local exact
v6.6.18 tree at commit `d8a27ea2c98685cdaa5fa66c809c7069a4ff394b`.

### Productive UART1 requirements

| Property | Productive requirement and evidence |
| --- | --- |
| Device and normal rate | `/dev/ttyS1` at 230400 baud. Both `printer-f005-mainline.cfg` and `f005-mcu-release.json` fix this value. The opt-in `connect_uart_passive()` path accepts only that device/rate pair and directly requests `termios.B230400`. |
| Bootloader rate | The productive `f005_bootloader.py` permits only `/dev/ttyS1` at 115200 baud. This is the only second required rate. |
| Frame format | 8 data bits, no parity, one stop bit (8N1). The passive Klipper path clears the input, output, and local flags and sets only `CS8 | CREAD | CLOCAL`; the bootloader's pyserial construction leaves its 8N1 defaults unchanged. |
| Flow control | None. The passive path does not set `CRTSCTS` and has no software-flow flags; the bootloader leaves pyserial's XON/XOFF, RTS/CTS, and DSR/DTR flow controls disabled. PC23/PC24 are used only as TX/RX. |
| Rate range | 230400 is the highest productive rate. It is above the traditional 115200 rate, but there is no rate above 1 Mbaud and no productive use for the vendor `SERIAL_INGENIC_LARGE_BAUDRATE` option. That symbol is not referenced by the driver source after its Kconfig declaration. |
| DMA | Not used. Neither the inherited UART1 node nor the board override has `dma-mode`, `dmas`, or `dma-names`; the vendor probe therefore selects PIO. |
| Console/earlycon | Not required for UART1. The board explicitly reserves UART1 for the F005 and instead names `ttyS4` in `console=`; it has no `earlycon` argument. Normal UART1 operation therefore need not extend the upstream earlycon declarations. |

The passive Klipper connection is material here: it bypasses the normal
pyserial attach sequence and its modem-control operations, so it does not
introduce transient 2400- or 115200-baud setup on the normal F005 application
connection. The separate, explicit bootloader client accounts for the required
115200-baud case.

### Vendor divisor algorithm

`ingenic_uart.c` chooses one of three compile-time tables from
`CONFIG_EXTAL_CLOCK` values 24, 26, or 48 MHz. An exact table match supplies the
DLL/DLH divisor `D`, UMR value `M`, and 12-bit UACR value `A`. For an unlisted
rate, `get_divisor()` first uses the ordinary `D = f / (16 * baud)`, `M = 16`,
`A = 0` case when it divides exactly. Otherwise it:

1. iterates integer divisors upward;
2. computes `M = floor(f / (baud * D))` and accepts values from 4 through 32;
3. distributes up to one added input-clock cycle over each of 12 bit-time
   slots by setting the corresponding UACR bit according to cumulative timing
   error; and
4. prefers a candidate whose UMR is closest to 16, breaking a tie in favour of
   the numerically smaller UACR pattern.

If `N = popcount(A & 0xfff)`, the average relationship implemented by that
algorithm is:

```text
cycles per transmitted bit = D * (M + N / 12)
resulting baud             = f / [D * (M + N / 12)]
                           = 12f / [D * (12M + N)]
signed error               = (resulting baud / requested baud - 1) * 100%
```

The UACR bit positions distribute the extra cycles over the 12 slots and thus
also determine their instantaneous pattern; their population count determines
the average rate. Standard 8250 16x oversampling is the special case `M = 16`,
`A = 0`. UMR/UACR are therefore not evidence of a structurally different UART
model: UMR changes the samples/input-clock cycles per bit, while nonzero UACR
is a fractional error-reduction mechanism for ratios that need added cycles.

Every vendor `set_termios()` call programs DLL/DLH, UMR, and UACR, regardless
of whether the selected tuple is fractional. The 24 MHz table uses:

```text
115200: D = 13, M = 16, A = 0
230400: D =  8, M = 13, A = 0
```

Thus Fre3nder needs a nonstandard UMR at 230400, but does not need a nonzero
UACR for either productive rate. The table also contains rates through 4 Mbaud,
but there is no separate high-rate branch and the
`SERIAL_INGENIC_LARGE_BAUDRATE` Kconfig symbol does not guard that code. The
vendor port declares a 64-byte FIFO and sends at most half of it per PIO fill,
which corresponds to the upstream X1000 data (`fifosize = 64`, `tx_loadsz =
32`); no X2000-specific FIFO extension beyond matching data is demonstrated.

### Upstream behavior

Linux v6.6.18 `8250_ingenic.c` already supplies the appropriate architecture:
a registered 16550A port with register shift 2, Ingenic UME/RTOIE and modem
quirks, separate `module` and `baud` clocks, and per-SoC FIFO data. It directly
matches JZ4740, JZ4750, JZ4760, JZ4770, JZ4775, JZ4780, and X1000. X1830 DTS
nodes use `ingenic,x1830-uart` followed by the supported
`ingenic,x1000-uart` fallback and the same 64/32 FIFO data.

The driver has no X2000 match and never reads or writes UMR/UACR. Its normal
path consequently reaches `uart_get_divisor()`, which rounds
`uartclk / (16 * baud)`, and `serial8250_do_set_divisor()`, which writes only
DLL/DLH. Its earlycon path uses the same fixed factor of 16. The 8250 core
already exposes per-port `get_divisor` and `set_divisor` hooks, so X2000 does
not require the standalone vendor `uart_driver`: a small X2000-only
`set_divisor` hook can override the 230400 tuple, call the normal DLL/DLH
writer, and program UMR/UACR. It must also restore `M = 16`, `A = 0` for
ordinary tuples so a previous nonstandard setting cannot leak across a termios
change.

### X2000 register and clock evidence

The X2000 vendor UART header assigns word register indices 9 and 10 to UMR and
UACR, corresponding to byte offsets `0x24` and `0x28` with the controller's
shift of 2. Independent X2000 PM/fastboot headers name these the "UART M
Register" and "UART Add Cycle Register", and X2000 PM, sleep, and fastboot
firmware writes them during UART baud setup. This establishes that the
registers are real X2000 UART controls. No X2000 reference manual was found in
the existing local material, so the bit-time equation above is an inference
from the vendor algorithm and tables rather than a quotation from an
authoritative register manual.

For the productive table-driven rates, the configured baud-clock assumption is
statically 24 MHz:

- the included X2000 DTSI fixes `extclk` at 24 MHz;
- the selected X2000 defconfig has `CONFIG_EXTAL_CLOCK=24`; and
- the compiled vendor tuples are taken from the 24 MHz table.

The current vendor DTS exposes only `CLK_GATE_UART1` under the name `uart1`,
while the driver asks for `gate_uart1`. The vendor clock provider registers
that name as a global lookup, so it can return the APB-derived module gate and
its rate as `port->uartclk`; nevertheless exact table matches ignore that
reported rate and remain hard-coded for the 24 MHz oscillator. This is
internally inconsistent clock metadata, not an alternative demonstrated baud
source. The clean upstream description should follow the existing X1000/X1830
model: 24 MHz `extclk` as `baud`, and the UART1 gate as `module`. The APB gate's
runtime rate is not statically fixed in the DTS, but no baud calculation for it
is warranted because the local sources consistently treat it as the module
gate rather than the sampling clock.

OpenKE adds no further divisor or clock finding. Its `ingenic_uart.c` is
byte-identical to the SDK copy, and its local history for that UART/DTS source
contains only the imported SDK baseline. The known PC23/PC24 work therefore
does not change this decision.

### Concrete baud-error calculation

With `f = 24,000,000 Hz`:

| Requested rate | Method | Tuple | Resulting rate | Signed error |
| ---: | --- | --- | ---: | ---: |
| 115200 | Upstream standard 8250 | `D=round(24000000/(16*115200))=13`; implicit `M=16`, `A=0` | 115384.615 baud | +0.160256% |
| 115200 | Vendor 24 MHz table | `D=13`, `M=16`, `A=0` | 115384.615 baud | +0.160256% |
| 230400 | Upstream standard 8250 | `D=round(24000000/(16*230400))=7`; implicit `M=16`, `A=0` | 214285.714 baud | -6.994048% |
| 230400 | Vendor 24 MHz table | `D=8`, `M=13`, `A=0` | 230769.231 baud | +0.160256% |

At 115200 the ordinary divisor and the vendor tuple are identical. At 230400,
the ordinary integer divisor is almost 7% low, whereas changing UMR from 16 to
13 reduces the static error to about 0.16%. Since 230400 is the normal
productive F005 rate, an X2000 match that merely reuses the upstream X1000
FIFO/clock data would leave a required function without the vendor-equivalent
baud generation. Conversely, no productive tuple requires fractional UACR.

```text
UART DECISION:
SMALL X2000 DIVISOR QUIRK REQUIRED

Required upstream change:
- add an X2000 compatible/match using the demonstrated 64-byte FIFO and
  32-byte transmit load
- describe separate 24 MHz baud and UART1 module-gate clocks
- add a small X2000-only 8250 divisor hook which always initializes UMR/UACR,
  uses D=8/M=13/A=0 at 230400, and preserves D=13/M=16/A=0 at 115200
- no UART1 DMA, console, or earlycon extension is required

Vendor code that can be dropped:
- the standalone Ingenic uart_driver and duplicated serial-core operations
- DMA, proc/debug, SysRq/console, and modem-control surface not used by UART1
- the full 24/26/48 MHz lookup tables, arbitrary-rate UACR search, and every
  greater-than-1-Mbaud tuple; nonzero UACR is not needed by Fre3nder

Remaining uncertainty:
- no local X2000 reference manual independently specifies the UMR/UACR timing
  equation or reset values
- this is a static source/configuration decision; the requested scope excluded
  a hardware UART measurement, so the proposed minimal hook is not yet
  hardware-qualified
```

## I2C controller decision

This decision is limited to X2000 I2C4 on the productive touchscreen path. The
requested partial vendor checkout contains the tree entry for
`module_drivers/drivers/i2c/busses/i2c-ingenic.c`, but its blob is not present
locally. No download was made. The comparison therefore uses the existing full
copy under `local/research/x2000-prototype/work/sdk` at the same pinned SDK
commit `a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`. Its SHA-256 is
`738b4dc175b2d226989e4646854c7fb16063b35f789af4e603974dee6f062248`,
identical to the existing OpenKE working-tree copy. The upstream side is Linux
v6.6.18 at `d8a27ea2c98685cdaa5fa66c809c7069a4ff394b`.

### Productive Fre3nder requirement

| Property | Demonstrated requirement |
| --- | --- |
| Controller and pins | I2C4 at `0x10054000`, IRQ `IRQ_I2C4` (`32 + 25`), with `i2c4_pc`: GPC25 as SDA and GPC26 as SCL, both function 1. UART3 is disabled because it shares those pins. |
| Bus rate | 100 kHz standard mode. Neither the inherited X2000 node nor the board override supplies `clock-frequency`; the selected vendor driver therefore uses its explicit 100000 Hz default. No productive 400 kHz use is established. |
| Slave | `nsiway,ns2009` at the 7-bit address `0x48`; GPC15 active-low supplies the separate pendown indication. |
| API and message form | `ns2009_ts_read_data()` calls `i2c_smbus_read_i2c_block_data(..., command, 2, ...)`. Linux emulates that operation as a one-byte command write followed, without STOP, by a repeated START and a two-byte read ending in STOP. The upstream adapter's `I2C_FUNC_I2C | I2C_FUNC_SMBUS_EMUL` advertises both I2C-block capability bits checked by the NS2009 probe. |
| Transfer size and cadence | With the board's pendown GPIO, an idle 30 ms poll performs no I2C transfer. A pressed poll performs one two-message transaction for X (`0xc0`) and one for Y (`0xd0`): each is 1 byte write plus 2 bytes read. The Z1 transaction is only the generic fallback when no pendown GPIO exists and is not on the productive KE path. |
| Explicit non-requirements | No 10-bit address, DMA property or DMA operation, multi-master topology, `I2C_M_NOSTART` transfer, or I2C slave mode is used. No local evidence says that the NS2009 requires or was observed using clock stretching; it is therefore not made a port requirement. |

The selected configuration has `CONFIG_I2C=y`, `CONFIG_I2C_INGENIC=y`,
`CONFIG_I2C_FIFO_LEN=64`, and `CONFIG_TOUCHSCREEN_NS2009=y`.
`CONFIG_I2C_NON_RESTART_MODE` and `CONFIG_I2C_DEBUG_INFO` are unset. A clean
upstream port replaces the vendor-controller selection with
`CONFIG_I2C_JZ4780=y`; the board-side NS2009 selection remains separate.

### Register and controller-model comparison

| Area | Vendor versus upstream v6.6.18 | Classification | Consequence for I2C4/NS2009 |
| --- | --- | --- | --- |
| Core register map | `CTRL 0x00`, `TAR 0x04`, `DATA_CMD 0x10`, standard/fast HCNT and LCNT at `0x14..0x20`, interrupt status/mask at `0x2c/0x30`, FIFO thresholds at `0x38/0x3c`, clear registers at `0x40..0x68`, `ENABLE 0x6c`, `STATUS 0x70`, `TX_ABRT_SOURCE 0x80`, `SDA_SETUP 0x94`, and `ENABLE_STATUS 0x9c` coincide. | **IDENTICAL / EQUIVALENT** | The X2000 vendor source exposes no different base register model. |
| Newer-core registers | Vendor has TX/RX FIFO levels at `0x74/0x78` and SDA hold at `0x7c`. Upstream's X1000 mode already uses `0x7c` and its FIFO algorithm does not need the level registers. | **IDENTICAL / EQUIVALENT** for SDA hold; **VENDOR IMPLEMENTATION DIFFERENCE ONLY** for level accounting | No X2000 data field beyond the existing X1000 mode is demonstrated. |
| MMIO access helper | Vendor performs one 32-bit `readl`/`writel` but deliberately returns/writes only an `unsigned short`. Upstream performs one 16-bit `readw`/`writew` per access. All reached fields fit in the same low 16 bits. | **VENDOR IMPLEMENTATION DIFFERENCE ONLY** in the available code; physical halfword-access tolerance remains **UNCLEAR** without a local X2000 register manual or an upstream-driver run | There is no source evidence for an X2000-only field or ordering rule. This is a later qualification item, not a demonstrated quirk to copy. |
| `DATA_CMD` | Read is bit 8 and the X1000/X2000 explicit STOP is bit 9 in both implementations. Vendor also defines a command-level restart bit 10 but never uses it. | **IDENTICAL / EQUIVALENT**; unused bit 10 is **VENDOR IMPLEMENTATION DIFFERENCE ONLY** | Upstream X1000 mode can issue the final STOP required by NS2009. |
| `ENABLE`, `ENABLE_STATUS`, and `STATUS` | Both use enable bit 0 and the same master-active, RX-not-empty, TX-empty and TX-not-full status bits. Vendor polls at 1 ms for up to 255 iterations; upstream makes five 5--15 ms attempts. | **IDENTICAL / EQUIVALENT** semantics; polling policy is **VENDOR IMPLEMENTATION DIFFERENCE ONLY** | No observed productive transition needs the longer vendor bound. |
| Interrupt map | TX abort bit 6, TX empty bit 4, RX full bit 2, RX overflow bit 1, and STOP detect bit 9 match. Both mask interrupts when a message completes. | **IDENTICAL / EQUIVALENT** register semantics | The drivers choose different completion events, but no new X2000 interrupt exists. |
| FIFO and thresholds | Vendor configuration is 64 entries, TX threshold 32, RX threshold 31. Upstream X1000 data is exactly 64/32/31. | **IDENTICAL / EQUIVALENT** | The largest productive message is two bytes, so it cannot distinguish the FIFO algorithms or approach either threshold. |
| SCL high/low counters | Both use the same standard/fast registers and the same hardware compensation macros: high count minus 8 with minimum 6, low count minus 1 with minimum 8. Their chosen duty cycles differ as described below. | **IDENTICAL / EQUIVALENT** hardware semantics; formula is **VENDOR IMPLEMENTATION DIFFERENCE ONLY** | Both produce 100 kHz from the demonstrated clock model; no special X2000 offset is present. |
| SDA setup/hold | Both write setup at `0x94`; vendor and upstream X1000 mode write hold at `0x7c`. Vendor derives both as roughly one quarter of an SCL period, while upstream derives standard-mode values from 300 ns setup and 400 ns hold and caps each programmed value at 255. | **VENDOR IMPLEMENTATION DIFFERENCE ONLY** | The upstream values satisfy the timing bounds stated in its source. No NS2009 evidence requires the much longer vendor values. |
| Restart and STOP | Both enable controller restart in `CTRL` bit 5. For a normal multi-message write/read, each omits STOP after the write and puts STOP on the final X1000-style read command. Vendor additionally supports `I2C_M_NOSTART`; upstream does not preserve a no-START continuation. | **IDENTICAL / EQUIVALENT** for the productive repeated-start sequence; `I2C_M_NOSTART` support is **VENDOR IMPLEMENTATION DIFFERENCE ONLY** | NS2009 needs repeated START, not `I2C_M_NOSTART`, and is covered by upstream. |
| Completion | Vendor waits for STOP detect on the final message (and RX completion for a read). Upstream completes a read after receiving the requested bytes; for a final write it waits after FIFO service until master-active clears and TX is empty. | **VENDOR IMPLEMENTATION DIFFERENCE ONLY** | The final NS2009 read command contains STOP. No source or OpenKE change identifies STOP-detect waiting as an X2000 requirement. |
| Abort and timeout | Vendor decodes abort causes, sometimes returns `-ENXIO`/`-EAGAIN`, and uses a 1000 ms base plus a wire-time estimate. Upstream reports abort as `-EIO` and uses `300 * (length + 5)` ms, giving 1800 ms for the one-byte write and 2100 ms for the two-byte read. Both set five adapter retries. | **VENDOR IMPLEMENTATION DIFFERENCE ONLY** | Both bounds are far beyond a normal 100 kHz three-byte coordinate transaction. NS2009 does not depend on a particular error number. |
| Flush and recovery | Vendor drains stale RX data before a read and toggles `ENABLE` after transfer errors. Upstream limits outstanding read commands to FIFO capacity, drains until the requested length, clears abort/all interrupts, toggles master mode during cleanup, and disables the controller after the complete transfer. | **VENDOR IMPLEMENTATION DIFFERENCE ONLY** | These are alternative driver-state machines. No X2000-specific flush/reset requirement is demonstrated for the short productive transfers. |
| Extra registers and diagnostics | Vendor names raw interrupt status, DMA control/thresholds, and filter `0xa0`; raw status and DMA registers are only dumped, the filter write is commented out, and neither driver implements I2C DMA. Vendor register dumps and its debug sysfs file are optional diagnostics. | **DEBUG / DIAGNOSTIC ONLY** or unreachable | None belongs in the minimal productive port. |

The apparent vendor 10-bit support is not a retained feature: it advertises
`I2C_FUNC_10BIT_ADDR`, but the transfer path never programs the master 10-bit
address bit. Fre3nder uses a normal 7-bit address in any case.

### Timing comparison

The vendor clock provider makes `gate_i2c4` a gate whose parent is `div_apb`.
The vendor driver discovers that clock through the generated global name
`gate_i2c4`; this is lookup structure, not a second hardware clock. The APB
divider is read from CPCCR at runtime and its rate is not fixed in the kernel
DTS. The local SDK U-Boot configuration describes AHB2 as 300 MHz and comments
that APB is AHB2/2, so 150 MHz is the SDK's nominal example, not a statically
proven rate for every productive boot.

Let the runtime gate rate be `F` Hz and the requested rate be 100000 Hz:

- Vendor chooses equal unadjusted counts
  `H = L = floor(F / (2 * 100000))`.
- Upstream first computes
  `P = floor(floor(F / 1000) / 100)`, then standard-mode
  `H = floor(P * 4000 / 8700)` and `L = P - H`.
- In both cases the common minus-8/minus-1 register compensation restores the
  respective `H` and `L` as the effective hardware counts. Thus the nominal
  SCL rates are `F / (2 * floor(F / 200000))` for the vendor calculation and
  `F / floor(floor(F / 1000) / 100)` for upstream, subject only to integer
  rounding.

At the SDK's nominal 150 MHz APB rate the concrete programming is:

| Calculation | Effective H/L counts | Programmed standard HCNT/LCNT | Programmed setup/hold | Resulting SCL |
| --- | --- | --- | --- | --- |
| Vendor | 750 / 750 | 742 / 749 | 374 / 375 | exactly 100000 Hz; 5.000 us high and 5.000 us low |
| Upstream X1000 | 689 / 811 | 681 / 810 | 46 / 59 | exactly 100000 Hz; about 4.593 us high and 5.407 us low |

The setup/hold count difference is intentional policy, not an X2000 register
difference: at 150 MHz the upstream values correspond to its documented 300 ns
setup and 400 ns hold, while the vendor calculation is approximately 2.5 us
for each. Both high/low choices meet the standard-mode minima quoted by the
upstream driver. Because both drivers derive counts from `clk_get_rate()`, no
hard-coded APB rate or X2000 timing table is required. An exact non-nominal SCL
value cannot be stated without the runtime CPCCR-derived clock, and none is
invented here.

### FIFO, clock, and transfer consequence

The existing upstream `x1000_i2c_config` already expresses every demonstrated
newer-core datum: version `ID_X1000`, FIFO size 64, TX threshold 32, and RX
threshold 31. Vendor uses the same constants. Its explicit reads of `TXFLR`
and `RXFLR` are one way to schedule FIFO work; upstream instead tracks issued
read commands and received bytes and uses `STATUS`. A one-byte command and
two-byte reply cannot make that implementation choice material.

For a clean generic X2000 description, I2C4 should reference the X2000 clock
provider directly, for example the provider's `CLK_GATE_SMB4`, and explicitly
state `clock-frequency = <100000>`. The upstream driver obtains and enables
that one unnamed clock. No reset phandle or separate reset sequence appears in
the vendor DTS or driver. The vendor's `clk-always-enable` property merely
prevents its optional per-transfer gating; I2C4 already uses that setting, and
the upstream v6.6.18 driver likewise keeps its acquired gate enabled for the
device lifetime.

The minimum controller match can directly map `ingenic,x2000-i2c` to the
unchanged `x1000_i2c_config`. An even smaller driver-side form is the normal
two-compatible DTS pattern
`"ingenic,x2000-i2c", "ingenic,x1000-i2c"`, which lets the existing X1000
match supply the data with no new C logic. Either form needs the binding to
admit X2000. The v6.6.18 YAML also requires `dmas` and `dma-names` even though
`i2c-jz4780.c` is entirely PIO and the working X2000 node supplies neither.
The X2000 binding addition should therefore make those properties optional for
this PIO instance rather than invent an unused DMA dependency.

For the NS2009 operation, upstream's first one-byte write is an intermediate
message, so X1000 mode omits its STOP. With restart enabled, the following
two-byte read begins with a repeated START and its last read command carries
the explicit STOP bit. TX-empty and RX-full service, TX-abort detection, and
the upstream cleanup path cover the only reached sequence. Upstream's known
limitation for a read message followed by another message is outside this
write-then-read path.

### Vendor code that is not on the productive path

- `CONFIG_I2C_DEBUG_INFO`, the write-only debug sysfs attribute, conditional
  transfer logs, register dumps, and the unconditional timing `dev_info()` are
  diagnostics; the selected debug option is unset.
- `CONFIG_I2C_NON_RESTART_MODE` is unset and would remove the restart behavior
  needed by the NS2009 combined read. It is not a feature to port.
- Configurable `CONFIG_I2C_FIFO_LEN` is unnecessary when X2000 selects the
  existing fixed 64-entry X1000 data.
- Dynamic `gate_i2cN` name construction, global clock lookup, numbered-adapter
  alias handling, and `clk-always-enable` are vendor integration choices; a DT
  clock phandle and normal upstream adapter registration replace them.
- Generic `ingenic,i2c` and X1600/X2500/X2600/AD100 match entries, 10-bit
  capability advertising, `I2C_M_NOSTART` handling, unused DMA/filter/register
  definitions, and per-transfer clock-gating/suspend code are not reached by
  Fre3nder's one X2000 I2C4 slave.
- The vendor FIFO scheduler, STOP-detect completion state machine, abort-string
  table, custom error mapping, and reset implementation are alternatives to
  functionality already present upstream, not independently required code.

### OpenKE findings

| Area | Classification | Finding |
| --- | --- | --- |
| `i2c-ingenic.c` | **NO RELEVANT CHANGE** | The OpenKE working-tree file is byte-identical to the pinned SDK copy; its local path history contains only the imported SDK baseline. |
| X2000 I2C clock/provider and base I2C4 node | **NO RELEVANT CHANGE** | `clk-x2000.c` is byte-identical to the SDK copy, and local history shows no I2C clock or base-controller correction. |
| I2C4 and GPC25/GPC26 board wiring | **CONFIRMS FRE3NDER** | OpenKE enabled I2C4, added `i2c4_pc`, and documented the real stock-DTB pin conflict with UART3. This confirms board routing, not a controller quirk. |
| NS2009 | **CONFIRMS FRE3NDER** | OpenKE's later NS2009 work established GPC15 pendown and the working `0x48` endpoint. Those changes are in the board/child-driver layer and do not alter I2C timing, FIFO, clock, or IRQ behavior. |

No OpenKE commit in the available local history supplies a known vendor I2C
fix, an X2000-only controller workaround, or a different I2C4 clock model.

```text
I2C DECISION:
UPSTREAM + MATCH/DATA SUFFICIENT

Required upstream change:
- enable CONFIG_I2C_JZ4780 instead of CONFIG_I2C_INGENIC
- admit X2000 and let it select the unchanged X1000 controller data
  (64-entry FIFO, TX threshold 32, RX threshold 31, SDA hold at 0x7c,
  explicit DATA_CMD STOP); this can be a direct match entry or an X1000
  fallback compatible

Required new X2000-specific code:
- no controller quirk; at most a compatible/match entry referring to the
  existing x1000_i2c_config

Vendor code that can be dropped:
- the complete standalone i2c-ingenic.c implementation
- debug sysfs/log/dump code, dynamic global clock-name lookup, configurable
  FIFO and restart switches, numbered-adapter plumbing, other-SoC matches,
  unused DMA/filter surface, unsupported 10-bit claim, I2C_M_NOSTART support,
  and the alternative FIFO/STOP/abort/reset state machine

Required DTS/binding change:
- generic X2000: allow "ingenic,x2000-i2c" with the X1000-compatible data,
  reference CLK_GATE_SMB4 from the X2000 clock provider, state
  clock-frequency = <100000>, and permit this PIO instance without fabricated
  dmas/dma-names; drop the vendor-only clk-always-enable property
- Fre3nder/KE: retain I2C4 at 0x10054000 with its IRQ, GPC25/GPC26 i2c4_pc
  pinctrl, NS2009 at 0x48, GPC15 active-low pendown, and disabled UART3

Remaining uncertainty:
- the kernel DTS does not fix the runtime CPCCR-derived APB rate; 150 MHz is
  only the local SDK configuration's nominal value, although both algorithms
  derive 100 kHz from the rate returned by the clock framework
- no local X2000 register manual independently confirms halfword MMIO access;
  the source comparison shows identical low-16-bit semantics but the upstream
  access method has not been exercised on X2000 in this scoped analysis
- absence of an NS2009 clock-stretching requirement is based on the available
  code and qualification records, not a controller-bus trace
- this is a static source/configuration decision; no upstream-driver hardware
  qualification was performed in the requested scope
```
