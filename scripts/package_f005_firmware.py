#!/usr/bin/env python3
"""Package a linker-reserved F005 Klipper binary for the stock updater."""

import argparse
import struct
from pathlib import Path


BOARD_INFO_OFFSET = 0x200
BOARD_INFO_SIZE = 0x20
VERSION_SIZE = 0x0c
CRC_OFFSET = 0x20c
LENGTH_OFFSET = 0x20e
STOCK_COMPAT_VERSION = "mcu0_004_000"


def crc16_ccitt(data):
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xffff
            else:
                crc = (crc << 1) & 0xffff
    return crc


def package(input_path, output_path, version):
    version_bytes = version.encode("ascii")
    if len(version_bytes) != VERSION_SIZE:
        raise ValueError("version must be exactly 12 ASCII bytes")

    image = bytearray(input_path.read_bytes())
    if len(image) < BOARD_INFO_OFFSET + BOARD_INFO_SIZE:
        raise ValueError("input is too small for the F005 board-information region")
    if any(image[BOARD_INFO_OFFSET:BOARD_INFO_OFFSET + BOARD_INFO_SIZE]):
        raise ValueError("F005 board-information region is not linker-reserved")

    image[BOARD_INFO_OFFSET:CRC_OFFSET] = version_bytes
    image[CRC_OFFSET:LENGTH_OFFSET + 4] = b"\0" * 6
    crc = crc16_ccitt(image)
    image[CRC_OFFSET:LENGTH_OFFSET] = struct.pack("<H", crc)
    image[LENGTH_OFFSET:LENGTH_OFFSET + 4] = struct.pack("<I", len(image))
    output_path.write_bytes(image)
    return crc, len(image)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--version", default=STOCK_COMPAT_VERSION)
    args = parser.parse_args()
    crc, length = package(args.input, args.output, args.version)
    print("version={}".format(args.version))
    print("crc16=0x{:04x}".format(crc))
    print("length=0x{:x}".format(length))


if __name__ == "__main__":
    main()
