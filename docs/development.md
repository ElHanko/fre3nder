# Developing Fre3nder

Work from a repository checkout. Productive inputs are in `build/`,
`configs/`, `patches/`, `scripts/`, `apps/`, and `tests/`; hardware analysis,
bring-up, rejected approaches, and dated qualification records belong in
[`research/`](../research/). Productive builds and runtime must have no
functional dependency on `research/`. The exact pinned dependencies are in
[`configs/x2000/sources.json`](../configs/x2000/sources.json).

## Typical iteration

1. Inspect the current implementation and its relevant contract before
   changing it. Use the smallest change that addresses the observed behavior.
   Keep device-specific paths, identifiers, and credentials out of tracked
   files; the ignored `docs/local-device.md` is only for non-secret local
   details. Follow [`AGENTS.md`](../AGENTS.md) for printer and build gates.
2. Edit the productive source or configuration and run focused static or
   fixture checks. For example, use `sh -n` for a changed shell script and
   select the matching fixture under `tests/`: `tests/test-x2000-storage`,
   `tests/test-x2000-backup`, `tests/test-deploy-x2000`,
   `tests/test-x2000-compose-only`, `tests/test-fre3nder-apps`, or the
   relevant service test. These fixtures do not establish hardware
   qualification. Check a test's scope before running it.
3. When the change needs a target artifact, select the smallest build scope
   described in [the build guide](build.md): `--kernel-only --develop`,
   `--rootfs-only --develop`, or a complete `--develop` build. A development
   artifact carries the current X2000 input fingerprint. A component-only
   build does not rebuild the other component; `--compose-only` validates and
   combines existing components without building either one. Under the
   repository's build rule, an automated agent must obtain explicit
   authorization for the specific build before running it.
4. Inspect the artifact manifest, effective configuration, hashes, and any
   affected access path. Record whether the result is source-implemented,
   fixture-tested, built, or actually qualified on the reference device;
   these are distinct claims. A build or fixture pass does not authorize
   deployment. Use the read-only [deployment preflight](installation.md) before
   proposing a concrete printer operation.
5. For normal development on a healthy mounted Fre3nder runtime, verify
   `/run/fre3nder-root/status` reports `active` before editing runtime files
   or restarting ordinary services. Reproduce any intended product change in
   repository inputs and validate it there. On-device state is evidence, not
   the release source of truth. Platform, boot, partition, and MCU writes
   remain separate operator-controlled operations.
6. Review the diff and relevant qualification evidence. Preserve exact
   provenance for imported material and scope device observations to the
   investigated reference system. Release numbering and tags follow
   [versioning](versioning.md); user-visible release changes belong in the
   [changelog](../CHANGELOG.md).

For a dirty development RootFS with `APP_REF=unpublished`, app definitions need
an explicit local source. The helper
[scripts/install-development-app](../scripts/install-development-app)
transfers only a checked app definition to the printer; see the
[app guide](apps.md#app-definition-source-revision) for its normal and `--apply`
forms. The Moonraker, GuppyScreen, F005, storage, and OTA documents describe
their own specific boundaries. Historical X2000 and F005 investigations remain
indexed from [`research/README.md`](../research/README.md).
