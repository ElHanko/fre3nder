# Public Fre3nder CLI

`/usr/bin/fre3nder` is the supported frontend. Direct calls to
`/usr/libexec/fre3nder/*` are internal. The command families below are supported
for their documented purpose, not as a stable general JSON protocol.
Implementation: [fre3nder](../../configs/x2000/rootfs-overlay/usr/bin/fre3nder).

## Output and exit behavior

| Path | Current behavior and limits |
| --- | --- |
| Top-level dispatch / malformed frontend syntax | Usage on stderr, exit `2` |
| Successful ordinary operation | Exit `0`; does not qualify the artifact or every service |
| Handled operation/Core-execution failure | Exit `1`; errors are operation-dependent |
| Delegated argument/validation errors | Can exit `1`, including Package-Core errors; do not assume every bad argument returns `2` |
| App operations | Delegate directly to Package-Core, which emits current JSON structures. App-service stdout can precede them. No exclusively-JSON stdout or complete schema-compatibility guarantee |
| OTA/backup operations | CLI formats internal JSON responses as human-readable text; no `--json` mode |
| Reboot | Can terminate the process/connection before any response is observed |

Package responses currently carry `api_version: 1`, `operation`, `ok`, then
operation-specific `package`, `apps`, `app`, `display`, `key`, `keys`, `name`,
`publisher` or `error`. These describe observable implementation; they are not a
new public JSON schema. `operation` can use Core names such as `display-list`.
Errors need not be solely on stderr because Package-Core emits error JSON.

A failed command is not a general rollback guarantee: service actions, data
changes, backups, payload writes or selector updates may already have occurred.
Do not automate retries of destructive operations from exit code alone.

## Permissions and arguments

Use the administrative/root context for package management, trust changes,
backup and OTA. Manager state is root-managed; services themselves run as
`fre3nder` with the documented groups. The CLI does not provide privilege
escalation. Pure package verification needs read access to the package and
trusted key; resolving user keys can also initialize manager directories.
There is no blanket promise that every inspection works unprivileged or is
side-effect free.

`<package.fre3app>` is a local signed package; `<package.ota>` is a local signed
platform package. `<app>` is the manifest name (lowercase letter, followed by
lowercase letters, digits, `_` or `-`, maximum 64 characters).
Publisher IDs use lowercase letters, digits, `_`, `.` and `-`, begin with a
letter and have the same maximum length. Pass paths as shell-quoted arguments
when necessary. A transaction ID is opaque: copy the returned value unchanged.

## Maintenance Web

The Maintenance Web feature is disabled by default. These commands use the
local [Management API v1](management.md); they do not require Lighttpd to be
running in order to work.

| Syntax | Purpose / effects |
| --- | --- |
| `fre3nder maintenance status` | Report the persistent Maintenance opt-in and current dedicated Maintenance listener status |
| `fre3nder maintenance enable` | Persist the explicit Maintenance opt-in and reconcile the dedicated port-8081 Maintenance listener |
| `fre3nder maintenance disable` | Remove the Maintenance opt-in, revoke browser admin sessions and stop the dedicated Maintenance listener; the selected frontend listener on port 80 is unaffected |
| `fre3nder maintenance unlock` | Generate a one-time six-digit browser pairing code; Maintenance must already be enabled |
| `fre3nder maintenance lock` | Revoke the pending pairing code and every browser admin session without disabling the read-only Maintenance Web |

The normal SSH administrative/root context may use all five commands. Pairing
codes live only in the running management daemon, expire after ten minutes and
are invalidated after five failed attempts or one successful redemption. The
generic `fre3nder` application user is not granted management-socket access.
Fre3nderScreen will later use the same API through an explicit narrow capability
rather than inheriting management authority for every app.

## App packages

All commands follow the output/exit rules above. Verification/trust and lifecycle
details are authoritative in [`.fre3app` v1](../fre3app.md).

| Syntax | Purpose / requirements | Effects and result |
| --- | --- | --- |
| `fre3nder app verify <package.fre3app>` | Check container, manifest, checksums, trusted publisher and signature | No app install/service action; current response describes identity/capabilities; trust resolution may initialize manager directories |
| `fre3nder app install <package.fre3app>` | Install a verified app not already installed; installer expects the `.fre3app` suffix | Extract payload, invoke signed `install`, start if autostart, cache package/state; first eligible web frontend may be selected; display selection is separate |
| `fre3nder app update <package.fre3app> [--allow-downgrade]` | Require installed app, same publisher/fingerprint and frontend capabilities; validate release ordering | Stop/update/restart as required, replace runtime and cache; keep selection; explicit flag permits lower serial but does not bypass other checks |
| `fre3nder app remove <app>` | Require installed app; invoke stop/uninstall as appropriate | Remove manager/runtime/recovery state; clear affected selection; service code can change app data, so do not infer data rollback |
| `fre3nder app list` | Inspect installed manager metadata | Current response contains `apps`; no service start |
| `fre3nder app status <app>` | Require installed app | Ordinary app invokes signed `status` as the app user; can initialize its data directory and emit service output. Display running-state uses selection/manager checks |

Same release serial is rejected; two development serial-zero packages use version
identity to reject the same package. A lower serial requires `--allow-downgrade`.
There is no repository search/download/update-discovery subcommand in this CLI.

## Display selection

