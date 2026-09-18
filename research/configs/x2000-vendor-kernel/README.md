# Historical X2000 vendor-kernel production inputs

These files are the final inputs used by Fre3nder's former productive Ingenic
vendor-kernel path. They were moved here after the upstream Linux v6.6.18 clean
port became the productive kernel input. Nothing under this directory is part
of a productive build.

The historical source basis was the public
`Llixuma/ingenic-linux-kernel6.6-x2000-v1.0-20250221` mirror at commit
`a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`, with kernel release
`6.6.18-rt23`. Before the move, all five files lived under `configs/x2000/`.

Their current clean-port replacements are:

| Historical input | Current production replacement |
| --- | --- |
| `kernel.fragment` | `configs/x2000/kernel-clean-port.defconfig` |
| `ender3-v3-ke.dts` | board support carried primarily by P06, with later subsystem patches completing the clean bindings |
| `ke-wlan.patch` | generic board data in P06 and X2000 SDHCI support in P07; the vendor manual-insertion workaround was intentionally not ported |
| `ke-touch.patch` | NS2009 support in P11 and board data in P06 |
| `ke-display.patch` | X2000 DPU support in P13 and the KE panel support in P14, with board data in P06 |

The historical hardware results remain evidence for the investigated reference
system and for the board requirements carried into the clean port. They do not
qualify the current clean-port kernel, which has completed offline integration
but has not yet been hardware-qualified.
