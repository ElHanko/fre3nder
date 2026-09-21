# Platform OTA architecture

## Scope

This document defines the planned Fre3nder platform OTA architecture.

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

The web UI and display must not reimplement slot selection, validation,
backups, persistence handling, or activation.

They should expose the same operations and state provided by the OTA core.

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
created the final signed package. The components must still agree on Fre3nder
version and artifact mode.

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
└── packages/
```

`/ota/keys/public.pem` is delivered by the immutable RootFS and is the Ed25519
trust anchor used to verify OTA packages. The RootFS build manifest records the
SHA-256 digest of this public key as `ota_public_key_sha256`.

`/ota/packages/` is the writable staging location for uploaded or otherwise
locally staged `.ota` packages. Package files are runtime state in the `SYS`
overlay; they are not persistent `HOME` data.

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

    fre3nder-ota verify <package.ota>

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

    fre3nder-ota preflight <package.ota>

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
and the intended `SYS` reset / `HOME` preserve policy.

The command remains read-only. It does not write p1 or p3-p8, create a reset
marker, modify `SYS` or `HOME`, change the boot selector, or reboot.

Offline fixtures cover both A-to-B and B-to-A slot discovery together with
fail-closed persistence and runtime-state cases. The implementation has also
been exercised on the project reference X2000 system against the real
`/proc/cmdline`, `/proc/mounts`, `blkid` state, installed trust anchor, and
OpenSSL verifier.

This technical preflight does not yet implement the complete architectural
preflight below: backup choices and user confirmation remain later OTA stages.

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

## Backup policy

Before a platform write begins, the user is offered a backup.

### HOME

OTA must offer a `HOME` backup.

`HOME` remains persistent across a normal Fre3nder update even when no backup is
requested.

The backup is an additional recovery measure and does not replace the normal
preserve-`HOME` contract.

### SYS

OTA must offer an optional `SYS` backup.

The purpose of this backup is primarily to preserve previous system
customizations for inspection or manual recovery because the active `SYS`
overlay is intentionally discarded by a normal platform update.

Backup logic consumes the logical storage roles. It must not contain physical
partition assumptions owned by the installer/storage layer.

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
