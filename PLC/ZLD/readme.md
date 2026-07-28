# ZLD Extractor

`zld_extract.py` inspects IDEC DataFileManager `.zld` files and optionally
extracts their individual binary sections.

The program reads the section count from the ZLD header, so it supports both
known layouts:

- **Program-only ZLD:** 2 sections, 72-byte header
- **Program plus firmware ZLD:** 4 sections, 120-byte header

It validates the file magic, declared size, section offsets, section lengths,
and that all sections are contiguous.

## Usage

Inspect a ZLD without extracting files:

```bash
./zld_extract.py project.zld
```

Extract all sections:

```bash
./zld_extract.py project.zld -o project_parts
```

Extract only the program-related sections:

```bash
./zld_extract.py project.zld -o project_parts --program-only
```

## Output files

### `section_10_program.bin`

Section type `0x0010`.

This is believed to be the compiled PLC program transferred with the extended
Maintenance Protocol `WPn` command. It is compiled binary data, not an editable
WindLDR source project.

### `section_11_supplemental.bin`

Section type `0x0011`.

This is believed to be the supplementary data transferred with `W;n`. Testing
shows that its size changes when comments are added to a project, so it likely
contains comments, symbols, project metadata, or related compiled information.

### `firmware_77ff01.bin`

Section type `0x1019`.

This is the firmware payload selected with `WS77FF01` and transferred with
`WPB`.

### `firmware_77ff05.bin`

Section type `0x1119`.

This is the firmware payload selected with `WS77FF05` and transferred with
`WPB`. Its size changes between firmware releases, so it appears to contain a
major firmware image.

### Cortex-M firmware note

Neither `firmware_77ff01.bin` nor `firmware_77ff05.bin` is the firmware image
that was positively identified as ARM Cortex-M code.

The confirmed Cortex-M image was a separate 55,296-byte firmware block selected
with:

```text
WS770120
```

That block was observed during a WindLDR serial firmware download, but it has
not appeared as a section in the ZLD files tested so far. Therefore,
`zld_extract.py` does not currently produce a Cortex-M firmware file.

### `manifest.json`

The manifest records:

- Source ZLD filename
- File and header sizes
- Section count
- Section types
- Original offsets and lengths
- Header check values
- Output filenames
- SHA-256 hashes

The extracted `.bin` files are raw section payloads. They do not include the ZLD
header or section table and are not standalone DataFileManager packages.

## Known section types

| Type | Output file | Current interpretation |
|---|---|---|
| `0x0010` | `section_10_program.bin` | Probable `WPn` compiled program |
| `0x0011` | `section_11_supplemental.bin` | Probable `W;n` supplementary data |
| `0x1019` | `firmware_77ff01.bin` | Confirmed `WS77FF01` firmware |
| `0x1119` | `firmware_77ff05.bin` | Confirmed `WS77FF05` firmware |

The `0x0010` and `0x0011` roles are strongly supported by captures and testing,
but should still be treated as reverse-engineered rather than official IDEC
documentation.



### Purpose:
The current status of this project, we are able to download a zld program file without firmware. 
This program can deconstruct a ZLD file with firmware, into the respective file components. 
This should provide a method to download ZLD files to a PLC via a platform of choice. 

About the ZLD binary format: 
These files are compiled bianry formats. even the comments are compiled. section 11, probably containes the comments, 
this is derrived from a frequency analysis of zld files with different comment lemgth, resulting in a linear size variation 
for ZlD files with, without, or with varying size commentary. 
-- sucks for me, but Im totaly stoked about that feature as a user. 

The section 11 header: 

6a 3b 20 c3 49 44 45 44 4a a0 fa 14 ...
            I  D  E  D  J
is followed by incomprendable nonsense, which changes in size and composition, 
as the commentary changes, under the same
code base.

<pre>
ZLD/
├── D0D1Q0
│   ├── firmware_77ff01.bin
│   ├── firmware_77ff05.bin
│   ├── manifest.json
│   ├── section_10_program.bin
│   └── section_11_supplemental.bin
├── D0_D1_Q0_Coments.txt
├── D0_D1_Q0_test_With_Comment_And_Firmware_V280.zld
├── D0_D1_Q0_test_With_Comment.zld
├── D0_D1_Q0_test.zld
├── readme.md
├── zld_extract.py
└── zld_rebuild.py

</pre>
