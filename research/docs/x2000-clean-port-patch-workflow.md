# X2000 Clean-Port Patch Workflow

This document defines the standard implementation and validation workflow for
the X2000 clean-port Linux patch series.

The architecture and patch contents are defined by
`x2000-clean-port-implementation-plan.md`. This document standardizes how each
patch is prepared, implemented, validated, recorded, reproduced, reviewed, and
committed.

`AGENTS.md` remains authoritative for safety, build authorization, Git rules,
hardware access, and proportionality. If this workflow conflicts with
`AGENTS.md`, follow `AGENTS.md`.

## Canonical base

The canonical upstream kernel reference is:

* Linux: v6.6.18
* commit: `d8a27ea2c98685cdaa5fa66c809c7069a4ff394b`
* local reference: `local/research/x2000-kernel/linux-upstream`

The canonical reference tree is read-only.

Never modify, reset, clean, commit in, rebase, or build directly in it.

All implementation and validation work happens in disposable trees below:

```text
local/production/work/x2000/
```

The canonical reference exists only to provide the exact reproducible upstream
base.

## Patch state model

Patch 01 applies directly to the canonical upstream commit.

Every later patch applies to the state produced by all preceding patches.

For example:

```text
upstream v6.6.18
  + 0001
    + 0002
      + 0003
        ...
```

Patch 03 therefore contains only the changes introduced by Patch 03. It must
not contain Patch 01 or Patch 02 again.

A dependent patch is never validated against the unpatched upstream tree when
its declared base includes predecessor patches.

### Development-tree index model

For Patch 02 and later, the disposable development clone uses Git's index as
the exact predecessor baseline:

```text
HEAD         = pristine pinned upstream commit
INDEX        = upstream + all predecessor patches
WORKTREE     = INDEX + current patch implementation
```

After applying all predecessor patches, run:

```sh
git add -A
```

This stages the predecessor state only.

Do not create temporary commits for predecessor patches.

The current patch remains unstaged during implementation. Therefore:

```text
git diff --cached
```

represents the predecessor baseline relative to upstream, while:

```text
git diff
```

represents the tracked part of the current patch.

New files belonging to the current patch remain untracked until a temporary
index is deliberately used for tree calculation or artifact generation.

The real disposable-tree index must remain unchanged throughout current-patch
development.

## 1. Preflight

Before starting a patch:

1. read `AGENTS.md`;
2. identify the patch purpose, dependencies, expected files, references,
   exclusions, and earliest useful validation gate from
   `x2000-clean-port-implementation-plan.md`;
3. verify that the Fre3nder project worktree contains no unrelated changes that
   could be mixed into the patch;
4. verify that the canonical upstream tree is clean and still at the pinned
   commit;
5. identify all predecessor patch artifacts required by the current patch;
6. identify the expected predecessor Git tree where practical.

The implementation scope must stay within the current patch.

Do not pull work from later patches forward merely because doing so would make
the current implementation more complete.

The implementation plan is a planning document, not immutable truth. If
investigation proves that the smallest correct implementation requires a
different file than originally predicted, update the plan instead of forcing
the implementation to match an obsolete prediction.

## 2. Create an isolated source tree

Create a disposable clone of the canonical upstream tree below:

```text
local/production/work/x2000/
```

Example naming:

```text
patch01-work.XXXXXX/
patch02-work.XXXXXX/
patch08-work.XXXXXX/
```

The isolated tree is the only kernel source tree modified during development.

For Patch 01, the initial state is the pinned upstream commit.

For Patch 02 and later:

1. apply every predecessor patch in numerical order;
2. verify each patch with `git apply --check` before applying it;
3. stage the complete predecessor state with `git add -A`;
4. record the resulting predecessor tree with `git write-tree`.

Conceptually:

```text
canonical upstream
  + predecessor artifacts
        =
BASE_TREE
```

`BASE_TREE` is the exact source state from which the current patch is developed.

During implementation, repeatedly verifying:

```sh
git write-tree
```

against the expected `BASE_TREE` is a useful guard that the real index has not
accidentally absorbed current-patch changes.

Do not create temporary predecessor commits.

Do not push anything from the disposable kernel clone.

## 3. Implement only the current patch

Make the smallest changes required by the current patch.

