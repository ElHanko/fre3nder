# Project roadmap

This project follows gated phases. The gates exist to prevent experimental work
from making the printer unrecoverable and to avoid designing a migration before
the vendor-specific behavior is understood.

## Target

Make the Creality Ender-3 V3 KE reproducibly usable as an open Klipper platform
while preserving a documented and validated path back to the original Creality
firmware.

## Phase 0 - Reference inventory

Status: **completed**

Objectives:

- identify the host hardware and operating system;
- document storage and partition layout;
- identify active Klipper and Moonraker components;
- document the main MCU and Host MCU connections;
- identify Creality-specific modules and services;
- identify visible update and recovery mechanisms;
- record open questions without modifying the printer.

Relevant documents:

- `system-inventory.md`
- `storage-layout.md`
- `klipper-stock.md`
- `recovery-analysis.md`
- `backup-plan.md`

No destructive or state-changing tests are part of this phase.

## Phase 1 - Establish the point of return

Status: **in progress**

This phase has priority over all migration work.

### 1.1 Archive official recovery material

Obtain the exact official Creality firmware package corresponding to the
reference system where available.

Record:

- source;
- original filename;
- firmware version;
- board/hardware designation;
- download date;
- file size;
- cryptographic hash.

Third-party firmware packages must not be committed to this repository unless
their redistribution rights have been explicitly verified.

Progress:

- **Phase 1.1 completed for the currently available vendor-documented path:**
  official V1.1.0.12 `.ingenic`, V1.1.0.12 F005 OTA `.img`, and V1.1.0.15 F005
  OTA `.img` files are archived outside Git with provenance, sizes, and SHA-256
  hashes. The local integrity manifest verifies all archived vendor artifacts.
- The V1.1.0.12 recovery package and OTA package remain distinct artifact types;
  content equivalence is not assumed.
- No official matching V1.1.0.15 `.ingenic` recovery image has been located. The
  documented V1.1.0.12 brick-recovery followed by direct V1.1.0.15 OTA route is
  sufficient for the current Gate-1 evidence result; its destructive execution
  remains documented but not personally rehearsed.

### 1.2 Complete storage and boot metadata

Determine, using read-only methods where possible:

- complete eMMC geometry;
- GPT layout and attributes;
- eMMC CID/CSD information required for recovery;
- EXT_CSD and active boot-area configuration;
- boot0 and boot1 contents;
- A/B selection state;
- inactive RTOS, kernel, and RootFS state;
- bootloader location and version where discoverable;
- available serial, USB, SoC-ROM, or other recovery interfaces.

Do not change eMMC boot configuration during discovery.

Progress:

- **P1.2-02a completed:** The reference eMMC EXT_CSD was read successfully through
  read-only access to an existing kernel debugfs file. Its revision, user-area sector
  count, boot/RPMB sizes, standard boot selection, boot capabilities, reset field,
  health indicators, and relevant partitioning/reliability/write-protection
  register values are documented in [`storage-layout.md`](../../docs/storage-layout.md).
- **P1.2-02b completed:** BusyBox `fdisk` read the reference user-area GPT without
  writes. The protective MBR, 512-byte block geometry, p1-p10 boundaries,
  contiguous partition layout, LBA 34-2047 pre-p1 alignment region, and physical
  tail after p10 are documented and cross-checked against sysfs. No sectors or
  partition/gap contents were read. BusyBox acceptance is not a full CRC or
  primary/backup-GPT verification.
- **Offline recovery-package analysis:** the official V1.1.0.12 `.ingenic`
  contains a user-area boot payload with SPL/U-Boot, protective MBR, primary GPT,
  and pre-p1 boot code. This establishes the vendor recovery layout but does not
  prove byte-for-byte identity with the running V1.1.0.15 reference device.
- **Private reference capture completed:** the whole eMMC user area, boot0, and
  boot1 were captured read-only. The primary GPT header and entry-array CRCs
  validate; the live layout has no conventional backup-GPT header in the physical
  tail. boot0/boot1 are entirely zero-filled.
- **A/B state confirmed:** p1 contains `ota:kernel`, active A carries V1.1.0.15,
  while inactive B retains exact V1.1.0.12 recovery RTOS/kernel/RootFS payloads
  followed only by zero padding.
- **Boot material confirmed:** the persistent loader material is in the user area
  before p1. Compared with the V1.1.0.12 recovery boot payload, differences are
  limited to GPT identifiers/derived CRCs and two copies of the embedded build
  timestamp; the rest of the compared boot payload matches.
- **Phase 1.2 completed for Gate-1 metadata scope.** Exact X2000 ROM sequencing,
  serial-console behavior, and low-level recovery commands remain research items
  but no longer block the backup definition.

### 1.3 Create a complete backup set

The recovery set should account for:

- complete eMMC user area;
- boot0;
- boot1;
- GPT and partition metadata;
- both A/B RTOS images;
- both A/B kernel images;
- both A/B RootFS images;
- OTA selector;
- device-specific factory/identity partition;
- writable overlay;
- `/usr/data`;
- Klipper and Moonraker configuration;
- shipped MCU firmware artifacts;
- relevant system and recovery metadata.

RPMB must be documented separately. If it cannot be backed up through a safe
supported mechanism, that limitation must be explicit.

A raw `/dev/mmcblk0` image alone must never be described as a complete eMMC
backup because it excludes hardware boot areas and RPMB.

**Status: completed for the reference device.** The `/dev/mmcblk0` user area was
captured once as one raw artifact; p1-p10 were extracted offline from that same
image. boot0 and boot1 were captured separately, persistent file exports were
created, and private metadata/manifests preserve the reference state.

RPMB remains explicitly inventory-only because no safe authenticated readback
method was established. Physical main-MCU flash readback also remains unavailable;
shipped MCU artifacts and version evidence are preserved instead. These documented
limitations do not masquerade as captured data.

### 1.4 Validate the backup offline

Validation should include:

