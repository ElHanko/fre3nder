# Recovery and return to Stock

This guide selects the existing recovery route for the investigated reference
Ender-3 V3 KE. Check the target board revision, storage layout, firmware and
preserved artifacts before applying it to another device. Gate 1 / Point of
Return is satisfied for the reference system, but a printer write, selector
change, MCU flash, reboot, or destructive restore still requires explicit
operator authorization under [`AGENTS.md`](../AGENTS.md).

The normal [`fre3nder backup create`](backup.md#create-and-check-a-backup)
archives HOME and SYS only. It is useful for user and system customizations,
but does not by itself satisfy Point-of-Return: that also depends on the
preserved Stock and recovery material, protected factory identity, eMMC boot
configuration, and offline validation recorded in the
[reference-system recovery evidence](../research/docs/recovery-validation-plan.md).

## Decide which state is still reachable

| State | Next path | Established limit |
| --- | --- | --- |
| Fre3nder Linux and SSH work | Preflight the inactive-slot Stock pair, then plan the separate MCU and host activation | `deploy-x2000 --stock` stages only; it does not complete return |
| Linux is unreachable but the known other A/B slot should still boot | Review the external Ingenic USB/RAM-U-Boot p1 selector fallback | Qualified only for a bounded p1 roundtrip, not a general restore |
| No usable Linux slot remains | Use the archived official KE `.ingenic` material with Creality's Windows/Cloner procedure | Vendor-documented and material-validated; full execution remains unverified on this device |

First preserve the observed failure and identify the actual active payload,
selector, and MCU identity where access remains possible. `STOCK_A` and
`DEVELOP_B` are historical selector-pattern names; they do not prove what a
slot contains. Do not select a slot solely from its name. The
[storage layout](storage-layout.md) maps A to p5/p7 and B to p6/p8.

## If Fre3nder is running

1. Verify the local Stock backup set and its `SHA256SUMS`. The default staging
   directory is `local/backup/stock/image/` and must contain full-partition
   `p5.img` and `p7.img` files. Keep device-specific backups outside Git.
2. From the repository root, use the read-only host preflight:

   ```sh
   scripts/deploy-x2000 <printer-host> --stock
   ```

   It requires Slot B active and the selector pointing to B, checks the exact
   p5/p7 targets, and validates the local files. A refusal means the stated
   preconditions have not been established; stop and inspect that mismatch.
3. In a separately authorized return sequence, `--stock --write` can stage and
   read back p5/p7. It leaves the selector, current boot, p9/p10, and F005 MCU
   unchanged. Coordinate the MCU with the Stock host **before** activation.
   The supported MCU identities and proven transition legs are in
   [F005 switching](f005-mcu-switching.md).
4. Activate and verify the intended Stock host and matching Stock MCU through
   the concrete operator-approved sequence. Require Stock Klipper to reach
   `Printer is ready`. A host boot alone does not prove a usable Stock printer:
   the historical Mainline-MCU/Stock-host mismatch produced
   `read_swap_prtouch` and a Stock error.

The software-only Fre3nder-to-Stock host handoff still **REQUIRES
QUALIFICATION**. A manual power-cycle return reached Stock `Printer is ready`
twice on the reference system. The project has no single qualified public
command that performs the entire Stock return, including the MCU and host
transition. Do not treat Stock staging or a selector change as that command.

## If normal Linux cannot boot

The external BootROM USB route can reach the X2000 without normal Linux. The
separate public Ingenic USB/RAM-U-Boot path has been confirmed on the reference
board only for a bounded p1 selector A -> B -> A readback test. Use
[`scripts/x2000-usb-selector-to-a`](../scripts/x2000-usb-selector-to-a) only
within an explicitly authorized plan that verifies the intended A-side
payload. It does not repair a missing or invalid Kernel/RootFS.

For a damaged system that needs full vendor restoration, Creality documents an
Ender-3 V3 KE Windows/Cloner route using the board's existing MicroUSB,
Boot/Reset buttons, official driver/tool, and the exact KE `.ingenic` recovery
image. Preserve and verify the vendor package and the complete backup set
before following the official procedure. The Boot/Reset entry was confirmed to
enumerate as `Ingenic USB BOOT DEVICE` / X2000 on the reference board without
writing.
The complete destructive Cloner restore was **not** executed there; it is a
documented route with residual uncertainty, including erased p1, partial p10
erasure, and first-boot recreation of p9/p10. Protect factory identity data
and do not substitute another model's image.

The exact official package, erase map, expected first-boot effects, protected
data, and unresolved selector risk are preserved in the
[recovery evidence record](../research/docs/recovery-current-state.md).
The [Phase-1 recovery validation record](../research/docs/recovery-validation-plan.md)
contains the vendor procedure reference and the non-writing USB entry test.
The project's private Linux RAM-only recovery client stopped before Stage 2
and is **not** an established restore path.

## After recovery

Check the booted slot/root, exact F005 identity, Stock or Fre3nder service
readiness, network/SSH access where expected, and preservation of factory
identity. Compare any restored user configuration with the separately retained
backup. Treat the historical qualification and limitations in the
[evidence record](../research/docs/recovery-current-state.md) as scoped to
the investigated reference system.
