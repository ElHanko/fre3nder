# Public release versioning

Fre3nder uses `YEAR.RELEASE[.STAGE]`, not SemVer. `YEAR` is a four-digit
calendar-year line; `RELEASE` is a positive numeric public counter that
restarts at 1 each year. Both omit leading zeroes. The optional stage is
exactly `a` (alpha), `b` (beta), or `rc` (release candidate); no suffix means
final. Extra components such as `a1`, `rc2`, or patch-level versions are not
part of the scheme.

The repository-root [`VERSION`](../VERSION) is the canonical project version
for a checkout and its artifacts. A release tag uses exactly that string,
without a `v` prefix. Changing `VERSION` alone creates neither a tag nor a
GitHub release. The checkout's staged development version can be ahead of
its latest published final release; use [CHANGELOG](../CHANGELOG.md) and tags
to identify released content.

Build manifests record `version`, numeric `release_year` and `release_number`,
normalized `release_stage` (`alpha`, `beta`, `rc`, or `final`), and
`release_scope`. Built RootFS images expose the project version at
`/usr/share/fre3nder/VERSION`. Order versions by numeric year/release and by
stage alpha, beta, release candidate, then final; do not compare the strings
lexicographically.

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

## 2026.4 managed-platform line

`2026.4`, scope ID `managed-platform`, titled **Managed Platform**, builds on
the usable-system and independent-kernel-stack releases by adding the managed
platform lifecycles for signed updates, applications, display frontends,
backup/recovery, and separately controlled host and MCU firmware.

The current development line uses `2026.5.a`. Exact released changes, source
identities, qualification limits, and the final release commit belong in
[`CHANGELOG.md`](../CHANGELOG.md).
