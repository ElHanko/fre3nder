# F005 MCU firmware switching

This document records the validated F005/GD32F303 firmware-return mechanism and
the target contract for later Stock/Fre3nder dual-mode operation.

It is a design and evidence document. It does not itself authorize an MCU flash.

## Current evidence

The investigated reference board uses the Creality serial bootloader below the
application image.

The validated memory contract is:

```text
0x08000000..0x08002fff  Creality bootloader, 12 KiB
0x08003000..            MCU application
```

The Fre3nder/Mainline application must not overwrite the first 12 KiB.

## 2026-08-30 current open product path

The bounded, bidirectional F005 MCU transition is **QUALIFIED ON DEVICE** on
the investigated reference system. The current product Stock -> Fre3nder helper
identifies Stock Klipper, sends the dictionary-derived `reset`, closes the
Klipper UART, waits one second, then uses the open F005 bootloader protocol at
115200 baud for handshake, exact identity, sector query, one firmware transfer,
and `app_start`. It then independently identifies the resulting Fre3nder MCU.
No 32-byte request is used for the Stock entry.

The qualified write used Stock runtime
`38d96adc-dirty-20231016_135251-longer-virtual-machine`, bootloader identity
`mcu0_001_G32-mcu0_005_000`, and this Fre3nder image:

```text
runtime:  ?-20260830_120730-cde6ec7a76a4
identity: mcu0_004_000
size:     22528 bytes
SHA-256:  7035a193779dc070eed540052eadd9db064fd48cee9e45dedc0cb0de73711aec
```

The prior Fre3nder -> Stock entry uses the serial bootloader request in the
production F005 application. Neither direction invoked `mcu_util`, retried a
transfer, or performed automatic recovery.

The initial product-integration qualification ran the new product files
non-persistently from `/run`. Later on 2026-08-30, the same product integration
was present in a newly built current-main RootFS from commit
`c4c6fa18e659a82ada32c708720202a5ad6592ac`. That image was written to Slot B,
read back completely, booted successfully, and started Klipper through the
normal product startup gate. The complete current-main RootFS installation is
therefore separately **QUALIFIED ON DEVICE** on the investigated reference
system. The tested build is `2026.1-1-gc4c6fa1` with embedded `VERSION=2026.1`;
it is not a new public `2026.1` release.


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
operator-side deployment interface. The qualified Fre3nder F005 image is
embedded in the immutable RootFS baseline and may be replaced in persistent
storage.

The interface deliberately remains separate from
[`scripts/deploy-x2000`](../scripts/deploy-x2000):

- `deploy-x2000` stages only the inactive X2000 A/B kernel and RootFS;
- `deploy-f005` manages only the current F005 firmware staging and the already
  qualified open Stock-to-Fre3nder MCU transition;
- neither tool silently expands into the other's persistent-write scope.

`deploy-f005` requires Fre3nder B to be active on p8 and requires the selector
to already be restored to `STOCK_A`. Its default mode is read-only. It validates
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

The wrapper and its fail-closed orchestration are **OFFLINE CONFIRMED** by the
current fixture test. This does not create a new hardware qualification: the
underlying Stock-to-Fre3nder transition and F005 product components retain
their existing **QUALIFIED ON DEVICE** status.

The immutable RootFS now contains the qualified F005 release. A persistent
system-overlay replacement remains possible, and `deploy-f005` remains the
explicit operator-side staging and transition interface.

The normal Fre3nder startup path remains fail-closed by default. If the exact
supported Stock runtime identity is observed, S60 starts no Klippy unless the
persistent opt-in file `/home/fre3nder/f005-auto-transition.enabled` is a
regular non-symlink file containing exactly seven bytes, `enabled`, without a
trailing newline. With that opt-in present, S60 invokes the existing
`f005-stock-to-fre3nder --write` helper exactly once. An unknown MCU identity,
missing helper, invalid marker, or failed transition does not start normal
Klippy.

## Historical 2026-08-27 `mcu_util` qualification

On 2026-08-27 the following no-write transition was validated on-device:

```text
running Mainline F005 application
-> Klipper FIRMWARE_RESTART
-> normal MCU "reset" command
-> NVIC_SystemReset()
-> Creality serial bootloader
-> mcu_util handshake
-> mcu_util version query
-> mcu_util app_start
-> unchanged Mainline application
```

