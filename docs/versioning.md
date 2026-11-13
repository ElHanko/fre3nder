# Public release versioning

Fre3nder uses `YEAR.RELEASE[.PATCH][.STAGE]`, not SemVer. `YEAR` is a
four-digit calendar-year line; `RELEASE` is a positive numeric public counter
that restarts at 1 each year. `PATCH` is an optional positive numeric
maintenance-release counter. An omitted patch is represented as patch `0` in
build metadata; `.0` is not a valid version suffix, so `2026.4` remains the
canonical base release and `2026.4.1` is its first maintenance release. Numeric
components omit leading zeroes.

The optional stage is exactly `a` (alpha), `b` (beta), or `rc` (release
candidate); no stage suffix means final. A stage may qualify either the base
release (`2026.5.a`) or a maintenance release (`2026.4.1.rc`). Numbered stage
suffixes such as `a1` or `rc2` are not part of the scheme.

The repository-root [`VERSION`](../VERSION) is the canonical project version
for a checkout and its artifacts. A release tag uses exactly that string,
without a `v` prefix. Changing `VERSION` alone creates neither a tag nor a
GitHub release. The checkout's staged development version can be ahead of
its latest published final release; use [CHANGELOG](../CHANGELOG.md) and tags
to identify released content.

Build manifests record `version`, numeric `release_year`, `release_number`,
and `release_patch`, normalized `release_stage` (`alpha`, `beta`, `rc`, or
`final`), and `release_scope`. Built RootFS images expose the project version
at `/usr/share/fre3nder/VERSION`. Order versions by numeric year, release, and
patch, then by stage alpha, beta, release candidate, and final; do not compare
the strings lexicographically.

A final release means its named scope is complete. It does not imply that the
whole roadmap is complete or that a build, fixture test, or release tag
qualifies every hardware path. The first final `2026.1` was the printable,
networked open-host scope; `2026.2` was the usable-system scope; `2026.3` was
the independent-kernel-stack scope. Exact released changes, dates, source
identities, and qualification limits belong in [CHANGELOG](../CHANGELOG.md).
The current productive Kernel, Buildroot, and application source identities
belong in [`configs/x2000/sources.json`](../configs/x2000/sources.json).

An untagged build can retain the same `VERSION` as an earlier tag while using
a later project commit. Distinguish artifacts using exact provenance and hashes;
a shared version string does not make them the same release or qualification.
Historical examples are preserved in
[F005 hardware evidence](../research/docs/f005-hardware-validation.md).

Installable applications are versioned and signed as `.fre3app` packages
independently of the platform build commit. The exact installed package is
cached under `/home/.fre3nder/packages/` for offline recovery; see the
[application contract](fre3app.md).

## Operating-system identity

Implemented and tested in `040b313`, then confirmed on the reference Ender-3
V3 KE with a newly built and deployed RootFS. Hardware validation is complete
for the Development build identified below.

The RootFS post-build hook writes `NAME=FRE3NDER`, `ID=fre3nder`, and
`PRETTY_NAME="FRE3NDER <version>"` to `/usr/lib/os-release`;
`/etc/os-release` is a relative symlink to it. Both `VERSION` and `VERSION_ID`
use the canonical project version already staged at `/usr/share/fre3nder/VERSION`.
The hook regenerates these paths and the versioned `/etc/issue` banner on every
assembly, replacing stale Buildroot identity in reused target directories.
`/etc/issue.net` points to the same banner. Dropbear does not enable a separate
pre-authentication banner.

Interactive login shells use `/etc/profile.d/fre3nder.sh` to display the OS
`NAME` with BusyBox's standard username and privilege escapes:
`root@FRE3NDER# ` or `<user>@FRE3NDER$ `. The actual hostname remains `fre3nder`;
network configuration, SSH aliases and deployment host arguments are unchanged.
The runtime `fre3nder` service account remains locked with `/bin/false`.

Buildroot's own version and commit remain in `configs/x2000/sources.json` and
build manifests as technical build provenance. Linux keeps its independent
kernel version and `-fre3nder` suffix; component and app versions remain
independent. The Management API, Maintenance UI and OTA continue to consume
`/usr/share/fre3nder/VERSION` for the OS version, without API changes.

The operator reports a successful full Development build from
`2a47ebffb65d6b8cdc0a3445561f7b6c9350b0c4`: Kernel, toolchain, RootFS and OTA
`2026.5.a` passed in `00:06:37`. Deployment through
`deploy-x2000 --develop --write`, Kernel/RootFS readback, A/B activation and
restart passed. The active RootFS after deployment was slot A
(`/dev/mmcblk0p7`). The following results were confirmed on the physical printer:

| Interface | Confirmed result |
| --- | --- |
| `/etc/os-release` | `NAME=FRE3NDER`, `ID=fre3nder`, `VERSION="2026.5.a"`, `VERSION_ID="2026.5.a"`, `PRETTY_NAME="FRE3NDER 2026.5.a"` |
| `/etc/issue` | `Welcome to FRE3NDER 2026.5.a` |
| Interactive SSH prompt | `root@FRE3NDER#` |
| `hostname` | `fre3nder` |
| `uname -r` | `6.6.161-fre3nder` |

The OS name and shell prompt therefore use `FRE3NDER`, while the network
hostname deliberately remains `fre3nder`. Existing SSH access continued to
work after deployment.

## 2026.4 managed-platform line

`2026.4`, scope ID `managed-platform`, titled **Managed Platform**, builds on
the usable-system and independent-kernel-stack releases by adding the managed
platform lifecycles for signed updates, applications, display frontends,
backup/recovery, and separately controlled host and MCU firmware.

Exact released changes, source identities, qualification limits, and the
final release commit belong in [`CHANGELOG.md`](../CHANGELOG.md).

## Current development line

Use the root [`VERSION`](../VERSION) for the version of this checkout.