Use upstream Linux abstractions where they already fit.

Vendor, stock, OpenKE, NebulaOS, or other external sources are evidence for
hardware semantics and implementation requirements, not a reason to import a
complete vendor subsystem.

Prefer:

```text
upstream abstraction
    +
minimal X2000-specific delta
```

over:

```text
vendor subsystem replacement
```

Keep provenance for adopted hardware facts, register sequences, algorithms, or
substantial implementation details.

Before any build, perform the useful non-build checks for the patch, including
as applicable:

```text
git diff
git diff --check
Kconfig inspection
DTS/static inspection
symbol/reference searches
API inspection
comparison with upstream implementations
comparison with vendor/reference implementations
checkpatch
scope checks
```

Untracked current-patch files must be reviewed explicitly because ordinary
`git diff` does not show them.

Do not build merely to discover something that static inspection can establish.

If static inspection reveals a concrete architecture or API problem, resolve it
before requesting a build.

## 4. Use the smallest declared validation gate

The implementation plan assigns the earliest useful validation type to every
patch:

```text
static
compile
DT compile
kernel link
boot
hardware
```

Use the smallest gate that meaningfully validates the current change.

A build requires separate operator authorization as defined by `AGENTS.md`.

A request to implement, continue, validate, test, or finish a patch is not build
authorization.

Before requesting build authorization, state:

1. why the build is required;
2. the smallest useful build scope;
3. the exact build command or build operation;
4. the expected result or artifact.

After authorization, execute only the authorized build scope.

If that build exposes a concrete problem:

1. diagnose the specific failure;
2. make the smallest required implementation change;
3. repeat relevant static checks;
4. request another build only when the fix requires build validation.

A materially different or broader build requires fresh authorization.

Boot or hardware validation requires its own applicable authorization and safety
gates.

Successful offline validation never constitutes hardware qualification.

A patch may therefore be compile- or link-qualified while remaining completely
untested on physical hardware.

## 5. Standard isolated build environment

Kernel compile/link validation uses an isolated Fre3nder X2000 build
environment.

Exact container mount names are implementation details. The required invariants
are:

```text
kernel source       read-only
build output        separate writable directory
Buildroot toolchain read-only
network             disabled
```

Use a fresh output directory for a qualification build rather than silently
reusing output generated from an earlier source state.

The prepared Buildroot toolchain is below:

```text
local/production/work/x2000/buildroot-output-fre3nder/host/bin/
```

with prefix:

```text
mipsel-buildroot-linux-gnu-
```

For kernel compilation, use the underlying compiler:

```text
mipsel-buildroot-linux-gnu-gcc.br_real
```

Do not use the Buildroot userspace compiler wrapper for kernel compilation.

The established X2000 kernel compiler contract is:

```text
MIPS32r5
O32
soft-float
legacy-NaN
little-endian
```

Relevant compile flags include:

```text
-march=mips32r5
-mabi=32
-msoft-float
-mnan=legacy
```

This compiler contract does not need to be rediscovered for every patch.

Re-check generated `.cmd` files when a patch changes or may affect:

* architecture compiler flags;
* toolchain selection;
* relevant architecture Kconfig;
* CPU ISA selection;
* ABI selection;
* floating-point mode;
* NaN mode;
* other inputs that could materially alter the established compiler contract.

The MIPS ELF header may report `mips32r2`. When the compiler contract itself is
under investigation, the actual Kbuild compile command is authoritative.

Qualification builds should record useful identities such as:

```text
effective relevant .config values
vmlinux SHA256
DTB SHA256 where applicable
current patch tree identity
```

Interactive diagnostic shells should not use an unguarded:

```sh
set -euo pipefail
```

when diagnostic pipelines may intentionally terminate early.

Commands such as:

```sh
grep ... | head
```

may otherwise terminate the shell through SIGPIPE.

Expected non-matches and diagnostic pipelines must be guarded appropriately.

## 6. Record the patch artifact

After the implementation has passed its authorized validation gate, create the
repository patch artifact below:

```text
patches/linux/
```

Naming follows the numerical series order, for example:

```text
0001-mips-ingenic-add-minimal-x2000-up-platform.patch
0002-clk-ingenic-add-x2000-clock-provider.patch
0008-mips-ingenic-add-x2000-smp-support.patch
```