The bootloader reported the Mainline application identity:

```text
mcu0_001_G32-mcu0_004_000
```

The following was a separately validated 2026-08-27 project-controlled
Mainline-to-Stock MCU-image return, not the current complete software-only host
handoff:

```text
running Mainline F005 application
-> FIRMWARE_RESTART
-> Creality serial bootloader
-> verify current application identity
-> verify preserved Stock image
-> one project-initiated mcu_util firmware-update invocation
-> app_run
-> Stock Klipper startup
-> original Stock MCU identified
-> Printer is ready
```

The preserved Stock image used for that validation was:

```text
path:
  /usr/share/klipper/fw/F005/mcu0_001_G32-mcu0_005_000.bin

size:
  31436 bytes

SHA-256:
  0b8ecfad8e65e90a3cfc08dd8534dd568e341c160897e6050eadcbf1eb917d4a
```

After restoration Stock Klipper loaded the original 116-command MCU firmware
and reached `Printer is ready`.

Therefore, for that historical MCU-image path:

**MAINLINE/FRE3NDER F005 MCU -> ORIGINAL STOCK F005 MCU FIRMWARE RETURN:
QUALIFIED ON DEVICE.**

This qualification is a project-controlled MCU leg, not the preferred single
uninterrupted host roundtrip. A separate clean Stock-A boot with the original
`S13mcu_update`, and a full power-cycle fallback ending in the exact Stock MCU
identity and `Printer is ready`, are also **QUALIFIED ON DEVICE**. The preferred
Fre3nder -> `FIRMWARE_RESTART` -> bootloader -> X2000 reboot -> unchanged Stock
S13 -> Stock MCU -> ready sequence was not completed in one uninterrupted run
and remains **REQUIRES QUALIFICATION**. On 2026-08-29 that software-only path
reached Stock A but ended in `Lost communication with MCU 'mcu'` and connection
timeouts before `Printer is ready`. Manual power-cycle recovery to Stock
`Printer is ready` was observed twice on the reference device and is **QUALIFIED
ON DEVICE (2/2)**; it does not qualify the software-only handoff.

### MCU shutdown state

An autonomous Fre3nder-B observation of the configured MCU recorded
`is_config=1`, CRC `368128875`, `is_shutdown=1`, and `move_count=1024`; the host
CRC matched exactly. A targeted `clear_shutdown` then changed only
`is_shutdown` from `1` to `0`; configuration, CRC, and move count stayed the
same, and the S60 session reconnected. This is **QUALIFIED ON DEVICE** as a
diagnostic operation. Automatic shutdown clearing is **NOT IMPLEMENTED** and
must not be inferred from a CRC match alone. The original shutdown reason after
an X2000 host reboot remains **REQUIRES QUALIFICATION**. The hypothesis
“Klippy vanishes -> MCU shutdown” is **WIDERLEGT**: normal Klippy/S60 stop did
not automatically shut down the configured MCU.

## Stock updater decision evidence

Offline static analysis of the investigated reference Stock RootFS artifacts
established the behavior of the unchanged updater chain. `S13mcu_update` is
byte-identical in the inspected p7 and p8 copies, with SHA-256:

```text
ad4fe0013af6033664ea230f86a746dfe149c742d5abb453d826ba110a69f151
```

The inspected `mcu_util` copies are also byte-identical:

```text
size:   11096 bytes
SHA-256:
d984f1a51ff9149a8971f9a3d3d0db13f81772c8122dd24b53b4d160f223cd03

format:
ELF32 little-endian MIPS32r2, dynamically linked, stripped
```

These are properties of the inspected reference Stock artifacts, not universal
constants for every Ender-3 V3 KE firmware revision.

For `model=F005` and `board=NEBULA V1.0.0.1`, the script selects `/dev/ttyS1`
and `/usr/share/klipper/fw/F005`. It first runs an `mcu_util` handshake and
version query. It then uses the hardware part of the reported identity as a
filename prefix and requires exactly one matching image in that directory.

For the currently qualified Fre3nder/Mainline identity and preserved Stock
image, the relevant values are:

```text
reported:              mcu0_001_G32-mcu0_004_000
hardware prefix:       mcu0_001_G32
installed version:     004
Stock image:           mcu0_001_G32-mcu0_005_000.bin
target version:        005
decision:              005 -ne 004 -> update
```

