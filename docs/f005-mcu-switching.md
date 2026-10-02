# F005 MCU firmware switching

F005 is a shared, non-A/B MCU resource behind the retained Creality bootloader.
The current host may use either qualified Fre3nder A/B slot. Historical
selector names do not establish which payload is stored in a slot. Writes need
explicit operator authorization; host and MCU deployment remain separate.

### F005 build and transitional deployment interfaces

The current repository provides
[`scripts/build-f005`](../scripts/build-f005) as the standardized build-only
entry point. It creates a candidate from the pinned upstream Klipper commit and
the productive F005 patches without accessing printer hardware. Candidate
output is intentionally separate from the currently qualified deployment
artifact and is not considered hardware-qualified merely because it built
successfully.

The repository also provides
[`scripts/deploy-f005`](../scripts/deploy-f005) as the standardized
operator-side deployment interface. The immutable RootFS baseline embeds its
effective F005 target image, which may be replaced in persistent storage.

The interface deliberately remains separate from
[`scripts/deploy-x2000`](../scripts/deploy-x2000):

- `deploy-x2000` stages only the inactive X2000 A/B kernel and RootFS;
- `deploy-f005` manages F005 firmware staging and the existing open MCU
  transition primitives;
- neither tool silently expands into the other's persistent-write scope.

Without `--develop`, `deploy-f005` requires Fre3nder B to be active on p8 and
requires the selector to already be restored to `STOCK_A`. Its default mode is
read-only. It validates
the local F005 image through the product release manifest, compares the remote
manifest and product helpers against the current project sources, verifies
an active persistent root, and accepts only MCU states classified by the normal
Fre3nder startup gate.

In `--write` mode it stages the exact release image under the current
`/var/lib/fre3nder/firmware/f005/` location if required. It does not
reflash an already current Fre3nder MCU. For an exact supported Stock MCU it
requires the existing transition helper's no-write preflight to pass before
performing one `--write` invocation. The wrapper does not implement retry or
automatic recovery.

The explicit `--develop` mode instead validates the local
`local/production/artifacts/f005/candidate/` build manifest through the shared
Candidate validation, including the current project commit, recipe inputs,
Klipper pin and exact image. It requires a Candidate/Development Runtime target
with `hardware_qualified: false`, an exact match with the remote Runtime target,
the unchanged project Qualified record, and matching installed product helpers.
Fre3nder A or B may be active, but its selector must select that active slot;
p1 identity checks and active persistent-root checks remain required.

`deploy-f005 <printer-host> --develop` is read-only. An exact Qualified
predecessor uses the transition helper's `--from-qualified` dry-run; an exact
Stock MCU uses its original dry-run. The predecessor dry-run requires the exact
target image to be installed and otherwise refuses without writing. The Stock
dry-run retains its existing deferral when target firmware needs staging.
An explicitly authorized `--develop --write` stages the Candidate if needed and
performs one existing transfer with `--from-qualified --write` for the Qualified
predecessor, or the unchanged Stock transition for Stock. The current target is
a no-op even with `--write`. Unknown MCU states refuse. There are no retries or
recovery attempts, and the Candidate remains hardware-unqualified.

The wrapper and its fail-closed orchestration are **OFFLINE CONFIRMED** by the
current fixture test. This does not create a new hardware qualification: the
underlying Stock-to-Fre3nder transition and F005 product components retain
their existing **QUALIFIED ON DEVICE** status.

`/usr/share/fre3nder/f005-mcu-release.json` remains immutable qualification
evidence. `/usr/share/fre3nder/f005-runtime-target.json` describes the desired
current MCU and embedded image. A previous exact Qualified Fre3nder identity
is a recognized predecessor when it differs from that target, rather than an
unknown or already-current MCU. A persistent system-overlay replacement remains
possible, and `deploy-f005` remains the explicit operator-side update interface.

The normal Fre3nder startup path remains fail-closed by default. If the exact
supported Stock runtime identity is observed, S60 starts no Klippy unless the
persistent opt-in file `/home/fre3nder/f005-auto-transition.enabled` is a
regular non-symlink file containing exactly seven bytes, `enabled`, without a
trailing newline. With that opt-in present, S60 invokes the existing
`f005-stock-to-fre3nder --write` helper exactly once. An unknown MCU identity,
missing helper, invalid marker, or failed transition does not start normal
Klippy.

For `fre3nder-qualified`, S60 reports `f005-update-required` and starts no
Klippy. It never automatically upgrades this predecessor, including when the
Stock auto-transition opt-in is enabled. A Development Candidate update requires
the explicit `deploy-f005 --develop [--write]` workflow above and subsequent
on-device qualification; recognizing the predecessor does not qualify the target.

## Fre3nder MCU requirements

A production Fre3nder F005 MCU build must preserve the following properties.

### Required: preserve the Creality bootloader

The application must continue to start at:

```text
0x08003000
```

The first 12 KiB at `0x08000000..0x08002fff` belong to the existing Creality
bootloader and must never be part of the Fre3nder application image.

A future linker, packaging, or flash-layout change must not silently move the
application below `0x08003000`.

### Required: retain the normal Klipper reset command

The validated return path depends on the ordinary Klipper MCU `reset` command
performing a Cortex-M system reset.

The Fre3nder MCU must retain a reset implementation equivalent to:

```text
reset command
-> NVIC_SystemReset()
```

It must remain usable from Klipper's normal firmware-restart path, including
the shutdown-safe behavior provided by Klipper's reset command.

### Required: use command restart from the host

The Fre3nder Klipper configuration should retain:

```ini
[mcu]
serial: /dev/ttyS1
baud: 230400
restart_method: command
```

