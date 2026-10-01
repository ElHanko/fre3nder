# Open F005 MCU flasher research

## 1. Goal and scope

This report evaluates a free replacement for Creality's proprietary
`mcu_util` and records the first Fre3nder-owned, offline-testable research
prototype. The implementation remains under `research/`; it is not part of the
Fre3nder `2026.1` production path and is not authorized for real hardware.

Current status:

```text
OPEN FLASHER PROTOCOL: OFFLINE IMPLEMENTED
F005 SERIAL BOOTLOADER REQUEST: OFFLINE IMPLEMENTED IN RESEARCH
REAL F005 USE: REQUIRES QUALIFICATION
PRODUCTION REPLACEMENT FOR mcu_util: NOT YET APPROVED
```

No serial device, printer, MCU, service, deployment target, or production build
artifact was accessed or changed during this work.

## 2. Fre3nder evidence baseline

The comparison basis is the investigated F005/GD32F303RET6 reference system
documented in:

- [`docs/f005-mcu-switching.md`](../../docs/f005-mcu-switching.md);
- [`docs/klipper-stock.md`](klipper-stock.md);
- [`docs/gd32f303-mainline-port.md`](gd32f303-mainline-port.md);
- [`research/docs/f005-first-print-reproduction.md`](f005-first-print-reproduction.md).

That evidence establishes `/dev/ttyS1`, application baud 230400, the retained
12 KiB Creality bootloader, application start at `0x08003000`, and the known
hardware prefix `mcu0_001_G32`. It also establishes successful on-device use of
the inspected Stock `mcu_util` for handshake, identity query, application start,
and firmware transfer after the bootloader had already been reached.

The inspected binary is not redistributed. Its recorded properties are:

```text
size: 11096 bytes
SHA-256: d984f1a51ff9149a8971f9a3d3d0db13f81772c8122dd24b53b4d160f223cd03
format: ELF32 little-endian MIPS32r2, dynamically linked, stripped
```

The Stock tool contains strings for `handshake`, `version_confirm`,
`sector_size_confirm`, `update_start`, `app_len_confirm`, `app_data_confirm`,
`start_app`, checksum/no-ACK retries, flash failure, and complete-update retry.
The existing repository analysis establishes bounded internal retries, including
up to three complete transfer attempts in one process for some failures.

Direct `mcu_util -c`, `-g`, and `-s` calls against a running Mainline application
timed out on the reference device. A normal Klipper `FIRMWARE_RESTART`, followed
by actual UART release, did reach the bootloader and made the same commands
succeed. Therefore Stock `mcu_util` itself does not implement the running-
application-to-bootloader transition.

## 3. CryoZ provenance

Audit date: 2026-08-30.

