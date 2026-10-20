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

The default command builds Kernel, the Buildroot toolchain, and
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
| `scripts/build-x2000 --develop --fre3nderscreen-app` | Development | Screen development sources (remote `main` or explicit local worktree), built and signed as a development app |
| `scripts/build-x2000 --fre3nderscreen-app` | Invalid | Requires `--develop` |

The optional app path first runs `scripts/build-x2000-fre3nderscreen --develop`,
then `../fre3nder-apps/scripts/build-fre3nderscreen-development` with the neutral
artifact and the existing `local/production/keys/apps/private.pem`. The sibling
apps development wrapper uses the current recipe, including pending tracked
changes, and reports `Recipe worktree: dirty` when applicable. The release
Factory-seed pipeline rejects tracked apps changes. Import and signing remain
owned by `fre3nder-apps`. Any failure stops the pipeline without falling back to a release
seed. The returned absolute regular, non-symlink package is passed to RootFS
assembly only for this invocation; the canonical release seed is never changed.

To include local Screen changes, explicitly select the sibling worktree:

```sh
FRE3NDER_FRE3NDERSCREEN_SOURCE=../fre3nderscreen \
  scripts/build-x2000 --develop --fre3nderscreen-app
```

This requires the already prepared Buildroot host toolchain used by the Screen
cross-builder. The variable is accepted only in development mode. The checkout
is mounted read-only; its tracked and non-ignored new files, edits, and deletions
are copied into the isolated build source. Initialized, clean submodules must
match the local recorded Git links; existing source patches are applied to their
copies. The artifact's `source` records `origin: local-worktree`, the baseline
commit, `worktree_status`, and `worktree_sha256`. The current local repository is
never reset or cleaned. Without the variable, development keeps the remote
`main` path but refuses to proceed if the conventional sibling Screen repository
has pending changes, so those changes cannot silently disappear from a build.
The default release pin is unchanged. This command requires separate explicit
build/signing authorization.

For a RootFS-only iteration using local Screen sources and an existing Kernel:

```sh
FRE3NDER_FRE3NDERSCREEN_SOURCE=../fre3nderscreen \
  scripts/build-x2000 --rootfs-only --develop --fre3nderscreen-app
scripts/build-x2000 --compose-only
```

