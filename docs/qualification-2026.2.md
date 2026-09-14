# Fre3nder 2026.2 candidate qualification

Status date: 2026-09-14

This document records the integrated hardware qualification of the `2026.2.a`
release candidate built from project commit
`885706f121c76190d6d74177ffac3895cd58c78d` on the investigated reference
Ender-3 V3 KE.

The qualification applies to this exact candidate and does not automatically
generalize to other hardware revisions or later source/toolchain revisions.

## Candidate identity

- Fre3nder version: `2026.2.a`
- project commit: `885706f121c76190d6d74177ffac3895cd58c78d`
- artifact mode: `release`
- kernel: `6.6.18-rt23`
- Buildroot: `2025.02.18`
- Buildroot commit: `d030e36bbc9669230c015be971b14b6e062cfdde`
- Klipper: `0499b30374315f2a9f49fc12808527fc7d0f5cfa`
- Moonraker: `985c1d0bbeb90bc057d34a232c9dc3b05e0c6c8d`
- GuppyScreen: `baa4f6689ac7334d240107529f6d3c42a1297319`
- GuppyScreen release: `0.0.26-beta+fre3nder.baa4f66`
- F005 runtime: `?-20260830_120730-cde6ec7a76a4`

Candidate payload hashes:

- kernel.uImage:
  `7925a6a58d11321c81fd77bc7eebe5670625f9e887419776af6d46a6b39f1918`
- rootfs.squashfs:
  `b745c59837013b151acd558277532d9853f8f826d71972e03ccc5ca0ed91c0d6`

The candidate was produced with one release-mode
`scripts/build-x2000 --kernel-build` run. F005 was not rebuilt.

## Artifact and deployment gates

The complete candidate artifact gate passed before deployment:

- regular non-symlink artifacts: PASS
- published SHA256 files: PASS
- component/composed artifact identity: PASS
- release provenance: PASS
- Buildroot source/toolchain identity: PASS
- Moonraker component provenance: PASS
- GuppyScreen component provenance: PASS
- `CANDIDATE_ARTIFACT_GATE=PASS`

The established A/B deployment path then passed:

- `KERNEL_P6=PASS`
- `ROOTFS_P8=PASS`
- `SYSTEM_PERSISTENCE_RESET=PASS`
- `DEPLOY_X2000=PASS`

Protected Stock kernel and RootFS slots remained unchanged.

## Managed application recovery

After the system-overlay reset, Fluidd reported:

- `desired=installed`
- `app_handler=present`
- `payload=missing`
- `moonraker_config=present`
- `moonraker_include=present`

`fre3nder restore fluidd` reconstructed the payload.

After the documented web and Moonraker restarts:

- Fluidd/Lighttpd returned HTTP 200
- `klippy_connected=true`
- `klippy_state=ready`
- `failed_components=[]`
- `warnings=[]`
- Moonraker version was `v0.11.0-0-g985c1d0`
- the expected qualified F005 runtime remained connected

This qualifies the explicit managed-app restore path after a system-overlay
reset.

## GuppyScreen real print

The exact pinned GuppyScreen build ran from the candidate RootFS using the native
framebuffer/evdev path.

A real print was selected and started directly through GuppyScreen and completed
successfully.

This exercised:

- GuppyScreen -> Moonraker -> Klipper -> F005
- heating
- homing
- motion
- extrusion
- job-state handling
- local display and touch operation
- simultaneous availability of the LAN web stack

Result: `GUPPYSCREEN_REAL_PRINT=PASS`.

## Reboot and persistence

One explicitly authorized Fre3nder-to-Fre3nder reboot was performed with the B
selector active.

The system returned on p8 with:

- kernel `6.6.18-rt23`
- persistent root `active`
- Klipper `active`
- Moonraker `active`
- web service `active`
- GuppyScreen `active`
- camera service `active`

The persistent GuppyScreen configuration, Moonraker configuration, and active
frontend selection retained their exact pre-reboot SHA256 values.

Fluidd desired state, handler, payload, and frontend selection remained present.

The post-reboot qualification returned:

- `REMOTE_RUNTIME=PASS`
- `HOME_PERSISTENCE=PASS`
- `MOONRAKER_KLIPPER=PASS`
- `F005_MCU=PASS`
- `FLUIDD_PERSISTENCE=PASS`
- `POST_REBOOT_GATE=PASS`

The selector was then returned to `STOCK_A` without another reboot.

## Reboot-gate timing observation

The first automated reboot gate used SSH reachability as its boot-complete
condition.

SSH became reachable before persistent-root and service startup had completely
settled, so the immediate runtime assertion failed before any individual
service state was printed.

A read-only check on the same boot subsequently showed the persistent root and
all required services active. The complete post-reboot gate then passed.

This was a test-harness timing race, not a runtime failure.

Future automated reboot gates should wait with a bounded timeout for the
required runtime status files to reach their expected states rather than using
SSH availability alone.

## Buildroot 2025.02.18 toolchains

This candidate provides integrated hardware qualification of the concrete
Buildroot `2025.02.18` internal toolchain profiles recorded in
`configs/x2000/sources.json`.

Qualified profiles:

- userspace: MIPS32r2 O32 hard-float FPXX NaN2008
- kernel: MIPS32r5 O32 soft-float legacy-NaN

Successful boot, service operation, system-overlay recovery, reboot persistence,
and the complete real print qualify both profiles for this exact Buildroot pin.

The candidate manifests still recorded `hardware_validated=false` because those
manifests were produced before the hardware evidence existed. This
documentation commit promotes the source metadata to `true`.

A later Buildroot patch release requires fresh qualification.

## Requirement impact

The integrated candidate run satisfies REQ-2026.2-009 on the investigated
reference system.

It also closes the previously open:

- exact-pin GuppyScreen persistent deployment
- normal local real-print control through GuppyScreen
- Moonraker final-candidate reboot persistence
- Moonraker system-overlay baseline recovery
- Fluidd explicit system-overlay restore
- Fluidd normal-reboot persistence
- Buildroot 2025.02.18 concrete toolchain hardware qualification

Separate open acceptance items are not inferred from this run.

In particular:

- REQ-2026.2-001 still retains its explicit missing/invalid persistence-backend
  cases.
- REQ-2026.2-007 still retains explicit normal printer control through the
  Fluidd UI and hardware qualification of the explicit uninstall path.
- creation of the final release tag remains a separate release action under
  `docs/versioning.md`.
