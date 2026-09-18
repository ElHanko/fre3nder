#!/usr/bin/env python3

import argparse
import json
import pathlib
import stat
import struct


ELF32_HEADER = struct.Struct("<16sHHIIIIIHHHHHH")
ELF32_PROGRAM_HEADER = struct.Struct("<IIIIIIII")
ELF32_SECTION_HEADER = struct.Struct("<IIIIIIIIII")
ELF32_SYMBOL = struct.Struct("<IIIBBH")
ELFCLASS32 = 1
ELFDATA2LSB = 1
EM_MIPS = 8
PT_LOAD = 1
SHT_SYMTAB = 2
SHN_UNDEF = 0


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def slice_checked(data, offset, size, description):
    require(offset >= 0 and size >= 0, f"invalid {description} bounds")
    end = offset + size
    require(end <= len(data), f"truncated {description}")
    return data[offset:end]


def table_entries(data, offset, count, entry_size, layout, description):
    require(entry_size >= layout.size, f"invalid {description} entry size")
    entries = []
    for index in range(count):
        raw = slice_checked(
            data,
            offset + index * entry_size,
            layout.size,
            f"{description} entry",
        )
        entries.append(layout.unpack(raw))
    return entries


def string_at(data, offset):
    require(0 <= offset < len(data), "invalid symbol-name offset")
    end = data.find(b"\0", offset)
    require(end != -1, "unterminated symbol name")
    return data[offset:end].decode("ascii", errors="strict")


def inspect(data, outer_load):
    require(len(data) >= ELF32_HEADER.size, "truncated ELF header")
    header = ELF32_HEADER.unpack(data[: ELF32_HEADER.size])
    (
        ident,
        _elf_type,
        machine,
        version,
        entry,
        program_offset,
        section_offset,
        _flags,
        header_size,
        program_entry_size,
        program_count,
        section_entry_size,
        section_count,
        _section_names,
    ) = header

    require(ident[:4] == b"\x7fELF", "input is not ELF")
    require(ident[4] == ELFCLASS32, "vmlinux is not ELF32")
    require(ident[5] == ELFDATA2LSB, "vmlinux is not little-endian")
    require(ident[6] == 1 and version == 1, "unsupported ELF version")
    require(machine == EM_MIPS, "vmlinux is not MIPS ELF")
    require(header_size == ELF32_HEADER.size, "unexpected ELF header size")
    require(program_count > 0, "vmlinux has no program headers")
    require(section_count > 0, "vmlinux has no section headers")

    programs = table_entries(
        data,
        program_offset,
        program_count,
        program_entry_size,
        ELF32_PROGRAM_HEADER,
        "program-header",
    )
    load_segments = []
    for program in programs:
        p_type, p_offset, vaddr, paddr, file_size, memory_size, flags, align = program
        if p_type != PT_LOAD:
            continue
        require(file_size <= memory_size, "LOAD file size exceeds memory size")
        slice_checked(data, p_offset, file_size, "LOAD segment")
        require(paddr + memory_size <= 0x100000000, "LOAD segment wraps ELF32 address space")
        load_segments.append(
            {
                "virtual_address": vaddr,
                "physical_address": paddr,
                "file_size": file_size,
                "memory_size": memory_size,
                "flags": flags,
                "alignment": align,
            }
        )

    require(load_segments, "vmlinux has no LOAD segments")
    load_start = min(segment["physical_address"] for segment in load_segments)
    load_file_end = max(
        segment["physical_address"] + segment["file_size"]
        for segment in load_segments
    )
    load_memory_end = max(
        segment["physical_address"] + segment["memory_size"]
        for segment in load_segments
    )
    require(
        any(
            segment["physical_address"]
            <= entry
            < segment["physical_address"] + segment["memory_size"]
            for segment in load_segments
        ),
        "ELF entry is outside the LOAD segments",
    )
    require(load_memory_end <= outer_load, "kernel LOAD range overlaps the xImage wrapper")

    sections = table_entries(
        data,
        section_offset,
        section_count,
        section_entry_size,
        ELF32_SECTION_HEADER,
        "section-header",
    )
    kernel_entries = []
    for section in sections:
        (
            _name,
            section_type,
            _section_flags,
            _section_address,
            symbol_offset,
            symbol_size,
            string_section_index,
            _info,
            _alignment,
            symbol_entry_size,
        ) = section
        if section_type != SHT_SYMTAB:
            continue
        require(string_section_index < len(sections), "invalid symbol string table")
        string_section = sections[string_section_index]
        strings = slice_checked(
            data, string_section[4], string_section[5], "symbol string table"
        )
        require(symbol_entry_size >= ELF32_SYMBOL.size, "invalid symbol entry size")
        require(symbol_size % symbol_entry_size == 0, "misaligned symbol table")
        symbols = table_entries(
            data,
            symbol_offset,
            symbol_size // symbol_entry_size,
            symbol_entry_size,
            ELF32_SYMBOL,
            "symbol",
        )
        for name_offset, value, _size, _info, _other, section_index in symbols:
            if section_index != SHN_UNDEF and string_at(strings, name_offset) == "kernel_entry":
                kernel_entries.append(value)

    require(kernel_entries, "kernel_entry symbol is missing")
    require(len(set(kernel_entries)) == 1, "kernel_entry symbol is ambiguous")
    kernel_entry = kernel_entries[0]
    require(kernel_entry == entry, "ELF entry does not match kernel_entry")
    require(
        any(
            segment["physical_address"]
            <= kernel_entry
            < segment["physical_address"] + segment["memory_size"]
            for segment in load_segments
        ),
        "kernel_entry is outside the LOAD segments",
    )

    return {
        "elf_class": 32,
        "endianness": "little",
        "machine": "MIPS",
        "load_address": f"0x{load_start:08x}",
        "load_file_end": f"0x{load_file_end:08x}",
        "load_memory_end": f"0x{load_memory_end:08x}",
        "elf_entry": f"0x{entry:08x}",
        "kernel_entry": f"0x{kernel_entry:08x}",
        "load_segments": [
            {
                **segment,
                "virtual_address": f"0x{segment['virtual_address']:08x}",
                "physical_address": f"0x{segment['physical_address']:08x}",
            }
            for segment in load_segments
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("vmlinux", type=pathlib.Path)
    parser.add_argument("--outer-load", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--field", choices=("load_address", "kernel_entry"))
    args = parser.parse_args()

    metadata = args.vmlinux.lstat()
    require(stat.S_ISREG(metadata.st_mode), "vmlinux is not a regular file")
    document = inspect(args.vmlinux.read_bytes(), args.outer_load)
    if args.field:
        print(document[args.field])
    else:
        print(json.dumps(document, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ContractError, OSError, UnicodeError, struct.error) as error:
        raise SystemExit(f"vmlinux contract error: {error}")
