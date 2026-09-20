# Project scope

This repository develops Fre3nder, an open Linux and upstream-Klipper
platform for the Creality Ender-3 V3 KE.

# Safety rules

The physical printer is the hardware-qualified Fre3nder development system.
Normal development inside a healthy writable Fre3nder runtime is covered by the
standing authorization below. Platform, boot, storage, firmware, and destructive
recovery operations remain operator-controlled.

By default, do not perform hardware- or platform-changing operations unless they
are covered by an established explicitly authorized workflow. This includes:

- raw writes to block devices or partitions;
- partition-table changes;
- filesystem creation, repair, or formatting;
- bootloader changes;
- kernel or RootFS deployment outside an authorized deployment sequence;
- MCU firmware flashing or replacement;
- factory reset, Stock restoration, or destructive recovery operations.

Prefer non-interactive remote access:

```sh
ssh -o BatchMode=yes <printer-host> '<command>'
```

If an investigation would require a write, do not perform it automatically.
Document it as a required next step instead.

## Physical-access constraints

The project must use existing external interfaces wherever possible.

Unless the project scope is explicitly changed by the operator, do not require:

- soldering;
- USB-UART adapters;
- added serial headers or test wires;
- board modifications solely to obtain a debug console.

The currently accepted non-invasive access paths are:

- the normal Fre3nder Linux interface, including SSH;
- Stock Linux when intentionally used for restoration or comparison;
- the existing external Ingenic USB / BootROM interface for recovery work.

A missing serial bootloader console is a project constraint, not a reason to
implicitly introduce hardware modification work.

## On-device Fre3nder development

Fre3nder is the qualified working system used for ongoing development on the
physical printer. It is no longer treated as a temporary experimental boot
environment that must return to Stock after each development session.

When `/run/fre3nder-root/status` reports `active`, normal development inside the
mounted Fre3nder Linux system is permitted without separate authorization for
each individual filesystem, configuration, application, or service change.

Normal on-device development may include:

- creating, editing, moving, and deleting normal files;
- changing configuration;
- installing or updating development/application software;
- starting, stopping, and restarting normal services;
- testing software directly on the X2000;
- iterating on system behavior before transferring the final change back into
  the reproducible repository/build inputs.

No mandatory development-session preparation, automatic `/home` backup, or
selector change is required for ordinary work on a healthy Fre3nder runtime.
Backups remain appropriate when the concrete task puts valuable persistent data
at risk, but they are not a ritual prerequisite for every normal development
change.

Fre3nder may run from either qualified A/B system slot. The currently active
slot may remain selected after a successful deployment or reboot. Do not change
the selector merely to restore a historical development safety state.

The `x2000-ab` classifications `STOCK_A` and `DEVELOP_B` describe the two known
selector byte patterns. They are historical names and do not establish what
payload is currently stored in slot A or B. In particular, slot A may contain
Fre3nder while the selector still reports `STOCK_A`.

A/B deployment is an established Fre3nder platform operation. When the operator
explicitly authorizes a deployment sequence, the authorization covers the
selector change, reboot, and post-boot validation that are defined parts of that
sequence. Do not split an already-authorized deployment into repeated approval
requests for those established internal steps.

On-device state is development evidence, not the release source of truth.
Changes intended to become part of Fre3nder must subsequently be reproduced in
the repository and validated through the normal build process.

The standing authorization for normal runtime development does not include
platform-destructive or recovery operations. Separate explicit authorization is
still required for:

- raw writes to kernel, RootFS, boot, recovery, or other block-device
  partitions outside an explicitly authorized deployment sequence;
- partition-table changes;
- filesystem creation, repair, or formatting;
- bootloader changes;
- MCU firmware flashing or replacement;
- Stock restoration;
- factory reset or destructive recovery operations;
- other hardware-changing operations that are not already part of an explicitly
  authorized established workflow.

# Decision discipline and proportionality

Before proposing, implementing, or expanding any task, ask:

> Is this step necessary, or does it materially advance the project goal?

Do not pursue work merely because it would make a helper, test, guard, recovery
procedure, or analysis more complete in theory.

In particular:

- prefer the smallest change or investigation that resolves the current blocker;
- do not chase hypothetical edge cases without concrete evidence that they matter
  to the next project step;
- do not turn temporary diagnostics, guards, or one-off migration helpers into
  projects of their own;
- if a supporting tool starts consuming effort comparable to or greater than the
  migration work it is supposed to enable, stop and re-evaluate whether that tool
  or prerequisite is still justified;
- distinguish clearly between `REQUIRED`, `USEFUL`, and `INTERESTING` work, and
  defer the latter two when they do not materially reduce risk or unblock progress;