| Item | Value |
| --- | --- |
| Repository | [`cryoz/k1_mcu_flasher`](https://github.com/cryoz/k1_mcu_flasher) |
| Audited commit | [`8417786290844a8f7b80dab5f1fb6761c43c4f1a`](https://github.com/cryoz/k1_mcu_flasher/tree/8417786290844a8f7b80dab5f1fb6761c43c4f1a) |
| Relevant code | `mcu_util.py`, labelled version 0.2 |
| Code SHA-256 | `05e6d6a8114b32b255fdcc3dae6abcaba130a129f2ad4f6dab5077e048af2535` |
| License | MIT, copyright 2024 CryoZ |
| License SHA-256 | `049620752b3cd6d7e9d87720d81cf4c7d23231bf3e5a2993a42abcb8a511a27e` |

CryoZ describes the program as a pure-Python implementation compatible with
the official command surface. The repository does not identify an earlier
source implementation. Its relevant contribution is a readable implementation
of the bootloader wire sequence, including the physical-serial Klipper request,
handshake, version and sector queries, update framing, status handling, retries,
and application start.

CryoZ attempts the serial bootloader request up to five times, retries an
application start up to three times, and retries a complete firmware transfer up
to three times. Those are implementation choices, not established protocol
requirements. They are not carried into the Fre3nder prototype.

## 4. NebulaOS provenance

Audit date: 2026-08-30.

| Item | Value |
| --- | --- |
| Repository | [`coreflake1/NebulaOS-klipper-mcu`](https://github.com/coreflake1/NebulaOS-klipper-mcu) |
| Audited commit | [`2c9bab5be07deef4c8df6d7db3b614d748a18065`](https://github.com/coreflake1/NebulaOS-klipper-mcu/tree/2c9bab5be07deef4c8df6d7db3b614d748a18065) |
| Relevant files | `tools/creality_flash.py`, `tools/test_creality_flash.py`, `tools/creality_validator.py`, `tools/creality_packer.py` |
| Flasher SHA-256 | `57a9bf417a25b834520ba46c0b5681648292002c8377622e6e89bd07f07946ad` |
| Flasher-test SHA-256 | `c229906da44a4d7d2fb7c6f2c9520477ff3a218322b49008188017a48aa6d478` |
| Validator SHA-256 | `f2aad3766253ea63f4513c55b62f19ffa070f52a6c30b25f330c42a1953bc79b` |
| License | GNU GPL version 3 |

NebulaOS's flasher explicitly says its protocol was ported from CryoZ version
0.2. NebulaOS adds an injectable transport, fake-transport tests, distinct CLI
subcommands, offline image validation, target validation, an exact hardware-ID
allowlist, and the absence of a global `--force` bypass. Its README explicitly
classifies the flasher as fake-transport-only and not hardware-qualified.

NebulaOS also adds a Klipper MCU patch that enables the physical-serial request
for its 12 KiB target and makes `bootloader_request()` call
`NVIC_SystemReset()`. This is a GPLv3 Klipper-derived patch. The tools are
NebulaOS-original but its `NOTICE.md` distributes them under GPLv3 as well.

The audit found two boundaries worth retaining:

- NebulaOS's validator models the length at `+0x20e` as 16-bit and limits an
  image to 65535 bytes. Fre3nder's established packager and Stock comparison
  model a 32-bit little-endian length at `+0x20e`. Both representations are
  byte-identical for the current 22392-byte image, but behavior above 65535
  bytes is `BINARY CORRESPONDENCE UNKNOWN`.
- NebulaOS documents a final `0x20` completion status, but its audited transfer
  function also returns success if every chunk, including the last, responds
  only with `0x75`. The Fre3nder prototype requires `0x20` on the final chunk.

## 5. License and provenance decision

No NebulaOS source code was copied. GPLv3-covered implementation text, tests,
validator code, and Klipper patch text remain external comparison material.
Their architectural ideas are used only at the level of independently
implemented concepts: an injectable transport, fake transport, separate
offline/live actions, exact allowlists, and fail-closed validation.

The Fre3nder prototype is independently written project code under the
repository's MIT license. Its protocol behavior is derived from:

1. the MIT-licensed CryoZ protocol publication at the exact commit above;
2. Fre3nder's own documented Stock-binary and on-device evidence;
3. Fre3nder's existing MIT image packager and F005 memory contract; and
4. new independent fake-transport tests.

No third-party source block or file was imported, so there is no copied
third-party source requiring an embedded notice. CryoZ's copyright, license,
exact revision, file hash, and role are nevertheless preserved here as protocol
provenance. If future work directly imports or adapts CryoZ code, its MIT
copyright and permission notice must accompany that code.

## 6. Protocol comparison

The table distinguishes wire correspondence from hardware qualification.

| Function | Stock `mcu_util` evidence | CryoZ | NebulaOS | Assessment |
| --- | --- | --- | --- | --- |
| Bootloader magic | Absent from the inspected tool; direct calls against a running app timed out | Sends the 32-byte Klipper physical-serial request at app baud | Same request through transport abstraction | Stock entry claim `WIDERLEGT`; free entry path `SOURCE BEHAVIOR ONLY` |
| Baud switch | Stock tool operates after another mechanism reaches the 115200 bootloader; Klipper runs at 230400 | Sends magic at configurable app baud, waits, then opens bootloader operations at 115200 | Sets 230400, sends magic, waits, sets 115200 | `OFFLINE CONFIRMED` baud roles; automatic transition `REQUIRES QUALIFICATION` |
| Handshake | Local binary comparison and real bootloader use | TX/RX `0x75` | TX/RX `0x75` | `OFFLINE CONFIRMED`; Stock path also qualified after bootloader entry |
| Version | Real known identities and binary comparison | `00 ff`, 25 payload bytes plus checksum | Same, strict length/checksum | `OFFLINE CONFIRMED` |
| Hardware ID | Real prefix `mcu0_001_G32` | Returns complete 25-byte identity without an allowlist | Exact default allowlist | Known reference identity `OFFLINE CONFIRMED`; other revisions `REQUIRES QUALIFICATION` |
| Sector size | Local binary/public-protocol comparison | `03 fc`, one-byte multiplier plus checksum | Same | Wire form `OFFLINE CONFIRMED`; real returned value not retained in public evidence |
| Flash request | Successful real update plus binary comparison | `01 fe`, expects `0x75` | Same | `OFFLINE CONFIRMED` |
| Firmware length | Stock tool uses file length | little-endian `uint32` plus checksum | little-endian `uint32` plus checksum | `OFFLINE CONFIRMED` |
| Chunk size | Local protocol comparison | sector multiplier times 1024 bytes | Same | `OFFLINE CONFIRMED` |
| Wire checksum | Local protocol comparison | `(sum(data) & 0xff) ^ 0xff` | Same | `OFFLINE CONFIRMED` |
| `0x75` | Binary/public comparison: ACK/chunk accepted | chunk accepted | chunk accepted | `OFFLINE CONFIRMED` |
| `0x20` | Binary/public comparison: transfer complete | transfer complete | transfer complete | `OFFLINE CONFIRMED`; exact final-status timing still hardware-sensitive |
| `0x21` | Binary/public comparison: flash failure | flash write failure | flash write failure | `OFFLINE CONFIRMED` |
| `0x1f` | Binary/public comparison: received-data checksum failure | checksum failure | checksum failure | `OFFLINE CONFIRMED` |
| Unknown status | No safe success interpretation | implicit failure | explicit failure | Fail closed in Fre3nder |
| Retry behavior | Bounded internal retries, including possible full-transfer restart | five entry attempts; three app/transfer attempts | five entry attempts; transfer failures propagate | Exact branch equivalence `BINARY CORRESPONDENCE UNKNOWN`; Fre3nder prototype performs no retry |
| Application start | Real `mcu_util -s` returned `app_run` | `02 fd`, expects checksummed `0x75` | Same | Wire form `OFFLINE CONFIRMED`; open implementation on hardware `REQUIRES QUALIFICATION` |
| Already in bootloader | Stock `-c/-g/-s` qualified in this state | Supports explicit handshake before actions | High-level identify always sends magic first | Direct-handshake behavior `OFFLINE CONFIRMED`; Nebula high-level behavior in this state `SOURCE BEHAVIOR ONLY` |
| Running Klipper application | Stock tool does not enter bootloader | Sends Klipper physical-serial request | Same | General Klipper mechanism `OFFLINE CONFIRMED`; F005 result `REQUIRES QUALIFICATION` |

`OFFLINE CONFIRMED` here means the protocol property is supported by the
repository's recorded binary comparison, public source comparison, or both. It
does not promote the new implementation to hardware-qualified status.

## 7. Known wire commands

| Operation | Host transmission | Response |
| --- | --- | --- |
| Physical-serial request | `20 1c 20 52 ... 21 21 20 7e` (the 32-byte Klipper request) | no direct ACK; application should reset |
| Handshake | `75` | `75` |
| Version | `00 ff` | 25-byte identity plus wire checksum |
| Sector multiplier | `03 fc` | one-byte multiplier plus wire checksum |
| Update request | `01 fe` | checksummed `75` |
| Firmware length | little-endian `uint32` plus wire checksum | checksummed `75` |
| Firmware chunk | up to `sector_multiplier * 1024` bytes plus wire checksum | checksummed status |
| Start application | `02 fd` | checksummed `75` |

The Klipper documentation notes that an extra leading sync byte can improve
reliability when another tool previously used the serial stream. CryoZ and the
audited NebulaOS tool send the exact 32-byte block recognized by Klipper's
`serial_irq.c`, without the optional leading sync byte.

## 8. Status codes

| Code | Meaning used by the sources | Prototype behavior |
| --- | --- | --- |
| `0x75` | request ACK / chunk accepted | accepted for request, length, app-start, and non-final chunks |
| `0x20` | complete image written | required on exactly the final chunk |
| `0x21` | RAM-to-flash/write failure | immediate failure, no retry |
| `0x1f` | transferred data checksum failure | immediate failure, no retry |
| other | unknown | immediate failure, no retry |

Every two-byte status response must also carry the correct wire checksum.

## 9. Checksums and image metadata

The wire checksum is:

```text
(sum(data) & 0xff) ^ 0xff
```

It is distinct from the image-at-rest CRC16. The prototype validates the
existing Fre3nder F005 package contract:

- 32-byte reserved board-info region at application-relative `+0x200`;
- 12-byte identity such as `mcu0_004_000` at `+0x200`;
- CRC16/CCITT at `+0x20c`;
- 32-bit little-endian total length at `+0x20e`;
- CRC calculated over the entire image while the two CRC and four length bytes at
  `+0x20c..+0x211` are zero;
- remaining board-info bytes are zero;
- initial stack pointer is within the F005 64 KiB RAM contract;
- Thumb reset vector is within `0x08003000..0x0803ffff`;
- exact expected version, size, and SHA-256 for a flash operation.

The validator does not accept a raw, un-packaged Klipper binary.

## 10. Differences and unresolved questions

- Stock `mcu_util` does not send the Klipper serial bootloader request.
- Retry counts are implementation choices and do not prove bootloader
  requirements. The prototype deliberately performs no retry.
- The exact reason Stock can restart some operations after checksum/no-ACK
  failures, and whether doing so is desirable, remains unresolved.
- The bootloader's 15-second startup window is a CryoZ source statement; its
  exact timing and corrupt-image behavior remain `SOURCE BEHAVIOR ONLY` for the
  investigated F005 bootloader.
- The public sources and Fre3nder agree for current sub-65536-byte images, but
  disagree on whether the stored image length is fundamentally 16 or 32 bits.
- No retained public log records the sector multiplier returned by the real
  F005.
- The correct behavior if the final chunk returns only `0x75` is not proven on
  hardware. The prototype requires the documented `0x20` completion signal.
- A successful `app_start` ACK does not independently prove that Klipper later
  starts and identifies the intended firmware.

## 11. Implemented Fre3nder architecture

[`research/f005-mcu/fre3nder_f005_flasher.py`](../f005-mcu/fre3nder_f005_flasher.py)
contains logically separate components:

- `Transport` and lazily loaded `SerialTransport`;
- `F005Protocol` for bootloader request, handshake, identity, sector size,
  transfer, and application start;
- strict `BootloaderIdentity` parsing;
- `ImagePolicy`, `ImageInfo`, and `validate_image()`;
- `F005Flasher` for the policy-gated high-level sequence;
- CLI subcommands `inspect`, `validate`, `identify`, and `flash`.

The CLI has no implicit action. `inspect` and `validate` are offline-only.
`identify` transmits handshake/version queries and is “read-only” only in the
narrow sense that it does not erase or flash; `--request-bootloader` also asks a
running compatible Klipper application to reset. Neither live action is
authorized by this report.

`flash` is an explicit subcommand and requires an exact expected image version,
size, lowercase SHA-256, and one or more exact `--allow-hw-id` values. The image
and policy are validated before the serial transport is opened and again before
protocol traffic. There is no `--force`, wildcard identity, automatic image
selection, automatic fallback, or retry.

## 12. Offline test coverage

[`research/f005-mcu/test_fre3nder_f005_flasher.py`](../f005-mcu/test_fre3nder_f005_flasher.py)
provides a scripted transport and a stateful fake bootloader. The current tests
cover:

- handshake success and timeout;
- correct, short, malformed, and bad-checksum version responses;
- allowed and unallowed hardware identities;
- sector multiplier;
- status `0x75`, `0x20`, `0x21`, `0x1f`, and unknown status;
- application start;
- app-baud to bootloader-baud request sequencing;
- valid image, wrong target type, and bad image CRC;
- update-request ACK;
- little-endian firmware size;
- multiple full chunks and a remainder chunk;
- exact byte-for-byte image receipt by the fake bootloader;
- required final completion status;
- invalid image and missing allowlist rejected before any transport write;
- unknown hardware rejected before the update request;
- flash/checksum/unknown status failures preventing application start.

The result is `OFFLINE IMPLEMENTED`, not hardware qualification.

The validator also accepted the retained 22392-byte Fre3nder candidate with
identity `mcu0_004_000` and SHA-256
`5b9678731b10a0f8c6159b3cf2432b1a499d6310b9466419d129dc42242e23ac`,
matching the established package metadata and CRC16 exactly.

## 13. Hardware qualification gate

Every later live step requires separate explicit authorization. The smallest
useful sequence is staged so that no flash is bundled into the first test:

1. Verify recovery readiness, exact artifact identities, no active print,
   heaters intentionally off, and exclusive `/dev/ttyS1` ownership.
2. Starting from the already qualified normal `FIRMWARE_RESTART` bootloader
   route, run only the open implementation's handshake and identity query;
   compare the exact 25-byte identity with the known result.
3. Query the real sector multiplier and start the unchanged application; then
   independently require normal Klipper identity and readiness.
4. Only after steps 2 and 3 pass, qualify the physical-serial bootloader request
   with no firmware transfer.
5. Only under another write authorization, validate one exact manifest image,
   exact source identity, allowlist, hash, size, target, recovery path, and UART
   ownership; perform one open-tool transfer with no retry.
6. Independently identify the flashed application and complete the existing
   staged printer validation appropriate to that image.

Unexpected responses stop the sequence. A failure is not followed by an
automatic second transfer.

## 14. Software-only Fre3nder-to-Stock hypothesis

CryoZ and NebulaOS assume that a running Klipper application recognizes the
standard physical-serial block `Request Serial Bootloader!!`, calls its platform
`bootloader_request()`, and resets into the retained Creality bootloader. This is
consistent with upstream Klipper's
[`docs/Bootloader_Entry.md`](https://github.com/Klipper3d/klipper/blob/0499b30374315f2a9f49fc12808527fc7d0f5cfa/docs/Bootloader_Entry.md)
and `src/generic/serial_irq.c` at Fre3nder's pinned upstream commit
`0499b30374315f2a9f49fc12808527fc7d0f5cfa`.

The current Fre3nder F005 firmware is not compatible with that mechanism as
built. Its project patch explicitly selects `HAVE_BOOTLOADER_REQUEST` only when
the target is not `MACH_GD32F303`. Even if that gate were simply enabled,
upstream `stm32f1.c::bootloader_request()` has branches only for its established
2 KiB and 8 KiB cases; it does not reset for `STM32_FLASH_START_3000`.

The separate GPLv3 Research patch documented in
[`f005-serial-bootloader-request.md`](f005-serial-bootloader-request.md) now
implements both missing pieces and passes offline F005 build and binary checks.
It does not modify or qualify the current productive firmware.

NebulaOS adds both missing pieces: request support and a 12 KiB branch that
calls `NVIC_SystemReset()`. That supports technical feasibility but is GPLv3
external source behavior, not a Fre3nder qualification and not code to copy
into an MIT file. Any Fre3nder MCU change would be a patch to GPLv3 Klipper and
would correctly remain GPLv3.

Conditions for the hypothesis to work are:

- a future F005 build applies the reviewed Research patch and enables
  `HAVE_BOOTLOADER_REQUEST`;
- its 12 KiB `bootloader_request()` path performs the already validated system
  reset without overwriting the retained bootloader;
- the request is delivered as one recognized serial block at 230400;
- Klippy has released or can safely release UART ownership at the right time;
- the host changes to 115200 inside the bootloader window;
- the bootloader remains responsive through the intended host handoff.

Risks include a request split or contaminated by existing serial traffic,
missing the bootloader window, losing the UART handoff race, receiving an
unexpected identity, the MCU/application entering shutdown, app-start behavior
that differs after an error, and the already observed unresolved behavior across
the subsequent X2000 reboot.

The minimum later no-write test is: build and offline-validate the explicit GPL
Klipper patch; start the exact known Fre3nder MCU; stop normal host traffic and
verify UART ownership; send the physical-serial request once; switch to 115200;
handshake and query the exact identity; send app-start; then independently
reconnect normal Klipper. It must not include a firmware transfer or X2000 slot
switch. The separate complete Fre3nder-to-Stock host-reboot handoff remains
`INFERENCE / REQUIRES QUALIFICATION` even if this test succeeds.

## 15. Open questions

- What exact sector multiplier does the investigated real F005 return?
- Does the new open parser receive exactly the known F005 identity?
- Does a future Fre3nder F005 build reliably accept the physical-serial request?
- Is an optional leading sync byte required on the X2000 UART path?
- Does the real bootloader always send `0x20` on the final chunk?
- How should a transfer failure be recovered without an automatic retry?
- Does open `app_start` return to the intended firmware and normal Klipper?
- What is the bootloader's real timeout and corrupt-image behavior?
- Can the MCU remain bootloader-responsive through the real X2000 reboot into
  unchanged Stock?

## 16. Promotion criteria

Promotion from `research/` into the productive Fre3nder tree requires all of:

1. review of this implementation against CryoZ, the recorded Stock binary
   behavior, and the exact Fre3nder packager contract;
2. license/provenance review confirming no GPL NebulaOS implementation text was
   imported into MIT project code;
3. read-only real F005 identity and sector-query qualification;
4. real application-start qualification with independent Klipper identity;
5. review, promote, and qualify the existing GPLv3 Fre3nder Research patch for
   the 12 KiB physical-serial request path;
6. one explicitly authorized exact-image flash with byte/image identity gates,
   no tool retry, and independent post-flash verification;
7. failure-path and recovery decisions for checksum, no-ACK, `0x21`, `0x1f`,
   unknown status, partial transfer, and app-start failure;
8. integration with the productive release manifest instead of free-form CLI
   image selection;
9. preservation of the existing UART ownership, heater/print-state, persistence,
   and recovery gates;
10. complete targeted regression tests and an explicit decision to remove the
    proprietary BYOF dependency only after the open path is qualified.

Until then, the proprietary production path and all existing qualification
labels remain unchanged.
