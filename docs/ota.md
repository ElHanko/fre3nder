# Platform OTA architecture

## Scope

This document defines the Fre3nder platform OTA architecture. Package
verification, preflight, backup integration, staged writes, readback,
activation preparation, reboot, and post-boot handling have an implemented
core/frontend interface. The complete release-to-release OTA flow remains
subject to its stated qualification boundary; implemented code and fixture
results do not by themselves establish a hardware-qualified update.

The goal is a simple A/B platform update mechanism with a usable previous
Fre3nder release as fallback, persistent user data, a clean system state after
an update, and an explicit path back to Creality Stock firmware.

The initial implementation targets the currently supported external Fre3nder
persistence model. Later storage backends may extend the storage-policy layer
without changing the basic OTA contract around the logical `SYS` and `HOME`
roles.

This document defines architecture and required behavior. It does not itself
authorize writes to printer block devices, firmware deployment, boot-selector
changes, filesystem changes, or MCU firmware changes. Those operations remain
subject to `AGENTS.md`.


## Design principles

The OTA design follows these rules:

1. The currently active system slot is never overwritten by a normal Fre3nder
   OTA update.
2. A new release is written completely to the inactive slot before that slot is
   activated.
3. The written artifacts are verified before the boot selector is changed.
4. `HOME` is release-persistent user data and is preserved across Fre3nder
   updates.
5. `SYS` is persistent system state but is disposable across platform releases.
   A successful Fre3nder platform update resets `SYS`.
6. OTA code operates on the logical persistence roles `SYS` and `HOME`, not on
   their physical backing devices.
7. The installation/storage layer owns the mapping from logical persistence
   roles to physical storage.
8. Stock restoration is an explicit destructive system transition. It does not
   rely on a preserved Stock A/B slot.
9. Normal Fre3nder platform OTA must not silently update the F005 MCU.
10. SSH, web UI, and local display must use one common OTA implementation rather
    than independent update paths.

## Storage abstraction

Fre3nder distinguishes between physical storage and logical persistence roles.

The logical roles are:

```text
SYS
    persistent system overlay

HOME
    persistent user data
```

Product logic must use these roles.

It must not depend on physical persistence paths such as:

```text
/dev/sda1
/dev/sda2
/dev/mmcblk0p9
/dev/mmcblk0p10
```

The physical backing is an installation/storage-policy concern.

Conceptually:

```text
installation / storage policy
        |
        +--> SYS  -> physical backend
        |
        `--> HOME -> physical backend

                |
                v

runtime consumers
        |
        +--> OTA
        +--> backup
        +--> reset
        +--> diagnostics
        `--> future UI
```

Changing the physical implementation of `SYS` or `HOME` must not require
redesigning the normal OTA state machine.

### Initial storage scope

The first OTA implementation supports only the current qualified Fre3nder
persistence model:

```text
SYS  -> external ext4 backend identified as FRE3NDERSYS
HOME -> external ext4 backend identified as FRE3NDERHOME
```

The existing runtime storage implementation resolves those backends by logical
role and does not depend on USB device names.

Internal Fre3nder persistence is explicitly outside the initial
implementation.

The OTA implementation must not add provisional p9/p10 handling merely for
future completeness.

If the supported logical persistence roles cannot be resolved through the
supported initial storage model, OTA must fail closed rather than guessing a
physical backend.

## A/B platform layout

The observed X2000 eMMC layout provides two system sides.

```text
p1  boot / OTA selector
p2  device identity and factory information

Side A:
    p3  RTOS A
    p5  kernel A
    p7  RootFS A

Side B:
    p4  RTOS B
    p6  kernel B
    p8  RootFS B

p9   Stock rootfs_data
p10  Stock userdata
```

For the normal Fre3nder Linux platform, the primary A/B release artifacts are:

```text
Slot A:
    p5  kernel
    p7  immutable RootFS

Slot B:
    p6  kernel
    p8  immutable RootFS
```