- when a diagnostic or validation step repeatedly fails for reasons unrelated to
  the actual migration target, explicitly reconsider whether the remaining
  uncertainty can be accepted instead of automatically adding another attempt;
- prefer evidence-driven fixes for observed failures over generalized hardening.

Safety is important, but 100 percent certainty or risk elimination is not a
project requirement and is generally unattainable. Risk reduction must be
proportionate to the actual hardware risk, expected benefit, and effort required.

Treat the system proportionally: this is a 3D-printer migration project, not an
aerospace or life-safety system. Do not apply aerospace-style process overhead to
ordinary software or diagnostic details unless a concrete printer hazard warrants
it.

This proportionality rule does not override explicit red-zone warnings or the
requirement for separate authorization before persistent or hardware-changing
operations. It exists to prevent unnecessary detail work from blocking the actual
migration.

Offline validation does not constitute hardware authorization.

A successful build, fixture test, image-size check, or simulated storage write
may establish that an implementation is ready for the next gate, but it must
not be used as implicit authorization to perform the corresponding operation
on the physical printer.

## Established operations, artifact invariants, and scope isolation

Repeated operations that have already been established and validated must be
treated proportionally.

- Do not treat every previously validated A/B operation as a completely new
  procedure. When the operator explicitly authorizes a concrete multi-step
  sequence, that authorization applies to the complete stated sequence. Do not
  split it into repeated approval requests for individual already-established
  steps unless the sequence changes materially.

- Before every deployment of a newly built kernel or RootFS to an inactive A/B
  slot, verify the functional invariants of the artifact that matter to the
  current operation. At minimum, verify the intended boot path, the expected
  artifact variant, and whether the currently established access and recovery
  path remains available after the deployment.

- Preserving operator access is a functional invariant. A build that boots but
  unintentionally removes the currently validated SSH, network, diagnostic, or
  other required access path must not be deployed merely because its build and
  storage checks pass.

- Do not implicitly test unrelated subsystems as part of another task. If the
  current task is, for example, Ethernet/WLAN policy validation, provisioning,
  authentication, recovery, or other independent subsystems must remain at their
  previously validated state unless changing them is explicitly part of that
  task.

- A change of artifact variant is a functional change even when the kernel,
  RootFS format, partition target, or build command otherwise appears equivalent.
  In particular, switching between diagnostic/provisioned and normal production
  RootFS variants must be called out and validated explicitly before deployment.

- Prefer investigation of concrete observed failures over enumerating extensive
  hypothetical failure modes before routine, already-established operations.
  Do not add disproportionate analysis or approval overhead to a validated
  procedure unless new evidence indicates a materially different risk.

The purpose of these rules is to put validation effort where it prevents actual
loss of access or project regressions rather than repeatedly re-validating
already established mechanics.

## Expensive build and validation cadence

### Build execution requires explicit operator authorization

Automated coding agents, including Codex, must not start builds on their own.

Builds are considered expensive operator-controlled actions because they can
consume substantial local compute time and coding-agent usage. Avoiding
unnecessary build execution is therefore an explicit project requirement.

Agents may:

- inspect build inputs, scripts, configurations, and existing build artifacts;
- run non-build syntax checks, static checks, fixture tests, and targeted tests
  that do not themselves invoke a build;
- determine whether a build is required for further validation;
- recommend the smallest appropriate build command and explain what it would
  validate.

Agents must not execute a build unless the operator explicitly authorizes that
specific build in the current session.

A general request to implement, validate, test, continue, or complete a task is
not build authorization.

When a build becomes necessary, stop before executing it and report:

- why the build is needed;
- the smallest suitable build scope;
- the exact command that should be run;
- what result or artifact is expected.

This applies to all build scopes, including full builds, RootFS-only builds,
kernel-only builds, package/component builds, firmware builds, Docker-based
build pipelines, and other commands whose purpose is to produce target
artifacts.

After explicit authorization, execute only the authorized build scope. A new or
materially broader build requires new authorization.

This authorization rule takes precedence over any other section that describes
builds as permitted, recommended, expected, or required. Such wording does not
authorize an automated coding agent to execute the build.

Do not repeatedly run expensive full builds or full validation pipelines after
every small implementation change when faster targeted checks can validate the
changed component.

During iterative development:

- use the smallest relevant validation for the current change, such as syntax
  checks, targeted configuration checks, patch checks, fixture tests, or static
  inspection;
- do not rebuild unchanged components merely to reconfirm results that have
  already been established;
- group related implementation changes before running an expensive end-to-end
  build;
- when the current implementation step is functionally complete, recommend the
  smallest complete build and end-to-end offline validation needed for the next
  gate; do not execute it without explicit operator authorization;
