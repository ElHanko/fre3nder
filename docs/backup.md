# Backing up Fre3nder

## Create and check a backup

Run the public CLI on an active Fre3nder runtime with mounted persistence.
For HOME, connect writable runtime USB storage formatted as exFAT, ext4, or
NTFS3; VFAT is usable for other USB purposes but cannot hold a HOME backup.
SYS may instead be stored in preserved `/home`. Ensure the selected target has
enough free space for an uncompressed archive.

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
        +--> future display / web frontends
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

A HOME backup may be written only to backup-capable runtime USB storage.

The backup directory is:

```text
/run/fre3nder/usb/Fre3nderBackup/
```

`HOME` itself remains persistent across a normal Fre3nder platform update.

A HOME backup is an additional recovery measure and does not replace that
persistence contract.

The HOME backup directory itself is excluded when HOME is archived so that
backups stored below HOME cannot recursively include themselves.

### SYS

The active SYS backup source is:

```text
/run/fre3nder-root/system/upper
```

Only the active OverlayFS `upper/` tree is backup content.

OverlayFS `work/` state, reset markers, and other runtime implementation state
are not included.

SYS may be backed up either to runtime USB or to preserved HOME:

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

HOME has exactly one possible backup destination:

```text
USB
```

SYS has two possible backup destinations:

```text
USB
HOME
```

No arbitrary destination path is part of the backup interface.

All archives are stored below a fixed `Fre3nderBackup/` directory at the root
of the selected logical target.

The resulting locations are:

```text
HOME -> USB:
    /run/fre3nder/usb/Fre3nderBackup/

SYS -> USB:
    /run/fre3nder/usb/Fre3nderBackup/

SYS -> HOME:
    /home/Fre3nderBackup/
```

## Archive format

The initial backup archive format is uncompressed POSIX tar using the PAX
format.

Backup traversal:

* does not cross filesystem boundaries below the selected source;
* archives symbolic links as symbolic links rather than following them;
* excludes the HOME backup directory when archiving HOME;
* writes to a temporary file in the destination directory;
* flushes the completed archive before publication;
* publishes the completed archive by rename;
* rereads the final archive to determine its size and SHA-256.

A successful archive result contains at least:

```text
archive path
size
SHA-256
```

Archive creation is separate from archive verification.

This allows higher-level consumers to decide when verification must occur.

## Selection policy

HOME has the following choices:

```text
USB
none
```

`USB` is available only when backup-capable runtime USB is present.

SYS has the following choices:

```text
USB
HOME
none
```

A selection must be explicit.

There is no implicit default that silently creates or skips a backup.

Selecting no backup at all is not a useful standalone backup operation and is
rejected by the public CLI.

Other consumers, such as OTA, may use the same backup-core selection policy as
part of a larger workflow.

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
/usr/libexec/fre3nder-backup-core
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

Archive verification remains a separate internal operation so callers can
control when verification occurs.

The public CLI hides this distinction and always performs verification as part
of `fre3nder backup create`.

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
core.

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

Other frontends should consume the same backup-core API rather than
reimplementing backup policy.

For example, a future GuppyScreen integration could use:

```text
offer
  |
  v
render currently valid choices
  |
  v
plan or validate selection
  |
  v
execute
  |
  v
verify
  |
  v
show successful completion
```

A graphical frontend may present this very differently from the CLI.

That does not change ownership of the underlying backup policy.

The public CLI itself is one such frontend.

Its implementation deliberately collapses the internal sequence into the
single user-facing operation:

```text
fre3nder backup create
```

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
* HOME backup-directory exclusion;
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

Hardware qualification must be performed and recorded separately.