The comparison is numeric inequality, not an upgrade/downgrade ordering. Thus
`004 -> 005` and `006 -> 005` both request an update, while `005 -> 005` does
not. The logic cannot distinguish a different application from an outdated
Stock application when both report the same hardware prefix and version field.
It does not use a release manifest or SHA-256 to select or verify the image.

This result is conditional on the Creality bootloader being reachable and the
version query returning the known identity. Neither `S13mcu_update` nor
`mcu_util` resets a running MCU application into the bootloader. Therefore the
static analysis establishes the Stock version/image decision but does not yet
qualify the bootloader handoff or a complete automatic Fre3nder-to-Stock
roundtrip.

The inspected `mcu_util` opens the supplied image and uses its length for the
protocol. Host-side, it does not verify SHA-256, a release manifest, expected
application identity, image hardware identity, or upgrade/downgrade direction.
Its `--ignore-hw-ver` and `--ignore-fw-ver` options do not establish that such
host-side protections are normally active.

Static analysis also found bounded internal retries. For some data-confirmation
or missing-ACK failures, `mcu_util` rewinds the image to offset zero and may
restart the complete update workflow, for up to three complete transfer attempts
within one process. Other protocol responses have bounded retries; an explicit
`flash fail` terminates with an error. One process invocation must therefore not
be described as a general guarantee of exactly one complete transfer attempt.

## Historical qualification boundary before the open product path

The original Stock -> Mainline first flash did not use the later
`FIRMWARE_RESTART` switching sequence. It used the Creality bootloader's early
startup window through a temporary one-shot Stock-host arrangement.

Before the 2026-08-30 open-path qualification, external implementations
indicated that Stock Klipper `FIRMWARE_RESTART` could be used to reach the same
Creality bootloader, but that exact Stock-host -> bootloader transition had not
yet been practically qualified by this project.

The 2026-08-27 Fre3nder-MCU -> Creality-bootloader path was qualified for UART
release and immediate `mcu_util` identity queries. The current 2026-08-30 open
path supersedes it for the bounded product MCU transitions. In both cases, actual
`/dev/ttyS1` release is the relevant bootloader-window trigger; waiting for a
failed Klippy process to exit or for a log marker missed the retained window and
is not a valid handoff trigger.

## Fre3nder-to-Stock host-reboot handoff analysis

The preferred return path has a separate host-reboot boundary after the
qualified Mainline/Fre3nder `FIRMWARE_RESTART` transition. The following is
**OFFLINE CONFIRMED** for the investigated reference Stock artifacts and the
current Fre3nder host artifacts:

- Stock `rcK` calls init scripts in reverse order with `stop`.
  `S13mcu_update` has no effective MCU `stop` path; `S55klipper_service stop`
  stops Klippy; and `S57klipper_mcu` concerns the Linux Host-MCU, not the F005.
  No inspected Stock init or module-driver script explicitly resets the F005,
  starts its application, or switches its supply.
- The current Fre3nder BusyBox reboot reaches the X2000 machine restart path:

  ```text
  _machine_restart
  -> jz_wdt_restart()
  -> internal X2000 watchdog reset
  ```

  No F005-specific GPIO or regulator access was found in that path. The current
  Fre3nder DTS describes the F005 only through UART1 GPC23/GPC24; it has no
  documented F005 reset GPIO or F005 regulator. The inspected public
  NebulaOS/OpenKE DTS reference likewise describes only these UART pins for this
  path.
- The A/B helper changes only the host selector. It does not access the F005 or
  `/dev/ttyS1`.

Thus no software component is known to intentionally disturb the F005 between:

```text
FIRMWARE_RESTART
-> bootloader verification
-> Stock-A selector
-> host reboot
```

In particular, no known component issues `app_run`, sends another F005 software
reset, actuates a documented F005 reset GPIO, or disables a documented F005
regulator in that interval.

This is not proof that the F005 is electrically independent of an X2000 reset.
It remains **UNKNOWN / REQUIRES QUALIFICATION** whether an undocumented or
electrically coupled reset line exists, whether the X2000 reset or its
BootROM/SPL/U-Boot path indirectly resets the F005, or whether the F005 supply
changes during that sequence.