p3/p4 remain slot-associated RTOS partitions. Normal Fre3nder OTA must not
implicitly assume ownership of them unless a later explicitly defined Fre3nder
release artifact requires that ownership.

p2 is device-specific factory state and is not a normal OTA target.

### Boot selector

p1 selects the host side:

```text
ota:kernel   -> A
ota:kernel2  -> B
```

The selector is changed only after all required inactive-slot artifacts have
been written and verified.

## Transition to true Fre3nder A/B

For the initial OTA development state, the expected platform state is
conceptually:

```text
A = Creality Stock
B = current Fre3nder
```

The first successful Fre3nder A/B OTA intentionally replaces the inactive Stock
side:

```text
before:

A = Stock
B = Fre3nder old       <- active


during update:

A = Fre3nder new       <- being written
B = Fre3nder old       <- remains active


after activation:

A = Fre3nder new       <- active
B = Fre3nder old       <- fallback
```

From that point onward both host slots may contain Fre3nder releases.

Stock is therefore not permanently reserved as a fallback slot.

The normal update sequence subsequently alternates between A and B.

Example:

```text
A = Fre3nder current
B = Fre3nder previous
```

followed by:

```text
A = Fre3nder current
B = Fre3nder next
```

and activation of B only after successful write verification.

## Single OTA core

There must be one implementation of OTA behavior.

Interfaces are clients of that implementation.

Planned interfaces are:

```text
initial:
    SSH / CLI

later:
    Moonraker / Fluidd
    local display
```

The web UI and display must not reimplement slot selection, package
validation, persistence handling, activation, or backup internals.

OTA frontends consume the OTA core. Backup frontends consume the standalone
backup core. A frontend may expose both capabilities without duplicating their
platform logic.

### Core/frontend contract

The first implementation separates OTA behavior from its CLI presentation:

    /usr/libexec/fre3nder-ota-core
        OTA verification, discovery, validation, and planning

    /usr/bin/fre3nder
        common human-facing CLI frontend; OTA namespace: `fre3nder ota`

The OTA core owns OTA decisions and OTA platform knowledge. Frontends
must not independently implement package verification, A/B slot mapping,
active-slot discovery, persistence-role resolution, OTA target selection,
write sequencing, activation rules, or rollback policy.

The standalone backup core owns backup-target policy, selection validation,
archive creation, and archive verification.

The OTA namespace of the common CLI frontend is deliberately limited to
invoking the OTA core, validating the returned protocol response, and
presenting that state to a human operator.

Future GuppyScreen and Moonraker/web integrations must consume the same logical
core operations and state rather than parsing CLI text or reimplementing OTA
behavior.

The current core/frontend transport is a local process invocation. The core
writes exactly one JSON response to standard output and uses its process exit
status to distinguish success, operation failure, and invocation errors.

The JSON contract carries:

    api_version
    ok
    operation

Successful responses additionally carry structured operation-specific state.
Failed responses carry an error description intended for presentation by the
calling frontend.

The initial internal API version is:

    api_version = 1

The implemented operations are currently:

    verify
    preflight
    backup-plan
    backup
    confirm
    write
    readback
    prepare-activation

`verify` returns structured package identity and verification state.

`preflight` additionally returns structured runtime, target-slot,
persistence, runtime-USB, and backup-offer state. The OTA core determines the
active slot, inactive target devices, `SYS`/`HOME` resolution, and their
intended update actions. Backup availability and logical backup targets are
obtained from the standalone backup core and included in the composed preflight
response.

`backup-plan` re-runs package verification and technical preflight, then
delegates explicit `HOME` and `SYS` selection validation to the backup core.
It remains read-only and does not create an archive.

`backup` performs the same verification and preflight, then delegates the
selected backup execution to the backup core. It returns each resulting
archive path, size, and SHA-256.
After successful backup execution it also creates a volatile pending OTA
transaction for the subsequent confirmation boundary. It does not write the
inactive kernel or RootFS slots.