The qualified project-controlled Mainline -> Stock return does not depend on
RTS/DTR manipulation, baud searching, USB DFU, CAN bootloaders, SWD, or a
power-cycle-only entry path. The separate dictionary-derived Stock-MCU reset
and exact Stock-MCU -> Fre3nder-MCU updater sequence are now **QUALIFIED ON
DEVICE** as described above.

### Required: preserve explicit F005 packaging metadata

A Fre3nder MCU image must continue to carry valid F005 application metadata and
CRC/length fields expected by the Creality bootloader and updater protocol.

The Creality Stock compatibility identity in the 12-byte board-info field must
remain distinguishable from the Stock identity. It is separate from the
Fre3nder runtime identity in Klipper's dictionary.

The Fre3nder compatibility board-info value is:

```text
mcu0_001_G32-mcu0_004_000
```

and the preserved Stock application uses:

```text
mcu0_001_G32-mcu0_005_000
```

The `mcu0_004_000` board-info value is an intentionally stable compatibility
sentinel, not a Fre3nder release number. Normal Fre3nder releases must not
increment it: unchanged Creality Stock must continue to detect `004 != 005`
on return and automatically install its existing `005` firmware. The actual
Fre3nder version is carried by the Klipper runtime identity, derived from
`VERSION` as `fre3nder-f005-<VERSION>-0-g<prepared-source-sha>` for new
candidates. The concrete values above also record the historical qualified
transition.

Future switching logic must use an explicit release manifest and expected
identity rather than assuming that a numerically higher MCU version is always
the desired target.

### Required: no second updater invocation after a flash failure

Fre3nder orchestration must start at most one deliberate updater invocation for
a transition. If that invocation fails:

- do not start a second updater invocation automatically;
- do not start another updater invocation or otherwise deliberately initiate another erase/write;
- do not guess whether the application is valid;
- do not continue with normal Fre3nder printer operation;
- keep the failure visible to the operator.

The current open product flasher performs one transfer and does not retry after
a failure. The current guarantee applies to the open product flasher; it is not a
retry guarantee for vendor tools.

### Required: serial bootloader request for the open return path

The productive GD32F303 patch enables Klipper's generic
`HAVE_BOOTLOADER_REQUEST`. Its `STM32_FLASH_START_3000` branch resets through
`NVIC_SystemReset()`. Preserve this path and the existing bootloader; it does
not qualify the coordinated X2000 host-reboot handoff.

## Fre3nder-owned MCU lifecycle

Fre3nder is responsible for establishing the MCU state required before
Upstream Klipper takes normal printer ownership. The effective Runtime target
sets the expected identity, size and SHA-256; the separate Qualified record
identifies the hardware-qualified predecessor. Classification uses exact
runtime version and all `REQUIRED_CONSTANTS`, in this order:

```text
fre3nder: exact current Runtime target
  -> no flash required; normal Klippy start

stock: exact supported Stock identity
  -> existing controlled Stock transition may be allowed

fre3nder-qualified: exact previous Qualified identity
  -> explicit update required; no automatic transition or Klippy start

unknown: all other identities
  -> fail closed
  -> do not guess or flash
  -> do not start normal printer operation
```

When Runtime target and Qualified identity coincide, the current MCU is
`fre3nder`, never `fre3nder-qualified`. No version-prefix matching is used.

### Fre3nder-side safety contract

Before Fre3nder initiates an MCU write, it must verify all machine-observable
transition invariants:

1. the current MCU/application identity is known and matches an expected
   Fre3nder or supported Stock source identity;
2. the exact target image matches the effective Runtime target, including its
   expected identity, size, and SHA-256;
3. `/dev/ttyS1` is controlled and free of unexpected owners before the
   bootloader or flash tool takes it over; and
4. the qualified host-recovery path remains available.

For manual MCU transitions, and before any startup or reboot that may trigger
the persistent Stock auto-transition opt-in, the operator must ensure that no
print is in progress and no heater is intentionally active. The current
transition architecture cannot truthfully infer those intentions: for `stock`
and `fre3nder-qualified`, normal Klippy is deliberately not running, and the
passive source-MCU probe exposes identity and reset capability rather than
printer-level print or heater targets.

Before the first bootloader firmware write, the helper resets the exact known
source MCU, closes its UART connection and waits for the bootloader handoff.
The automatic Stock transition is likewise performed during the S60 startup
gate before normal Fre3nder Klippy starts. These properties are machine-enforced;
they do not replace the operator prerequisite that applies before either
transition path.

An unknown source identity fails closed: Fre3nder must not guess, flash, or
start normal printer operation. After a failed updater invocation, Fre3nder must
fail closed and must not start another invocation automatically.

A version number alone must never choose the target image. There must be no
directory scan for an arbitrary firmware image, orchestration-level retry after
a failed invocation, automatic fallback flash, or unrelated printer action.

## Qualification boundary

The controlled open Stock-to-Fre3nder MCU transfer and the bounded
Fre3nder-to-Stock MCU leg are qualified only for their recorded identities on
the investigated reference. The preferred uninterrupted host/MCU return to
Stock remains unqualified. A power-cycle result is not proof of that software
handoff. Do not patch the Stock RootFS or automatically retry a failed flash.

The detailed transition, `mcu_util`, shutdown, Stock updater, NebulaOS and
host-reboot evidence is preserved in
[MCU switching history](../research/docs/f005-mcu-switching-history.md) and
[hardware validation](../research/docs/f005-hardware-validation.md).
Firmware invariants and current pin/configuration ownership are summarized in
[F005](f005.md); use [recovery](recovery.md) for bounded recovery decisions.
