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
a later project commit. The 2026-08-30 RootFS-only and full Kernel/RootFS
qualifications were examples: both embedded `2026.1` but were separate
current-main artifacts, not additional public releases. Their exact commits,
hashes, and results remain in
[F005 hardware validation](f005-hardware-validation.md#2026-08-30-current-main-rootfs-installation-qualification).
For the earlier functional milestone and reference-system bring-up, see
[roadmap history](../research/docs/roadmap-history.md) and
[X2000 A/B bring-up](../research/docs/x2000-ab-bringup-plan.md).

Installable app definitions use the exact build-source commit rather than a
version-derived tag. A clean RootFS embeds `project_commit` in
`/usr/share/fre3nder/APP_REF`; a dirty build writes `unpublished` and needs a
valid cached handler or explicit local source. There is no floating-branch
fallback. The [app-definition source rule](apps.md#app-definition-source-revision)
is authoritative for that interface.

## Open development-line scope assignment

At this documentation audit, [`VERSION`](../VERSION) contains `2026.4.a`,
while [`build/x2000/entrypoint.sh`](../build/x2000/entrypoint.sh) still sets
`release_scope=independent-kernel-stack`, the `2026.3` scope. No `2026.4`
release scope is established by the changelog or roadmap. This discrepancy
needs a release decision before a `2026.4` artifact is presented as a public
release; documentation changes alone do not change emitted build metadata.