- if an authorized build exposes a concrete problem, fix that problem with
  targeted checks first and recommend a rebuild when required; do not rerun it
  without explicit operator authorization;
- recommend another full build during implementation only when the changed
  behavior cannot be meaningfully validated without it; execution still
  requires explicit operator authorization.

A full build is a validation gate, not the default feedback loop for every edit.

This rule does not permit skipping the final validation required for the current
project step. It requires validation effort to remain proportional to the change
being made.

# Device-specific information

Do not commit information that identifies only one printer, computer, user, or
network. This includes:

- IP and MAC addresses;
- serial numbers and unique device identifiers;
- SSH fingerprints and local SSH aliases;
- personal usernames and home paths;
- concrete filesystem or partition UUIDs;
- current local storage usage;
- individually installed software or printer modifications;
- previous local experiments, helper scripts, and network details.

Store such information only in `docs/local-device.md`, which must remain ignored
by Git. Keep a sanitized template in `docs/local-device.example.md`.

## Hardware research and external references

For Ender-3 V3 KE / Ingenic X2000 hardware enablement, consult relevant
existing public hardware research before repeating board-specific
investigation from scratch.

In particular, NebulaOS / OpenKE should be treated as a primary external
reference for Ender-3 V3 KE hardware work where applicable:

- https://github.com/coreflake1/NebulaOS
- https://github.com/coreflake1/NebulaOS-firmware
- https://github.com/coreflake1/NebulaOS-kernel

External findings are reference evidence, not authority:

1. Prefer findings backed by stock firmware, stock DTB, vendor sources,
   measurements, or real-hardware qualification.
2. Verify applicable findings against this project's pinned kernel,
   drivers, device tree, and observed hardware before adopting them.
3. Do not blindly copy implementation details when versions, drivers,
   bindings, or architecture differ.
4. Clearly distinguish:
   - findings independently observed in this project,
   - findings reproduced from an external source,
   - unverified hypotheses.
5. When a concrete hardware fact, configuration value, pin assignment,
   patch concept, or implementation detail is adopted from another
   project, preserve provenance by citing the specific source in the
   relevant technical documentation or source comment.
6. Prefer the most specific source available: exact file, commit,
   documentation section, stock-derived artifact, or hardware report,
   rather than only the project homepage.

### Canonical kernel references

The historical X2000 clean-port investigation used this read-only upstream
reference:

- Path: `local/research/x2000-kernel/linux-upstream`
- Version: Linux `v6.6.18`
- Commit: `d8a27ea2c98685cdaa5fa66c809c7069a4ff394b`

Keep that tree unchanged as historical migration/reference material.

The productive Fre3nder kernel baseline is defined by
`configs/x2000/sources.json`. For the current `2026.3` line it is:

- Linux stable `v6.6.157`
- Commit: `79643295eba17affbd16ca97f3ef04c90266b28c`
- Baseline tree: `e2963aecbdc92c10a52434a5ae11a82522dc38d5`
- Fre3nder result tree: `40d8b5cee4341505c12373e9bb1386e80241f0d6`

For productive kernel maintenance and future stable updates, use the pinned
baseline in `configs/x2000/sources.json` rather than treating the historical
`v6.6.18` clean-port reference as the current target.

Do not modify, commit in, rebase, reset, or otherwise mutate historical
read-only reference trees.

# Secrets

Never store or commit passwords, tokens, API keys, private SSH keys, credentials,
session secrets, or authentication cookies. Secrets must not be placed in
`docs/local-device.md` either.

# Documentation rules

General documentation must either describe a demonstrated general property of the
Ender-3 V3 KE or clearly scope an observation to a reference firmware/system. When
generality is not proven, use wording such as:

> Observed on the reference system running Creality firmware ...

Do not generalize from a single inspected printer to all Ender-3 V3 KE firmware or
hardware revisions.

# Local paths

Do not commit personal local paths. Use placeholders:

- `<project-root>`
- `<printer-host>`
- `<printer-ip>`
- `<local-user>`

Technical paths on the printer, such as `/usr/data`, `/overlay`, `/etc`, and
`/dev/ttyS1`, may be documented normally.

# Git rules

Before every commit, at minimum:

1. run `git status --short`;
2. run `git diff --check`;
3. review the complete diff;
4. verify that `docs/local-device.md` is ignored;
5. scan for secrets and individual device information.
6. verify that new or modified third-party material has documented provenance
   and redistribution status.

Do not create a commit unless the task explicitly requests one.

# Project goal

The project goal is to make the Creality Ender-3 V3 KE reproducibly usable as
an open Klipper platform while preserving a documented and validated path back
to the original Creality firmware.

The project requires the functionality needed to operate the printer, not
necessarily preservation of Creality's implementation.