- cryptographic hashes;
- exact expected sizes;
- GPT parsing;
- partition-boundary validation;
- extraction of partition images from the whole-device image;
- read-only filesystem validation;
- SquashFS inspection;
- file-level archive inspection;
- cross-validation between whole-device and partition data;
- documentation of consistency limitations for live ext4 captures.

Backup artifacts are private device data and must not be committed to Git.

**Status: completed with a documented live-ext4 limitation.** All raw/partition,
structural, metadata, and file-archive hashes verify. Both SquashFS sides pass full
offline tests, the file-level archives are readable, and p9 passes read-only
`e2fsck -fn`. p10 returns filesystem-consistency errors under `e2fsck -fn`, as
anticipated for a long live stream of a mounted writable filesystem; the original
raw image is preserved unchanged and the separate readable `/usr/data` archive is
part of the recovery set.

### 1.5 Establish brick recovery

A recovery method must be identified that does not depend solely on the normal
Creality Linux system continuing to boot.

The controlled validation sequence is defined in
[`recovery-validation-plan.md`](recovery-validation-plan.md).

Candidate mechanisms may include:

- bootloader console;
- SoC ROM USB loader;
- temporary SPL/U-Boot loading;
- serial recovery;
- board-specific service interfaces;
- external eMMC access or programming.

The selected path must be documented sufficiently to restore the original
software stack after a failed migration.

Progress:

