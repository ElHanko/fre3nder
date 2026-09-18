# Development-only Ingenic xImage diagnostic wrapper

This component isolates one boot-path variable for the X2000 clean-port
investigation. It wraps the freshly built upstream Linux `vmlinux` in the
Ingenic gzip decompressor and handoff used by the hardware-qualified `main`
build. It does not replace any clean-port kernel code, configuration, patch,
DTB, or toolchain input.

The wrapper source is derived from
`Llixuma/ingenic-linux-kernel6.6-x2000-v1.0-20250221` commit
`a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`, specifically
`arch/mips/boot/zcompressed/`. That source is Linux kernel material under
`GPL-2.0-only`; the repository's `LICENSES/GPL-2.0-only.txt` applies.

Only `Makefile`, `head.S`, `misc.c`, `ld.script`, and `dummy.c` are retained.
The build file takes the inner load address and kernel entry from the validated
input ELF instead of the Vendor Kconfig and its fragile `nm` helper. `misc.c`
uses the X2000 UART0 base directly because the upstream clean-port tree does
not contain the Vendor `soc/base.h`; decompression, argument preservation,
cache flush, and kernel handoff are otherwise retained. The shared
`lib/inflate.c` comes from the pinned upstream Linux v6.6.18 tree and is
byte-identical to the Vendor commit's copy.

The regular build continues to emit upstream `uzImage.bin`. This wrapper is
reachable only through the explicitly named development diagnostic command,
exports to `kernel-ximage-diagnostic/`, and is not hardware qualified.

## `main` reference boundary

The hardware-qualified `main` workflow builds its pinned Vendor kernel with
the `xImage dtbs` target and exports
`arch/mips/boot/compressed/xImage` as `kernel.uImage`. This diagnostic path
retains only the gzip decompressor, `a0`-`a3` preservation, XBurst cache flush,
ELF-derived handoff, and uncompressed legacy U-Boot envelope from that path.

It deliberately does not retain the Vendor kernel `vmlinux`, kernel
configuration, DTS, drivers, clocks, interrupts, cache implementation, RootFS,
or SDK toolchain. The payload remains the newly built pinned upstream v6.6.18
Clean Port with P01-P14, its XBurst2 port, SMP, two CPUs, current DTS, and the
normal Buildroot kernel toolchain.