`confirm` requires the transaction ID returned by the successful `backup`
operation. It re-verifies the OTA package, re-runs technical preflight, requires
the same active and target slot state, and re-verifies every selected backup
archive against its recorded size and SHA-256. On success it atomically changes
the volatile transaction from `awaiting-confirmation` to `confirmed`. It still
does not write the inactive kernel or RootFS slots.

`write` requires that same transaction to be in the `confirmed` state. Before
writing it again validates the package, runtime, inactive target slot, and
selected backup archives.

Before the first physical write, the production path additionally requires the
established X2000 A/B partition identity:

    p5  kernel   16384 sectors    PARTLABEL=kernel
    p6  kernel2  16384 sectors    PARTLABEL=kernel2
    p7  rootfs   1024000 sectors  PARTLABEL=rootfs
    p8  rootfs2  1024000 sectors  PARTLABEL=rootfs2

The selected kernel and RootFS must be the exact partitions belonging to the
inactive logical slot, their sysfs partition numbers and sizes must match, they
must reside on the same block device as the active root, and any available
partlabel infrastructure must resolve the expected labels to those devices.

Both inactive targets must also be unmounted and large enough for their signed
payloads.

The initial write order is:

    rootfs.squashfs -> inactive RootFS
    kernel.uImage   -> inactive kernel

Each payload is streamed directly from the verified OTA package and the target
is synchronized before continuing. The source stream is checked against the
signed payload size and SHA-256 while it is written.

After both writes complete, the volatile transaction becomes:

    written-awaiting-readback

`readback` requires that transaction state and reads exactly the signed payload
length back from the inactive RootFS and kernel targets. The read bytes must
match the signed SHA-256 values from the OTA package. A mismatch leaves the
transaction in `written-awaiting-readback` and activation remains prohibited.

Only after both inactive-slot payloads pass readback verification does the
transaction become:

    readback-verified

Neither `write` nor `readback` prepares activation, changes the boot selector,
creates the activation/reset marker, or reboots. Those remain later OTA stages.

### Persistent activation handoff

The volatile OTA transaction below `/run/fre3nder/ota/` intentionally does not
survive reboot. `PREPARE_ACTIVATION` therefore requires a small persistent
handoff before changing the boot selector.

The handoff record is stored at:

    /run/fre3nder-root/system/.fre3nder-ota-activation.json

It resides at the root of the logical `SYS` filesystem rather than inside
`upper/` or `work/`. The targeted system-overlay reset therefore does not remove
it.

The initial record carries the transaction ID, verified package identity,
previous runtime slot, intended target slot, and the completed write/readback
results needed for post-boot validation.

Before selector activation, OTA also prepares the existing targeted reset marker:

    /run/fre3nder-root/system/.fre3nder-reset-target

with the established payload:

    RESET_ON_NEXT_BOOT_ROOT=<target-root>

Both persistent handoff objects must be established and verified before the
selector may change. This ensures that an immediate reboot after selector
activation still leaves enough persistent state for target-boot validation.

The OTA implementation uses the same established 512-byte selector payload
contract as `scripts/x2000-ab`. The historical selector classifications map to
the logical boot slots as follows:

    A -> ota:kernel
    B -> ota:kernel2

The historical names `STOCK_A` and `DEVELOP_B` are not used as payload
semantics by OTA; only logical slot A/B matters.

A selector transition must verify that the currently stored selector agrees
with the active runtime slot, write exactly the 512-byte target record without
truncating the partition, synchronize it, and verify the resulting known
selector hash by readback.

The existing `.fre3nder-reset-target` boot behavior remains unchanged: the SYS
overlay is reset only when the actual booted `root=` matches the recorded target
root. If the old slot remains active, the reset is deferred.

`prepare-activation` requires a `readback-verified` transaction. Immediately
before activation it re-verifies the signed package, active/target runtime
binding, selected backup archives, and the actual inactive kernel/RootFS bytes.

It then establishes and verifies the persistent activation record and targeted
SYS reset marker before touching the boot selector.

