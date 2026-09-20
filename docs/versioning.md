# Public release versioning

This project does not use SemVer. Public releases use `YEAR.RELEASE[.STAGE]`.
`YEAR` is the calendar-year line and `RELEASE` is its numeric public counter,
restarting at 1 each year. The only optional stages are `a` (alpha), `b` (beta),
and `rc` (release candidate); no suffix is a final release. There are no extra
components such as `a1`, `rc2`, or patch-level versions. The canonical spelling
uses a four-digit nonzero year and a positive release number without leading
zeroes.

The repository-root [`VERSION`](../VERSION) file is the canonical source of the
project version. Release tags use exactly that version number, without a `v`
prefix. The first final release version is `2026.1`. Setting or changing
`VERSION` does not by itself create a Git tag or GitHub release.

Repository-root [`CHANGELOG.md`](../CHANGELOG.md) records user-visible and
architecturally relevant release changes. Current technical behavior remains in
the subject-specific documentation. Temporary requirement and qualification
documents may be removed after their release evidence has been incorporated
into those durable locations.

Build manifests record the canonical `version`, numeric `release_year` and
`release_number`, the normalized `release_stage` (`alpha`, `beta`, `rc`, or
`final`), and `release_scope`. Built RootFS images expose the same canonical
project version in `/usr/share/fre3nder/VERSION`.

Within a release line, the structured order is alpha, beta, release candidate,
then final. Year and release number are numeric; consumers must not compare
version strings lexicographically.

The first release target is `2026.1`, scope ID
`first-printable-networked-open-host`, titled **First printable networked
open-host release**. A final `2026.1` means this scope is complete, not that the
whole roadmap or Gate 1 is complete. It requires reliable open-host boot,
required SMP/CPU and filesystem operation, at least one qualified administrative
network path, stable IP configuration, reliable SSH administration, persistent SSH
host identity, and network/SSH usable after normal reboot, and a reliable real
Mainline-F005 print without stock Klippy. The current hardware-validated
Production path uses an external AX88179B/CDC-NCM Ethernet adapter first and
provisioned SDIO WLAN as boot-time fallback.

Moonraker, Mainsail, local display/touch, camera, ADXL/Input Shaper, Bluetooth,
a consumer installer, automatic updates, and hardware-validated stock return are
outside `2026.1`. Network plus SSH is not optional: a printable but unreachable
host fails this scope.

## Current functional milestone

**`2026.1.a` achieved: 2026-08-23.** This is the historical first functional alpha of the
open X2000 host on the investigated reference system. It directly proves Linux
6.6.18-rt23 booting from Slot B (p6/p8), a read-only SquashFS RootFS on p8,
working userspace and eMMC, SDIO WLAN (`BCM43430/1`), WPA, DHCP, Dropbear,
public-key SSH, non-interactive remote commands, and the early p1 B -> A
rollback while Mainline continues from p8. The detailed evidence is in
[`x2000-ab-bringup-plan.md`](../research/docs/x2000-ab-bringup-plan.md).

The subsequent Production candidate also proves USB provisioning,
Ethernet-first/WLAN-fallback operation, volatile Dropbear host-key generation,
and public-key SSH on the investigated reference system. A subsequent read-only
qualification additionally proves interactive SSH PTY allocation and shell
operation. A later Development candidate qualified the now-superseded
`/persist/system` and `/persist/userdata` adapter, persistent Dropbear host
identity across a normal
Develop-B -> Develop-B reboot, and SSH administration becoming available again
after that reboot on the investigated reference system. The same persistent key
was verified as both Dropbear's configured key and the key presented over SSH.

**`2026.1 FUNCTIONALLY ACHIEVED: 2026-08-29.`** The complete Fre3nder-B print
without Stock Klippy finished successfully on the investigated reference device.
It ran with the then-unmodified 1.900 image configuration plus temporary
`SET_GCODE_OFFSET Z=-0.280`, establishing the effective 2.180 probe offset;
the separate tracked configuration now records `z_offset: 2.180`, **QUALIFIED
ON DEVICE** for that reference device. The complete Stock/Fre3nder roundtrip is
not a 2026.1 release blocker: the software-only Fre3nder-to-Stock handoff still
**REQUIRES QUALIFICATION**, while manual power-cycle recovery is qualified on
the reference device. General persistent configuration and runtime/hotplug
network failover likewise remain later work. Persistent SSH identity and normal
reboot with SSH are qualified only on the investigated Development USB-adapter
Develop-B -> Develop-B path.

