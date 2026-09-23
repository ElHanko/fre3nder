# GD32F303/F005 mainline MCU port

This case study documents the offline port for the investigated Ender-3 V3 KE
reference system, specifically its F005 board with a GD32F303RET6 main MCU. It
is not a universal claim about every KE hardware revision or every GD32F303
board.

## Scope and result

The comparison and implementation use Klipper upstream commit
`0499b30374315f2a9f49fc12808527fc7d0f5cfa`. The result is a **SMALL MCU PORT**
whose productive change is limited to:

```text
src/stm32/Kconfig
src/stm32/Makefile
src/stm32/stm32f1.c
src/generic/armcm_link.lds.S
```

The current product build also applies the separate serial-bootloader-request
patch after this port. The first-port image and its tests below are historical
candidates; the current build interface and candidate/qualified distinction
are in [the build guide](build.md#f005-mcu-candidate).

A complete `src/gd32/` backend is unnecessary for this F005 contract. The
required GPIO, ADC, serial, watchdog, generic timer, software-PWM and ARM
startup paths already exist in the STM32F1-compatible and generic upstream
paths. The GD32F303 executes the selected Cortex-M3 Thumb subset on its
Cortex-M4 core, and the relevant register blocks share the offsets used by the
existing STM32F1 code. No GD32 SDK library is required.

## F005 updater image profile

The linker reserves raw offsets `+0x200..+0x21f` for the F005 board-info
region. The project packager writes the 12-byte candidate version
`mcu0_004_000`, the image length as a 32-bit little-endian value at `+0x20e`,
and the F005 CRC16/CCITT value as a 16-bit little-endian value at `+0x20c`.
The CRC is calculated over the complete raw image with the six CRC/length bytes
zeroed during calculation.

The local `mcu_util` implementation was compared offline with the public
compatible protocol implementation: handshake `75`, version `00ff`, sector
size `03fc`, update `01fe`, block checksums, application start `02fd`, and
status values `75/20/21/1f` match. The Stock updater uses the bootloader window
at MCU startup; no explicit Physical-Serial-Bootloader request was used for
this first path.

A later authorized no-write test on 2026-08-27 established a separate runtime
entry route: Klipper `FIRMWARE_RESTART` with `restart_method: command` resets
the running Mainline MCU into the Creality bootloader window. This does not
validate or enable the separate serial `bootloader_request` magic path, which
remained disabled in that initial Mainline candidate. The later productive
patch is a separate source change and qualification boundary.

The initial validated port candidate was 22392 bytes before and after packaging;
its packed-image SHA-256 is
`5b9678731b10a0f8c6159b3cf2432b1a499d6310b9466419d129dc42242e23ac`.
The binary itself is not stored in this repository.

## Productive changes

### Kconfig target

The patch adds an explicit `GD32F303xE` target with MCU identity
`gd32f303xe`, 120 MHz clock, 8 MHz external reference, 64 KiB RAM, and the
validated 12 KiB bootloader layout. The application starts at `0x08003000` and
the only offered bootloader offset for this target is the 12 KiB choice.

Unvalidated USB, CAN, main-MCU SPI/I2C, hardware-PWM, and bootloader-request
capabilities are not enabled for this target. The target intentionally reuses
the STM32F1-compatible implementation marker without presenting unrelated
STM32F1 bootloader choices.

### Makefile binding

The target is compiled for the Cortex-M3 Thumb-compatible subset and selects
the existing `STM32F103xE` register header while retaining the external
Klipper identity `gd32f303xe`. This is a narrow compatibility binding; it does
not claim that the physical MCU is an STM32F103.

### Clock initialization

The GD32 branch in `stm32f1.c` implements the F005 120 MHz contract:

- 8 MHz HXTAL divided by two, multiplied by 30;
- the HD/xE PLLM extension bit 27;
- AHB at 120 MHz, APB1 divided by two, APB2 divided by two;
- ADC clock divided by six;
- high LDO setting;
- high-drive enable/ready and high-drive switch/ready handshakes.

Normal GPIO, ADC, UART, watchdog, timer and software-PWM operation stays in
the existing upstream paths.

### GD32 flash fix

The inherited STM32F1 assignment is deliberately skipped for GD32F303:

```c
FLASH->ACR = (2 << FLASH_ACR_LATENCY_Pos) | FLASH_ACR_PRFTBE;
```

GD32 FMC semantics differ: writing `WSCNT` alone does not enable wait states,
and the STM32 prefetch bit maps to a reserved GD32 bit. The official GD32F30x
120 MHz startup leaves the FMC state at reset for the relevant image range.
The patch therefore adds no GD32 FMC or prefetch emulation.

## Conservative flash boundary

The physical GD32F303RET6 has 512 KiB of Flash at
`0x08000000..0x0807ffff`. The first mainline port deliberately exposes only
the documented first-256-KiB region:

```text
application:   0x08003000..0x0803ffff
CONFIG_FLASH_SIZE: 0x3d000
linker end:    0x08040000 (exclusive)
```

The 12 KiB bootloader occupies `0x08000000..0x08002fff`. The `0x3d000` value
is therefore a linker-visible application limit, not a claim that the chip has
only 256 KiB. The upper 256 KiB remains intentionally unused until a separate
GD32 FMC wait-state configuration for that range is documented and validated.

The validated candidate starts at `0x08003000` and ends its Flash load data at
`0x08008778`. It leaves `0x37888` bytes before `0x08040000`.

## Firmware switching contract

The validated MCU return mechanism and requirements for a future controlled
Stock <-> Fre3nder switch are documented in
[`f005-mcu-switching.md`](f005-mcu-switching.md). In particular, future
Fre3nder MCU builds must preserve the 12 KiB Creality bootloader and the normal
Klipper command-reset path.

## Offline validation

The following builds passed in the isolated Debian 13 Docker environment:

1. GD32F303/F005 build and F005 packaging;
2. representative STM32F103 regression build;
3. a second clean GD32F303/F005 build.

The GD32 ELF and vector table start at `0x08003000`; all Flash load data stays
below `0x08040000`, and RAM remains within `0x20000000..0x2000ffff`. The GD32
machine code contains no `FMC_WS`/`FMC_WSEN` access. The STM32F103 regression
still contains its existing `FLASH->ACR` assignment. The build image uses no
host ARM-toolchain installation and no hardware or device access.

The earlier non-bit-identical rebuilds were subsequently explained by
Klipper's embedded runtime version. The historical hardware-qualified image
embeds the volatile version `?-20260830_120730-cde6ec7a76a4`. Rebuilding
the same pinned upstream revision, productive patches, resolved configuration,
and compiler environment, with only Klipper's generated runtime version
diagnostically forced to that historical value, reproduced the qualified
packaged firmware byte-for-byte:

```text
size:   22528
sha256: 7035a193779dc070eed540052eadd9db064fd48cee9e45dedc0cb0de73711aec
```

The standardized `scripts/build-f005` path instead records the productive
patches in a deterministic local source commit and therefore embeds the stable
Git-derived runtime version `v0.13.0-734-g2c418b65`. Two normal builds from
project commit `5a0e731f015e241ef5dc2e640eedb85b9f07db8a` independently produced
the same prepared source commit
`2c418b65fbb0374296f66d03e89642fb5b44a569` and the same packaged candidate:

```text
size:   22520
sha256: b909659be8b96aa52c14b6130c8ea4c625faa9f1794a431fe7c2baf12ac23fda
```

A dictionary comparison found the runtime `version` field to be the only
semantic dictionary difference between the two builds. Replacing the stable
runtime version with the historical volatile value reproduced the qualified
binary exactly, establishing that the observed binary-size and hash difference
is caused by the embedded runtime-version data and its resulting binary layout,
not by an unidentified source or toolchain change.

This establishes **F005 DETERMINISTIC BUILD: OFFLINE CONFIRMED** for the
standardized build path. The new `b909659b...` candidate has not itself been
flashed and therefore is not `QUALIFIED ON DEVICE`; the existing
`7035a193...` release remains the hardware-qualified firmware.

These were the static build results before the controlled hardware test:

```text
OFFLINE MCU PORT AND F005 IMAGE VALIDATION COMPLETE
READY TO DESIGN CONTROLLED FIRST MCU FLASH
```

Build instructions and the exact source patch are published separately in
[`build/klipper-f005/README.md`](../build/klipper-f005/README.md) and
[`patches/klipper/0001-gd32f303-f005-mainline.patch`](../patches/klipper/0001-gd32f303-f005-mainline.patch).
The current host configuration is published in
[`../configs/klipper-f005/`](../configs/klipper-f005/); historical no-action
candidates remain under
[`../research/configs/klipper-f005/`](../research/configs/klipper-f005/).
They are documented in [`f005-mainline-config.md`](f005-mainline-config.md)
and the [historical milestone](../research/docs/f005-mainline-config-milestone.md).
The early offline tests exercised this MCU
dictionary in Klippy's debugoutput mode only and do not validate printer
peripherals or make further flashing safe.

## First hardware validation

The packaged candidate was flashed through one project-initiated updater
invocation on the investigated reference F005/GD32F303RET6 board through the
original early-boot Stock updater:

```text
mcu_util -i /dev/ttyS1 -c
mcu_util -i /dev/ttyS1 -g
mcu_util -i /dev/ttyS1 -u -f <mainline-f005-image>
```

The MCU initially reported `mcu0_001_G32-mcu0_005_000`. The updater returned
`update:0` and then logged `app_run`. A later identify-only exchange over the
same UART completed with:

```text
MCU=gd32f303xe
CLOCK_FREQ=120000000
SERIAL_BAUD=230400
PROTOCOL_BUILD_VERSION=?-20260820_092609-29ca4e70a84f
status=IDENTIFY COMPLETE
```

The updater's trailing `select time out, state = 12` line was not an update
failure: it was followed by `app_run`, a successful updater return, and the
successful Klipper identify response. This demonstrates **MAINLINE F005 MCU
FLASH + IDENTIFY: PASS** on the reference system. It does not
validate motion, endstops, TMC software UART, ADC/thermistors, heaters, fans,
BLTouch/probe, filament sensing, full Klippy configuration, or printing.
Those later results are recorded separately in
[`f005-hardware-validation.md`](f005-hardware-validation.md).

The first identify attempt also exposed a host-side compatibility issue:
`TIOCEXCL` returned `ENOTTY` on the Stock UART driver. The private diagnostic
helper was adjusted to tolerate only that specific host ioctl case; this was
not an MCU or protocol failure. No second flash or rollback was performed.

The successful Stock -> Mainline flash does not by itself qualify the reverse
firmware write. An initial no-write test on 2026-08-27 stopped Stock Klipper,
verified `/dev/ttyS1` free, and then ran `mcu_util -c`, `-g`, and `-s` directly
against the already running Mainline application. All three timed out because
that sequence did not first reset the MCU into its bootloader.

A subsequent separately authorized no-write test used Moonraker
`FIRMWARE_RESTART`, then released `/dev/ttyS1`. The Creality bootloader
immediately answered `mcu_util -c`; `mcu_util -g` returned
`mcu0_001_G32-mcu0_004_000`; and `mcu_util -s` returned `app_run`. All returned
0. Stock Klipper subsequently reconnected to the same Mainline MCU version and
the same known `read_swap_prtouch` incompatibility. No erase or firmware upload
occurred.

This establishes **MAINLINE -> CREALITY BOOTLOADER -> EXISTING MAINLINE APP
RETURN: QUALIFIED ON DEVICE**. A subsequent separately authorized test on
2026-08-27 then restored the preserved original Stock F005 image through one
project-initiated `mcu_util` update invocation. `mcu_util` returned success and
`app_run`; Stock
Klipper loaded the original 116-command MCU firmware and reached
`Printer is ready`. Therefore **MAINLINE F005 MCU -> ORIGINAL STOCK F005 MCU
FIRMWARE RETURN: QUALIFIED ON DEVICE**.

### Passive Mainline Klippy runtime validation

A subsequent, separately authorized passive runtime test used the pinned
Mainline Klippy tree and the empty-MCU configuration below on the investigated
reference system:

```ini
[mcu]
serial: /dev/ttyS1
baud: 230400

[printer]
kinematics: none
max_velocity: 1
max_accel: 1
```

The test exited cleanly with code `0`. Klippy loaded the real
`gd32f303xe` dictionary at 120 MHz and 230400 baud, completed ClockSync, and
sent only the empty configuration sequence:

```text
allocate_oids count=0
finalize_config crc=3912464276
is_config=1 is_shutdown=0
```

The initial `get_config` response is not separately printed in the runtime
log. The reviewed private gate nevertheless requires `is_config=0` and
`is_shutdown=0` before any configuration send; reaching `Sending MCU 'mcu'
printer configuration...` proves that this gate allowed the observed run to
continue. The log does not contain a literal `ready` line. In the pinned code,
`/dev/null` input is registered only by the `klippy:ready` handler, and EOF then
requests the ordinary host `exit` result. The clean EOF exit with code `0`
therefore establishes that READY was reached and that no firmware restart was
performed.

This establishes **MAINLINE KLIPPY ↔ MAINLINE F005 MCU PASSIVE RUNTIME
CONFIG/FINALIZE: PASS** on the investigated reference system. The validated
scope is limited to Stock Python 3.8 startup, the Mainline X2000/MIPS
`c_helper.so`, `/dev/ttyS1` at 230400 baud, dictionary loading, ClockSync,
empty-MCU configuration, `allocate_oids count=0`, `finalize_config`, the
configured MCU state, READY, and clean host exit.

This passive test alone did not validate printer peripherals. The later staged
hardware result and complete-print scope are recorded in
[`f005-hardware-validation.md`](f005-hardware-validation.md). Host ADXL/Host-
MCU, input shaping, optional PR-Touch/Z compensation, and persistent recovery
remain outside that report. The combined results do not claim support for
every KE revision. The observed MCU state at
the end was the volatile state `is_config=1`, `is_shutdown=0`; Klippy then
exited cleanly. It is not a basis for treating a later different runtime test
as a simple repetition.

Gate 1 / Point of Return is **SATISFIED** by the current evidence review;
recovery execution remains documented but not personally rehearsed. Any further
persistent hardware work remains WARNING / RED ZONE. The Stock updater should not be
reactivated for a later boot without an explicit rollback decision. The Stock
image carries `mcu0_005_000` while this candidate carries `mcu0_004_000`, so
re-enabling the Stock updater could trigger an unintended Stock firmware
update.

## References

The hardware and startup conclusions use the following primary sources:

- GigaDevice, *GD32F30x User Manual*, Rev. 3.4; official download catalogue:
  [GD32F30x downloads](https://www.gd32mcu.com/en/download/0?kw=GD32F30x).
- GigaDevice, *GD32F303xx Datasheet*: official download-catalogue entry 3.3;
  the served PDF identifies itself as Rev. 1.4. The catalogue is the provenance
  point for the revision discrepancy.
- GigaDevice, *GD32F30x Firmware Library*, version 3.0.3; official package from
  the same [GD32F30x downloads](https://www.gd32mcu.com/en/download/0?kw=GD32F30x)
  catalogue.
- Klipper upstream, commit
  `0499b30374315f2a9f49fc12808527fc7d0f5cfa`, the implementation comparison
  basis and patch parent.

No manufacturer PDF or firmware-library package is redistributed here.