The selector transition requires the current selector to agree with the active
runtime slot. The exact established 512-byte target selector is then written,
synchronized, and verified by readback.

After successful selector verification the persistent activation record and the
volatile runtime transaction both become:

    activation-prepared

The operation is idempotent. If the selector write succeeded but a later state
update was interrupted, a retry before reboot may observe that the selector
already points to the intended target and finish the remaining state transition
without rewriting the selector.

If power is lost after the verified selector write but before the persistent
record advances from `preparing` to `activation-prepared`, the target boot may
complete that boundary during post-boot validation. This recovery is accepted
only when the actual booted root, previous runtime slot, and exact known selector
all match the persistent activation handoff.

`prepare-activation` does not reboot the printer.

### Reboot boundary

After `activation-prepared`, the OTA core may request the reboot without needing
the original `.ota` package to remain available. The inactive kernel and RootFS
have already been written and readback-verified at this point.

Immediately before reboot the core verifies again that:

* the volatile transaction is `activation-prepared`;
* the persistent activation record describes the same transaction;
* `.fre3nder-reset-target` names the intended target root;
* the current selector is still the prepared target selector;
* selector-device identity remains valid.

Only after those checks does the core synchronize mounted filesystems and invoke
the system reboot command.

The reboot itself does not mark the update successful. Success is established
only by the subsequent persistent post-boot validation and known-good update.

### Post-boot validation and known-good state

After the target slot boots, Fre3nder performs local post-boot validation from
the persistent activation record. The validation requires:

* the actual `root=` device to match the prepared target slot;
* the boot selector to match that same slot;
* the installed Fre3nder version to match the prepared package;
* the writable Fre3nder root state to report `active`;
* `/` to be writable OverlayFS;
* `/rom` to be read-only SquashFS;
* `/home` to be writable ext4;
* the logical `SYS` mount to be writable ext4;
* the targeted SYS reset marker to have been consumed.

On success the current release is recorded persistently as:

    /run/fre3nder-root/system/.fre3nder-ota-known-good.json

Only then is the transient activation record removed.

A failed post-boot validation leaves the activation record intact and does not
replace the previous known-good record. This preserves the information needed
for recovery and later rollback handling.

The initial post-boot implementation does not yet provide automatic rollback
when the target kernel or RootFS fails before userspace becomes reachable.
A boot-attempt or bootloader-level rollback mechanism is still required before
that failure class can be called automatically recoverable.

The inactive-slot write path is covered offline using regular files as simulated
partition targets. This does not qualify physical writes to the reference X2000
system; real block-device execution remains a separate hardware-controlled
validation step.

Human-readable strings such as the CLI reports are not part of the core API
and must not be consumed by another frontend.

The process transport is an implementation detail rather than a requirement
that the core remain a short-lived command forever. A later privileged OTA
service may expose the same logical operations and response model when
long-running update execution, progress reporting, or mutual exclusion require
it.

Incompatible changes to the structured interface require an API version change.
Compatible additions may extend operation-specific response objects without
moving OTA decisions into a frontend.

## Update sources

The initial OTA architecture supports local release packages.

Required source classes are:

```text
uploaded / locally staged file
USB removable storage
```

Network-based release discovery or direct Internet download may be added later
but is not required for the first OTA implementation.

The source of the package must not change installation semantics.

## Release package verification

A Fre3nder OTA package must be verifiable before any platform partition is
written.

At minimum the release metadata must identify:

* Fre3nder version;
* supported platform/model;
* contained artifacts;
* expected artifact sizes;
* cryptographic hashes;
* project/build provenance required by the release contract.

Public release artifacts require authenticity verification in addition to
ordinary corruption detection.

### OTA package format v1

Fre3nder OTA v1 uses one self-contained release package with the `.ota`
filename extension. The container is a deterministic POSIX ustar archive.

The normal filename is:

```text
fre3nder-<version>-ender3-v3-ke.ota
```

The archive contains exactly five top-level regular files:

