# X2000 Clean-Port Patch Workflow

This document defines the standard implementation and validation workflow for
the X2000 clean-port Linux patch series.

The architecture and patch contents are defined by
`x2000-clean-port-implementation-plan.md`. This document only standardizes how
each patch is prepared, tested, recorded, and reviewed.

## Canonical base

The canonical upstream kernel reference is:

* Linux: v6.6.18
* commit: `d8a27ea2c98685cdaa5fa66c809c7069a4ff394b`
* local reference: `local/research/x2000-kernel/linux-upstream`

The canonical reference tree is read-only. Never modify, reset, clean, commit
in, or build directly in it.

All implementation and validation work happens in disposable trees below
`local/production/work/x2000/`.

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
not contain the changes from Patch 01 or Patch 02 again.

A patch is not considered validated merely because it applies directly to the
unpatched upstream tree when its declared dependencies include earlier patches.

## 1. Preflight

Before starting a patch:

1. read `AGENTS.md`;
2. identify the patch purpose, dependencies, expected files, references,
   exclusions, and earliest validation gate from
   `x2000-clean-port-implementation-plan.md`;
3. verify that the project worktree contains no unrelated changes that could be
   mixed into the patch;
4. verify that the canonical upstream tree is still at the pinned commit.

The implementation scope must stay within the current patch. Do not pull work
from later patches forward merely because doing so would make the current
implementation more complete.

## 2. Create an isolated source tree

Create a disposable clone of the canonical upstream tree under
`local/production/work/x2000/`.

Example naming:

```text
patch01-work.XXXXXX/
patch02-work.XXXXXX/
...
```

The isolated tree is the only kernel source tree modified during development.

For Patch 01, the initial state is the pinned upstream commit.

For Patch 02 and later, apply every predecessor patch in numerical order.

After applying the predecessor series, stage that state in the disposable
clone's Git index with `git add -A`. The index then acts as the predecessor
baseline while the working tree remains available for the current patch.

Do not create a temporary commit. Changes for the current patch remain
unstaged, so `git diff` contains only the current patch delta. The staged
predecessor state exists only inside the disposable kernel clone and must never
be pushed.

## 3. Implement only the current patch

Make the smallest changes required by the current patch plan.

Use upstream Linux abstractions where they already fit. Vendor, stock, OpenKE,
NebulaOS, or other external sources are evidence for hardware semantics, not a
reason to copy an entire implementation.

Keep provenance for adopted hardware facts or implementation details.

Before any build, perform the useful non-build checks for the patch, including
as applicable:

```text
git diff
git diff --check
Kconfig inspection
DTS syntax/static inspection
symbol/reference searches
comparison with the vendor/reference implementation
```

Do not build merely to discover something that static inspection can establish.

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
Do not interpret implementation or test authorization as build authorization.

Boot or hardware validation also requires its applicable explicit authorization
and safety gates.

Successful offline validation never constitutes hardware qualification.

## 5. Standard isolated build environment

Kernel compile/link validation uses the Fre3nder X2000 build container with:

```text
/project  read-only Fre3nder repository
/work     writable local/production/work/x2000
network   disabled
```

Use the prepared Buildroot toolchain:

```text
/work/buildroot-output-fre3nder/host/bin/mipsel-buildroot-linux-gnu-
```

For kernel builds use the underlying compiler:

```text
mipsel-buildroot-linux-gnu-gcc.br_real
```

Do not use the Buildroot userspace compiler wrapper for the kernel.

The established X2000 kernel compiler contract is:

```text
MIPS32r5
O32
soft-float
legacy-NaN
little-endian
```

For an X2000 build, verify the actual `.cmd` files rather than inferring the
contract only from the compiler defaults or ELF architecture label.

The expected relevant compile flags include:

```text
-march=mips32r5
-mabi=32
-msoft-float
-mnan=legacy
```

The MIPS ELF header may report `mips32r2`; the actual Kbuild compile command is
the authoritative check for the selected MIPS32r5 ISA.

Interactive diagnostic shells should not use an unguarded
`set -euo pipefail`. Commands such as `grep | head` may otherwise terminate the
container through SIGPIPE. Expected non-matches or diagnostic pipelines must be
guarded explicitly where appropriate.

## 6. Record the patch artifact

After the implementation has passed its authorized validation gate, create the
repository patch artifact under:

```text
research/patches/linux/
```

Naming follows the series order, for example:

```text
0001-mips-ingenic-add-minimal-x2000-up-platform.patch
0002-clk-ingenic-add-x2000-clock-provider.patch
```

Each patch begins with a small provenance header containing at least:

```text
SPDX-License-Identifier
target upstream Linux version
target upstream commit
hardware-semantics/reference source when applicable
exact reference commit when applicable
```

Linux clean-port patches are covered by the repository's
`research/patches/linux/**` GPL-2.0-only REUSE annotation.

Generate the patch body from the current disposable source tree relative to its
prepared predecessor baseline.

The patch artifact must contain only the current patch delta.

## 7. Patch apply gate

Never validate a dependent patch against the wrong base.

Create a fresh disposable verification clone from the canonical upstream tree.

Then:

1. apply all predecessor patches in numerical order;
2. run `git apply --check` for the current patch;
3. run the whitespace-aware patch check;
4. apply the current patch only inside the disposable verification clone.

For the current patch, the required checks include:

```text
git apply --check
git apply --check --whitespace=error-all
```

These checks validate the patch as a patch.

Do not use ordinary repository `git diff --check` output on a `.patch` file as
the authoritative patch-whitespace gate. Unified-diff context lines contain a
required leading space and can produce misleading `space before tab` or
`trailing whitespace` diagnostics when the patch file itself is treated as
ordinary source text.

The resulting source files must remain whitespace-clean.

## 8. Reproducibility gate

The patch artifact must reproduce exactly the source state that passed
validation.

After applying the patch series in the fresh verification clone, compare every
file modified by the current patch with the corresponding file from the tested
source tree.

All comparisons must match exactly.

This establishes the chain:

```text
canonical upstream
  + predecessor patch artifacts
  + current patch artifact
        =
tested source tree
```

A successful build of one source tree is not sufficient if the stored patch
artifact produces a different tree.

## 9. Final review

Before declaring a patch commit-ready, verify:

* correct canonical upstream commit;
* correct predecessor series;
* current patch applies cleanly;
* patch whitespace gate passes;
* stored artifact reproduces the tested source state;
* only intended files and scope are present;
* implementation-plan file list matches reality;
* exclusions remain excluded;
* provenance and licensing are present;
* the required authorized validation gate passed;
* no stronger validation claim is made than the evidence supports;
* no hardware qualification is claimed unless hardware testing actually passed.

Keep the validation label in the implementation plan at its defined earliest
useful gate. Stronger validation evidence obtained during development does not
require changing that label.

## 10. Repository commit

The Fre3nder repository commit is separate from the disposable kernel clone's
staged predecessor baseline.

Before a Fre3nder commit, follow the normal `AGENTS.md` Git checks and review
the complete staged change.

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

Do not commit without explicit operator approval.

## 11. Cleanup

Disposable work and verification trees may be removed after:

1. the patch artifact is committed;
2. its reproducibility check has passed;
3. no further evidence is needed from the build output.

The canonical upstream reference is never cleaned up or replaced as part of
this process.
