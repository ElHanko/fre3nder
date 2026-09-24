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

The default command builds Kernel, Moonraker, the Buildroot toolchain,
Fre3nderScreen, and RootFS, then composes a signed OTA package. For a development
artifact from the current worktree, use:

```sh
scripts/build-x2000 --develop
```

The orchestrator runs the Kernel builder, then Moonraker, Buildroot
`--toolchain`, Fre3nderScreen, and Buildroot `--assemble`. It uses the pinned
Buildroot internal MIPS toolchain for the host components. The resulting
RootFS is read-only SquashFS.

The component scripts are
[`scripts/build-x2000-kernel`](../scripts/build-x2000-kernel),
[`scripts/build-x2000-moonraker`](../scripts/build-x2000-moonraker),
[`scripts/build-x2000-buildroot`](../scripts/build-x2000-buildroot), and
[`scripts/build-x2000-fre3nderscreen`](../scripts/build-x2000-fre3nderscreen).
Use the top-level orchestrator for normal build scopes.

The host artifact directories are:

| Directory under `local/production/artifacts/x2000/` | Result |
| --- | --- |
| `kernel-only/` | `kernel.uImage`, DTB, effective kernel configuration, manifest and checksums |
| `moonraker/`, `fre3nderscreen/` | Validated component overlay archives |
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
| `scripts/build-x2000 --rootfs-only` | Moonraker, Buildroot toolchain/RootFS, Fre3nderScreen | Kernel or OTA package | Component directories and `rootfs-only/` |
| `scripts/build-x2000 --compose-only` | No component | Kernel and RootFS | Validated `full/` and signed OTA package |

Add `--develop` to a Kernel-only or RootFS-only development build. Add
`--f005-build` to a full or RootFS-only build only when a new F005 candidate
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
| `--rootfs-only` | The same identity fields, `artifacts` hashes for `rootfs.squashfs` and `buildroot.config`, plus `ota_public_key_sha256` and `rootfs_components` |
| Full build or `--compose-only` | The same identity fields and `artifacts` hashes for Kernel and RootFS, `ota_public_key_sha256`, `rootfs_components`, plus `component_provenance` for each input and `composition_provenance` for the final assembly |

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
