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

`release_serial = 0` is reserved for development packages outside the
published release sequence. Development serial 0 has no ordering: updating
between different `version` values is allowed, while the same version is
rejected. Published releases use monotonically increasing `release_serial`
values starting at 1. Moving from development to a release is a normal
upgrade; moving from a release to development requires `--allow-downgrade`.
An update must retain the installed publisher identity and key fingerprint;
changing publisher ownership is not an ordinary update operation.

An optional section declares a static web frontend:

```toml
[web]
frontend = true
```

Without `[web]`, `web_frontend` is false. If supplied, `frontend` must be a
Boolean. A frontend package must include a signed, nonempty
`payload/index.html`. The capability is stored in `metadata.json`, returned by
verify/list/status, and cannot change during a normal package update.

An optional section declares a local display frontend:

```toml
[display]
frontend = true
api = 1
```

Without `[display]`, `display_frontend` is false and `display_api` is null. A
display frontend must declare `api = 1` and set `runtime.autostart = false`. The
capability and API version are stored in `metadata.json`, returned by
verify/list/status, and cannot change during a normal package update. Installing
a display frontend never selects it automatically.

## Display Frontend API v1

Exactly one installed display frontend may be selected by the root-controlled
platform state. The selected application is started by the platform display
manager, not by the generic application autostart path. The manager retains
privileged ownership of hardware discovery and permission setup and invokes the
selected package service as the unprivileged `fre3nder` user.

For `service start`, a selected display frontend receives these additional
environment variables:

```text
FRE3NDER_DISPLAY_API=1
FRE3NDER_DISPLAY_FRAMEBUFFER=<framebuffer device>
FRE3NDER_DISPLAY_INPUT=<touch input path>
FRE3NDER_DISPLAY_BACKLIGHT_POWER=<backlight power path or empty>
FRE3NDER_DISPLAY_BEEPER=<beeper input path or empty>
```

`FRE3NDER_DISPLAY_FRAMEBUFFER` and `FRE3NDER_DISPLAY_INPUT` are required for
display-managed `start`, `stop`, and `status` actions. Backlight and beeper are
optional and are represented by empty values when unavailable. Applications
must consume the supplied paths and must not depend on platform-specific input
names, `eventX` numbering, or privileged device setup.

`S64fre3nder-display` implements this platform contract. Ordinary `.fre3app`
service actions run without supplementary groups. For the selected display
frontend only, the package core supplies the `video`, `input`, and `beep`
supplementary groups while the display manager retains root ownership of device
discovery and permission setup.

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

`status` returns zero while the application is healthy or running and non-zero otherwise. A static web frontend can report a valid payload without starting a daemon. Lifecycle operations must be idempotent where practical. Package service code must not require root privileges; privileged platform work belongs in the generic Fre3nder core.

Signed files under `payload/bin/` are extracted with mode 0755 for
native app executables. Other payload files are extracted with mode 0644.

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

The root-managed active web frontend is recorded separately at
`/home/.fre3nder/frontend/active` as `<app>\n`. The first installed frontend
is selected; an existing valid selection survives other installs and updates.
Removing the selected frontend clears the file. Package services cannot write
this state.

The independently selected local display frontend is recorded at
`/home/.fre3nder/display/active` as `<app>\n`. Display selection is always
explicit: installing another display frontend does not change the current
selection. Updating a selected package preserves the selection. Removing the
selected package or explicitly disabling the display clears it. Boot recovery
never invents a display selection. Package services cannot write this state.

Unprivileged persistent application data is exposed separately as:

```text
/home/fre3nder/.local/share/<app>/
```

The exact installed `.fre3app` is cached in root-controlled persistent state under `/home/.fre3nder` so recovery does not depend on a repository, network access, or the original USB device. Application services running as `fre3nder` cannot modify package trust or installed-package metadata. This is required for manual/offline installations to remain recoverable after a SYS/OTA reconstruction.

## Recovery

During boot the package recovery step verifies each cached package again, reconstructs missing `/opt` runtime state, then calls `service restore`.

`S65fre3nder-app-runtime` subsequently starts packages marked for autostart and asks running packages to stop during platform shutdown. Static web frontends such as Fluidd and all display frontends set `autostart = false`; their platform managers own activation instead. S62 remains the platform HTTP daemon. S58 recovery does not restart S62. Interactive install, update, and remove of the selected web frontend ask the privileged package core to refresh S62 after the package transaction; a web refresh failure is reported without rolling back the package. Display selection is persistent package-manager state and is restored without being changed or invented.

## Repository layer

Repository management is not part of the core package format. The optional `fre3nder-app-update.fre3app` package will provide:

- source configuration;
- signed package-index refresh;
- search and version resolution;
- package downloads;
- update discovery;
- optional package-update reporting to Moonraker.

The repository layer ultimately hands the downloaded `.fre3app` to the same package core used for USB/SSH/local installation.

The official source is expected to be `ElHanko/fre3nder-apps`, but Fre3nder does not require it.