The functionally achieved milestone was initially recorded as a
project/development milestone. The final `2026.1` tag was subsequently created
at commit `27194a4f583243d87eb0c01dd3df5596e548e536`.

Later current-main qualification may occur after that tag without changing the
canonical `VERSION` file. The RootFS-only installation qualified on 2026-08-30
was built from commit `c4c6fa18e659a82ada32c708720202a5ad6592ac`, described by
Git as `2026.1-1-gc4c6fa1`.

A subsequent full kernel-plus-RootFS qualification was built from commit
`833cbd43132e5a818a422f25d9478cd6b3f76123`, described by Git as
`2026.1-4-g833cbd4`. That complete p6/p8 pair was installed and booted
successfully on the reference system and qualified the product hostname
`fre3nder`.

Both builds retained the embedded project version `2026.1`. They are therefore
untagged current-main qualification builds, not additional `2026.1` releases.
A subsequent public release requires an appropriate new canonical version and
matching tag.

Build manifests carry the structured version fields documented above together
with project commit, source/config/patch identities, and artifact hashes.

Installable app definitions use that exact build-source commit rather than a
tag inferred from `VERSION`. Clean RootFS builds embed `project_commit` in
`/usr/share/fre3nder/APP_REF`; dirty builds write `unpublished` and require a
local handler or explicitly selected local source. There is no floating-branch
fallback. See [the app-definition source rule](apps.md#app-definition-source-revision).

## 2026.2 usable-system line

`2026.2`, scope ID `usable-system`, titled **Usable System**, was released on
2026-09-14. Development candidates used the normal staged version suffixes; the
implementation candidate was `2026.2.a`.

The `2026.2` scope builds on the functionally achieved `2026.1` open-host
baseline and adds the persistent runtime and application architecture required
for normal day-to-day operation. Its completed functional scope and release
history are summarized in [`CHANGELOG.md`](../CHANGELOG.md); current behavior
is described by the subject-specific technical documentation. The final release
was built, validated, and tagged from commit
`fcabe6089dba72ded7c256b8550ea65bc7a34ec6`.

## 2026.3 independent-kernel-stack line

`2026.3`, scope ID `independent-kernel-stack`, titled
**Independent Kernel Stack**, was released on 2026-09-20. It completes the
transition away from the vendor kernel while intentionally changing little
user-facing printer behavior.

The productive X2000 kernel baseline is official Linux stable `v6.6.157` at
commit `79643295eba17affbd16ca97f3ef04c90266b28c`. An ordered five-patch
Fre3nder hardware-support series supplies the retained X2000 platform support,
Ender-3 V3 KE display, NS2009 touch, WLAN integration, and Fre3nder board/
forward-port integration. The series produces source tree
`40d8b5cee4341505c12373e9bb1386e80241f0d6`.

The historical Ingenic kernel/SDK and RT23 trees remain migration provenance
and reference material only. They are not productive kernel source checkouts.
PREEMPT_RT/RT23 is no longer required.

The `6.6.157-fre3nder` kernel host baseline is hardware-qualified on the
investigated reference Ender-3 V3 KE for the exercised boot, network, and SSH
path. This does not by itself re-qualify every peripheral or application flow
on the new kernel baseline.

The matching `2026.3` tag identifies the final release source. Release-mode
artifacts must be built and validated from the clean release commit before that
tag is published; changing the canonical `VERSION` alone does not create a
release.

## Project name

The public project identity is:

**Fre3nder**

*An open software platform for the Ender-3 V3 KE.*

Fre3nder is an independent open-source project and is not affiliated with or
endorsed by Creality. Ender and Ender-3 are trademarks of their respective
owner.

The canonical repository name is `fre3nder`. Historical technical identifiers
may retain former development names where required to preserve provenance or
recorded evidence. The project name does not alter the `2026.1` release
criteria.
