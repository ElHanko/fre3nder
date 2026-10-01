# Fre3nder

**Your printer. Your stack.**

Fre3nder started with a simple question:

> **Can we update the firmware of an Ender-3 V3 KE?**

Once that door was open, a much bigger question followed:

> **Why stop at updating what Creality shipped?**

Replace the Linux system?\
The build environment?\
Take control of Klipper and Moonraker?\
The touchscreen software?\
The update mechanism?\
Even the firmware on the printer's own MCU?

Piece by piece, the answer became **yes**.

And somewhere along the way, Fre3nder stopped being an experiment about updating a printer and became something much more interesting:

> **What would this printer look like if we could build its software the way we wanted from the start?**

Fre3nder is that answer.

An open, maintainable software platform for the Ender-3 V3 KE — built to be understood, changed, rebuilt and extended by the people who actually own the machine.

## What the heck is a Fre3nder?

It's an **Ender-3 with a little more freedom.**

**Free + Ender-3 = Fre3nder.**

The name started as a play on words, but it ended up describing the project surprisingly well: take a printer built around closed vendor software and keep opening it up until the machine becomes something you can understand, rebuild and make your own.

That's Fre3nder.

## Why Fre3nder?

### 🔓 Own more than the settings

Changing a config file is useful. Owning the stack is better.

Fre3nder reaches from the Linux system underneath Klipper all the way to apps, the touchscreen, updates, persistent data and the F005 controller firmware.

The goal is not to replace things just because we can.

The goal is to make every layer we *do* replace understandable and maintainable.

### 🚀 Keep the printer moving forward

Vendor firmware eventually freezes in time. Fre3nder does not have to.

The host is built from pinned, maintained upstream Linux, Buildroot, Klipper and Moonraker sources, with the hardware-specific pieces kept explicit instead of buried inside an old vendor SDK.

That means a future update can be an engineering problem — not an archaeological expedition.

### 🔄 Updates you can reason about

A firmware update should not be an act of faith.

Fre3nder writes host updates to the inactive A/B slot, reads them back, verifies them and only then prepares activation.

It does not hide the remaining failure modes behind promises of magic rollback. The safety boundaries are part of the design — and part of the documentation.

### 🧩 Extend the printer without rebuilding the world

Fre3nder has its own signed `.fre3app` application format.

Apps can add web interfaces, background services or native touchscreen frontends while running as unprivileged services and without turning every extension into another permanent modification of the base system.

### 🖥️ The touchscreen is part of the platform

Fre3nderScreen gives the printer a native local interface without putting a browser between you and the machine.

And the screen is not hard-wired to one application: Fre3nder treats framebuffer, touch, backlight and beeper access as platform resources that signed display apps can use.

### ⚙️ We didn't stop at Linux

The X2000 host was only half the printer.

Fre3nder also opens a path for the F005 controller firmware, with explicit firmware identities and separate **qualified**, **candidate** and runtime states.

The host and MCU keep separate update lifecycles because owning more of the machine should not mean throwing away safety boundaries.

### 💾 Recovery is a feature

Backups, persistent data and recovery are not afterthoughts.

Fre3nder verifies HOME and system-state backups and documents what is — and is not — required to recover the machine or move back toward its original software.

### 🔬 Want to know how we know?

Nothing important has to be folklore.

[`docs/`](docs/README.md) describes **how Fre3nder works today**.

[`research/`](research/README.md) preserves **how we got there** — reverse engineering, hardware investigation, failed approaches, measurements and exact qualification records.

The result is not just an open codebase.

It is an open trail of evidence.

## Architecture

```text
Ender-3 V3 KE
│
├── X2000 host
│   ├── Linux / Buildroot
│   ├── Klipper + Moonraker
│   └── Fre3nder
│       ├── Apps
│       ├── Display
│       ├── OTA updates
│       └── Backup / recovery
│
└── F005 MCU
    └── Fre3nder-managed Klipper firmware lifecycle
```

The currently supported scope is the investigated Ender-3 V3 KE / F005 reference platform. Other hardware and firmware revisions require their own verification.

## Explore the repository

```text
build/       Build environments and component recipes
configs/     Product configuration and RootFS integration
patches/     Maintained upstream hardware and package deltas
scripts/     Build, signing, deployment and recovery tooling
tests/       Offline architecture and regression tests
docs/        Current product, API and developer documentation
research/    Hardware research, qualification and project history
```

## Get started

Want to run Fre3nder?

→ [Installation](docs/installation.md)

Want to see what Fre3nder can do and how to configure it?

→ [Documentation](docs/README.md)

Want to integrate with Fre3nder?

→ [API reference](docs/api/README.md)

Want to work on Fre3nder itself?

→ [Development](docs/development.md)\
→ [Build guide](docs/build.md)\
→ [Repository rules](AGENTS.md)

Want to understand how the hardware was reverse engineered and qualified?

→ [Research and qualification](research/README.md)

## Changelog

The README describes **Fre3nder**, not individual releases.

For released versions and what changed between them, see [`CHANGELOG.md`](CHANGELOG.md).

## License

Project-authored Fre3nder system material is licensed under `AGPL-3.0-or-later`.

Research exceptions, third-party material and provenance are documented in the [licensing and provenance policy](docs/licensing-and-provenance.md), with path-specific assignments in `REUSE.toml`.

See also the [acknowledgements](ACKNOWLEDGEMENTS.md).

Fre3nder is an independent project and is not affiliated with or endorsed by Creality. Ender and Ender-3 are trademarks of their respective owner.
