# Building Fre3nder

Builds create local artifacts; they do not access or change a printer. Run the
commands below from the repository root. The productive entry points are
[`scripts/build-x2000`](../scripts/build-x2000) for the host and
[`scripts/build-f005`](../scripts/build-f005) for an optional, separate MCU
candidate. Building an artifact does not qualify or authorize its deployment.

## Prerequisites

- A checkout of this repository with its pinned inputs under
  [`configs/x2000`](../configs/x2000) and
  [`configs/x2000/sources.json`](../configs/x2000/sources.json).
- Docker, Git, Python 3, and OpenSSL on the build host. The component scripts
  build [`build/x2000`](../build/x2000) as their container environment, fetch
  pinned sources, then compile without network access.
- Sufficient local space for the ignored `local/production/` source, toolchain,
  and artifact trees. Keep that directory out of Git.
- For a complete X2000 build or composition, an Ed25519 OTA signing pair.
  Create it once with `scripts/generate-ota-keypair`; the default location is
  `local/production/keys/ota/`. Keep `private.pem` local and private. The
  command refuses to replace an existing pair. Kernel-only does not need the
  keys; RootFS assembly needs the public key as its trust anchor, and final
  composition needs the matching pair.

A normal release build requires a clean project worktree. Use `--develop`
explicitly for a build from the current worktree. This changes artifact mode
and provenance, not build scope. It does not authorize `--write` in a deploy
command. Source versions, toolchains, licenses, and exact patch identities are
recorded in the [source manifest](../configs/x2000/sources.json) and
[licensing record](licensing-and-provenance.md).

## Complete X2000 build

```sh
scripts/generate-ota-keypair  # once per build environment
scripts/build-x2000
```

The default command builds Kernel, Moonraker, the Buildroot toolchain, and
RootFS, then composes a signed OTA package. RootFS assembly requires an already
signed Fre3nderScreen factory `.fre3app` at
`local/production/factory-apps/fre3nderscreen.fre3app`, or an explicit
`FRE3NDER_FACTORY_FRE3NDERSCREEN_APP` path. By default this is a release app
(`release_serial >= 1`), independently of the platform's artifact mode.
For a development artifact from the current worktree, use:

```sh
scripts/build-x2000 --develop
```

| Command | Fre3nder platform | Fre3nderScreen Factory app |
| --- | --- | --- |
| `scripts/build-x2000` | Release | Prepared release seed; no Screen build or packaging |
| `scripts/build-x2000 --develop` | Development | Prepared release seed; no Screen build or packaging |
| `scripts/build-x2000 --develop --fre3nderscreen-app` | Development | Current remote Screen `main`, built and signed as a development app |
| `scripts/build-x2000 --fre3nderscreen-app` | Invalid | Requires `--develop` |

The optional app path first runs `scripts/build-x2000-fre3nderscreen --develop`,
then `../fre3nder-apps/scripts/build-fre3nderscreen-development` with the neutral
artifact and the existing `local/production/keys/apps/private.pem`. The sibling
apps repository must have no tracked staged or unstaged changes; untracked and
ignored generated files do not block it. Import and signing remain owned by
`fre3nder-apps`. Any failure stops the pipeline without falling back to a release
seed. The returned absolute regular, non-symlink package is passed to RootFS
assembly only for this invocation; the canonical release seed is never changed.

`FRE3NDER_FACTORY_FRE3NDERSCREEN_MODE` explicitly controls the Buildroot wrapper's
expected app mode: `release` (default) requires `release_serial >= 1`, and
`development` requires `release_serial = 0`. Other values are rejected before
building. The top-level orchestrator selects `development` only with the app
flag and otherwise selects `release`. A release platform cannot use a development
Factory app. These commands still require explicit build/signing authorization.

The orchestrator runs the Kernel builder, then Moonraker, Buildroot
`--toolchain`, and Buildroot `--assemble`. It uses the pinned
Buildroot internal MIPS toolchain for the host components. The resulting
RootFS is read-only SquashFS.

Prepare the Fre3nderScreen release factory seed separately with:

```sh
scripts/build-x2000-fre3nderscreen-release
```

This release-only pipeline runs `scripts/build-x2000-fre3nderscreen`, then the
existing `../fre3nder-apps/scripts/build-fre3nderscreen-release` importer/package
wrapper. It takes the package path from that wrapper's PASS block and atomically
copies the package to `local/production/factory-apps/fre3nderscreen.fre3app` with
mode `0644`, checking byte equality and SHA256. Defaults are the sibling
`../fre3nder-apps` repository and the existing key at
`local/production/keys/apps/private.pem`; `--apps-repo <path>` and `--key <path>`
override them. It performs no RootFS build or deployment and requires explicit
build/signing authorization before execution.