- **VENDOR-DOCUMENTED / ENTRY LOCALLY VALIDATED:** Creality publishes a KE-specific
  [Brick Rescue / Wire Brushing procedure](https://wiki.creality.com/en/ender-series/ender-3-v3-ke/quick-start-guide/firmware-open-source/brick-rescue-wire-brushing-process)
  using a Boot/Reset-initiated `Ingenic USB BOOT DEVICE`, the Windows Ingenic
  Cloner utility, and `.ingenic` recovery images. Normal Linux is not required for
  this vendor flow. The reference board has entered that USB mode without
  flashing; it enumerated as `a108:eaef` / `Ingenic USB BOOT DEVICE`, and a
  non-writing CPU-info request returned `X2000`.
- **OFFLINE-CONFIRMED / PRACTICAL ATTEMPT:** a private KE-specific Linux client
  validates the original V1.1.0.12 archive and the fixed Boot-ROM sequence. A
  fresh RAM-only hardware attempt completed GET_CPU_INFO and the complete
  Stage-1 transfer, including GINFO, original SPL, and PROGRAM_START1; the first
  Stage-2 address transfer then timed out. Stage 2 was not loaded or started.
  The official Windows Cloner remains vendor documentation and policy reference,
  not a personally verified recovery path.
- **OFFLINE-CONFIRMED:** the V1.1.0.12 `.ingenic` package selectively provides
  boot/SPL/U-Boot/GPT plus p3 RTOS, p5 kernel, and p7 RootFS. It does not provide
  p1, p2, the B-side p4/p6/p8, p9, p10, boot0, boot1, or RPMB.
- **OFFLINE-CONFIRMED for the configured map:** on the exact reference GPT, the
  erase ranges preserve p2 `sn_mac`, erase p1 and p3-p9, and erase the beginning
  of p10. Active payloads rewrite p3, p5, and p7.
- **OFFLINE-CONFIRMED:** V1.1.0.12 recreates p9 `/overlay` and p10 `/usr/data`
  as ext4 after mount failure.
- **Offline preflight completed:** the private preflight re-validates the exact
  recovery set and both independently stored raw backup copies. Current result:
  `READY FOR MANUAL RECOVERY REVIEW` / `NOT READY TO FLASH`.
- **Accepted residual risk:** p1 is erased and receives no payload. Evidence
  strongly supports A-side boot unless `ota:kernel2` selects B, but the erased
  selector branch has not been formally proven.
- **CONFIRMED-ON-DEVICE:** retained `upgrade-server.log` data records the
  reference device at V1.1.0.12 on 2024-11-22, selecting the official V1.1.0.15
  F005 OTA image from removable media, invoking `local_ota_update.sh` directly on
  it, and subsequently reporting V1.1.0.15. The captured A/B state independently
  matches this direct transition: inactive B remains exact V1.1.0.12 while active
  A is V1.1.0.15.
- **Phase 1.5 closed without success:** the vendor procedure has not been
  executed on the reference device and no complete restore has been demonstrated.
  The private Linux client is retained as unsuccessful/not demonstrated. No
  further recovery research or new recovery-tool development is planned.

- **Additional p1 A/B rollback gate satisfied on the reference device:** a
  separate upstream/community-derived RAM-U-Boot path completed a bounded p1
  A -> B -> A selector roundtrip with immediate readback verification and a
  subsequent normal Stock-A boot. No B boot, p6/p8 write, deployment, or MCU
  firmware operation was performed. This additional gate does not replace Gate
  1. Recovery execution through the official Creality/Windows Cloner remains
  **DOCUMENTED / NOT PERSONALLY REHEARSED**.

Gate 1 does not require a one-step or bit-exact restore directly to the most
recently used firmware. A reproducibly validated multi-stage route to a known
working starting state is acceptable. One candidate model is:

```text
brick
  -> official V1.1.0.12 .ingenic brick recovery
  -> successful normal boot
  -> official update to V1.1.0.15
  -> restore protected device-specific data and settings
  -> known working starting state
```

The full model has not been personally rehearsed because the destructive
`.ingenic` brick-recovery stage has not been exercised. The subsequent direct
V1.1.0.12-to-V1.1.0.15 OTA stage is, however, confirmed by retained reference
device evidence. The model does not make V1.1.0.12 mandatory and may be shortened
if an official V1.1.0.15 `.ingenic` becomes available. This remains a
vendor-documented model, not a guaranteed or personally rehearsed return path.
Identity/factory restoration is allowed only after the `.ingenic` write coverage
is understood and only at a verified safe stage for the original device. Gate 1
requires a documented return path with preserved and offline-validated material,
not technical elegance; an open
Ingenic USB client or project-authored `.ingenic` build system is not required.

### Gate 1 - POINT OF RETURN

Status: **satisfied (current evidence review)**

The backup/metadata and offline-preflight sides of Gate 1 are established for the
reference device. A second independent physical copy of the private recovery set
has been created and verified. Non-writing Ingenic USB entry and the Boot-ROM
Stage-1 transport were observed, but the Linux client timed out before Stage 2;
the destructive vendor recovery and first-boot validation remain documented but
not personally rehearsed.

Gate 1 satisfaction does not authorize a hardware write. Any experimental
persistent modification remains WARNING / RED ZONE work and requires a separate
explicit project decision, scope, and risk acceptance; this roadmap does not
authorize such an operation.

Recovery execution remains **DOCUMENTED / NOT PERSONALLY REHEARSED**. The
remaining execution uncertainty is present and documented; the vendor route is
not a guaranteed restore.

Gate 1 requires:

- a complete backup set appropriate for the known storage architecture;
- verified hashes and offline readability;
- original firmware material archived where available;
- device identity/factory data protected;
- eMMC boot configuration documented;
- a recovery path that remains usable when normal Linux no longer boots;
- a documented procedure for returning to the original Creality firmware.

A backup without a usable restore path does not satisfy Gate 1.

Where a full destructive restore test on the production printer would itself be
unreasonable, the remaining uncertainty must be documented explicitly. The
project must not claim a stronger recovery guarantee than has actually been
demonstrated.

## Phase 2 - Reconstruct the Creality Klipper delta

Status: **completed for the required first-print scope; Gate 1 is satisfied by
the current evidence review**

WARNING / RED ZONE: the recovery path is vendor-documented but not personally
rehearsed on this device. Further work that changes persistent contents may make the printer
unbootable, require additional hardware intervention, or permanently damage or
destroy it. Backups reduce risk but do not prove restoration. This status does
not authorize any particular hardware write or flash operation.

The public Creality source tree does not necessarily correspond to the firmware
running on the reference system.

The analysis therefore uses three references:

```text
A = upstream Klipper
B = publicly released Creality Ender-3 V3 KE Klipper source
C = Klipper tree shipped with the reference Creality firmware
```

Required comparisons:

```text
A <-> B
What did Creality change in the publicly released fork?

B <-> C
What changed between the published Creality source and the firmware currently
shipped on the printer?

A <-> C
What actually differs between the reference firmware and upstream Klipper?
```

The exact upstream revisions used for comparisons must always be recorded.

### Classification

Every discovered vendor-specific change should be classified as one of:

- `UPSTREAM` - equivalent functionality now exists upstream;
- `KEEP` - required hardware support and suitable for continued use;
- `REIMPLEMENT` - required function that should be replaced by an open implementation;
- `DROP` - vendor-specific functionality not needed for the open platform;
- `UNKNOWN` - insufficiently understood.

Areas of particular interest include:

- PR-Touch;
- Z compensation;
- load/pressure sensing;
- EEPROM access;
- Host MCU changes;
- MCU protocol changes;
- motion and homing changes;
- config extensions;
- binary Python wrappers;
- firmware update coupling;
- Creality application-stack integration.

### Completed Phase 2 MCU sub-milestone

The first mainline MCU milestone is complete for the investigated reference
F005/GD32F303RET6 hardware. The comparison basis is recorded as:

```text
A = aktueller Implementations-Upstream:
    0499b30374315f2a9f49fc12808527fc7d0f5cfa
B = public Creality Klipper source and F005 configuration evidence
C = reference-firmware configuration, runtime logs, and archived F005 material
D = historical PR #7027 / b4b0c2ce... material, used only as comparison evidence
U0 = reconstructed best historical public content baseline only:
     9b60daf62dd7c02164c53f2baa72e3e6c8af441f
     v0.11.0-41-g9b60daf62
```

U0 is a content-comparison baseline, not a claim about fork ancestry.

The active probe path is the normal BLTouch/`probe` path. Archived runtime
evidence shows complete 5x5 bed-mesh runs through that path; PR-Touch,
`z_compensate`, HX711, dir-Z, filter, soft-homing, and fan-feedback paths are
not part of the first milestone. Only the main MCU and Host MCU are loaded in
the observed active path; a separate nozzle-MCU instance is not required by
this port scope.

The resulting port is classified as **SMALL MCU PORT**. It changes
`src/stm32/Kconfig`, `src/stm32/Makefile`, `src/stm32/stm32f1.c`, and the
generic linker script `src/generic/armcm_link.lds.S`. Existing STM32F1-
compatible and generic Klipper code supplies the GPIO, ADC, UART, watchdog,
timer/software-PWM, and ARM startup paths; a new full `src/gd32/` backend is
not required. The GD32 clock branch, conservative flash wait-state handling,
first-256-KiB linker boundary, and F005 board-info reservation are documented in
[`gd32f303-mainline-port.md`](../../docs/gd32f303-mainline-port.md).

The F005-compatible image profile is offline validated: the raw image reserves
board-info offsets `+0x200..+0x21f`, and the packager writes version
`mcu0_004_000`, length, and CRC16. The F005 transport protocol matches the
offline local `mcu_util` analysis and the public compatible implementation; the
Stock updater uses its bootloader startup window, so no Physical-Serial-
Bootloader request is needed for this first path.

The GD32 build, F005 packaging, STM32F103 regression, and a second clean GD32
build passed. The two clean builds were not bit-identical; the first artifacts
were overwritten before a byte-level comparison was retained, so the exact
source of the nondeterminism is not proven. Bit-identical builds are not
required before the first controlled MCU flash. The reproducible source patch
and network-isolated Docker build recipe are published under
[`../patches/klipper/`](../../patches/klipper/) and [`../build/klipper-f005/`](../../build/klipper-f005/).

The packaged candidate was subsequently flashed once on the investigated
reference F005 board through the original early-boot Creality updater. The
Stock updater reported `update:0` and then `app_run`; the newly flashed MCU
answered the existing `/dev/ttyS1` Klipper protocol with
`gd32f303xe`, `120000000` Hz, and `230400` baud. This establishes the milestone
**MAINLINE F005 MCU FLASH + IDENTIFY: PASS** on that reference
system. It does not validate motion, endstops, TMC communication, ADCs,
heaters, fans, probing, or printer operation.

A subsequent separately authorized passive Mainline Klippy runtime test also
completed with exit code `0`. Using `kinematics: none`, it loaded the real
dictionary, completed ClockSync, passed the reviewed pre-config gate, sent
`allocate_oids count=0` and `finalize_config`, observed
`is_config=1/is_shutdown=0`, reached READY through the pinned `/dev/null` EOF
path, and exited without a firmware restart. This establishes
**MAINLINE KLIPPY ↔ MAINLINE F005 MCU PASSIVE RUNTIME CONFIG/FINALIZE: PASS** on
the investigated reference system. The initial `get_config` response was not
separately logged; reaching the configuration-send line is the evidence that
the code gate allowed continuation.

This passive test validated only communication/configuration. The subsequent
staged reference-board bring-up and complete PLA Benchy are documented in
[`f005-hardware-validation.md`](../../docs/f005-hardware-validation.md); they establish
the required first-print surface without changing the Gate-1 recovery boundary.

### Completed Phase 2 host/config sub-milestone

Offline host/printer configuration integration is complete for the investigated
F005/GD32F303RET6 reference. The two candidate configurations and sanitized pin
matrix are published in [`../configs/klipper-f005/`](../../configs/klipper-f005/)
and [`f005-pin-matrix.md`](../../docs/f005-pin-matrix.md). Klipper's own
`scripts/test_klippy.py` accepted both candidates with the exact 88-command
GD32 dictionary (`gd32f303xe`, 120 MHz, PA3/PA2 at 230400 baud) in
debugoutput/dictionary mode, without serial, USB, or hardware access.

This proves offline parser and command-surface compatibility for the
configuration candidates. The later staged hardware result and complete print
are recorded in [`f005-hardware-validation.md`](../../docs/f005-hardware-validation.md).
Host-MCU/ADXL support is deferred and is not required for first mainline
bring-up. Creality-only
PR-Touch, Z compensation, calibration, UI/cloud, and other removed surfaces
remain classified in the host/config document.

The stock dependency graph, first bring-up candidate, and first-mainline
candidate are complete. The staged hardware result closed the required first-
print validation scope; optional Host-MCU/ADXL and PR-Touch/Z-compensation work
is deferred.

### Completed Phase 2 reference hardware validation

The investigated F005/GD32F303RET6 reference passed staged validation of
thermistors, TMC2208 X/Y/Z, X/Y endstops, bounded X/Y/Z motion and direction,
BLTouch/probe and XYZ homing, both heaters and thermistors, fans, filament
sensing, 50 mm hot extrusion, and one complete heated 5x5-mesh PLA Benchy.
The detailed evidence, PID/reference calibration scope, and the one controlled
`Timer too close` retry are recorded in
[`f005-hardware-validation.md`](../../docs/f005-hardware-validation.md).

The temporary PTY feeder used during the print was test scaffolding only and is
not part of the proposed production architecture.

### Mainline-to-Stock MCU return-path qualification

Historical status: the 2026-08-27 project-controlled MCU-image restoration was
**QUALIFIED ON DEVICE**. Current full software-only Fre3nder-B -> Stock status:
**REQUIRES QUALIFICATION**.

An initial non-writing test on 2026-08-27 showed that direct `mcu_util`
communication against the already running Mainline application does not itself
enter the Creality bootloader.

A subsequent authorized no-write test established the required transition:
Stock Klipper accepted `FIRMWARE_RESTART`, the UART was released, the retained
Creality bootloader answered its handshake and version query, and `mcu_util -s`
returned successfully to the unchanged Mainline application.

A separately authorized final test then verified the preserved original Stock
F005 image and completed one project-initiated `mcu_util` update invocation
through that bootloader. `mcu_util` returned success and `app_run`; Stock
Klipper loaded the original 116-command MCU firmware and reached
`Printer is ready`. The invocation is not evidence that the utility performed
exactly one internal transfer attempt.

The 2026-08-27 result remains **QUALIFIED ON DEVICE** for its tested
project-controlled MCU-image path. The separately qualified legs on the
investigated reference system are Fre3nder `FIRMWARE_RESTART` to actual UART
release and exact bootloader identity `mcu0_001_G32-mcu0_004_000`, and the
manual power-cycle recovery to exact Stock F005 identity and `Printer is ready`.
Actual UART release, not process exit or a particular log line, is the
qualified bootloader-window trigger.

On 2026-08-29 the complete software-only Fre3nder -> bootloader -> X2000
reboot -> unchanged Stock S13 -> Stock MCU -> ready sequence booted Stock A on
p7 with the correct selector, unchanged `S13mcu_update`, and hash-valid Stock
image, but Moonraker shut down and Stock Klipper reported `Lost communication
with MCU 'mcu'` with repeated connection timeouts. This full path therefore
**REQUIRES QUALIFICATION**. In contrast, manual power-cycle recovery reached
the exact Stock MCU, 116 commands, complete Stock configuration, and `Printer
is ready` twice on the reference device: **POWER-CYCLE STOCK RECOVERY:
QUALIFIED ON DEVICE (2/2)**. It is the current recovery boundary, not a general
guarantee and not proof of the software-only path. This does not qualify the
separate full-device Ingenic/Cloner recovery path.

### Phase 2.12 hardware-communication checkpoint

The first three identify-only attempts produced no successful live MCU
dictionary. That checkpoint was superseded by the separately authorized first
mainline F005 flash/identify and passive runtime results documented above;
detailed attempt records remain private.

Phase 2.12 does not authorize further identify attempts. Any later hardware
work requires a separate, explicit scope and authorization.

Phase 2 is **complete for the required first-print behavior on the investigated
reference**. Gate 1 is satisfied by the current evidence review; recovery
execution remains documented but not personally rehearsed. Gate 2 is closed
below. The next scope is
Phase 3 host/print-computer architecture and userspace integration.

### Gate 2 - CREALITY DELTA UNDERSTOOD

Status: **satisfied for the required first-print scope**

Mainline migration design begins only when all required vendor-specific
functionality is either:

- understood;
- known to exist upstream;
- deliberately dropped;
- or assigned a concrete open reimplementation plan.

The required F005 first-print surface is now classified: ordinary upstream
motion, TMC, endstops, BLTouch/probe, thermistors, heaters, fans, filament
sensing, mesh, and extrusion are `UPSTREAM`/`KEEP`; inactive Creality-only
surfaces are `DROP`; Host-MCU/ADXL and input shaping are deferred; optional
PR-Touch/Z compensation is assigned `REIMPLEMENT` if later needed. No required
first-print behavior remains `UNKNOWN`. This closes Gate 2 without implying
that recovery execution has been personally rehearsed or guaranteed.

## Phase 3 - Open X2000 host replacement

Status: **Phases 3.1 and 3.2 complete; Gate 1 evidence satisfied; recovery
execution remains documented but not personally rehearsed**

Selected target: **complete open X2000 host replacement**. The selected system
is a conservative, LTS-oriented embedded appliance: an open kernel/Device Tree,
minimal Buildroot root filesystem, upstream Klipper and Moonraker, open Web and
touchscreen UI, camera streaming, and a Linux Host MCU for ADXL345/Input
Shaping. The established X2000 -> `/dev/ttyS1` at 230400 -> Mainline F005 path
remains the reference printer-control contract.

The selected target must retain a stock-compatible recovery boundary. Gate 1 is
**SATISFIED** by the current evidence review, but no Phase-3 design or later
implementation may claim a personally demonstrated or guaranteed stock return
without separate execution evidence and authorization.

Options A (minimal host change) and B (open applications on the stock host) are
no longer equal long-term objectives. They may be used only as explicitly scoped
diagnostic/intermediate paths where they materially reduce risk.

### Phase 3.1 - Hardware + Boot Contract

Status: **completed**

The required X2000 interfaces, boot/recovery constraints, and resulting target
architecture are recorded in:

- [`x2000-hardware-contract.md`](../../docs/x2000-hardware-contract.md);
- [`x2000-open-host-architecture.md`](../../docs/x2000-open-host-architecture.md).

The contract covers stock-recovery compatibility, an LTS-oriented embedded base,
F005 UART, networking, display/touch, camera, ADXL345/vibration sensing/Input
Shaper, and the constraints for a reproducible image/update architecture. It
does not implement a kernel, Device Tree, Buildroot system, bootloader change,
deployment, or update scheme.

### Phase 3.2 - Kernel / Device-Tree feasibility

Compare pinned, maintained LTS candidates against the Phase-3.1 contract.
Establish the smallest viable X2000 kernel/DT basis for CPU/SMP, DRAM, eMMC,
UART, SPI/ADXL345, I2C/touch, SDIO WLAN, display, camera, USB as needed, and
reset/watchdog behavior. Do not select a release merely for recency.

Status: **completed.** The bounded result is recorded in
[`x2000-kernel-dt-feasibility.md`](x2000-kernel-dt-feasibility.md). It selects
the pinned Ingenic Linux 6.6.18 X2000 SDK mirror plus a minimal,
project-authored KE board patch set. A public NebulaOS implementation is
evidence and patch-level prior art only; it is not selected as the project
distribution or firmware basis. The separately authorized non-persistent
prototype was the next phase and has now established the bounded `2026.1.a`
Open-Host baseline described below.

### Phase 3.3a - Offline prototype build

Status: **COMPLETE; no printer access**

The pinned offline build and lifecycle boundary are in
[`x2000-prototype-build.md`](x2000-prototype-build.md) and
[`x2000-lifecycle.md`](x2000-lifecycle.md). It creates ignored local artifacts
only and does not authorize installation, a boot attempt, or storage changes.
The public release model and planned `2026.1` scope are defined once in
[`versioning.md`](../../docs/versioning.md).

### Phase 3.3b - Controlled hardware evaluation

Status: **`2026.1 FUNCTIONALLY ACHIEVED` (2026-08-29)**

The separately authorized Slot-B evaluation has proven deployment to p6/p8 with
complete read-back, boot of the project Linux 6.6.18-rt23 kernel from p6 with
the p8 SquashFS root, entry into early userspace, and automatic p1 rollback to
Stock A. The later bounded Network-Smoke additionally proved SDIO WLAN,
firmware start, WPA association, DHCP/default route, ICMP, and non-interactive
public-key SSH while the Stock-A rollback was already armed. See
[`x2000-ab-bringup-plan.md`](x2000-ab-bringup-plan.md) for the evidence and
explicit limits.

The later Production RootFS additionally proved USB mass-storage provisioning,
AX88179B/CDC-NCM Ethernet-first operation, WLAN fallback, volatile host-key
generation, and public-key SSH through the S20 -> S40 -> S50 path. A subsequent
read-only qualification also proved interactive SSH PTY allocation and shell
operation. It embeds no user credentials.

On 2026-08-27 the Develop RootFS deployment orchestrator completed its full
hardware sequence with a 2,838,528-byte candidate whose SHA-256 is
`c34eb06b0a01abd03844a76c1a3da7825a89cdaf7c84670b91b1ca031b073e3f`:
Develop p8 plus `STOCK_A`, Stock-A boot, p8 write, complete RootFS artifact
read-back, `select-b`, Develop p8 plus `DEVELOP_B`, `select-a`, and final
Develop p8 plus `STOCK_A`. Reboot synchronization uses explicit operator
confirmation because Stock SSH must be enabled manually. A safely aborted run
can resume from validated Stock p7 plus `STOCK_A`.

The corrected Development persistence path is **QUALIFIED ON DEVICE** through a
normal Develop-B -> Develop-B reboot on 2026-08-28. `FRE3NDERDATA:/p9` supplies
`/persist/system` and `FRE3NDERDATA:/p10` supplies `/persist/userdata`; both
S09 storage and S10 final persistence reached `active` before and after that
reboot. S09 alone now waits at most ten seconds for the
observed delayed USB mass-storage enumeration, scanning about once per second,
proceeding immediately for exactly one volume, refusing multiple volumes, and
ending at `no-volume` on timeout. The persistent Dropbear Ed25519 host-key file
was created as a regular mode-0600 file and used from
`/persist/system/fre3nder/ssh/`. The same file was reused over the reboot,
verified as Dropbear's configured key, and matched the key presented over SSH.
The system remained on p8 with the valid `DEVELOP_B` selector and non-interactive
public-key SSH became available again automatically.

### Phase 3.5 - Fre3nder host integration and MCU lifecycle

Runtime/hotplug network failover, general persistent configuration, display,
touch, non-required USB peripheral classes, and later product functions
**REQUIRE QUALIFICATION**. Phase 3.5 **QUALIFIED ON DEVICE** the Fre3nder-B upstream
Klippy runtime: S60 recognized the exact Fre3nder MCU; the MCU reported version
`?-20260820_092609-29ca4e70a84f`; Klippy loaded the 88-command dictionary and
complete configuration, reported 1024 moves, stable ClockSync/UART, and heater/ADC
telemetry; `/run/fre3nder-klipper/printer` existed and Klippy owned
`/dev/ttyS1`. The exact Stock-MCU -> Fre3nder-MCU transition is also
**QUALIFIED ON DEVICE**, including the dictionary-derived exact `reset`, one
project-initiated `mcu_util -u -f` invocation returning `app_run`, and an
independent exact Fre3nder identity after the exact Stock identity
`mcu0_001_G32-mcu0_005_000`.

Two startup races are a qualified procedural boundary: SSH can be reachable
before S60 finalizes its MCU status, and S60 `active` can precede immediate
observation of its PTY and complete configuration. Neither signal alone is a
readiness gate. The combined gate is S60 `active`, expected Klippy process,
PTY, Klippy ownership of `/dev/ttyS1`, fresh log with expected MCU identity,
and complete configuration; it is **QUALIFIED ON DEVICE**. The
`/proc/<pid>/cmdline` stale-PID ownership hardening is separately **OFFLINE
CONFIRMED** by local fixtures.

The historical Phase-2 complete Mainline print remains **QUALIFIED ON DEVICE**.
The separately controlled first 2026-08-29 Fre3nder-B attempt was aborted during
its first layer; its explanation remains an **INFERENCE**. The repeat used the
then-unmodified 1.900 image configuration plus session-only
`SET_GCODE_OFFSET Z=-0.280`, completed successfully, and therefore establishes
the effective 2.180 offset and the **FRE3NDER-B END-TO-END PRINT: QUALIFIED ON
DEVICE**. `z_offset: 1.900` is **WIDERLEGT as the current reference value**;
the separately tracked configuration now records the 2.180 result. The
persistence and reboot qualification remains limited to the investigated Development
USB-adapter Develop-B -> Develop-B path. Further hardware work still requires
separate explicit authorization. Automatic MCU shutdown clear is **NOT
IMPLEMENTED**, and the original shutdown reason after an X2000 host reboot
**REQUIRES QUALIFICATION**. The complete coordinated Stock <-> Fre3nder
switching implementation remains separately scoped work.

The usable open-host and printing release question is now answered positively
for the investigated reference system: **`2026.1 FUNCTIONALLY ACHIEVED`**.
This does not qualify every peripheral or product feature. Display/touch,
camera, and ADXL/Input Shaping remain later work and are not 2026.1 release
blockers.

Before any subsequent Phase-3.3b implementation, hardware test, or change, the
session must begin with the public-state reproducibility audit defined in
[`x2000-ab-bringup-plan.md`](x2000-ab-bringup-plan.md). It must explicitly
classify the public repository as `PUBLIC STATE: REPRODUCIBLE` or `PUBLIC STATE:
INCOMPLETE`; a relevant documentation gap is closed before technical work
continues.

The deliberately separate operator-controlled A/B Slot-B path
`scripts/x2000-ab` is hardware-validated on the investigated reference system
for explicit p1 A -> B and B -> A selector changes. The existing automatic
B -> A one-shot Smoke and Network-Smoke paths remain the reproducible safety
and regression paths. The tool deliberately has no early automatic Stock-A
fallback. Normal Develop-B -> Develop-B reboot persistence is qualified on the
investigated reference system; an unreachable Mainline system still requires the
qualified external Ingenic USB / RAM-U-Boot p1 rollback.

### Further Phase-3 sequence

1. qualify the preferred uninterrupted Fre3nder -> Stock-A -> Stock-MCU
   handoff, including the original shutdown reason after an X2000 host reboot;
2. implement and qualify automatic MCU shutdown handling only if the observed
   shutdown state requires it; it is currently **NOT IMPLEMENTED**;
3. qualify a complete Stock <-> Fre3nder roundtrip with Stock A unchanged;
4. remaining peripheral and product integration, including display/touch,
   camera, ADXL/Input Shaping, Moonraker, and the user-facing UI stack; and
5. persistent deployment/update model.

Persistent deployment or further stock-return validation remains red-zone work
and requires separate explicit authorization. The F005 MCU image restoration
was qualified on 2026-08-27 as project-controlled recovery and regression
evidence; it does not qualify the currently failing software-only
Fre3nder-to-Stock ready path. The twice-observed power-cycle Stock recovery is
the current reference-device boundary.


## Phase 4 - Implementation

Develop all migration work reproducibly.

Prefer:

- source patches;
- documented build environments;
- scripts;
- deterministic configuration generation;
- explicit version pinning;
- automated validation.

Do not rely on undocumented manual edits to the production printer.

## Phase 5 - Controlled deployment

Deployment should proceed incrementally.

Suggested validation order:

1. host software starts without controlling heaters or motion;
2. Moonraker/API communication;
3. MCU connection;
4. temperature sensing;
5. fan outputs;
6. endstops and probe inputs;
7. low-risk motion;
8. homing;
9. bed probing;
10. heater safety;
11. extrusion;
12. calibration;
13. test print.

Rollback must remain available throughout testing.

## Phase 6 - Reproducible release

### Public project identity

Phase 6 publishes a reproducible release under the existing public project
identity.

The project identity is:

**Fre3nder**

*An open software platform for the Ender-3 V3 KE.*

The name combines `Free`, `Ender`, and the `3` of the Ender-3 / V3 platform.
The repository was originally developed under a descriptive working name.
Historical technical identifiers and evidence may retain names from that
period; they do not change the public project name.

The public README must clearly state that
Fre3nder is an independent open-source project and is not affiliated with or
endorsed by Creality, and must identify Ender and Ender-3 as trademarks of
their respective owner.

A successful project release should allow another Ender-3 V3 KE owner to:

1. inventory their printer;
2. verify hardware/firmware compatibility;
3. create and validate their own backup;
4. establish their own recovery path;
5. obtain required third-party artifacts from their original sources;
6. build the open software stack;
7. migrate in documented stages;
8. validate printer operation;
9. return to stock firmware if necessary.

No project release should require downloading another user's device backup or
factory identity data.

## Preserved X2000 architecture status and Phase-3 sequence

The following status table and phase sequence were recorded in the open-host architecture document before the 2026-09-23 documentation consolidation. They preserve the dated qualification scope and former planning language; consult current subject documents for the present contract.

### Architecture status record

- `PROVEN`: a reference-system observation or offline capture directly
  establishes the component/interface.
- `TARGET`: selected architecture, not yet implemented.
- `LIKELY`: an open path is technically indicated but needs Phase-3.2 kernel/DT
  feasibility evidence.
- `UNKNOWN`: required property not established.
- `DEFERRED`: not needed to make the Phase-3.2 decision now.

| Area | Status | Architecture consequence |
| --- | --- | --- |
| Main F005 path | PROVEN | Mainline Klipper communicates with the investigated F005 over `/dev/ttyS1` at 230400. Retain this contract; do not redesign it in Phase 3. |
| X2000 CPU, RAM, eMMC | PROVEN | An X2000 Linux appliance is the hardware target; the productive kernel is official Linux stable `v6.6.157` plus the ordered Fre3nder X2000 hardware-support patch series. |
| Lower boot chain | LIKELY | Preserve the existing pre-p1 loader boundary unless evidence requires replacement. Exact normal BootROM/SPL/U-Boot handoff remains UNKNOWN. |
| LTS kernel + DT | HARDWARE QUALIFIED (HOST BASELINE) | Official Linux stable `v6.6.157` plus the reproducible ordered Fre3nder X2000 patch series builds as `6.6.157-fre3nder` and boots on the investigated reference system. The `2026.3` qualification covers the exercised boot, network, and SSH path; it does not by itself re-qualify every peripheral or application flow. The former Ingenic 6.6.18/RT23 basis is retained only as migration provenance and historical qualification evidence. |
| Minimal Buildroot root filesystem | PERSISTENCE HARDWARE QUALIFIED | The bounded `2026.1.a` system runs its immutable Buildroot SquashFS RootFS from p8. The former single-volume `/persist` Development adapter was qualified through a normal Develop-B -> Develop-B reboot and is now superseded. The `2026.2` implementation resolves separate external ext4 filesystems labelled `FRE3NDERSYS` and `FRE3NDERHOME`, builds a writable root OverlayFS, exposes the immutable lower at `/rom`, and mounts userdata at `/home`. Normal persistence, the marker-authorized system reset retaining `/home`, and fail-closed degraded boots for missing or invalid system and userdata backends are qualified on the investigated reference system. |
| Network/SSH | PROVEN | The Production S20 -> S40 -> S50 path is hardware-validated on the investigated reference system: USB provisioning, CDC-NCM Ethernet-first operation, WLAN fallback, public-key login, and interactive SSH PTY allocation and shell operation all succeeded. The image embeds no user credentials. A persistent Dropbear host key was reused over a normal Develop-B -> Develop-B reboot and verified as both Dropbear's configured key and the key presented over SSH; SSH became available again afterward. This qualification is limited to the Development USB-adapter path; runtime/hotplug failover remains open. |
| Moonraker | NORMAL AND RECOVERY LIFECYCLE HARDWARE QUALIFIED | The RootFS build stages the pinned stable Git checkout under `/opt/fre3nder/moonraker` and a system-site-packages-enabled environment under `/opt/fre3nder/moonraker-env`. Persistent state remains in `/home`; PID/status/socket remain in `/run`. Runtime, Klippy/API, LAN-proxied HTTP, real WebSocket behavior, normal-reboot state retention, and OverlayFS baseline recovery are hardware-qualified on the investigated reference system. Self-update and automatic post-update restart are deferred beyond `2026.2`. |
| Display/touch | QUALIFIED ON DEVICE | The project DTS and RootFS provide the X2000 framebuffer/panel path, GPC22 active-high backlight, NS2009 I2C/evdev input, calibrated rotated touch mapping, 60-second standby/wake, and touch feedback. Physical framebuffer output, panel colors, automatic backlight startup, touch acceptance, and the GuppyScreen Core-UI are demonstrated on the investigated reference system. The current compact-layout pin was persistently deployed and qualified through normal printer control and a complete real print. |
| Camera | QUALIFIED ON DEVICE | On the investigated reference system, S63 selected the index-0 `uvcvideo` capture node, `mjpg_streamer` served JPEG only at `127.0.0.1:8080`, Lighttpd proxied `/webcam/`, Moonraker published the platform-owned webcam configuration, and Fluidd displayed the real camera image. The kernel and RootFS inputs were built and deployed. Automatic restart after inserting a camera that was absent during boot remains a separate QoL item. |
| Linux Host MCU / ADXL345 | INPUT SHAPING QUALIFIED ON DEVICE | On the investigated reference device, the complete chain through `/dev/spidev2.0`, Linux-process MCU, NumPy, `SHAPER_CALIBRATE` X/Y, the extended 100-Hz X sweep, and `SAVE_CONFIG` succeeded. The reference baseline is MZV at 62.4 Hz for X and MZV at 39.8 Hz for Y, with conservative `max_accel: 4500`; other printers require independent calibration. |
| BL24C16F | DEFERRED | It is not evidenced as necessary for the required open-host/ADXL path. Preserve rather than modify its data. |
| Update/rollback model | PROVEN / HARDWARE VALIDATED | The automatic p1 one-shot model proved bounded Slot-B boot and Stock-A return for `2026.1.a`; it remains the safety/regression path. The separate host-side operator tool is hardware-validated for explicit p1 A -> B and B -> A selector changes and has no automatic B -> A fallback. Normal Develop-B -> Develop-B reboot persistence is qualified on the investigated reference system. An unreachable Develop system relies on the qualified external Ingenic USB / RAM-U-Boot p1 rollback. Persistent updates remain unqualified. |
| Stock return | QUALIFIED PARTIAL / SOFTWARE-ONLY HANDOFF OPEN | Gate 1 is satisfied by the current evidence review. The documented full-device vendor recovery process remains execution-unverified and is not a guaranteed restore on the reference device. Fre3nder `FIRMWARE_RESTART` -> UART release -> exact bootloader identity is **QUALIFIED ON DEVICE**. The 2026-08-29 software-only handoff reached Stock A but ended with `Lost communication with MCU 'mcu'` and timeouts before ready, so it **REQUIRES QUALIFICATION**. Manual power-cycle recovery to Stock `Printer is ready` is **QUALIFIED ON DEVICE (2/2)** on the reference device. |

### Historical Phase-3 sequence

1. **3.1 Hardware + Boot Contract — complete.** Record only the REQUIRED
   interfaces and compatibility constraints in
   [x2000-hardware-contract.md](../../docs/x2000-hardware-contract.md).
2. **3.2 Kernel / Device-Tree feasibility — complete and superseded as a
   production-source decision.** The original bounded result in
   [x2000-kernel-dt-feasibility.md](x2000-kernel-dt-feasibility.md)
   selected the Ingenic 6.6.18 source for initial bring-up. The `2026.3`
   migration subsequently replaced that productive dependency with official
   Linux stable `v6.6.157` plus the ordered Fre3nder X2000 hardware-support
   series. The historical document remains evidence; NebulaOS remains prior art
   and explicit source provenance, not an adopted distribution.
3. **3.3 A/B bring-up qualification — complete for `2026.1.a`.** The selected
   Slot-B kernel/DT/rootfs, bounded network administration path, and one-shot
   return-to-Stock-A sequence are proven. The RAM-only prototype remains a
   deferred alternative.
4. **Separate manual Slot-B selection — HARDWARE VALIDATED.** The host-side
   `scripts/x2000-ab` tool intentionally has no
   automatic B -> A fallback and leaves the one-shot paths unchanged.
   Explicit p1 A -> B and B -> A selector changes are hardware-validated.
   Normal Develop-B -> Develop-B reboot persistence is qualified on the
   investigated reference system; loss of Mainline reachability remains an
   external-p1-rollback recovery case.
5. **3.4 Minimal Buildroot appliance — Production base hardware-validated.**
   The immutable USB-provisioned Ethernet-first/WLAN-fallback and public-key SSH
   path is implemented and proven on the investigated reference system. The
   RootFS deployment orchestrator and Development persistent SSH identity across
   a normal Develop-B -> Develop-B reboot are also hardware-validated. The
   `2026.2` persistence roles, reset behavior, and missing/invalid backend
   failure modes are hardware-qualified.
6. **3.5 Dual-mode MCU lifecycle — MCU transitions qualified, coordinated host
   roundtrip open.** Fre3nder identity gating, the exact Stock-MCU ->
   Fre3nder-MCU transition, passive UART release, exact bootloader identity, and
   the project-controlled Stock image update are qualified on device. Automatic
   shutdown clear is **NOT IMPLEMENTED**; the original shutdown reason after a
   host reboot and the preferred uninterrupted handoff remain **REQUIRES
   QUALIFICATION**.
7. **3.6 Klipper host integration and printer validation — QUALIFIED ON DEVICE.** Upstream Klippy
   with the passive UART patch, exact 88-command dictionary, complete
   configuration, ClockSync, target-zero heater/ADC telemetry, S60 gate, and
   writable input PTY are qualified on device. The 2026-08-29 complete
   Fre3nder-B print is also **QUALIFIED ON DEVICE**, making `2026.1`
   **FUNCTIONALLY ACHIEVED**. The loopback Moonraker runtime/service chain,
   built-in RootFS baseline, reboot persistence, and overlay-reset recovery are
   qualified for `2026.2`.
8. **3.7 Complete dual-mode roundtrip validation.** Qualify the Stock <->
   Fre3nder roundtrip with Stock A unchanged.
9. **3.8 Remaining peripheral and product integration.** Display/touch and the
   GuppyScreen Core-UI are **QUALIFIED ON DEVICE**, including persistent
   deployment of the current compact-layout pin and a complete real print. The
   open camera path through Fluidd is
   **QUALIFIED ON DEVICE**; automatic camera restart after a camera-absent boot
   remains a later QoL item. Moonraker overlay recovery, the LAN-facing product
   path, Fluidd printer control, and Fluidd uninstall are qualified. Moonraker
   self-update and automatic post-update restart are deferred beyond `2026.2`.
   SDIO WLAN itself is
   already proven by `2026.1.a`; production network lifecycle work belongs to
   the appliance/network path above rather than to remaining peripheral
   bring-up.
10. **3.9 Persistent deployment / update model.** Design and validate persistence,
   image activation, rollback, and configuration migration only after the
   preceding non-persistent result.

The display/UI, Moonraker recovery, persistence, and integrated user-facing
stack required by `2026.2` are qualified. Application self-update automation
remains later work and is not a `2026.2` release requirement.
