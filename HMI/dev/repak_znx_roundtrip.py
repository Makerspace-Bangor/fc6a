#!/usr/bin/env python3

import hashlib
import struct
import sys
from pathlib import Path


BASE_OFFSET = 0x1C


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def idec_checksum(data):
    value = 0

    for offset in range(0, len(data) - 3, 4):
        value ^= struct.unpack_from("<I", data, offset)[0]

    return value


def parse_znx(data):
    if len(data) < BASE_OFFSET + 20:
        raise ValueError("File is too small to be a ZNX")

    if data[:4] != b"ZNX\x00":
        raise ValueError("ZNX magic not found")

    records = []
    pos = BASE_OFFSET

    first_payload_rel = u32(data, pos + 4)
    directory_end = BASE_OFFSET + first_payload_rel

    if directory_end > len(data):
        raise ValueError("Invalid first payload offset")

    while pos < directory_end:
        if pos + 20 > directory_end:
            raise ValueError("Truncated ZNX directory record")

        file_type = u32(data, pos)
        rel_offset = u32(data, pos + 4)
        size = u32(data, pos + 8)
        checksum = u32(data, pos + 12)
        name_size = u32(data, pos + 16)

        name_start = pos + 20
        name_end = name_start + name_size

        if name_end > directory_end:
            raise ValueError("Filename extends beyond ZNX directory")

        raw_name = data[name_start:name_end]
        name = raw_name.split(b"\x00", 1)[0].decode("ascii")

        payload_offset = BASE_OFFSET + rel_offset
        payload_end = payload_offset + size

        if payload_end > len(data):
            raise ValueError(f"Payload outside file: {name}")

        records.append({
            "file_type": file_type,
            "rel_offset": rel_offset,
            "size": size,
            "checksum": checksum,
            "name_size": name_size,
            "name": name,
            "record_offset": pos,
            "payload_offset": payload_offset,
        })

        pos = name_end

    if pos != directory_end:
        raise ValueError("ZNX directory did not end on first payload offset")

    return records


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def repack(template_path, extracted_dir, output_path):
    template_path = Path(template_path)
    extracted_dir = Path(extracted_dir)
    output_path = Path(output_path)

    template = template_path.read_bytes()
    records = parse_znx(template)

    print(f"Template: {template_path}")
    print(f"Size:     {len(template)}")
    print(f"SHA256:   {sha256(template)}")
    print()
    print(f"Found {len(records)} ZNX member(s):")

    members = []

    for record in records:
        source = extracted_dir / record["name"]

        if not source.is_file():
            raise FileNotFoundError(
                f"Required extracted member not found: {source}"
            )

        payload = source.read_bytes()
        checksum = idec_checksum(payload)

        print()
        print(f"  {record['name']}")
        print(f"    type:              {record['file_type']}")
        print(f"    original size:     {record['size']}")
        print(f"    extracted size:    {len(payload)}")
        print(f"    original checksum: 0x{record['checksum']:08x}")
        print(f"    current checksum:  0x{checksum:08x}")

        if len(payload) == record["size"]:
            print("    size match:         YES")
        else:
            print("    size match:         NO")

        if checksum == record["checksum"]:
            print("    checksum match:     YES")
        else:
            print("    checksum match:     NO")

        members.append({
            **record,
            "data": payload,
            "new_checksum": checksum,
        })

    directory_size = sum(20 + member["name_size"] for member in members)
    current_rel_offset = directory_size

    output = bytearray()

    # Preserve the currently unknown header fields from the original.
    output.extend(template[:BASE_OFFSET])

    for member in members:
        name_data = member["name"].encode("ascii")

        if len(name_data) + 1 > member["name_size"]:
            raise ValueError(
                f"Filename no longer fits original name slot: {member['name']}"
            )

        name_field = name_data + b"\x00"
        name_field += b"\x00" * (member["name_size"] - len(name_field))

        output.extend(struct.pack("<I", member["file_type"]))
        output.extend(struct.pack("<I", current_rel_offset))
        output.extend(struct.pack("<I", len(member["data"])))
        output.extend(struct.pack("<I", member["new_checksum"]))
        output.extend(struct.pack("<I", member["name_size"]))
        output.extend(name_field)

        member["new_rel_offset"] = current_rel_offset
        current_rel_offset += len(member["data"])

    if len(output) != BASE_OFFSET + directory_size:
        raise RuntimeError("Internal directory-size calculation error")

    for member in members:
        output.extend(member["data"])

    # Offset 0x18 is the body size measured from 0x1c to EOF.
    struct.pack_into("<I", output, 0x18, len(output) - BASE_OFFSET)

    output_path.write_bytes(output)

    print()
    print(f"Output:   {output_path}")
    print(f"Size:     {len(output)}")
    print(f"SHA256:   {sha256(output)}")

    if output == template:
        print()
        print("ROUND TRIP: BYTE-FOR-BYTE IDENTICAL")
        return 0

    print()
    print("ROUND TRIP: DIFFERENT")

    limit = min(len(template), len(output))

    for offset in range(limit):
        if template[offset] != output[offset]:
            print(
                f"First difference: 0x{offset:08x} "
                f"original=0x{template[offset]:02x} "
                f"new=0x{output[offset]:02x}"
            )
            break
    else:
        if len(template) != len(output):
            print(f"First difference is EOF at offset 0x{limit:08x}")

    return 1


def main():
    if len(sys.argv) != 4:
        print(
            "Usage: repack_znx_roundtrip.py "
            "<original.ZNX> <extracted_dir> <output.ZNX>"
        )
        return 2

    try:
        return repack(sys.argv[1], sys.argv[2], sys.argv[3])
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