No reliable dump of the retained 12 KiB Creality F005 bootloader at
`0x08000000..0x08002fff` is available. Its automatic application-start
behavior, timeout, persistent command-wait behavior, and any effect of a prior
handshake on that state are therefore also **UNKNOWN / REQUIRES
QUALIFICATION**. The historical "early bootloader window" does not establish a
specific timeout or automatic application start.

### External NebulaOS on-device cross-check

An independent external reference supports the software-side finding above.
[`coreflake1/NebulaOS-firmware`](https://github.com/coreflake1/NebulaOS-firmware/commit/07d1459f71ef18545dadf5f5f4dcb8093b9853bb) at commit
`07d1459f71ef18545dadf5f5f4dcb8093b9853bb` documents the Stock F005 link as
UART1 (`GPC23/GPC24`, `/dev/ttyS1`) and records searches of Stock
`S13mcu_update`/`mcu_util` for reset, GPIO, boot-select, and power-control
signals. `docs/PRINTER_MAINBOARD_PRECONNECTION_CHECKLIST.md` and
`docs/KNOWN_GOOD_PRODUCTION_BASELINE.md` classify the result as no software
control signal identified; the accompanying
`scripts/build/overlay/etc/init.d/S95mcu-boot-recovery` is a bounded one-shot
mitigation, not evidence of a hidden reset or power API.

The same NebulaOS reference records real F005 observations in which a
firmware-reported `shutdown` state was present after particular X2000 host
reboots and required a later `FIRMWARE_RESTART`. NebulaOS did not determine
whether that state persisted through the reboot or arose during the reboot
sequence itself. It classifies the shutdown as operationally
mitigated while leaving its trigger unresolved. This is **EXTERNAL ON-DEVICE
EVIDENCE / STRONGLY SUPPORTING**, not a qualification on this project's
reference device: an X2000 host reboot is not inherently equivalent to an MCU
power-cycle or guaranteed MCU reset, but the electrical reset/supply coupling
and the behavior of this specific device remain **UNKNOWN / REQUIRES
QUALIFICATION**.

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

The application identity must be distinguishable from the Stock identity.

The current validated Mainline candidate uses:

```text
mcu0_001_G32-mcu0_004_000
```

and the preserved Stock application uses:

```text
mcu0_001_G32-mcu0_005_000
```

These concrete version numbers are evidence from the current candidate, not a
permanent release-numbering contract.

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
a failure. The earlier historical `mcu_util` procedure used one
project-initiated process invocation, but that tool can internally retry and
therefore did not establish tool-level exact-once behavior.

### Required: serial bootloader request for the open Fre3nder -> Stock path

The production F005 patch enables Klipper's generic `HAVE_BOOTLOADER_REQUEST`
path for GD32F303. Its `STM32_FLASH_START_3000` branch calls
`NVIC_SystemReset()`, leaving the retained Creality bootloader available.

This serial request was used in the qualified Fre3nder -> Stock leg on
2026-08-30. It is a functional invariant of the open return path. It does not
qualify the separate coordinated X2000 host-reboot handoff.

## Stock/Fre3nder dual-mode target

**DESIGN TARGET — not yet fully qualified.** The X2000 host uses A/B dualboot,
while the F005 remains a shared, non-A/B resource with exactly one active
application behind the retained Creality bootloader.

```text
STOCK
  unchanged Creality Stock host (Stock A: p5 kernel, p7 RootFS)
  Stock Klipper
  Stock F005 MCU

FRE3NDER
  project-owned Fre3nder host (Fre3nder B: p6 kernel, p8 RootFS)
  Upstream Klipper
  Fre3nder/Mainline F005 MCU
```

A mixed host/MCU combination may occur during a controlled transition, but is
not a normal operating state. Stock A is the preserved vendor fallback domain;
Fre3nder B is the project-owned integration domain.

The normal Fre3nder release must not patch or extend the Stock RootFS. In
particular, it must not require Fre3nder init scripts, Stock-Klipper changes,
changes to `S13mcu_update` or `mcu_util`, a Fre3nder mode switcher in Stock A,
or other Fre3nder files or hooks in p7. This is a design target, not evidence
that every return path has already been qualified.

## Fre3nder-owned MCU lifecycle

Fre3nder B is responsible for establishing the MCU state required before
Upstream Klipper takes normal printer ownership. A later release implementation
must use an explicit Fre3nder MCU release manifest with the expected identity,
size, and SHA-256. It must identify the installed application and apply this
fail-closed policy:

```text
known expected Fre3nder MCU
  -> no flash required

known supported Stock MCU
  -> controlled transition may be allowed

unknown MCU identity
  -> fail closed
  -> do not guess or flash
  -> do not start normal printer operation
```

### Fre3nder-side safety contract

Before Fre3nder initiates an MCU write, it must verify all of the following:

1. the current MCU/application identity is known and matches an expected
   Fre3nder or supported Stock source identity;
2. the exact target image matches the Fre3nder release manifest, including its
   expected identity, size, and SHA-256;
3. no print is active and heaters are not intentionally active;
4. `/dev/ttyS1` is controlled and free of unexpected owners before the
   bootloader or flash tool takes it over; and
5. the qualified host-recovery path remains available.

An unknown source identity fails closed: Fre3nder must not guess, flash, or
start normal printer operation. After a failed updater invocation, Fre3nder must
fail closed and must not start another invocation automatically.

A version number alone must never choose the target image. There must be no
directory scan for an arbitrary firmware image, orchestration-level retry after
a failed invocation, automatic fallback flash, or unrelated printer action.
The current controlled transition passes the exact manifest image to one open
bootloader transfer and validates the result before Upstream Klipper starts
normally. It has no automatic retry or fallback flash.

**QUALIFIED ON DEVICE:** for the investigated supported Stock identity and the
new qualified Fre3nder image, Fre3nder identified Stock, sent the
dictionary-derived `reset`, closed the UART, waited one second, completed one
open bootloader transfer and `app_start`, and independently identified the exact
Fre3nder MCU. No `mcu_util` process, retry, or automatic recovery was observed.
This qualifies the MCU transition, not a complete coordinated Stock/Fre3nder
host roundtrip.

## Target transitions

### Stock -> Fre3nder

**COORDINATED STOCK -> FRE3NDER HOST LEG: QUALIFIED ON DEVICE.**

```text
Stock A + exact Stock MCU
-> select and boot Fre3nder B
-> S60 identifies the exact supported Stock runtime
-> persistent opt-in authorizes one Stock -> Fre3nder transition
-> F005 transition helper completes and verifies the transition
-> exact qualified Fre3nder MCU is identified
-> Upstream Klipper reaches Printer is ready
-> Moonraker is active
```

On 2026-09-11 this complete host leg was exercised on the investigated
reference system. After a complete power-cycle, unchanged Stock
`S13mcu_update` handshook with the F005, reported
`mcu0_001_G32-mcu0_004_000`, and successfully installed
`mcu0_001_G32-mcu0_005_000.bin`. Stock Klipper then identified the expected
116-command Stock runtime
`38d96adc-dirty-20231016_135251-longer-virtual-machine`.

After selecting Fre3nder B and rebooting, the persistent opt-in caused S60 to
invoke the production transition helper. The runtime log reported
`f005-stock-to-fre3nder: transition-complete`. Klipper then identified
`?-20260830_120730-cde6ec7a76a4`, reached `Printer is ready`, and reported zero
retransmitted and zero invalid UART bytes. Moonraker was active.

This qualifies the coordinated Stock -> Fre3nder host leg, including the
opt-in startup orchestration. The complete Stock -> Fre3nder -> Stock
software-only roundtrip remains **REQUIRES QUALIFICATION** because the reverse
warm-reboot handoff remains unresolved.

### Fre3nder -> Stock

**PREFERRED RELEASE TARGET / DECISION ANALYZED, HOST-REBOOT HANDOFF
REQUIRES QUALIFICATION:**

```text
Fre3nder B + Fre3nder MCU
-> Fre3nder leaves the F005 in the retained Creality bootloader
-> select and boot unchanged Stock A
-> unchanged Stock S13mcu_update queries the known 004 identity
-> 004 != 005 selects Stock's own F005 image
-> Stock's existing updater machinery can restore the Stock MCU
-> Stock Klipper becomes operational
```

Offline analysis proves the version/image decision for the currently known
`mcu0_001_G32-mcu0_004_000` Fre3nder/Mainline identity: if the bootloader is
reachable and reports that identity, the inspected Stock updater selects
`mcu0_001_G32-mcu0_005_000.bin` because `005 -ne 004`. This does not establish
recognition of every Fre3nder identity or recovery from every foreign MCU state.

The handoff status is:

```text
Fre3nder FIRMWARE_RESTART -> Creality bootloader
    QUALIFIED ON DEVICE

Stock decision 004 != 005 -> Stock image
    OFFLINE CONFIRMED

No known software action disturbs the MCU between
bootloader verification and X2000 reboot
    OFFLINE CONFIRMED

No known software-controlled F005 reset/power path
    OFFLINE CONFIRMED
    EXTERNAL ON-DEVICE SUPPORT: NebulaOS

F005 may be found in a firmware-reported non-clean state after X2000 host reboot
    EXTERNAL ON-DEVICE EVIDENCE FROM NEBULAOS
    RESET/POWER CAUSE UNRESOLVED

MCU still being in the bootloader when Stock S13 runs
after the real X2000 reboot
    REQUIRES QUALIFICATION
```

The remaining handoff uncertainty is whether the F005 still answers the
retained Creality bootloader protocol and reports the known Fre3nder identity
when unchanged Stock reaches the `S13mcu_update` point after the X2000 reboot.
NebulaOS independently supports that no software-controlled F005 reset/power
path has been identified. Its on-device reboot observations do not resolve the
electrical reset/power question: the MCU was found in a firmware-reported
shutdown state after some host reboots, but NebulaOS did not establish whether
that state survived the reboot or arose during it.
The dominant remaining question is whether the retained Creality bootloader
remains responsive long enough for Stock `S13mcu_update` to reach it after the X2000 reboot.
This one observation covers possible reset/power effects and a possible bootloader timeout/application
start; they need not be distinguished separately if the end-to-end handoff is
reproducible.

### Bounded later NO-WRITE qualification (host-reboot leg still open)

The smallest relevant later handoff test is:

```text
already-running Fre3nder/Mainline MCU
-> FIRMWARE_RESTART
-> verify Creality bootloader and known 004 identity
-> select Stock A
-> X2000 reboot
-> at the normal early Stock updater point:
     handshake only
     version query only
-> verify 004 identity is still visible
-> no firmware update
```

After the NebulaOS cross-check, this test primarily answers whether the
retained Creality bootloader remains responsive long enough for Stock
`S13mcu_update` to reach it after the X2000 reboot. A successful result need not
separately identify the underlying reset, power, or bootloader-timing mechanism.

Unchanged normal `S13mcu_update` must not simply run for this test: after a
successful handshake, `004 != 005` would select the Stock firmware write. A
temporary test-only instrumentation must technically prevent that update call
and allow only `mcu_util -c` and `mcu_util -g`. It is not release architecture,
does not add Stock responsibility, and is not a permanent Stock modification.
`NO-WRITE` refers to the handoff test itself; it assumes a Fre3nder/Mainline MCU
application is already running at the beginning. Stock A remains unchanged for
the release path.

## Qualified evidence and its role

The following remains **QUALIFIED ON DEVICE**: a running Mainline/Fre3nder F005
application was reset into the retained Creality bootloader, the preserved
original Stock image was verified, one project-initiated `mcu_util` update
invocation succeeded, and Stock Klipper then reached `Printer is ready`.
No external second update invocation was started. The later static finding that
`mcu_util` contains internal retry paths does not show that such a retry occurred
in that successful run and does not invalidate the qualified result.

This is project-controlled Mainline/Fre3nder -> Stock recovery and regression
evidence. It remains important during development, but it is not the required
final release switching path and does not establish the Stock-owned return path
above.

The existing external Ingenic USB/RAM-U-Boot p1 recovery remains a separate
host-side recovery boundary and must not be conflated with MCU recovery.

## Remaining analysis and qualification

Before claiming complete Stock/Fre3nder dual-mode operation:

1. **Completed offline:** analyze the untouched Stock updater decision,
   including `S13mcu_update` and `mcu_util`, against the known Fre3nder MCU
   identity;
2. **Completed offline:** analyze the X2000/F005 software reset path for the
   Fre3nder-to-Stock handoff;
3. qualify the remaining Fre3nder B -> Stock A host-reboot handoff with one
   bounded no-firmware-write hardware test;
4. **Completed on device:** qualify the Fre3nder-owned exact Stock-MCU ->
   Fre3nder-MCU transition through the open product path, without retry; and
5. qualify a complete coordinated Stock -> Fre3nder -> Stock host roundtrip.

No additional MCU recovery mechanism is required merely to begin that work.