The underlying cross-builder remains available for separate artifact builds,
including `--develop`; the release pipeline accepts no `--develop`. RootFS assembly
validates the finished package using the same package core as runtime install
and embeds it without unpacking. Its SHA256 is recorded under `factory_apps` in
the RootFS build manifest; the seed is not part of the Fre3nder build-input hash.

The component scripts are
[`scripts/build-x2000-kernel`](../scripts/build-x2000-kernel),
[`scripts/build-x2000-moonraker`](../scripts/build-x2000-moonraker),
[`scripts/build-x2000-buildroot`](../scripts/build-x2000-buildroot).
Use the top-level orchestrator for normal build scopes.

The host artifact directories are:

| Directory under `local/production/artifacts/x2000/` | Result |
| --- | --- |
| `kernel-only/` | `kernel.uImage`, DTB, effective kernel configuration, manifest and checksums |
| `moonraker/` | Validated component overlay archive |
| `fre3nderscreen/app/` | Separate neutral binary, themes, licenses, source/ABI manifest and checksums |
| `rootfs-only/` | `rootfs.squashfs`, effective Buildroot configuration, manifest and checksums |
| `full/` | Combined individual artifacts, manifest, checksums and `fre3nder-<version>-ender3-v3-ke.ota` |

`full/` keeps the individual Kernel and RootFS files available for inspection.
The OTA package contains `manifest.json`, `SHA256SUMS`, `SHA256SUMS.sig`,
`kernel.uImage`, and `rootfs.squashfs`. Its signature and installed RootFS
trust-anchor relationship are specified in [OTA architecture](ota.md).

## Partial builds and reuse

| Command | Builds | Does not build | Output |
| --- | --- | --- | --- |
| `scripts/build-x2000 --kernel-only` | Buildroot toolchain and linux-firmware prerequisites, then Kernel | RootFS artifact or OTA package | `kernel-only/` |
| `scripts/build-x2000 --rootfs-only` | Moonraker and Buildroot toolchain/RootFS | Kernel, Fre3nderScreen cross-build, or OTA package | Moonraker component and `rootfs-only/` |
| `scripts/build-x2000 --compose-only` | No component | Kernel and RootFS | Validated `full/` and signed OTA package |

Add `--develop` to a Kernel-only or RootFS-only development build.
`--rootfs-only --develop --fre3nderscreen-app` also uses the optional app path,
without building a Kernel. The app flag is invalid with `--kernel-only` or
`--compose-only`, and can be combined with `--f005-build` in full or RootFS scopes.
Add `--f005-build` to a full or RootFS-only build only when a new F005 candidate
must be built before RootFS assembly; it invokes the separate F005 builder,
which requires a clean project worktree. `--f005-build` is invalid with
`--kernel-only` and `--compose-only`.

The F005 builder requires an already prepared X2000 Buildroot `host/` toolchain.
In a full build, the preceding Kernel step prepares it. With
`--rootfs-only --f005-build`, it must exist before the command starts: F005 runs
before that command's Buildroot `--toolchain` phase.

`--compose-only` is a standalone scope and cannot be combined with `--develop`,
`--kernel-only`, `--rootfs-only`, or `--f005-build`. It requires existing
`kernel-only/` and `rootfs-only/` artifacts plus the signing keypair. It
checks required files, component hashes, matching project `VERSION`, matching
component `artifact_mode`, and the RootFS public key against the signing pair.
It permits Kernel and RootFS from different commits or build-input
fingerprints; their origins are recorded separately in
`component_provenance`. The final project state is recorded in
`composition_provenance`. Check those fields before composing artifacts from
different origins.
The composition command reports validation start and an explicit `PASS` or
`FAIL`; on success it prints the mode, package path, and Kernel/RootFS hashes.

Development Buildroot output and its internal toolchain may be reused when the
toolchain fingerprint matches; the configuration is reapplied for the
incremental build. Release builds remove old Buildroot output before the
toolchain phase, then reuse that prepared toolchain in the same orchestration.
Development reuse is an iteration aid, not a release reproducibility claim.
The detailed maintenance and WLAN source contract is in
[Buildroot maintenance](buildroot-maintenance.md).

## Inspect the artifacts

From the repository root, check the recorded hashes and parse the manifest in
the output directory of the build scope you ran. For a full build:

```sh
(cd local/production/artifacts/x2000/full &&
  sha256sum -c SHA256SUMS &&
  python3 -m json.tool build-manifest.json >/dev/null)
```

For a partial build, substitute `kernel-only/` or `rootfs-only/` for `full/` in
that command. In each directory, inspect its own `build-manifest.json`:

