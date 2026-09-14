# Offline GD32F303/F005 Klipper build

This build recipe targets the investigated Ender-3 V3 KE F005 board with
GD32F303RET6. It is a validated containerized source-build recipe, not a
flashing or hardware procedure. The Debian base image and package versions are
not pinned to a snapshot, so this is not a bit-for-bit hermetic environment.

The recipe is based on upstream Klipper commit
`0499b30374315f2a9f49fc12808527fc7d0f5cfa` and the public patches
`patches/klipper/0001-gd32f303-f005-mainline.patch` and
`patches/klipper/0002-f005-serial-bootloader-request.patch`, applied in that
order.

## Product build interface

The current product entry point is
[`scripts/build-f005`](../../scripts/build-f005).

A read-only recipe check is available with:

```sh
scripts/build-f005 --check
```

A normal candidate build is started with:

```sh
scripts/build-f005
```

The build requires a clean Fre3nder project worktree and the shared Buildroot
toolchain output produced by the X2000 build under
`local/production/work/x2000/buildroot-output-fre3nder/host/`. It prepares the
pinned upstream Klipper source, applies the two productive F005 patches,
records them in a deterministic local source commit, builds the container,
compiles the MCU firmware and X2000 host helper with network access disabled,
packages the F005 updater image, and writes a candidate artifact set under:

```text
local/production/artifacts/f005/candidate/
```

The candidate contains the raw firmware, ELF, Klipper dictionary, resolved
configuration, packaged F005 image, X2000 `c_helper.so`, packaging report,
build manifest, and checksums.

A newly built candidate is not automatically a qualified release. In
particular, `build-f005` does not overwrite the currently hardware-qualified
F005 artifact used by the default `deploy-f005` path. Promotion of a candidate
to a deployable release requires an explicit qualification and release
decision.

The build path performs no SSH, UART, flash, selector, partition, reboot, or
other printer operation.

## Reproducibility status

The standardized build path is **OFFLINE CONFIRMED**. Two normal
`scripts/build-f005` runs from project commit
`5a0e731f015e241ef5dc2e640eedb85b9f07db8a` produced the same deterministic
prepared source commit:

```text
2c418b65fbb0374296f66d03e89642fb5b44a569
```

Both builds embedded runtime version:

```text
v0.13.0-734-g2c418b65
```

and produced the same packaged candidate:

```text
size:   22520
sha256: b909659be8b96aa52c14b6130c8ea4c625faa9f1794a431fe7c2baf12ac23fda
```

The previously hardware-qualified firmware has size 22528 and SHA-256
`7035a193779dc070eed540052eadd9db064fd48cee9e45dedc0cb0de73711aec`.
It embeds the historical volatile runtime version
`?-20260830_120730-cde6ec7a76a4`.

A diagnostic offline rebuild that changed only the embedded runtime version
back to that historical value reproduced the qualified packaged firmware
byte-for-byte. The historical and deterministic data dictionaries are
semantically identical after normalizing the `version` field.

The deterministic candidate remains an unqualified candidate until separately
exercised on hardware. `build-f005` does not promote it or replace the
qualified deployment artifact.

The build environment is offline-oriented rather than fully hermetic. The
Dockerfile references `debian:13` rather than a pinned image digest, and Debian
package versions are not pinned to a repository snapshot. The tested build log
records the concrete base-image digest and toolchain versions that were used.

## Low-level build recipe

From the project root, with the upstream Klipper checkout at `klipper/`:

```sh
git -C klipper checkout 0499b30374315f2a9f49fc12808527fc7d0f5cfa
git -C klipper apply ../patches/klipper/0001-gd32f303-f005-mainline.patch
git -C klipper apply ../patches/klipper/0002-f005-serial-bootloader-request.patch
docker build --tag ender3-ke-klipper-build:f005 build/klipper-f005
docker run --rm --network none \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/klipper:/work/klipper:rw" \
  -v "$PWD/build/klipper-f005/f005-gd32f303.config:/config/f005-gd32f303.config:ro" \
  -w /work/klipper \
  ender3-ke-klipper-build:f005 \
  sh -lc 'cp /config/f005-gd32f303.config .config && make olddefconfig && make'
```

The normal build produces the raw `klipper/out/klipper.bin`. After that build,
create the F005-updater candidate image offline:

```sh
python3 scripts/package_f005_firmware.py \
  klipper/out/klipper.bin klipper/out/klipper-f005-mainline.bin
```

`klipper.bin` is the raw Klipper build. `klipper-f005-mainline.bin` is the
separately packaged candidate image for the investigated F005 updater; the
packager writes the board-info version, length, and CRC16 fields.

The configuration is mounted read-only and copied to `.config` inside the
checkout before running `make olddefconfig`. The expected resolved values
include:

```text
CONFIG_MCU="gd32f303xe"
CONFIG_MACH_GD32F303=y
CONFIG_MACH_STM32F1=y
CONFIG_CLOCK_FREQ=120000000
CONFIG_CLOCK_REF_FREQ=8000000
CONFIG_FLASH_APPLICATION_ADDRESS=0x8003000
CONFIG_FLASH_SIZE=0x3d000
CONFIG_RAM_START=0x20000000
CONFIG_RAM_SIZE=0x10000
CONFIG_STM32_FLASH_START_3000=y
CONFIG_STM32_SERIAL_USART2=y
CONFIG_SERIAL_BAUD=230400
CONFIG_HAVE_BOOTLOADER_REQUEST=y
```

The image build installs only the compiler/build packages needed for this
recipe. It does not build firmware automatically. The container should be run
without network access for the compilation step, as shown above.

## Host c_helper for X2000

The F005 container does not contain or download a separate MIPS toolchain.
The normal build mounts the existing upstream Buildroot 2025.02.18 `host/`
output read-only and invokes its
`mipsel-buildroot-linux-gnu-gcc` userspace wrapper. This gives the helper the
same MIPS32r2/O32/hard-float/FPXX/NaN2008 contract as the Fre3nder RootFS.
The separate `arm-none-eabi` toolchain remains responsible only for the
GD32F303 MCU firmware.

With a prepared Klipper source checkout, the shared toolchain output and an
existing writable output directory, the equivalent low-level host build is:

```sh
docker run --rm --network none \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/klipper:/source:ro" \
  -v "$PWD/out:/output:rw" \
  -v "$PWD/local/production/work/x2000/buildroot-output-fre3nder/host:/opt/fre3nder-mips-toolchain:ro" \
  ender3-ke-klipper-build:f005 \
  build-x2000-chelper /source /output/c_helper.so
```

`build-x2000-chelper` uses the same `klippy/chelper` C source list and compiler
options as the selected Klipper source's `klippy/chelper/__init__.py`. The
result is a Fre3nder X2000 host artifact, not MCU firmware. Its static ABI
validation is part of the normal candidate build; no runtime validation is
part of this procedure. The historical GCC 7.2/Stock-X2000 helper remains
documented only as research evidence and is not a productive build input.

Do not run `flash`, `serialflash`, USB, serial-device, or other hardware
targets as part of this procedure. The recipe itself is build-only. The
documented packaged candidate produced from this source was separately
validated on the investigated reference F005 board by one controlled MCU flash,
an identify-only protocol check, and a passive Klippy configuration/finalize
test. The subsequent staged peripheral validation and complete-print result are
documented in [`../../docs/f005-hardware-validation.md`](../../docs/f005-hardware-validation.md);
arbitrary rebuilds are not thereby hardware-validated.
