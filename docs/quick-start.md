# Quick Start: build an X2000 Fre3nder release

This host-side entry point calls the existing application and platform build
scripts in order. It creates signed `.fre3app` packages and a signed OTA
image; **it does not install anything on a printer**. This is the release
build path, not an A/B installation or recovery workflow.

## Inputs

On a Linux build host with Git, Docker, Python 3, OpenSSL and enough disk
space, clone both repositories as siblings:

```sh
git clone https://github.com/ElHanko/fre3nder.git
git clone https://github.com/ElHanko/fre3nder-apps.git
```

The build also needs the **qualified F005 MCU firmware** matching
`configs/x2000/f005-mcu-release.json`. This file is a deliberately external
build input; it is not downloaded from the repositories, and a new MCU
candidate must not silently replace it. The supplied firmware is checked
against the release's expected size and SHA-256 **before any builds begin**.
Obtain it from an appropriately preserved, verified source.

## Run

```sh
cd fre3nder
scripts/quick-start --check --firmware /path/to/klipper-f005-mainline.bin
scripts/quick-start --firmware /path/to/klipper-f005-mainline.bin
```

If the qualified firmware is already at
`local/production/artifacts/x2000/f005/klipper-f005-mainline.bin`, omit
`--firmware`. `--check` performs only the host/repository/firmware preflight;
it does **not** generate keys or start builds. Run the actual build only after
reviewing and authorizing its scope.

The Quick Start performs these existing operations, in order:

1. Generate or verify the local **app signing key**; generate an OTA keypair
   only if neither OTA key exists. An incomplete OTA keypair is an error.
2. Fetch and verify pinned Moonraker inputs, prepare its payload, and sign
   `local/production/system-apps/moonraker.fre3app`.
3. Fetch and verify the pinned Fluidd archive, prepare the payload, and sign
   a versioned Fluidd `.fre3app` in `../fre3nder-apps/dist/`.
4. Prepare the X2000 Buildroot toolchain needed to compile Fre3nderScreen.
5. Run `build-x2000-fre3nderscreen-release` to produce the signed factory
   seed at `local/production/factory-apps/fre3nderscreen.fre3app`.
6. Run `build-x2000` to compile Kernel and RootFS and compose the signed OTA
   release, then check the final artifact hashes.

The platform build currently invokes its own Buildroot toolchain preparation
again. This deliberate reuse of the existing release script prioritizes its
established build contract over introducing a second build implementation.
The fetch/preparation scripts reuse verified Moonraker and Fluidd caches.

## Results

A successful run reports `Fre3nder Quick Start: PASS` and paths for:

- `local/production/artifacts/x2000/full/fre3nder-<version>-ender3-v3-ke.ota`
- `local/production/system-apps/moonraker.fre3app`
- `local/production/factory-apps/fre3nderscreen.fre3app`
- `../fre3nder-apps/dist/fluidd-<version>-x2000.fre3app`

Both repositories must have clean, committed worktrees for the release run.
The private signing keys stay in the ignored `local/production/keys/`
directory; **back them up securely**. Changing those keys changes the trust
identity of future packages and images.

Deployment is intentionally separate and requires the established platform
safety/backup gates and the operator's explicit authorization. Consult
[installation](installation.md) and [build](build.md) before deploying an
artifact. Fluidd is built as an installable app, not silently installed or
embedded into the RootFS.
