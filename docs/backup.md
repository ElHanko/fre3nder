# Backing up Fre3nder

## Create and check a backup

Maintenance Web has an independent **Backups** area. Unlock the browser with
its existing pairing flow, choose HOME or SYS, and select a destination from
the API offer. Web defaults to `download`; USB is optional, and HOME storage
is available for SYS. After creation, use the download link to save the verified
archive. Downloads can be repeated. **Discard temporary backup** removes the
printer's temporary copy, as does the next system start. Browser closure and
an interrupted download do not remove the archive.

Backup archives can contain private data and credentials. Maintenance downloads
use unencrypted HTTP on port 8081: pairing and CSRF checks do not encrypt the
archive in transit. Use a trusted LAN or an operator-provided protected transport
for access to Maintenance.

Fre3nderScreen uses the same [Management API](api/management.md#standalone-backup-endpoints),
with USB preferred when available and HOME optional for SYS. It offers no
browser download destination. The CLI retains its existing permanent choices.

Run the public CLI on an active Fre3nder runtime with mounted persistence.
For HOME, connect writable runtime USB storage formatted as exFAT, ext4, or
NTFS3; VFAT is usable for other USB purposes but cannot hold a HOME backup.
SYS may instead be stored in preserved `/home`. Ensure the selected target has
enough free space for an uncompressed archive, and that HOME also has space
for its temporary staging copy.

For interactive selection:

```sh
fre3nder backup create
```

For a script, select both roles explicitly. For example:

```sh
fre3nder backup create --home usb --sys home
```

Other valid values are `--home usb|none` and `--sys usb|home|none`; both
`none` is rejected. The CLI offers only currently available targets and
creates HOME before SYS. On success it reports each archive path, size, and
SHA-256 and ends with `BACKUP: COMPLETE`. That success includes a reread and
verification of every published archive. Retain the reported metadata with
the archive, and copy a valuable backup to independent storage. For a later
integrity check, recompute `sha256sum <archive>` and compare it with the
SHA-256 recorded at creation time. A failed command or missing completion
line is not a verified backup.

HOME archives live below `/run/fre3nder/usb/Fre3nderBackup/`; SYS archives
live there or below `/home/Fre3nderBackup/`, according to the selected
target. HOME is persistent across an ordinary platform update, but a separate
HOME backup is useful for storage failure or recovery. SYS contains the active
system OverlayFS `upper/` tree. It is intended for inspection and manual
recovery of customizations; the project does not define an automatic
full-OverlayFS restore command. To inspect a saved archive, list its members
with `tar -tf backup.tar`, substituting the reported archive path, before
extracting selected files to a separate working directory. Do not unpack a
SYS archive directly over a running root.

The current CLI exposes creation only. Its internal `verify` operation is a
platform API, not a public `fre3nder backup verify` command. OTA may reverify
selected archives as part of its transaction. The logical HOME/SYS roles and
their current backing are defined in [storage layout](storage-layout.md);
the OTA use of backups is in [OTA architecture](ota.md).

This CLI backs up only the active HOME and SYS roles. Its archives are not a
complete Point-of-Return set: the operation does not by itself capture or
validate raw Stock partitions, factory/identity data, eMMC boot configuration,
or original recovery firmware.

The separate requirements and limits for return to Stock are in
[recovery](recovery.md) and the [Point-of-Return evidence](../research/docs/recovery-validation-plan.md).

The following sections define the backup implementation contract for platform
consumers and developers.

## Scope

Backup is a standalone Fre3nder platform capability.

It is not part of OTA, although OTA consumes it before platform writes.

The dependency direction is:

```text
runtime USB / storage
        |
        v
     backup
        |
        +--> fre3nder CLI
        +--> OTA
        +--> Management API --> Maintenance Web / Fre3nderScreen
```

The backup layer owns backup availability, target policy, selection
validation, archive creation, and archive verification.

It does not know about OTA packages, A/B slots, boot selectors, OTA
transactions, activation, reboot, or known-good state.

## Design principles

Backup operates on logical Fre3nder storage roles rather than physical
partition numbers.

The initial roles are:

```text
HOME
SYS
```

Backup reads only from the active mounted Fre3nder runtime.

It does not mount or inspect persistence block devices directly.

Frontends must not implement backup policy independently. They consume the
backup core and may present its capabilities differently.

The public CLI intentionally exposes a much smaller interface than the
internal backup-core API.

## Storage dependency

Backup depends on the runtime storage layer for removable-storage state.

Runtime USB determines whether a removable filesystem is present, writable,
and suitable as a backup target.

Backup consumes that state and decides which logical backup targets are
available.

The storage layer does not know about backup archives or backup roles.

The dependency is therefore one-way:

```text
runtime USB / storage
        |
        v
      backup
```

Backup must not reimplement device discovery, mounting, filesystem detection,
or removable-storage lifecycle management.

## Logical backup roles

### HOME

The active HOME backup source is:

```text
/home
```

A HOME backup may be downloaded through Management or delivered to
backup-capable runtime USB storage.

The backup directory is:

```text
/run/fre3nder/usb/Fre3nderBackup/
```

`HOME` itself remains persistent across a normal Fre3nder platform update.

A HOME backup is an additional recovery measure and does not replace that
persistence contract.

Both `/home/.tmp/` and `/home/Fre3nderBackup/` are excluded when HOME is archived,
so temporary files and permanent SYS backups cannot recursively enter the archive.

### SYS

The active SYS backup source is:

```text
/run/fre3nder-root/system/upper
```

Only the active OverlayFS `upper/` tree is backup content.

`<SYS_SOURCE>/ota/packages/` is excluded using the existing archive exclusion
mechanism. It contains reconstructible staged OTA packages and Maintenance
proxy buffers, not system customizations. Other SYS content remains included.
HOME excludes `.tmp/` and `Fre3nderBackup/`.

OverlayFS `work/` state, reset markers, and other runtime implementation state
are not included.

SYS may be downloaded through Management, or delivered to runtime USB or
preserved HOME:

```text
/run/fre3nder/usb/Fre3nderBackup/
/home/Fre3nderBackup/
```

A SYS archive is primarily intended for inspection or manual recovery of
previous customizations.

It is not defined as a complete automatically restorable OverlayFS image.

## Runtime USB requirements

The runtime USB layer recognizes:

```text
vfat
exfat
ext4
ntfs3
```

A mounted filesystem must be writable before backup may use it.

VFAT is not a backup-capable target because FAT32 cannot store a single file
larger than 4 GiB.

Backup to runtime USB therefore requires:

```text
exfat
ext4
ntfs3
```

Runtime USB may still use VFAT for other purposes such as provisioning or
ordinary file access.

Backup capability is therefore distinct from general runtime USB
availability.

The selected USB volume is revalidated immediately before backup execution.

If the USB source or filesystem identity changed after selection or preflight,
backup execution fails rather than writing to an unexpected volume.

## Backup targets

Backup targets are derived from the logical backup role and currently
available storage.

| Role | Destinations |
|---|---|
| HOME | `download`, `usb` |
| SYS | `download`, `usb`, `home` |

USB appears only when runtime storage reports a writable backup-capable volume.
No arbitrary destination path is part of the interface. Core sets no frontend
preference. Web chooses `download` initially; Screen prefers USB; CLI retains
USB for HOME and USB/HOME for SYS.

`download` retains the verified archive in a private job directory below
`/home/.tmp/backup/`. Management maps a random server-generated job ID to that
archive. It does not expose the staging tree as static web content.

Permanent destinations remain:

```text
HOME or SYS -> USB: /run/fre3nder/usb/Fre3nderBackup/
SYS -> HOME:        /home/Fre3nderBackup/
```

## Archive format

The initial backup archive format is uncompressed POSIX tar using the PAX
format.

Every target uses one pipeline:

1. Validate the explicit selection and current USB identity, if selected.
2. Estimate the uncompressed TAR size using the same source traversal. Check
   staging and destination capacity, with 5% estimation headroom and a 32 MiB
   operating reserve. Reserve both copies when copying on the same filesystem.
3. Create the PAX-TAR using `create_backup_archive()` in a private job directory
   below `/home/.tmp/backup/`; flush and fsync the complete archive.
4. Reread it with `verify_backup_archive()` before delivery.
5. For `download`, retain the staged archive. For USB, copy to a hidden `.part`
   file, flush/fsync, verify, recheck the selected volume, then rename to its
   final name with Linux `renameat2(RENAME_NOREPLACE)`. A concurrent existing
   name causes failure and is never replaced. A pinned directory descriptor keeps writes and cleanup on the
   selected filesystem if USB changes. For HOME on the same filesystem, rename
   the verified staged archive atomically with the same no-replace rule;
   otherwise use the verified-copy path. Unsupported no-replace publication
   fails closed, without an overwriting fallback.
6. Verify each final permanent file, fsync its directory and recheck USB identity.
7. Remove temporary job data once no longer needed. Failed copies and failed
   final verification never produce a successful result.

The staging directory is root-controlled, mode `0700`, and created when needed.
The existing boot cleanup of `/home/.tmp/` remains responsible for leftovers;
there is no new cleanup service. Space checks do not reserve blocks against
unrelated writers. ENOSPC or other write errors fail the operation and clean its
temporary files. A source which changes during traversal can fail creation;
this is a filesystem archive, not a point-in-time snapshot.

Traversal does not cross filesystem boundaries and preserves symbolic links
without following them. HOME excludes `.tmp/` and `Fre3nderBackup/`; SYS excludes
`ota/packages/`.

A successful archive result contains at least:

```text
archive path
size
SHA-256
```

Archive creation and verification remain separate primitives. The complete
`execute` pipeline always verifies staging and final delivery; callers can
add later integrity checks using `verify`.

## Selection policy

Core accepts `download` or `usb` for HOME and `download`, `usb`, or `home`
for SYS. Each role may also be explicitly declined. The public CLI and OTA
retain their narrower permanent choices: HOME `usb|none`, SYS `usb|home|none`.

A selection must be explicit.

There is no implicit default that silently creates or skips a backup.

Selecting no backup at all is not a useful standalone backup operation and is
rejected by the public CLI.

OTA additionally rejects temporary `download` targets on the server. It does
not inherit new defaults from the expanded standalone offer.

## Backup execution

Backup execution works only with already active Fre3nder runtime mounts.

It does not mount source filesystems itself and does not access persistence
partitions directly.

When both roles are selected, HOME is processed before SYS.

This is important when SYS is backed up to HOME because the resulting SYS
archive must not become part of a HOME archive created during the same backup
operation.

A successful execution result records the actual result for every role,
including whether it was selected and, when selected:

```text
target
archive path
size
SHA-256
```

The result describes what was actually created.

It is not merely a restatement of the requested selection.

## Verification

Backup verification validates an existing archive against its expected:

```text
size
SHA-256
```

Verification rereads the final published archive.

A caller must not treat archive creation alone as proof that the resulting
backup is valid.

Different consumers may integrate verification differently.

For the public Fre3nder CLI, verification is mandatory and is part of the
single user-visible `create` operation.

OTA may perform verification again later when validating a stored OTA
transaction before subsequent update stages.

## Public CLI

The public user interface is intentionally small.

The only public backup command is:

```text
fre3nder backup create
```

The public CLI does not expose the internal backup-core operations separately.

Commands such as the following are intentionally not user-facing:

```text
offer
plan
execute
archive
verify
```

### Interactive create

With no additional arguments:

```text
fre3nder backup create
```

the CLI discovers the currently available targets and asks the user which
backups should be created.

Only currently valid destinations are offered.

Conceptually:

```text
Fre3nder backup

HOME backup [usb/none]:
SYS backup [usb/home/none]:
```

The actual choices depend on current storage availability.

For example, if no backup-capable USB volume is available, USB must not be
offered as a destination.

### Non-interactive create

For scripts and other non-interactive use, both roles must be specified
explicitly:

```text
fre3nder backup create --home usb --sys home
fre3nder backup create --home usb --sys usb
fre3nder backup create --home none --sys home
fre3nder backup create --home none --sys usb
```

Valid HOME values are:

```text
usb
none
```

Valid SYS values are:

```text
usb
home
none
```

When command-line selection is used, both `--home` and `--sys` are required.

This avoids a partially implicit backup selection.

The following is rejected because no backup would be created:

```text
fre3nder backup create --home none --sys none
```

### User-visible create contract

From the user's perspective, `create` is one complete operation:

```text
discover available targets
        |
        v
select backup roles
        |
        v
execute selected backups
        |
        v
verify every created archive
        |
        v
BACKUP: COMPLETE
```

Every archive created through the public CLI must be verified before success
is reported.

If verification of any selected archive fails, the command fails.

It must not report:

```text
BACKUP: COMPLETE
```

unless every selected backup completed and verified successfully.

## Internal backup-core API

The implementation lives at:

```text
/usr/libexec/fre3nder/backup-core
```

Its internal API version is currently `1`.

The internal API is intended for trusted Fre3nder platform components and
frontends.

It is deliberately more detailed than the public user CLI.

### `offer`

Returns the currently available backup targets for HOME and SYS.

It consumes runtime storage state but performs no backup.

This operation allows a frontend to present only valid choices.

### `plan`

Validates an explicit backup selection against the currently available
targets.

It is read-only.

It does not create an archive.

This is useful for higher-level workflows that need to validate a selection
before later execution.

### `execute`

Executes a complete validated backup selection.

HOME is processed before SYS.

The operation returns the actual archive path, size, and SHA-256 for each
selected role.

Execution verifies staging and delivery before `backup_result.complete` is
true. Selected role results include `verified: true`, `target`, `archive`,
`size`, and `sha256`. The CLI also retains its explicit final verification.
The internal selection syntax accepts `--home download|usb`; the existing
bare `--home` still means USB. SYS accepts `--sys download|usb|home`.
`--no-home` and `--no-sys` remain explicit declines.

### `archive`

Low-level primitive that creates one archive for one already-resolved backup
role and destination.

This operation is an implementation primitive.

It is not part of the public user CLI.

Higher-level callers should normally use `execute` rather than invoking the
archive primitive directly.

### `verify`

Verifies an existing backup archive against its expected size and SHA-256.

This operation is used by the public CLI and by higher-level platform
workflows such as OTA.

It is not exposed as a standalone user command.

## Version metadata

Backup archives are associated with the Fre3nder version present when they are
created.

For standalone backup operation, the backup core reads the installed Fre3nder
version from:

```text
/usr/share/fre3nder/VERSION
```

The user does not supply a version through the public CLI.

Integrators may explicitly bind a version when they already own a verified
version context.

OTA uses this mechanism to pass the installed version that was already
resolved during its own verified workflow.

Backup itself does not derive any OTA meaning from that value.

## OTA integration

OTA consumes backup as an independent Fre3nder platform capability.

The dependency direction is:

```text
backup
   |
   v
 OTA
```

OTA may use the internal backup operations:

```text
offer
plan
execute
verify
```

but does not own their implementation.

Backup knows nothing about:

```text
OTA packages
A/B slots
kernel partitions
RootFS partitions
boot selectors
OTA transactions
activation
reboot
known-good state
```

OTA owns those concepts.

During OTA preflight, OTA obtains available backup choices from the backup
core and filters them to persistent targets: HOME `usb`, SYS `usb|home`.
Planning, execution, and stored-transaction validation reject `download`; no
implicit selection is introduced. Existing transaction archive metadata remains
compatible, and later OTA stages still reverify it before system changes.

OTA then records the user's explicit backup selection as part of its own
workflow.

When selected backups are executed, OTA receives the resulting archive path,
size, and SHA-256 from the backup core.

OTA binds those results to its volatile OTA transaction.

Before later OTA stages such as confirmation, platform writes, or activation
preparation, OTA may invoke backup verification again against the metadata
stored in that transaction.

The transaction binding belongs to OTA.

Archive creation and archive verification belong to backup.

See [ota.md](ota.md) for the OTA-specific workflow.

## Frontend integration

Maintenance Web and the protected local Screen use the same asynchronous
[Management API](api/management.md#standalone-backup-endpoints). They select roles
and destinations and display receipts; they do not archive files themselves.

Manual Core execution shares `/run/fre3nder/ota/write.lock` with OTA and app
mutations, using a nonblocking lock. OTA passes its already-held open lock
descriptor to its Backup-Core child, so the child does not acquire a second
independent lock. Management also serializes acceptance of running manual
backup, OTA and app jobs. Downloads only read completed archives and do not
hold the platform operation lock. Discarding an open download unlinks its name;
the existing reader can finish through its open descriptor, including a
verification already in progress. The complete SHA-256 pass does not hold the
receipt lock, so status and discard remain available during verification.

## Failure behavior

Backup operations fail closed.

Examples include:

* a requested target is not currently available;
* a USB filesystem is not backup-capable;
* the selected USB volume changes before execution;
* a source cannot be read;
* an archive cannot be written completely;
* publication of the archive fails;
* final archive metadata cannot be read;
* size verification fails;
* SHA-256 verification fails.

A failed backup operation must not be reported as successful.

The public CLI must not print `BACKUP: COMPLETE` after any execution or
verification failure.

## Qualification boundary

The current automated fixtures cover:

* archive creation;
* filesystem-boundary handling;
* symbolic-link handling;
* HOME `.tmp/` and backup-directory exclusions;
* download staging and permanent delivery;
* reserve checks, ENOSPC, checksum and USB-change failures;
* shared operation locking;
* authenticated streaming, repeat and aborted downloads;
* explicit discard and asynchronous job receipts;
* Maintenance backup selection and error handling;
* archive size and SHA-256 calculation;
* archive verification;
* rejection of modified archives;
* backup offer policy;
* backup selection validation;
* runtime USB capability handling;
* rejection when the selected USB identity changes;
* installed-version handling;
* public interactive backup creation;
* public non-interactive backup creation;
* mandatory verification before public CLI success;
* failure of the public CLI when verification fails;
* OTA integration regressions.

These fixtures validate software behavior using controlled test environments.

They do not by themselves constitute hardware qualification of every
supported USB filesystem, USB storage device, storage failure mode, or
power-loss scenario.

The operator reports successful development-build and A/B-deployment validation
on the reference Ender-3 V3 KE running Fre3nder `2026.5.a`, with the new
Backup-Core present in the RootFS. SYS backups to HOME passed through the CLI,
Maintenance Web and Fre3nderScreen. The browser-download path also passed:
the downloaded TAR had the same SHA-256 as the archive on the printer, and
discarding the temporary archive succeeded. The Screen package passed signature
verification and installation, and its backup panel was tested on the physical
touchscreen.

HOME backups and USB destinations have not yet been hardware-qualified. The
reported SYS results do not qualify those paths, every supported USB filesystem,
or power-loss recovery.
