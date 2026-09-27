# Fre3nder application packages (`.fre3app`) — format v1

## Scope

`.fre3app` is Fre3nder's signed application package format. Package transport is deliberately outside the trust model: the same package may be installed from USB, SSH/SCP, a local file, or an optional package repository.

`fre3nder` provides the trusted package core. Repository discovery and automatic updates are optional and belong to the separately packaged `fre3nder-app-update` application.

## Trust model

Fre3nder trusts publishers, not URLs.

- The official `fre3nder-apps` publisher public key is shipped by Fre3nder.
- Users may add additional Ed25519 publisher keys.
- A manually installed package is accepted when its declared publisher is locally trusted and its signature verifies.
- A repository may additionally constrain packages to an expected publisher, but publisher keys are not intrinsically bound to repository URLs.

Built-in keys live under:

```text
/usr/share/fre3nder/app-keys/<publisher>.pem
```

User-added trust keys live persistently in root-controlled platform state under:

```text
/home/.fre3nder/app-keys/<publisher>.pem
```

Fingerprints are SHA-256 over the DER SubjectPublicKeyInfo representation of the Ed25519 public key.

## Container

Format v1 is a ZIP archive with the `.fre3app` suffix.

Required top-level members:

```text
manifest.toml
service
SHA256SUMS
SHA256SUMS.sig
```

Additional signed files may be included, normally under `payload/` and `licenses/`.

The archive must not contain absolute paths, `.`, `..`, empty path components, backslashes, control characters, symlinks, duplicate/colliding members, encrypted members, or unsigned payload files.

## Signature

`SHA256SUMS` contains every regular file except `SHA256SUMS` and `SHA256SUMS.sig`, sorted by archive path:

```text
<sha256>  manifest.toml
<sha256>  payload/...
<sha256>  service
```

`SHA256SUMS.sig` is a raw Ed25519 signature over the exact `SHA256SUMS` bytes.

The package verifier reads only the untrusted publisher identity/fingerprint from `manifest.toml` to select a pre-existing local trust anchor. No other manifest data is trusted until the signature and all file hashes have verified.

## Manifest

Minimum v1 manifest:

```toml
format = 1

[app]
name = "example"
version = "1.0.0-fre3nder.1"
release_serial = 1

[publisher]
id = "fre3nder-official"
key_fingerprint = "<64 lowercase hex characters>"

[target]
platform = "fre3nder-x2000"
arch = "mipsel"

[runtime]
service = "service"
autostart = true

[signature]
algorithm = "Ed25519"
file = "SHA256SUMS.sig"
signed_file = "SHA256SUMS"
```

`release_serial` is a publisher-controlled monotonically increasing integer used for deterministic upgrade/downgrade decisions independently from the display version string. An update must retain the installed publisher identity and key fingerprint; changing publisher ownership is not an ordinary update operation.

## Service contract

`service` is a signed executable POSIX-compatible program. The package core invokes it as the unprivileged `fre3nder` user and supplies:

```text
FRE3NDER_APP_NAME
FRE3NDER_APP_RUNTIME_DIR
FRE3NDER_APP_STATE_DIR
FRE3NDER_APP_DATA_DIR
FRE3NDER_HOME_DIR
```

Format v1 service actions are:

```text
install
update
restore
start
stop
status
uninstall
```

`status` returns zero while the application is running and non-zero otherwise. Lifecycle operations must be idempotent where practical. Package service code must not require root privileges; privileged platform work belongs in the generic Fre3nder core.

## Runtime and persistence

Reconstructible runtime:

```text
/opt/fre3nder/apps-v2/<app>/
```

Root-controlled persistent package-manager state:

```text
/home/.fre3nder/packages/<app>/
├── installed
├── autostart          # when enabled
├── metadata.json
└── package.fre3app    # exact verified package used for installation
```

Unprivileged persistent application data is exposed separately as:

```text
/home/fre3nder/.local/share/<app>/
```

The exact installed `.fre3app` is cached in root-controlled persistent state under `/home/.fre3nder` so recovery does not depend on a repository, network access, or the original USB device. Application services running as `fre3nder` cannot modify package trust or installed-package metadata. This is required for manual/offline installations to remain recoverable after a SYS/OTA reconstruction.

## Recovery

During boot the package recovery step verifies each cached package again, reconstructs missing `/opt` runtime state, then calls `service restore`.

`S65fre3nder-app-runtime` subsequently starts packages marked for autostart and asks running packages to stop during platform shutdown.

The existing legacy app loader remains in place until Fluidd has migrated to `.fre3app`. New package runtime paths intentionally use `apps-v2` during that transition to avoid collisions.

## Repository layer

Repository management is not part of the core package format. The optional `fre3nder-app-update.fre3app` package will provide:

- source configuration;
- signed package-index refresh;
- search and version resolution;
- package downloads;
- update discovery;
- Moonraker/Fluidd integration.

The repository layer ultimately hands the downloaded `.fre3app` to the same package core used for USB/SSH/local installation.

The official source is expected to be `ElHanko/fre3nder-apps`, but Fre3nder does not require it.
