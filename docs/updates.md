# Updating the Fre3nder platform

The current update workflow is the explicit `fre3nder ota` CLI sequence below.
It targets the inactive X2000 Kernel/RootFS pair, retains HOME and prepares a
target-specific SYS-overlay reset. It never silently updates F005 firmware.
This implemented workflow does not establish complete end-to-end hardware
qualification for a new release; see [OTA qualification](ota.md#qualification-boundary).

## Prerequisites

Use a signed `.ota` for the intended platform and installed trust anchor. Stage
it below `/ota/packages/` using the existing administrative access path. Work as
root on a healthy writable Fre3nder runtime; confirm
`/run/fre3nder-root/status` is `active`, preserve required network/SSH access,
and do not update while printing or intentionally heating. Inspect
[version/provenance](build.md#inspect-the-artifacts), current F005 state and any
explicit Stock auto-transition opt-in before an authorized reboot.

Development artifacts are not releases or hardware qualifications. Release
builds require clean, committed inputs; development mode carries a fingerprint.
Check `artifact_mode`, component provenance and hashes. A reused Kernel and new
RootFS must agree on version and artifact mode; composition enforces both.
The 2026.4 release scope is **Managed Platform** (`managed-platform`).

## Update sequence

The same manual workflow is available under **System Updates** on an explicitly
enabled Maintenance listener at `http://<printer-host>:8081/`. Pair the browser
using `fre3nder maintenance unlock`. Upload a local signed `.ota` (maximum
96 MiB); the platform publishes it under `/ota/packages/` and verifies it through
OTA-Core. **Upload and verify** automatically waits for verification and runs
technical preflight. A staged package has one **Check package** action. The page
shows upload, verification and compatibility results, both versions and slots,
HOME preservation and SYS reset. Matching version labels do not prohibit an
update or establish identical binaries. With `artifact_mode: development`, both
the page and confirmation explain that builds may differ despite matching
versions. Release packages and unavailable/unknown modes use a neutral notice
that the selected package will be installed again.

Choose HOME and SYS explicitly from the Core backup offer. **Update Fre3nder**
asks once for approval of the displayed versions, slots, backup choices, SYS
reset, Kernel/RootFS writes, activation and restart. An explicit backup decline
is called out in that confirmation. Only after approval does the browser invoke
`backup-plan`, `backup`, `confirm`, `write`, `readback`, `prepare-activation` and
`reboot`, waiting for each result while the connection remains available. Both
`none` still invokes OTA `backup` to create
the Core transaction without archives. Selected archives are created and
verified before any write; staged OTA packages remain excluded from SYS backups.

Completed phases retain their status; only upload uses byte-based percentages.
Errors stop further submissions without automatic retries. Reload restores the
session and actual Core/execution state, then offers **Continue update** when
safe. Continuation requires a new explicit confirmation and starts at the next
Core phase, without repeating completed writes or backups. Unknown executions
remain blocked for operator inspection. Non-destructive package checks can be
retried separately.

A small per-tab browser receipt stores package/transaction identity, backup
choices and the reboot request outcome, never credentials or permission to
resume automatically. Progress ends at successful activation preparation. The
browser prepares a dedicated **REBOOT** view before submitting the restart
request, initially without claiming acceptance. A successful Core reboot result
shows **Printer restart requested**. Explicit request or Core rejection returns
to the error/continuation flow. A lost connection or otherwise unconfirmed result
shows **Printer restart status unclear**, asking the user to inspect the printer
without treating the update as failed or claiming reboot acceptance.

The browser stops polling when the reboot result is confirmed or unclear. The
final view remains visible on disconnect and is restored on reload when the
per-tab receipt is available; an interrupted pending request becomes unclear.
Reload repeats no operation. The page does not require Maintenance to return or
a new pairing session. It asks the user to verify normal Fre3nder startup,
display operation and printer reconnection, and states that the final boot result
cannot be verified from this page. Core postboot validation and known-good
recording remain independent and unchanged. Closing the tab or losing its
receipt loses the browser's final view; it does not affect Core state.
See [Management OTA API](api/management.md#manual-ota-endpoints) for upload storage,
authorization and interrupted-execution behavior. The selected frontend on
port 80 has no management route.

Use one package throughout. `<transaction-id>` is the opaque value returned by
the successful OTA `backup` step; copy it unchanged, rather than constructing
or parsing an ID. Commands and their individual effects are in the
[CLI reference](api/cli.md#ota).

1. `fre3nder ota verify <package.ota>` checks container, signature, trust and
   payload identity.
2. `fre3nder ota preflight <package.ota>` checks runtime, inactive targets,
   persistence and available backup destinations without writing system slots.
3. Choose HOME/SYS explicitly. For example,
   `fre3nder ota backup-plan <package.ota> --home --sys usb` validates a plan;
   `fre3nder ota backup <package.ota> --home --sys usb` executes and verifies it
   and creates the pending transaction. Available alternatives are `--no-home`
   and either `--sys home` or `--no-sys`; satisfy the OTA-specific selection
   policy shown by preflight. A plan alone does not create a transaction.
4. `fre3nder ota confirm <package.ota> <transaction-id>` rechecks bindings and
   archives and records confirmation. It still does not write system slots.
5. After explicit authorization,
   `fre3nder ota write <package.ota> <transaction-id>` validates actual inactive
   partition identity and writes RootFS and Kernel. The active pair is retained.
6. `fre3nder ota readback <package.ota> <transaction-id>` verifies the written
   payloads; do not infer readback success from the preceding write result.
7. `fre3nder ota prepare-activation <package.ota> <transaction-id>` rechecks
   package, backups and target bytes, writes persistent handoff/reset records,
   then changes and verifies the boot selector. This changes the selected slot
   but does not itself reboot.
8. `fre3nder ota reboot <transaction-id>` separately validates the prepared
   activation and requests reboot. The connection/process may end before an
   answer is observable.

The source of truth for required backup choices, error states and transaction
binding is [OTA](ota.md), with archive behavior in [backup](backup.md). Do not
bypass failed guards or edit transaction/activation files to advance a step.

## After reboot and on failure

The intended target consumes its targeted SYS reset, exposes the immutable
baseline and keeps HOME. The startup postboot integration validates the active
slot and persistence contract and records the known-good handoff. It is internal;
there is no public `fre3nder ota postboot` command. Check actual runtime/version,
services and the responsible [diagnostic sources](troubleshooting.md#ota-is-blocked).

A nonzero exit is not a general rollback guarantee. Failure after a write or
selector change can leave partial effects; stop and retain evidence. Automatic
failed-boot rollback and a general Stock restoration flow are not implied by
this sequence. Use [recovery](recovery.md) within its documented authorization
and qualification boundary. F005 updates remain the separate
[MCU workflow](f005-mcu-switching.md).