The stored artifact is a reproducible unified diff containing only the current
patch delta.

It does not require an additional textual header before the first:

```text
diff --git
```

record.

Generate the artifact from the current disposable source tree relative to its
prepared predecessor baseline.

Because the real Git index contains only the predecessor baseline, use a
temporary Git index when current-patch untracked files must participate in the
artifact.

Conceptually:

```text
real index
    =
BASE_TREE

temporary index
    =
BASE_TREE + current patch
```

Do not disturb the real predecessor index merely to create the patch artifact.

When adopted code, register semantics, hardware sequences, or other
third-party-derived material require attribution, preserve provenance in the
resulting source comments or accompanying technical documentation.

Repository-level redistribution metadata for:

```text
patches/linux/**
```

is maintained through `REUSE.toml`.

File-level SPDX identifiers and upstream copyright notices inside newly added or
derived source remain authoritative for the material they describe.

After generating the artifact:

1. verify its expected file scope;
2. verify its semantics and exclusions;
3. run the relevant patch/static checks;
4. record its SHA256.

The artifact SHA256 becomes the identity of the reviewed repository artifact
until commit.

## 7. Patch apply gate

Never validate a dependent patch against the wrong base.

Create a fresh disposable verification clone from the canonical upstream tree.

Then:

1. check out the exact pinned upstream commit;
2. apply all predecessor patches in numerical order;
3. run `git apply --check` for the current patch;
4. run the whitespace-aware patch check;
5. apply the current patch;
6. verify the resulting source tree.

`git apply --check` for a kernel patch must run inside this correctly prepared
kernel verification tree.

Do not run the kernel patch check in the Fre3nder repository itself. Paths such
as:

```text
arch/mips/...
drivers/...
```

refer to the Linux source tree, not to the Fre3nder project root.

Required current-patch checks include:

```sh
git apply --check <patch>
git apply --check --whitespace=error-all <patch>
```

Do not use ordinary Fre3nder-repository:

```sh
git diff --check
```

on the `.patch` file as the authoritative patch-whitespace check.

Unified-diff context lines contain required leading whitespace and can otherwise
produce misleading diagnostics when treated as ordinary source text.

After applying the patch, the resulting kernel source must itself remain
whitespace-clean.

## 8. Reproducibility gate

The stored patch artifact must reproduce exactly the source state that passed
validation.

The standard identity check uses Git tree objects.

### Qualified implementation tree

Starting from:

```text
INDEX    = BASE_TREE
WORKTREE = current implementation
```

create a temporary Git index containing:

```text
BASE_TREE + current implementation
```

and calculate:

```sh
git write-tree
```

This produces:

```text
QUALIFIED_PATCH_TREE
```

The real development-tree index remains unchanged.

### Fresh artifact tree

In a fresh verification clone:

```text
canonical upstream
  + artifacts 01..N
        =
VERIFY_TREE
```

After applying the entire series through the current patch:

```sh
git add -A
git write-tree
```

produces `VERIFY_TREE`.

The required invariant is:

```text
QUALIFIED_PATCH_TREE == VERIFY_TREE
```

Therefore:

```text
canonical upstream
  + predecessor artifacts
  + current stored artifact
        =
exact source state that passed validation
```

This is stronger and simpler than relying only on individual file comparisons.

The predecessor development index must still equal `BASE_TREE` after this
process.

A successful build alone is not sufficient if the stored artifact reconstructs
a different source tree.

## 9. Final review

Before declaring a patch commit-ready, verify all relevant items below.

### Repository and base state

* Fre3nder is at the expected predecessor commit.
* The canonical upstream tree is clean and still at the pinned commit.
* The disposable development index still equals `BASE_TREE`.
* No unrelated Fre3nder changes are present.

### Artifact identity

* Only the expected patch artifact is new or modified.
* Its SHA256 matches the artifact that was reviewed.
* Its file scope is exactly the intended current patch scope.
* The artifact applies on the correctly prepared predecessor series.
* The whitespace-aware patch gate passes.
* Fresh apply reproduces exactly `QUALIFIED_PATCH_TREE`.

### Implementation review

* All required current-patch functionality is present.
* Later-patch functionality remains excluded.
* Vendor-only or explicitly rejected implementation surfaces have not leaked
  into the patch.