The first command builds the app and RootFS stack without rebuilding the Kernel;
the second composes existing components. A full invocation without
`--rootfs-only` also builds the Kernel. Check its effective VT/fbcon/USB-HID
configuration before reusing a Kernel for the [display contract](display.md#linux-virtual-terminals).

Development packages use
`<artifact.source.release>-fre3nder.0.<apps-commit>` and `release_serial = 0`.
The source release includes the resolved Screen commit's short ID; the final
suffix identifies the apps recipe commit. These version strings do not identify
pending worktree changes. Inspect `source.worktree_sha256` for local Screen
content, the signed service and package SHA256 for recipe content, and
`factory_apps.fre3nderscreen.sha256` for the embedded seed. Rebuilding dirty
sources at the same commits can produce different bytes with the same version;
the package manager rejects an update to the same development version.

`FRE3NDER_FACTORY_FRE3NDERSCREEN_MODE` explicitly controls the Buildroot wrapper's
expected app mode: `release` (default) requires `release_serial >= 1`, and
`development` requires `release_serial = 0`. Other values are rejected before
building. The top-level orchestrator selects `development` only with the app
flag and otherwise selects `release`. A release platform cannot use a development
Factory app. These commands still require explicit build/signing authorization.

RootFS assembly also requires the official signed Moonraker system app in
`local/production/system-apps/` or `FRE3NDER_SYSTEM_APP_PACKAGES_DIR`.
It is prepared and signed separately in `fre3nder-apps`; a release image
requires a positive release serial. See [Moonraker](moonraker.md).

The orchestrator runs the Kernel builder, then Buildroot
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

The combined release wrapper requires a clean tracked fre3nder-apps worktree
(both staged and unstaged changes are checked). The platform worktree is
recorded as clean or dirty in the artifact manifest rather than rejected;
use reviewed, committed inputs for the release. Do not bypass the apps
check by invoking lower-level packaging commands.

The underlying cross-builder remains available for separate artifact builds,
including `--develop`; the release pipeline accepts no `--develop`. RootFS assembly
validates the finished package using the same package core as runtime install
and embeds it without unpacking. Its SHA256 is recorded under `factory_apps` in
the RootFS build manifest; the seed is not part of the Fre3nder build-input hash.
An embedded seed does not replace an installed app after Factory bootstrap has
completed. Deployment and [updating that app](installation.md#update-the-installed-display-app)
are separate steps.

### Fre3nderScreen 2026.2 release integration

The cross-builder and fre3nder-apps importer now agree on a reduced app
artifact: one binary, six themes and seven required license texts, plus
`artifact-manifest.json` and `SHA256SUMS`. The unused Screen-vendored WPA
control client is gone; Core's separate Buildroot `wpa_supplicant` remains.
Submodule/patch, static MIPS32r2 hardfloat ABI, provenance, exact file-set
and checksum validation remain in place. No Management/OTA API changes
are needed.

The source cleanup is committed and fetchable at
`823d090bc97f9e6b429aebda93f588450b33f40b`, the current
`userspace.fre3nderscreen.commit` pin. Release `2026.2` and the four submodule
pins remain unchanged. The matching platform and apps integration is committed.
The operator reports successful Docker/SDL build and manual UI testing, and
a local X2000 Development cross-build of the cleaned sources. Production
release packaging and hardware qualification of the final release binary
remain pending.

The app template remains `2026.2-fre3nder.2`, serial `2`; Development uses
serial `0` and cannot silently replace a Release. The standalone Screen
pipeline does not build Moonraker or require its system-app seed. A later
RootFS assembly independently requires the signed Moonraker seed, with a
positive release serial for a release image.

Remaining release steps:

1. Use reviewed, committed inputs and a clean tracked apps worktree. After
   explicit build/signing approval, run from Fre3nder:

   ```sh
   scripts/build-x2000-fre3nderscreen-release \
     --apps-repo ../fre3nder-apps \
     --key <existing-signing-key>
   ```

   It needs the prepared Buildroot host toolchain and an existing signing
   key. The cross-builder fetches the exact pin rather than using an old
   Development artifact. The apps wrapper replaces the generated payload
   after rejecting unsafe recipe boundaries and payload symlinks; no manual
   deletion of old payloads is required. Outputs are the neutral app artifact,
   `dist/fre3nderscreen-2026.2-fre3nder.2-x2000.fre3app` in fre3nder-apps,
   and the byte-identical local Factory seed. No Kernel or RootFS rebuild is
   needed for this app package.
2. Verify the package offline using Fre3nder Package-Core's `verify_package()`
   with `BUILTIN_KEYS` set to the repository's
   `configs/x2000/rootfs-overlay/usr/share/fre3nder/app-keys/`. Require the
   official publisher, version `2026.2-fre3nder.2`, serial `2`, display API `1`
   and `autostart = false`. Check the signed
   `payload/artifact-manifest.json` against the source/submodule pins and ABI.
   The importer checks the exact file set, manifest hashes and `SHA256SUMS`;
   Package-Core verifies the package checksums and Ed25519 signature. Confirm
   package/Factory-seed byte equality and SHA256 without installing anything.
3. Separately authorize installation and regression testing of that exact
   package on X2000. Prior hardware tests cover Screen `65b37b9`; the
   cleanup simulator and Development cross-build do not qualify the release.
4. Before publishing, explicitly resolve the existing local/remote Screen
   tag `2026.2`, currently targeting `63e7ecb`. Do not move or delete it
   automatically. Correcting that prepared tag requires a separate
   decision; choosing a new version instead also requires matching pin
   and package-version changes. Tags, pushes and releases need approval.

The component scripts are
[`scripts/build-x2000-kernel`](../scripts/build-x2000-kernel),
[`scripts/build-x2000-buildroot`](../scripts/build-x2000-buildroot).
Use the top-level orchestrator for normal build scopes.

The host artifact directories are:

| Directory under `local/production/artifacts/x2000/` | Result |
| --- | --- |
| `kernel-only/` | `kernel.uImage`, DTB, effective kernel configuration, manifest and checksums |
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
| `scripts/build-x2000 --rootfs-only` | Buildroot toolchain/RootFS with signed app seeds | Kernel, Moonraker package, Fre3nderScreen cross-build, or OTA package | `rootfs-only/` |
| `scripts/build-x2000 --compose-only` | No component | Kernel and RootFS | Validated `full/` and signed OTA package |

Add `--develop` to a Kernel-only or RootFS-only development build.
`--rootfs-only --develop --fre3nderscreen-app` also uses the optional app path,
without building a Kernel. The app flag is invalid with `--kernel-only` or
`--compose-only`, and can be combined with `--f005-build` in full or RootFS scopes.
Add `--f005-build` to a full or RootFS-only build only when a new F005 candidate
must be built before RootFS assembly; it invokes the separate F005 builder,
which requires a clean project worktree. `--f005-build` requires `--develop`
and is invalid with `--kernel-only` and `--compose-only`.

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
| `--rootfs-only` | The same identity fields, `artifacts` hashes for `rootfs.squashfs` and `buildroot.config`, plus `ota_public_key_sha256`, `f005_firmware`, `system_apps`, and `factory_apps.fre3nderscreen.sha256` for the signed seeds embedded in the RootFS |
| Full build or `--compose-only` | The same identity fields and `artifacts` hashes for Kernel and RootFS, `ota_public_key_sha256`, `f005_firmware`, `system_apps`, `factory_apps.fre3nderscreen.sha256`, plus `component_provenance` for each input and `composition_provenance` for the final assembly |

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

RootFS assembly defaults to `FRE3NDER_F005_FIRMWARE_MODE=qualified`, including
Development builds without `--f005-build`. It verifies the exact size and SHA256
in `configs/x2000/f005-mcu-release.json`; that hardware-qualified manifest stays
unchanged. Only a successful `--develop --f005-build` selects `candidate` in the
orchestrator. The assembler rejects Candidate mode in Release builds.

Candidate validation uses the adjacent schema-1 `build-manifest.json`: regular
files without symlinks, Candidate classification, a boolean
`qualified_release_match`, exact binary size/SHA256, the current canonical Klipper
pin, the current project commit, and all recorded F005 recipe input hashes.
Stale Candidates require a new separately authorized build. The RootFS build
manifest records `f005_firmware` with classification, runtime version, size and
SHA256, plus Candidate upstream and prepared-source commits. Embedding a Candidate
does not qualify, promote, deploy, or flash it.

The immutable `f005-mcu-release.json` remains the hardware-qualified release
record. The generated `/usr/share/fre3nder/f005-runtime-target.json` describes
the embedded firmware and is used by the Runtime transition and MCU identity
probe. Qualified targets preserve the release model. Candidate targets carry
their actual runtime version, size and SHA256, with explicit Development and
unqualified metadata; UART, Stock identity, MCU constants and the stable
`mcu0_001_G32-mcu0_004_000` bootloader identity remain unchanged.
Without `--develop`, `scripts/deploy-f005` continues to use the qualified record
and rejects a different effective Runtime target. Its explicit `--develop`
mode validates the Candidate and exact remote Runtime target before a separately
authorized MCU update. A previous exact Qualified MCU is recognized as
`fre3nder-qualified`; S60 reports `f005-update-required` and never upgrades it
automatically. See [F005 switching](f005-mcu-switching.md#f005-build-and-transitional-deployment-interfaces).

The current Moonraker authorization and ownership contract is in
[Moonraker](moonraker.md). Dated source-refresh audits and their exact
comparison identities are in [build history](../research/docs/x2000-build-history.md#upstream-refresh-audits-from-the-20264-development-line).

### Kernel and Buildroot source identity

Active Kernel and Buildroot source values are defined in
`configs/x2000/sources.json` and read with `scripts/source-value`.
Kernel tag and release are derived from `kernel.kernel_version` and
`kernel.kernel_localversion`; `kernel.patch_series.baseline_ref` points to
`kernel.source.commit`. The ordered patch paths and SHA256 digests come from
`kernel.patch_series.patches`. Versioned patch filenames identify their
maintained baseline and are preserved along with historical qualification.
Buildroot's annotated release tag is derived from `buildroot.version` and
must dereference to `buildroot.commit`. This centralization changes no source
version, commit, patch content, or expected source tree.

The F3 kernel bootlogo uses the existing Ingenic `CONFIG_TRUE_COLOR_LOGO_FILE`
path and `scripts/pic2logo`. Patch 0005 replaces
`module_drivers/drivers/video/logo-ingenic/logo.png` with the prepared 480x272
RGB image; `kernel-fre3nder.defconfig` selects a black logo background. The
binary replacement is covered by the ordered patch checksum and result-tree
checks. The original portrait artwork, preparation command and asset hashes
are retained in [assets/bootlogo](../assets/bootlogo/README.md). FFmpeg is used
only when regenerating the patch-carried asset, not during normal builds.
The replacement has passed offline checks; no new kernel build or hardware
qualification has been performed for it.

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
