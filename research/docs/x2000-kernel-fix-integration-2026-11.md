# X2000 kernel fix integration, November 2026

Recorded on 2026-11-23 for the reference Ender-3 V3 KE and Fre3nder
`2026.6.a`. The four fixes are local commits on `fix/x2000-l2-dma-invalidation`,
based on `8d33ef3ad0e0c81770f449dea7eb899834cd5b8b`. The integration record
ends at `9d43d1d3f8540f6d7c93d7d1cfabd45141ee44c9`. The separate
[kernel audit](x2000-kernel-audit-2026-11.md) records the rejected candidates,
open issues and evidence for the observed freezes.

The operator identified the installed kernel as the **L2-only diagnostic
kernel**. The MSC, GPT and UART fixes were built and checked locally. The
four-fix image has no recorded device boot, print or deployment. The audit
did not query the printer. The local images are distinguished by their source
trees and hashes in [Build identities](#build-identities).

## L2 and DMA invalidation

Commit `9996a96c19e98f40ec81da9ec02f17dae0e432bc`, 2026-11-22.

In `arch/mips/xburst2/core/sc.c`, `mips_sc_inv()` is the XBurst-II secondary
cache `bc_inv` operation. In the noncoherent DMA path, MIPS R4K cache code
performs primary-cache maintenance and calls `bc_inv()` for the secondary
cache. For ranges smaller than the L2, `mips_sc_inv()` writes back and
invalidates the boundary lines with `Hit_Writeback_Inv_SD`, then invalidates
the range. The SDK ended this sequence with `__fast_iob()` but had no matching
pre-read in this branch. An earlier access still in flight when hit-based
maintenance starts can undermine DMA visibility. This is an ordering
hypothesis for stale or inconsistent data, including when either Linux CPU
executes the sequence on the shared L2. It is not a measured X2000 erratum.

Fre3nder inserts `__fast_iob()` immediately before the first Hit operation.
On this MIPS build it issues an uncached `lw` to `$zero` through `CKSEG1`,
with a compiler memory clobber. The pre-read gives earlier transactions a
completion point before maintenance. The post-read and the whole-cache
index-based branch retain their original sequences. The change provides no
new CPU-to-CPU exclusion and does not change the DMA API's cache-ownership
contract. NebulaOS uses a different precaution in the same function. It adds
`__sync()` before choosing either range or whole-cache invalidation. A `sync`
and an uncached read are different mechanisms, so the two changes must be
compared at the instruction and bus-ordering level. The SDK's
`mips_sc_wback_inv()` already uses a leading `__sync()` and trailing
`__fast_iob()`.
[Original SDK reader](https://github.com/Llixuma/ingenic-linux-kernel6.6-x2000-v1.0-20250221/blob/a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b/kernel/kernel-6.6/arch/mips/xburst2/core/sc.c#L43-L66),
[NebulaOS reader](https://github.com/NebulaOS-KE/NebulaOS-kernel/blob/1e6ab35fc75758397e1ef69b2834b699e149aaba/kernel/kernel-6.6/arch/mips/xburst2/core/sc.c#L43-L70),
[Fre3nder platform patch](../../patches/kernel/0001-x2000-platform.patch#L3237).

The ordering change is technically motivated. The L2-only image is an
ongoing hardware diagnostic, with no recorded A/B result proving that the
change removes the full Linux freezes. The retained manifest and payload
support the build identity. The current integration ELF also permits static
inspection of `mips_sc_inv()`. Neither check establishes peripheral ordering
or sustained DMA behavior on the silicon.

## MSC clock register

Commit `87527bf28a3f7c4b5f1352cac90808bff5260070`, 2026-11-23.

`module_drivers/drivers/mmc/host/sdhci-ingenic.c` maps the controller's
`host->ioaddr` to `cpm_msc` in `sdhci_ingenic_get_cpm_msc()`. On X2000 the
eMMC host MSC0 at physical `0x13450000` maps to `CPM_MSC0_CLK_R`
(`0xb0000068`). The WLAN/SDIO host MSC1 at `0x13460000` maps to
`CPM_MSC1_CLK_R` (`0xb00000a4`). The disabled MSC2 maps to `0xb00000a8`.
`sdhci_ingenic_set_clock()` used the correct instance to select `ext` at a
nonzero request of up to 400 kHz, then wrote bit 21 to `0xb0000068`
regardless of the host. It now uses the existing instance value:

```c
*(volatile unsigned int *)cpm_msc |= 1 << 21;
```

MSC1 identification can now program its own clock without changing the
eMMC register. MSC0 receives the same bit update as before. The zero-clock
exit, the MPLL path above 400 kHz and the existing phase and divider handling
are preserved. The defect was an instance-specific register write in an
active initialization path. Improved WLAN enumeration or eMMC stability on
the reference device has yet to be measured for this image. The one-line
port follows OpenKE/NebulaOS. The rest of its WLAN changes were outside this
fix. [OpenKE MSC correction](https://github.com/coreflake1/NebulaOS-kernel/commit/858509a4a0387d4f181a01e3679213b93bbd6863),
[NebulaOS comparison pin](https://github.com/NebulaOS-KE/NebulaOS-kernel/blob/1e6ab35fc75758397e1ef69b2834b699e149aaba/kernel/kernel-6.6/module_drivers/drivers/mmc/host/sdhci-ingenic.c#L150-L173).

## GPT partition size

Commit `cd6246f6f339ec6f3e08e52cdbeefb68c84bbcfa`, 2026-11-23.

The retained Ingenic fallback in `block/partitions/efi.c`, `efi_partition()`,
adjusts a GPT entry with an all-ones or oversized end LBA after checking the
table. It had two representations of the end. It rewrote the in-memory entry
while `size` still used the earlier decoded `end`. A valid adjusted entry
could then reach `put_partition()` with a wrapped or oversized length. The
backport first sets `end = disk_size - 1`, stores it as
`cpu_to_le64(end)`, and uses that same CPU-order value for the size. It
rejects `start > end` and an invalid entry before subtracting. For valid
entries, `size = end - start + 1` describes the inclusive range. No on-disk
GPT write is involved.

K1 Debian's Ingenic fix `35fd77723d76af8c5442766da66b7dada71b8b5a` reloads
`end` after writing the in-memory field. It still assigns the field in
native byte order and can calculate an unsigned length for an inverted
range. Fre3nder preserves the existing trigger and physical end limit while
addressing both issues. The inherited mismatch between `get_capacity()`
units and GPT logical LBAs on 4Kn, and the difference between the physical
last LBA and `last_usable_lba`, are tracked in the
[audit](x2000-kernel-audit-2026-11.md#open-findings).
[Ingenic GPT fix in K1 Debian](https://github.com/k1-debian/linux/commit/35fd77723d76af8c5442766da66b7dada71b8b5a).

The retained fixture log records **14 passing synthetic GPT images**. The
host harness ran the actual pre-fix and candidate parsers against simulated
block I/O. The units below are the sectors reported to `put_partition()`.
Passing a boundary case can mean that the parser correctly rejected the
entry or reproduced an explicitly recorded remaining limitation.

| Fixture | Recorded result |
| --- | --- |
| Valid 512-byte sectors | Start 40, length 60 in both parsers. |
| All-ones end | Adjusted end 255, start 40, length 216. Previous length wrapped to `18446744073709551576`. |
| End beyond capacity | Adjusted end 255, start 40, length 216. Previous length was 261. |
| Start after the adjusted end | No partition published. |
| End at the physical last LBA | Start 255, length 1, accepted by the existing policy. |
| End equal to capacity | No partition published. The fallback uses strict `>` and later validation rejects the entry. |
| Inverted in-bounds range | Rejected. Previous length wrapped to `18446744073709551607`. |
| End at the last usable GPT LBA | Start 222, length 1. |
| Invalid GPT header CRC | No table accepted. |
| Invalid entry-array CRC | No table accepted. |
| Empty disk | No table accepted. |
| Valid 4Kn table | Start 320, length 480 in 512-byte output sectors. |
| 4Kn end beyond the last logical LBA | No partition published. |
| 4Kn all-ones end | Adjustment to 2047 followed by rejection, demonstrating the remaining units issue. |

## UART synchronization

Commit `9d43d1d3f8540f6d7c93d7d1cfabd45141ee44c9`, 2026-11-23.

The effective board uses the Ingenic driver on UART1 at `0x10031000`, with
PC23/PC24 TX/RX and the passive Klipper MCU session on `/dev/ttyS1` at
230400 baud, 8N1 and no hardware flow control. The DTB has no `dma-mode`
for this port. The kernel uses PIO, two XBurst-II hardware threads and
`CONFIG_PREEMPT=y` without `PREEMPT_RT`. `CONFIG_SERIAL_8250` is unset.
The PIO handler normally runs as a hard IRQ with local IRQs masked. The
other hardware thread can still use the same Serial-Core port concurrently.
[KE hardware contract](../../docs/x2000-hardware-contract.md),
[7.3.4 board adaptation](../../patches/kernel/0005-x2000-board.patch).

- **TX and flush.** The old `transmit_chars()` could see an empty queue on
  one CPU. The writer on the second CPU could then enqueue and observe
  `THRI` still set in `start_tx()`. The IRQ could clear `THRI` after that,
  leaving data queued until another kick or suitable interrupt. A concurrent
  `uart_flush_buffer()` could reset both `kfifo` indices while the IRQ was
  advancing `out`. Fre3nder already uses `kfifo` through the generic Serial
  Core and has no Ingenic-specific `.flush_buffer` callback. Both
  interleavings are now serialized by the same port lock.
- **PIO RX, modem and termios.** After `IIR_NO_INT` handling, the driver
  takes the port lock with IRQ saving before reading the initial LSR. RX
  consumes that sample, including its error bits, and returns the last LSR
  for the TX decision. Modem-status handling meets the lock requirement of
  `uart_handle_cts_change()`. The initial termios LCR write now falls inside
  the existing lock, preventing PIO access to TX/IER while DLAB aliases
  those addresses to DLL/DLM. The baud calculation and 8N1 programming are
  preserved. The DMA entry and its RX helper keep their own lock boundaries.
- **SysRq.** `uart_prepare_sysrq_char()` records the character under the
  lock. `uart_unlock_and_check_sysrq_irqrestore()` releases the lock,
  restores the incoming IRQ state and then dispatches the character. This
  permits synchronous console output without trying to reacquire the
  currently held port lock. The option is compiled in. Serial BREAK arms
  this path only on the selected console port.
- **Console.** The regular writer takes the IRQ-saving port lock. In Oops
  and Panic it tries the lock once and skips that output on failure. The
  trylock API restores IRQ flags on failure and there is no register access
  or unlock in that case. Success masks THRI temporarily and restores the
  **actual hardware IER** after the existing polling and transmit wait,
  without changing the IER shadow. Routine legacy `printk` already masks
  local IRQs around the writer in this non-RT kernel. The documented
  `console=ttyS4` would find UART4 disabled in the compiled DTB. The active
  runtime console list and early-polled UART selection were not captured.

NebulaOS A introduced IRQ saving and an Oops trylock. Its failed-trylock
path still writes the UART and updates the IER shadow, and it sets THRI
unconditionally at the end. Fre3nder skips the contended output to preserve
register and IRQ state. NebulaOS B places the PIO work under the lock and
defers SysRq, but samples LSR before taking the lock and uses `circ_buf`.
Fre3nder keeps the 7.3.4 FIFO API and uses a locked initial LSR plus the
latest RX status. The 7.3.4 Upstream 8250 IRQ already uses a SysRq-aware port
lock and a locked LSR. Its console uses nbcon, which is a different
implementation from the Ingenic legacy writer. These fixes address
demonstrated UART races. A UART stall can interrupt MCU traffic, but the
audits did not identify a UART path as the cause of the observed full Linux
freezes. [NebulaOS A](https://github.com/NebulaOS-KE/NebulaOS-kernel/commit/bc785d6ff8780a1572ab16edb7147d3d01de63a9),
[NebulaOS B](https://github.com/NebulaOS-KE/NebulaOS-kernel/commit/73422bd7a8e0a14da0b8a901a2473770996bc0d7),
[Upstream 8250](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/tty/serial/8250/8250_port.c?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d).

## Build identities

All four commits change only `0001-x2000-platform.patch` and the resulting
patch hash and tree pin in [`sources.json`](../../configs/x2000/sources.json).
The series starts at Linux `7.3.4` commit
`7595a62d45ee1a2297eafa5f2ef5d0a45142d84d`, tree
`d07c331ebf5acbde9ebf9caea9eac6e33b07ad77`. The five ordered patches are
platform, display, touchscreen, WLAN and board. The other four patch hashes
are identical across these four commits. The prefix sources and license
assignments are recorded in the [audit](x2000-kernel-audit-2026-11.md#source-references)
and the [licensing policy](../../docs/licensing-and-provenance.md).

| State | Platform patch SHA-256 | Kernel result tree | `kernel.uImage` SHA-256 |
| --- | --- | --- | --- |
| L2 diagnostic, `9996a96c` | `e58bf202aacde3dd17281e67565ae23f8b2ef088e93428acf1c64ffdb01b0dc8` | `a8b66921b21b3812b26760db222d6f3a9e7363a6` | `d94b049abcba0616290292492202f3fe70951d288be7c33bb73038418a382c84` |
| With MSC, `87527bf` | `be7eb5e47680b3b79c6d4d49034ac61ab959be76aa6fb9caf9326e9c377aa48d` | `ecd479391920f702f0fd1998b136fec50d3b141a` | `c17c4c5da708c2cc2f8d3b40d1a4a88e63b22d46b635acd1b44829755d134ead` |
| With GPT, `cd6246f6` | `e0ebe0254ea508de50de7034b1444ee57b7fc1846a431710de3e6598056f478a` | `0b5b17b023eb316b869cb490e1535d8d2425b5a1` | `de9614a45188936f347f142eb83f25b0c0d83cd72bdb4de6b83ca0d54045e68c` |
| With UART, `9d43d1d3` | `d0f40144a342aacf1b3546155654c1c0c7b8884e329d6ecb89ed1ed20921d47e` | `7abdbf56ee232e7e789e7183ff98b7a2b12ec1a6` | `ce10024c673df54c99295f8102adc721bc38747c362b392cae58a08cd93c65d4` |

The retained MSC and GPT manifests supply their image hashes. The historical
payload files for those two intermediate states were not retained with them.
The L2 image hash was checked against the local payload in the composed
`full` artifact and the retained L2 kernel-only manifest. The composed
manifest carries older project metadata at the top level. Its kernel
component fingerprint `cfc9fec6f857076b377123bb5113ecfc8d0c4fed8b0aa5f73086cfa194313310`
and payload hash match the L2 build. They identify the local artifact. The
installed state is the operator's report.

The final kernel-only manifest records the pre-commit GPT HEAD with a dirty
worktree, because the UART image was built before committing the change. The
embedded kernel pins match the completed UART commit. The snapshot input
fingerprint is `a7c5baaeec1aeb775fd1aced855682857e34fce146d841e5fb311a94c8a5f273`.
All four manifests record the same effective `.config` SHA-256
`9b06d83d95909ed88b4c54299bdad2d1627cb1dd50b284b06e96f6de9b9a238b` and
the same `ender3-v3-ke.dtb` SHA-256
`715109777440d0178715f0abce6bcbd18a4c4bdf954744e4f9311da4c1e0647f`.
The final image is 5,947,456 bytes. Its verified U-Boot header CRC is
`0x10611bd8` and its data CRC is `0xeefe000c`. The final manifest, image,
DTB and configuration passed `SHA256SUMS`. The DTB matches the bytes in
the linked `vmlinux`. [Artifact format and paths](../../docs/build.md#partial-builds-and-reuse).

## Validation and evidence

| Fix | Commit | Offline tests | Kernel build | Hardware test | Status |
| --- | --- | --- | --- | --- | --- |
| L2/DMA | `9996a96c` | Narrow cache-maintenance diff, pinned tree and payload identity checked. | Development kernel image evidenced by the retained manifest and matching composed payload. | L2-only diagnostic installed per operator. Endurance result and causal attribution open. | Integrated, hardware diagnosis in progress. |
| MSC clock | `87527bf` | Reviewed both MMIO/CPM mappings and replayed the series. The only kernel-tree delta was `sdhci-ingenic.c`. | Kernel-only Development PASS in 4:10. Effective config and DTB match the L2 build. | Open. | Integrated locally. |
| GPT size | `cd6246f6` | Fourteen synthetic images passed on the real parser with simulated I/O. Buildroot and wrapper fixtures passed. Replay isolated `efi.c`. | Kernel-only Development PASS in 4:03. Manifest and checksums recorded. | Open. | Integrated locally. |
| UART locking | `9d43d1d3` | Seven UART scenarios in each of three SysRq variants. MIPS syntax checks, Buildroot and wrapper fixtures and 42 additional Python tests passed. Replay isolated `ingenic_uart.c`. | Kernel-only Development PASS in 4:03. Five patch hashes, result tree, manifest, image CRCs and checksums verified. | Open, including Klipper and long-print tests. | Integrated locally. |

The MSC, GPT and UART build logs show the same 28 DT decompilation
warning messages. GPT and UART also show the same 284 other warning lines
after normalizing moved source line numbers. The Ingenic UART init/exit
prototype warnings predate the locking changes. The retained L2 snapshot
contains the DT warnings. It does not provide a complete compiler-warning
baseline for the MSC build.

The UART harness extracted the real driver functions and used simulated
MMIO and Serial-Core state. It forced concurrent empty-check/enqueue and
dequeue/flush, and checked initial LSR errors, final THRE, CTS callbacks,
`IRQ_NONE`, SysRq reentry after unlocking, successful and failed console
trylock, IER/IRQ restoration, DMA lock boundaries and the 230400/8N1 termios
register sequence. The three modes were production SysRq, Serial-Core SysRq
with Ingenic SysRq off, and both off. A syntax-only pass compiled the full
driver with the captured MIPS Kbuild flags in all three modes. In the linked
ELF, `serial_ingenic_irq()` takes the lock before the LSR/MSR accesses and
branches to `handle_sysrq()` after unlocking. The console's failed-trylock
path returns with IRQ flags restored before MMIO and termios acquires its
lock before the first LCR write. The additional Python groups ran 11 build
logging, 21 Klipper and 10 F005 bootloader fixture tests.
[Buildroot architecture test](../../tests/test-x2000-buildroot),
[Wrapper test](../../tests/test-x2000-build-wrappers),
[Build logging test](../../tests/test_x2000_build_logging.py),
[Klipper test](../../tests/test_x2000_klipper.py),
[F005 test](../../tests/test_f005_bootloader.py).

The original test logs, fixtures and disassemblies were local validation
material. This record preserves the observed outcomes and ties them to commits
and artifact identities. The documentation revision rechecked the available
records and artifacts. It did not rerun the target builds or regression tests.
Offline results cover the modeled behavior. Board timing, live data integrity
and endurance remain hardware questions.