| Build scope | Fields to inspect in that manifest |
| --- | --- |
| `--kernel-only` | `version`, `artifact_mode`, `project_commit`, `project_worktree_status`, and `artifacts` hashes for `kernel.uImage`, DTB, and effective Kernel configuration |
| `--rootfs-only` | The same identity fields, `artifacts` hashes for `rootfs.squashfs` and `buildroot.config`, plus `ota_public_key_sha256`, `rootfs_components`, and `factory_apps.fre3nderscreen.sha256` for the signed seed embedded in the RootFS |
| Full build or `--compose-only` | The same identity fields and `artifacts` hashes for Kernel and RootFS, `ota_public_key_sha256`, `rootfs_components`, `factory_apps.fre3nderscreen.sha256`, plus `component_provenance` for each input and `composition_provenance` for the final assembly |

For `development` artifacts, also check `build_input_sha256`; release artifacts
have no such field and require `project_worktree_status: clean`. The
`artifact_mode` field distinguishes build/provenance mode, not a diagnostic,
provisioned, or normal RootFS content variant. There is no separate RootFS
variant field in the current manifest. Check the effective configuration and
RootFS contents for the intended boot and access path; hashes establish the
identity of what was built, not its behavior on a printer or permission to
deploy.

Buildroot provides `unsquashfs` under
`local/production/work/x2000/buildroot-output-fre3nder/host/bin/`. For example,
from the repository root:

```sh
local/production/work/x2000/buildroot-output-fre3nder/host/bin/unsquashfs \
  -ll local/production/artifacts/x2000/rootfs-only/rootfs.squashfs
```

## F005 MCU candidate

A read-only recipe check is available without fetching or building:

```sh
scripts/build-f005 --check
```

A separately authorized F005 candidate build uses `scripts/build-f005` from a
clean project worktree. It requires the prepared X2000 Buildroot `host/`
toolchain for `c_helper.so`, but uses a separate ARM bare-metal toolchain for
the MCU. Its output is under `local/production/artifacts/f005/candidate/`:
raw firmware, ELF, dictionary, resolved configuration, packaged updater image,
X2000 `c_helper.so`, report, manifest, and checksums. It neither flashes nor
promotes that candidate to the hardware-qualified release image. The detailed
recipe is in [`build/klipper-f005/README.md`](../build/klipper-f005/README.md).

### Klipper upstream refresh (2026-09-28)

The productive pin moves from `0499b30374315f2a9f49fc12808527fc7d0f5cfa`
to upstream `master` commit `7bc4d09465d31cd30fc0822e8d0abe02cc8c547f`
(44 commits). `serialhdl.py` is unchanged, so the passive X2000 UART patch
applies unchanged. Upstream now embeds the minimal MCU Kconfig in identify data
and exposes it in Klippy status, fixes generic command parsing and `trapq`, and
adds N32G45x clock changes in `stm32f1.c`. The F005 patch was rebased around
those clock changes and keeps the 64 KiB bootloader option hidden for GD32F303;
the serial bootloader-request patch remains necessary. The new Python 3.12
requirements are `greenlet 3.3.2` and `cffi 2.1.1`, supplied through the
existing Buildroot package path. No new F005 candidate or RootFS artifact was
built or qualified during this refresh.

### Moonraker upstream refresh (2026-10-01)

The productive Moonraker commit is defined only by
`userspace.moonraker.commit` in `configs/x2000/sources.json`; build and test
consumers read it with `scripts/source-value userspace.moonraker.commit`.
The refresh advances three commits beyond the hardware-qualified `v0.11.0`
baseline. GitHub release detection now prefers `tag_name`; Git checkout
detection, dependencies, runtime arguments, and data/config paths are unchanged.

Fre3nder 2026.4 explicitly accepts the upstream
[authorization change](https://github.com/Arksine/moonraker/commit/fbfe3482c32c934b34cbe00d04c0a29f3abb0291):
an already trusted connection retains its authorization after a failed
credential attempt. With API-key authentication enabled, an invalid nonblank
API key remains invalid, and an untrusted client gains no trusted authorization.
The existing `trusted_clients` configuration remains the trust boundary. No
Fre3nder configuration change was required; API-key authentication remains
enabled by default and logins are not forced. This refresh has no new build or
hardware qualification; the historical qualification record remains unchanged.

## Common failures and next steps

- Missing signing keys: generate the local pair before a complete build or
  `--compose-only`; check that its public half is the one recorded by RootFS.
- Dirty release worktree: either restore a clean release checkout or choose
  `--develop` for a development artifact.
- Stale or incompatible partial artifacts: rebuild the affected component;
  `--compose-only` validates them and stops without rebuilding anything.
- Missing F005 `host/` toolchain: run the Kernel build scope first when using
  `--rootfs-only --f005-build` or the separate F005 candidate builder.

For installing a checked host artifact, continue with
[installation](installation.md). For the host design and hardware contracts,
see [X2000 architecture](x2000-open-host-architecture.md) and
[X2000 hardware](x2000-hardware-contract.md). Historical X2000 build and
qualification records remain in
[`research/docs/x2000-build-history.md`](../research/docs/x2000-build-history.md).