* The implementation plan reflects the actual architecture and file scope.

The implementation plan is not immutable. If implementation evidence changes
the smallest correct file set, update the plan rather than forcing the code to
match an outdated prediction.

### Licensing and provenance

* New or modified third-party-derived material has documented provenance where
  required.
* Redistribution status is understood.
* File-level SPDX identifiers and copyright notices are appropriate.
* Repository REUSE metadata remains compatible with the artifact.

### Repository hygiene

Before commit, perform the normal `AGENTS.md` checks, including:

```text
git status --short
git diff --check
complete diff review
docs/local-device.md ignore guard
secret scan
device-specific-information scan
provenance / redistribution review
```

`docs/local-device.md` must remain untracked and ignored.

Personal local paths, hostnames, network addresses, credentials, and other
individual device information must not appear in the patch.

### Static tooling

Run `checkpatch.pl` where applicable.

A patch does not need zero warnings at any cost.

Warnings must be understood and reviewed. Do not add unnecessary abstractions
merely to silence a stylistic warning when the resulting implementation would
be less appropriate.

Errors require resolution unless there is a concrete and documented reason they
are inapplicable.

### Qualification claim

Verify that:

* the required authorized validation gate passed;
* no stronger validation claim is made than the evidence supports;
* hardware qualification is not claimed unless physical hardware testing
  actually passed.

Keep the validation label in the implementation plan at its defined earliest
useful gate.

Obtaining stronger evidence during implementation does not require changing that
planning label.

## 10. Repository commit

The Fre3nder repository commit is separate from the disposable kernel clone and
its staged predecessor baseline.

Do not commit without explicit operator approval.

Before staging the patch artifact, verify its previously reviewed SHA256 again.

Then stage only the intended Fre3nder repository files.

Before commit, at minimum run or verify:

```text
git status --short
git diff --check
git diff --cached --check
complete staged diff
artifact SHA256
docs/local-device.md guard
secret/device scan
provenance / redistribution status
```

The commit should contain the repository artifact and any explicitly intended
documentation updates, not disposable build or verification state.

A patch may be described as:

```text
static validated
compile validated
link validated
DT-compile validated
boot validated
hardware qualified
```

only according to evidence actually obtained.

### Commit and push are separate operations

Authorization to create a commit does not implicitly authorize a push.

Push only when:

* the operator explicitly requests it; or
* the operator performs the push separately.

After a push, verifying the remote commit identity is useful evidence that the
intended commit reached the expected branch.

## 11. Cleanup

Disposable development, verification, temporary-index, and build trees may be
removed after:

1. the patch artifact is committed;
2. its reproducibility check has passed;
3. the required validation evidence has been recorded;
4. no further investigation requires the build output.

Do not remove useful build evidence prematurely when it is still needed for the
current patch or a directly following validation step.

Temporary Git index files should be removed after their tree calculation or
artifact-generation purpose is complete.

The canonical upstream reference is never cleaned, replaced, rebuilt, reset, or
otherwise mutated as part of this process.

## Workflow summary

For Patch N, the standard sequence is:

```text
1. Read AGENTS.md and implementation plan
2. Verify clean Fre3nder state and canonical upstream
3. Create disposable kernel clone
4. Apply patches 01..N-1
5. Stage predecessor state
6. Record BASE_TREE
7. Implement Patch N unstaged
8. Perform static inspection
9. Request the smallest required build authorization
10. Run the authorized validation gate
11. Fix concrete failures and revalidate as required
12. Compute QUALIFIED_PATCH_TREE with a temporary index
13. Generate Patch N artifact
14. Record artifact SHA256
15. Fresh-clone canonical upstream
16. Apply patches 01..N
17. Run patch whitespace/static gates
18. Compute VERIFY_TREE
19. Require VERIFY_TREE == QUALIFIED_PATCH_TREE
20. Run complete pre-commit review
21. Request explicit commit authorization
22. Commit only intended repository artifacts/docs
23. Push only separately authorized
24. Retain or clean disposable evidence proportionally
```

The core reproducibility invariant is:

```text
canonical upstream
  + stored patch series
        =
exact qualified source tree
```

while the core safety invariant is:

```text
offline validation != hardware authorization
```