These commands manage one installed display frontend; they do not select a web
frontend. See [apps](../apps.md#local-display-frontend-selection) and
[display](../display.md).

| Syntax | Requirements / purpose | Effects and result |
| --- | --- | --- |
| `fre3nder app display list` | Read installed display-capable packages and selection | Current response lists apps and active name; does not start them |
| `fre3nder app display status` | Read selected name | Returns current selection, not a complete hardware/readiness test |
| `fre3nder app display select <app>` | Require valid installed display frontend/API | Stop previous selected service when needed, persist choice, request manager start; selection success alone does not prove physical output |
| `fre3nder app display disable` | Administrative choice | Stop previous selection and clear it; Factory bootstrap must not replace a completed user choice |

## Publisher keys

Keys are Ed25519 public PEM files. Fingerprints are SHA-256 of DER
SubjectPublicKeyInfo. Publisher trust is not intrinsically tied to a repository
URL. Built-in keys cannot be replaced/removed by these commands; see
[trust model](../fre3app.md#trust-model).

| Syntax | Requirements / purpose | Effects and result |
| --- | --- | --- |
| `fre3nder app key list` | Enumerate valid built-in and user keys | Current response lists publisher, fingerprint and trust class; manager directories may be initialized |
| `fre3nder app key show <publisher>` | Resolve an existing valid key | Current response gives identity/fingerprint/path; it does not dump the PEM contents |
| `fre3nder app key add <publisher> <public-key.pem>` | New user publisher; regular non-symlink Ed25519 public key, at most 16 KiB | Persist trust below `/home/.fre3nder/app-keys/`; reject existing publisher or built-in replacement |
| `fre3nder app key remove <publisher>` | Existing user key, not required by any installed app | Remove that trust key; refuse built-in or in-use publisher |

Adding trust permits packages signed by that publisher; it does not sandbox
arbitrary service behavior beyond the existing unprivileged service contract.

## Backup

```text
fre3nder backup create
fre3nder backup create --home <usb|none> --sys <usb|home|none>
```

With no options the command discovers available targets and asks interactively.
For noninteractive use, both roles must be explicit. HOME can target USB or be
omitted; SYS can target USB, HOME or be omitted. Both `none` is rejected.
There is no arbitrary destination argument. The selected sources/targets must
satisfy the active-runtime/storage and capacity requirements in
[backup](../backup.md).

The command creates archives and verifies every selected archive before reporting
`BACKUP: COMPLETE`. Text results identify destinations, archive paths, sizes,
SHA-256 and verification. Creation failure or any verification failure returns
`1`; frontend option errors may return `2`. Interactive selection needs usable
input; do not rely on prompts in unattended scripts. Partial archives/effects may
remain on failure. No public standalone `offer`, `plan`, `archive`, `verify` or
restore command is implied.

## OTA

Read-only inspection needs package/key and, for preflight, runtime discovery
access. Backup and later phases require the administrative context and healthy
active persistence. Each phase validates its actual required state. Platform
write, activation and reboot remain separately authorized actions. Full ordering
and qualification limits are in [updates](../updates.md) and [OTA](../ota.md).

| Syntax | Purpose / prerequisites | Effects and output |
| --- | --- | --- |
| `fre3nder ota verify <package.ota>` | Validate exact container, signature, platform, trust and hashes | No slot write; text verification and package identity |
| `fre3nder ota preflight <package.ota>` | Verify plus active/inactive slot and SYS/HOME discovery, backup offer | No slot write; text runtime/target/persistence/backup eligibility; failed preflight reports failure |
| `fre3nder ota backup-plan <package.ota> (--home\|--no-home) (--sys <usb\|home>\|--no-sys)` | Validate explicit role selection against OTA policy | No archive or pending transaction; text plan |
| `fre3nder ota backup <package.ota> (--home\|--no-home) (--sys <usb\|home>\|--no-sys)` | Reverify/preflight, require available permitted backup destinations | Create/verify selected archives; create pending transaction, report its opaque ID; no system-slot write |
| `fre3nder ota confirm <package.ota> <transaction-id>` | Matching awaiting-confirmation transaction; recheck runtime/package/backups | Record confirmed state; text confirmation; no slot write |
| `fre3nder ota write <package.ota> <transaction-id>` | Confirmed matching transaction; validate actual inactive partition identity, mounts, sizes and backups | Write inactive RootFS/Kernel; text completion; does not activate or guarantee later readback |
| `fre3nder ota readback <package.ota> <transaction-id>` | Written matching transaction | Read/verify payload hashes and record readback state; no new payload write |
| `fre3nder ota prepare-activation <package.ota> <transaction-id>` | Readback-verified matching transaction; revalidate actual target bytes | Persist handoff and targeted SYS reset, write/verify selector; text activation result; does not reboot |
| `fre3nder ota reboot <transaction-id>` | Prepared matching activation | Validate prepared state and request reboot; response can be unobservable |

Always specify HOME and SYS choices for `backup-plan`/`backup`. A standalone
`fre3nder backup create` result does not create an OTA transaction. Selection
must satisfy OTA policy; standalone backup's `none` rule is not an OTA waiver.
Reuse of a stale ID, different package/runtime or wrong state fails rather than
advancing. Do not generate IDs or manipulate internal state to skip confirmation.

These commands use text output and the common exit rules. Handled OTA failures
return `1`; extra delegated arguments can also be reported as operation errors.
The public command family has no `postboot` entry or promise of automatic
failed-boot rollback. F005 remains outside platform OTA.