```text
manifest.json
SHA256SUMS
SHA256SUMS.sig
kernel.uImage
rootfs.squashfs
```

`manifest.json` carries the existing Fre3nder build and source provenance and
adds the OTA package format version, target platform, packaged artifact sizes,
and packaged artifact hashes. Kernel and RootFS may originate from different
project commits or development build-input fingerprints when an unchanged
Kernel is intentionally reused. `component_provenance` records those two build
origins separately. `composition_provenance` records the project state that
created the final signed package. The components must agree on the Fre3nder
version. Matching artifact mode remains the intended composition contract,
but the current `--compose-only` implementation checks only the version;
the fixture expects mode mismatch rejection. Until code and fixture agree,
check the two component modes explicitly before composition. See the
[build guide](build.md#partial-builds-and-reuse).

`SHA256SUMS` contains SHA-256 digests for `manifest.json`, `kernel.uImage`, and
`rootfs.squashfs`. The manifest therefore does not contain a self-referential
hash; its integrity is covered by the checksum file.

`SHA256SUMS.sig` is an Ed25519 signature over the exact `SHA256SUMS` bytes.
The private signing key is never stored in the repository or shipped on the
printer. The corresponding public key is the OTA trust anchor used by the
device-side verifier.

The repository provides `scripts/generate-ota-keypair` to create a local
keypair under the ignored `local/production/keys/ota/` path. Key generation is
explicit and refuses to overwrite an existing pair.

The `.ota` extension identifies the artifact as a Fre3nder update package; it
does not define a proprietary container format. Standard tar tooling may be
used to inspect it.

### On-device OTA storage

Fre3nder reserves `/ota` for the device-side OTA workflow:

```text
/ota/
├── keys/
│   └── public.pem
├── packages/
└── apps/
    └── <name>/
        └── restored
```

`/ota/keys/public.pem` is delivered by the immutable RootFS and is the Ed25519
trust anchor used to verify OTA packages. The RootFS build manifest records the
SHA-256 digest of this public key as `ota_public_key_sha256`.

`/ota/packages/` is the writable staging location for uploaded or otherwise
locally staged `.ota` packages. Package files are runtime state in the `SYS`
overlay; they are not persistent `HOME` data.

`/ota/apps/<name>/restored` is also SYS-overlay state. It records only that an
app whose persistent desired state lives in `HOME` has already been reconstructed
for the current system overlay. A platform update/reset removes this marker
together with reconstructible app files. The next boot can therefore restore
the app once from its persistent desired state without carrying the old app
payload across platform releases.

This intentionally couples package cleanup to the existing update lifecycle.
If verification or preflight aborts before activation, the staged package
remains available for retry or inspection. After a successful inactive-slot
write and activation, the target-specific `SYS` reset removes the staged package
automatically. The freshly booted immutable RootFS then exposes an empty
`/ota/packages/` directory again.

OTA v1 therefore does not require a separate successful-update cleanup
mechanism for staged packages.

Normal OTA upload handling must write only below `/ota/packages/`; it must not
replace the trust anchor below `/ota/keys/`.

Package verification must establish the Ed25519 signature first and then require
the checksum file, manifest metadata, declared sizes, and actual payload hashes
to agree before any platform partition is written.

### Device-side verify-only command

The immutable RootFS provides:

    fre3nder ota verify <package.ota>

The v1 verifier is deliberately read-only. It does not select a slot, write a
kernel or RootFS partition, change the boot selector, create a SYS reset marker,
or reboot the printer.

Verification requires exactly the five v1 top-level regular TAR members in their
defined order. It authenticates `SHA256SUMS` with Ed25519 and
`/ota/keys/public.pem` before trusting any declared digest. It then validates the
manifest format and `ender3-v3-ke` platform, requires the package trust-anchor
hash to match the installed v1 trust anchor, and streams both payloads while
checking their signed SHA-256 digests and declared sizes. Kernel and RootFS
payloads are not extracted to `/tmp` and are not loaded into memory as complete
files.

The RootFS includes the OpenSSL command-line utility for Ed25519 verification;
Python handles TAR structure, JSON metadata, size checks, and streaming SHA-256.

The v1 format deliberately does not introduce a general-purpose update
framework or certificate infrastructure. Future key rotation may extend the
trust policy without replacing the package container.

Verification must complete before destructive platform writes begin.

### Device-side technical preflight

The immutable RootFS also provides:

    fre3nder ota preflight <package.ota>

This command is the read-only technical preflight used before the later
backup, confirmation, and write stages. It first performs the complete v1
package verification described above.

After successful package verification it requires the writable Fre3nder
runtime to be active and determines the currently running A/B slot from the
actual `root=` argument in `/proc/cmdline`. The running root is authoritative;
the boot-selector contents are not used to infer which slot is currently
executing.

The supported roots are:

    /dev/mmcblk0p7 -> active A, target B
    /dev/mmcblk0p8 -> active B, target A

Any other root, or an ambiguous `root=` command line, fails closed.

The technical preflight also resolves exactly one `FRE3NDERSYS` and exactly one
`FRE3NDERHOME` backend through `blkid`. It then requires:

* `SYS` to be mounted exactly once at `/run/fre3nder-root/system`;
* `HOME` to be mounted exactly once at `/home`;
* each mounted source to match the backend resolved from its logical label;
* both mounted persistence filesystems to be `ext4`;
* `SYS` and `HOME` to resolve to different backends.

On success the command reports the installed and target versions, active and
target slots, inactive kernel and RootFS targets, persistence-role resolution,
the intended `SYS` reset / `HOME` preserve policy, and the backup roles offered
before a later write operation.

The command remains read-only. It does not write p1 or p3-p8, create a reset
marker, modify `SYS` or `HOME`, change the boot selector, or reboot.

Offline fixtures cover both A-to-B and B-to-A slot discovery together with
fail-closed persistence and runtime-state cases. The implementation has also
been exercised on the project reference X2000 system against the real
`/proc/cmdline`, `/proc/mounts`, `blkid` state, installed trust anchor, and
OpenSSL verifier.

This technical preflight now exposes the backup-offer policy but remains
read-only. It does not create a backup, record a backup selection, request user
confirmation, or authorize a later write operation. Those remain subsequent
OTA stages.

## Preflight

Before writing the inactive A/B slot, OTA performs a preflight.

The preflight must determine and present at least:

* currently installed Fre3nder version;
* selected target version or Stock target;
* currently active A/B slot;
* intended inactive write target;
* resolution status of `SYS`;
* resolution status of `HOME`;
* whether `SYS` will be reset;
* whether `HOME` will be retained;
* available backup choices;
* the platform components that will be written.

No block-device write starts before preflight, package validation, backup
selection, and required user confirmation have completed successfully.

## Backup integration

Backup is a standalone Fre3nder platform capability, not an OTA
implementation detail.

Its target policy, archive format, execution rules, standalone CLI, and
internal core API are documented in [backup.md](backup.md).

OTA consumes the backup core through its internal API.

During preflight, OTA obtains the currently available backup targets from the
backup core. The OTA workflow then requires an explicit selection or decline
for `HOME` and `SYS`, invokes backup execution, and binds the returned archive
metadata to the volatile OTA transaction.

OTA owns that transaction binding. The backup core owns backup availability,
selection validation, archive creation, and archive verification.

The OTA transaction records the verified package identity, active and target
slot, explicit backup selection, actual backup results, and a random
transaction ID. The state is runtime-only and disappears on reboot.

A new OTA backup transaction is refused while another OTA transaction or
persistent activation handoff is still active. OTA state is never implicitly
discarded by starting another update.

Before confirmation, platform writes, and activation preparation, OTA
revalidates every selected backup against its recorded archive path, size, and
SHA-256.

A normal platform write may proceed only after every offered backup has an
explicit selection and every selected backup has completed successfully.

Declining an optional backup is valid. It does not change the normal contract
that `HOME` itself is preserved across a Fre3nder update.

## Fre3nder-to-Fre3nder OTA

A normal Fre3nder platform update follows this logical sequence:

```text
SELECT_SOURCE
    |
VERIFY_PACKAGE
    |
DISCOVER_ACTIVE_SLOT
    |
RESOLVE_SYS_HOME
    |
PREFLIGHT
    |
BACKUP_OFFER
    |
BACKUP_SELECTION
    |
BACKUP_EXECUTION
    |
CONFIRM
    |
WRITE_INACTIVE_SLOT
    |
READBACK_VERIFY
    |
PREPARE_ACTIVATION
    |
REBOOT
    |
POST_BOOT_VALIDATION
```

The active kernel/RootFS pair is never the normal write target.

If B is active:

```text
write A
```

If A is active:

```text
write B
```

Activation occurs only after the complete required target-slot contents have
passed their defined verification. Normal Fre3nder updates require kernel and
RootFS as one pair. Component-only deployment with `--kernel` or `--rootfs` is
permitted only together with `--develop` and is outside the normal OTA release
contract.

`PREPARE_ACTIVATION` extends the established next-boot system-overlay reset
mechanism with a separate target-slot marker whose payload encodes the intended
target root. The legacy `.fre3nder-reset` marker remains unchanged for backward
compatibility; A/B activation uses `.fre3nder-reset-target`. The marker
is installed only after target-slot write/readback verification. The target
selector is then written and verified before reboot.

At early boot, a targeted reset marker is acted on only when the actual
`root=` device matches the marker's intended target root. If activation is
interrupted before the selector changes, the previously active slot therefore
keeps its existing `SYS` overlay and leaves the marker pending. If the target
slot boots, it consumes the marker and starts with a clean `SYS` overlay.

## SYS update semantics

`SYS` is persistent but not release-persistent.

A normal Fre3nder system update preserves the logical `SYS` assignment and its
underlying filesystem, but intentionally discards the existing system overlay.

Conceptually:

```text
SYS before update:
    upper/
    work/

update:
    keep SYS backend
    reset overlay contents

SYS after update:
    fresh upper/
    fresh work/
```

The OTA implementation must not reformat, repartition, or remap `SYS` as part of
a normal update.

The existing authorized next-boot system-overlay reset mechanism should be
preferred over inventing a second reset mechanism where it satisfies the OTA
requirements.

This behavior prevents a new immutable RootFS from being combined with stale
system files from an older release.

A platform rollback therefore means:

```text
previous immutable Fre3nder release
+
preserved HOME
+
clean SYS
```

It does not promise restoration of the exact previous system-overlay state.

Exact rollback of `SYS` would require versioned or slot-specific overlays and is
outside the v1 design.

## HOME update semantics

`HOME` is release-persistent.

Normal Fre3nder OTA must:

```text
preserve the HOME assignment
preserve the HOME filesystem
preserve HOME contents
```

The new release consumes the same logical `HOME` role after activation.

Any required future user-data schema migration must be designed explicitly. It
must not be introduced implicitly through physical storage assumptions.

## Rollback model

The inactive previous Fre3nder slot is the platform fallback after successful
activation of a new release.

The architecture requires a defined distinction between:

```text
candidate slot
known-good slot
```

A final OTA implementation must define how a newly selected slot becomes
known-good and how boot failure returns to the previous usable slot.

The exact boot-attempt and automatic rollback mechanism is still an
implementation decision and must be resolved before automatic A/B rollback can
be considered qualified.

The current external Ingenic recovery path remains an independent recovery
boundary and does not replace the normal A/B rollback requirement.

## Stock restoration

Returning to Creality Stock is an explicit OTA target.

Stock restoration does not assume that a preserved Stock slot still exists.

After the first Fre3nder A/B update both A and B may contain Fre3nder.

Therefore Stock restoration writes a verified compatible Stock image into the
currently inactive slot while retaining the currently running Fre3nder slot.

Example:

```text
before:

A = Fre3nder current    <- active
B = Fre3nder previous


restore:

A = Fre3nder current    <- remains untouched
B = Stock               <- written and verified


after activation:

A = Fre3nder current
B = Stock               <- active
```

This preserves the running Fre3nder side until the Stock target has been written
and verified.

The other Fre3nder slot is not automatically converted to Stock.

A later genuine Creality OTA may use Creality's own A/B policy and may therefore
overwrite the remaining Fre3nder side. This is expected behavior after the user
has intentionally returned control to Stock firmware.

## Storage outside the OTA target

The initial OTA implementation owns only the selected inactive A/B system
target, the required boot-selection state, and the logical `SYS` and `HOME`
operations defined in this document.

Partitions and storage that are not resolved through those roles or explicitly
part of the selected system target are outside the OTA write scope.

Stock restoration follows the same rule: it writes only the components required
for the selected inactive Stock system target and does not introduce persistence
migration or storage reprovisioning.

Future installation work may assign different physical storage to `SYS` and
`HOME`. Any resulting Stock-transition conflicts must then be handled by the
storage-policy layer without changing the basic OTA abstraction.

## F005 policy

Normal Fre3nder platform OTA and F005 firmware ownership remain separate.

A Fre3nder-to-Fre3nder OTA must not silently flash or replace F005 firmware.

A deliberate Stock restoration is different: returning the complete printer to
Stock operation may require an explicit F005 transition to the compatible Stock
firmware.

Such a transition must be visible as part of the requested Stock restoration,
must use the separately defined F005 transition contract, and must not be hidden
inside an otherwise ordinary Fre3nder update.

The complete coordinated Fre3nder-host/F005-to-Stock-host/F005 path requires
qualification as part of the Stock restoration workflow.

## Installer boundary

OTA is not responsible for choosing the physical backing of `SYS` and `HOME`.

That decision belongs to installation and storage provisioning.

The intended long-term architecture is:

```text
INSTALL

choose/provision physical storage
        |
        +--> bind SYS
        `--> bind HOME


RUNTIME / OTA

use SYS
use HOME
```

The current installer and OTA paths do not yet share a complete storage
lifecycle. This is an accepted development inconsistency for the initial
implementation.

Fre3nder currently cannot be installed through the original Creality OTA path,
so the first OTA implementation only needs to support an already installed
Fre3nder system with the current external persistence model.

When an internal Fre3nder persistence backend is designed later, installation
will define what physically backs `SYS` and `HOME`.

At that point the storage abstraction and Stock-impact policy must be extended.

Normal OTA semantics should remain:

```text
SYS  -> reset for a new Fre3nder platform release
HOME -> preserve
```

OTA should not need to be redesigned around p9/p10.

## Explicit v1 non-goals

The following are outside the initial OTA implementation:

* using p9 as Fre3nder `SYS`;
* using p10 as Fre3nder `HOME`;
* migrating persistence between external and internal storage;
* repartitioning the eMMC;
* formatting p9 or p10;
* maintaining slot-specific `SYS` overlays;
* silently updating F005 during normal Fre3nder OTA;
* implementing independent update engines for SSH, Fluidd, and the display;
* adding a general package manager or enterprise OTA framework without a
  concrete requirement;
* solving future installer storage policy before internal persistence is
  actually implemented.

## Qualification boundary

The design intentionally separates offline implementation from hardware
authorization.

Implementation may first establish offline:

* package parsing and validation;
* version/model checks;
* A/B target selection;
* logical `SYS`/`HOME` resolution;
* backup orchestration;
* write plans;
* readback verification logic;
* activation-state logic;
* fixture-based interrupted-update behavior.

Actual writes to p1, p3-p8, filesystem changes, Stock restoration, F005
transitions, and destructive recovery remain subject to the RED-ZONE rules and
explicit operator authorization in `AGENTS.md`.

No OTA implementation is hardware-qualified merely because its offline tests
pass.