Creality-specific user interfaces, application services, touchscreen software,
or other proprietary components may be replaced with open alternatives where
appropriate.

The project must prioritize maintainability, reproducibility, recoverability,
and open implementations over compatibility with unnecessary vendor software.

# Project gates

The roadmap in `docs/roadmap.md` defines mandatory project gates.

## Gate precedence

Mandatory roadmap gates cannot be replaced, weakened, or bypassed by a
task-specific safety check or bring-up gate.

Additional gates may impose stricter conditions for a particular operation,
but satisfying such a gate does not satisfy an unmet mandatory roadmap gate.

In particular, an A/B rollback or slot-switching check may be required in
addition to Gate 1, but it does not replace Gate 1.

## Gate 1 - POINT OF RETURN

Before Gate 1 is satisfied, do not perform experimental changes to persistent
printer state, even when the change appears reversible or is confined to an
inactive A/B slot.

This includes, unless Gate 1 has first been satisfied:

- boot-selector or OTA-marker writes;
- writes to inactive kernel or RootFS slots;
- bootloader-environment writes;
- partition or filesystem changes;
- kernel or RootFS deployment;
- MCU firmware changes.

Read-only inspection, offline builds, fixture-based tests, and volatile
experiments that provably do not modify persistent printer state may continue
before Gate 1.

After Gate 1 is satisfied, persistent or hardware-changing work still requires
explicit authorization for the concrete operation.

Gate 1 requires, at minimum:

- a sufficiently complete backup for the known storage architecture;
- offline validation of the backup;
- protected device-specific identity/factory data;
- documented eMMC boot configuration;
- archived original firmware material where available;
- a recovery path that does not depend solely on the normal Linux system
  continuing to boot;
- a documented route back to the original Creality firmware.

A recovery path does not have to be destructively rehearsed on a working
production printer solely to satisfy Gate 1 when an applicable vendor-documented
external recovery procedure exists and all material required to execute that
procedure has been preserved and validated.

An untested recovery procedure must not be described as guaranteed. Its
remaining execution uncertainty must be documented explicitly.

## Recovery red zone

The reference board's previous non-destructive Linux-hosted RAM-only recovery
attempt reached Stage 1 but did not successfully load or start Stage 2.

A Linux-hosted recovery path was therefore not established by this project.
Such a path is not required for Gate 1 when a separate recovery route exists
that does not depend on the normal Linux system continuing to boot.

Creality provides a documented external recovery procedure using its
Windows/Cloner tooling. The project preserves the material required for the
documented recovery route and the backups required by Gate 1.

The complete recovery procedure has not been executed on the reference device.
It must therefore be treated as a documented but execution-unverified recovery
path, not as a guaranteed restore procedure.

Public prior art for the Ingenic BootROM USB interface, including loading SPL
and RAM-resident U-Boot, provides an additional possible recovery mechanism but
is not required to substitute for the documented Creality recovery route.

Any later work that changes the bootloader, partitions, kernel, RootFS, MCU
firmware, boot selector, or other persistent contents is **WARNING / RED ZONE**
work. Gate 1 satisfaction reduces the risk of losing the documented return path;
it does not make such operations risk-free and does not authorize them
implicitly.

## Gate 2 - CREALITY DELTA UNDERSTOOD

Do not begin the final mainline migration design until required
Creality-specific behavior has been classified.

Use the classifications defined in `docs/roadmap.md`:

- `UPSTREAM`
- `KEEP`
- `REIMPLEMENT`
- `DROP`
- `UNKNOWN`

Required printer functionality may be reimplemented openly instead of retaining
the original vendor implementation.

# Copyright, licensing, and provenance

Follow `docs/licensing-and-provenance.md`.

Do not commit or redistribute third-party firmware images, extracted vendor
binaries, device backups, factory identity data, certificates, or other
third-party artifacts unless their redistribution rights have been verified.

Prefer:

- official source links;
- hashes and version identifiers;
- patches against publicly licensed source;
- locally executed extraction/import workflows;
- independently written documentation;
- open reimplementations of required behavior.

Do not assume that the license of Creality's published Klipper source also
covers unrelated binaries or other components contained in Creality firmware
images.

When importing or comparing third-party source, record its exact provenance,
including repository, version or commit, and applicable license.

For Klipper comparisons, always identify the exact comparison basis:

- upstream Klipper revision;
- public Creality revision;
- reference Creality firmware/tree.

Do not call a difference a "Creality modification" unless the comparison basis
supports that conclusion.

Follow the path-specific licensing policy in
`docs/licensing-and-provenance.md` and `REUSE.toml`. Do not relicense
GPL-covered or other third-party material.
