# fc6a

**Python Maintenance Protocol tools for IDEC MicroSmart and FC6A PLCs**

Read and write PLC operands over Ethernet or serial, build monitoring and control
applications, and access files on supported FC6A SD cards.

[Quick start](#quick-start) · [Libraries](#libraries) ·
[API documentation](#api-documentation) · [Roadmap](#roadmap)

---

## Overview

The `fc6a` project provides Python libraries for communicating with IDEC PLCs through
the Maintenance Protocol.

Typical uses include:

- reading and writing PLC registers;
- monitoring bits, words, counters, timers, and sensor values;
- logging and plotting operational data;
- controlling multiple PLCs with separate client instances;
- handling PLCs that use different 32-bit word orders;
- building custom service, test, maintenance, and control applications;
- listing, reading, writing, and managing files on supported FC6A SD cards.

The repository keeps the historical `fc6a` name, while the current libraries use the
`MiSm` prefix to reflect the broader MicroSmart family.

> [!IMPORTANT]
> This project is under active development. Program upload, program download,
> provisioning, and some capture-derived commands are not yet complete production
> interfaces.

> [!CAUTION]
> Force I/O can override normal PLC-program control. Use it only during controlled
> testing when changing an output cannot create an unsafe machine condition.

---

## Libraries

| Library | Purpose |
|---|---|
| [`MiSmTCP.py`](src/MiSmTCP.py) | Maintenance Protocol communication over TCP/IP. The default PLC port is `2101`. |
| [`MiSmSerial.py`](src/MiSmSerial.py) | Maintenance Protocol communication over a serial connection. The default baud rate is `9600`. |
| [`MiSmSDCard.py`](src/MiSmSDCard.py) | SD-card helper that works with an existing `MiSmTCP` or `MiSmSerial` client. |
| [`fc6a.py`](src/fc6a.py) | Original library retained for reference and compatibility while the MiSm libraries replace it. |

### Common register operations

`MiSmTCP` and `MiSmSerial` share the same user-facing calls for the core PLC
operations:

```text
read()          write()
read_bit()      write_bit()
read_block()    write_block()
read_uint()     write_uint()
read_float()    write_float()
read_timer()    write_timer()
write_counter()
read_error()
input()         output()
force_io()      force()
```

See the [common API guide](src/API/MiSm_Common_API.md) for portable code that can use
either transport.

### Supported value types

- Individual bits
- 16-bit words
- Consecutive word blocks
- Multi-register unsigned integers
- 32-bit IEEE-754 floats
- Timer information and values
- Counter preset values
- Raw PLC error-code words
- Physical inputs and outputs

---

## Requirements

- Python 3
- An IDEC PLC with Maintenance Communication enabled
- Ethernet access for `MiSmTCP`, or a supported serial connection for `MiSmSerial`
- [`pyserial`](https://pypi.org/project/pyserial/) only when using `MiSmSerial`

Clone the repository:

```bash
git clone https://github.com/Makerspace-Bangor/fc6a.git
cd fc6a
```

Install the Serial dependency when needed:

```bash
python3 -m pip install pyserial
```

The libraries are currently distributed as source modules. Add `src` to
`PYTHONPATH` while working from the repository:

```bash
export PYTHONPATH="$PWD/src:$PYTHONPATH"
```

---

## Quick Start

### TCP

```python
from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    status = plc.read("D8005")
    running = plc.read_bit("M8125")
    words = plc.read_block("D0100", count=4)

    print(f"D8005: {status}")
    print(f"Running: {running}")
    print(f"D0100-D0103: {words}")
```

`MiSmTCP` uses TCP port `2101` by default:

```python
plc = MiSmTCP("192.168.1.50", port=2101)
```

### Serial

```python
from MiSmSerial import MiSmSerial


plc = MiSmSerial("/dev/ttyACM0", baud=9600)

try:
    status = plc.read("D8005")
    running = plc.read_bit("M8125")
    words = plc.read_block("D0100", count=4)

    print(f"D8005: {status}")
    print(f"Running: {running}")
    print(f"D0100-D0103: {words}")
finally:
    plc.close()
```

### The same application code with either transport

After creating the client, the core calls are the same:

```python
status = plc.read("D8005")
relay = plc.read_bit("M8010")
serial_number = plc.read_uint("D0105", count=2, endian=1)
temperature = plc.read_float("D0200", endian=0)

plc.write("D0100", 1234)
plc.write_bit("M8010", 1)
```

### Address examples

```python
plc.read("D0100")          # One 16-bit data register
plc.read_bit("M8010")      # One internal relay
plc.read_bit("D0100.3")    # Bit 3 inside D0100
plc.read_block("D0100", 4)
plc.read_float("D0200", endian=0)
```

The libraries accept `endian=0` or `endian=1` where word order matters for multi-word
values.

---

## SD Card Access

`MiSmSDCard` borrows an existing PLC connection.

```python
from MiSmSDCard import MiSmSDCard
from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    sd = MiSmSDCard(plc)

    print(sd.checkSD())

    for entry in sd.listSD("/FCDATA01"):
        entry_type = "DIR " if entry["is_dir"] else "FILE"
        print(entry_type, entry["name"], entry["size"])
```

Currently implemented SD-card operations include:

```text
checkSD()       listSD()        walkSD()
readSD()        saveSD()        writeSD()
mkdirSD()       makedirsSD()    deleteSD()
```

SD-card commands are based on observed Maintenance Protocol behavior and should be
tested carefully with the target PLC and media.

---

## API Documentation

| Guide | Description |
|---|---|
| [MiSm Common API](src/API/MiSm_Common_API.md) | Methods called the same way through `MiSmTCP` and `MiSmSerial`. |
| [MiSmTCP API](src/API/MiSmTCP_API.md) | TCP constructor, connection management, register access, and TCP-specific behavior. |
| [MiSmSerial API](src/API/MiSmSerial_API.md) | Serial constructor, serial settings, register access, and Serial-specific behavior. |

Additional examples are available under:

- [`src/examples`](src/examples)
- [`src/fc6a_examples`](src/fc6a_examples)
- [`documentation`](documentation)

---

## Development Status

The core register API supports practical monitoring and control applications over TCP
and Serial.

Areas still under development include:

- ZLD binary program download
- Program upload and integrity verification
- PLC security-bit handling
- Factory reset and provisioning workflows
- Dedicated HMI Maintenance Protocol support
- Additional testing and documentation for capture-derived commands

### Planned library organization

| Name | Intended scope |
|---|---|
| `MiSmTCP` | Maintenance Protocol over TCP sockets |
| `MiSmSerial` | Maintenance Protocol over serial connections |
| `MiSmSDCard` | PLC SD-card file operations |
| `MiSmFactory` | PLC programming, reset, and provisioning |
| `MiSmHMI` | IDEC HMI Maintenance Protocol operations |

---

## Legacy `fc6a.py`

[`src/fc6a.py`](src/fc6a.py) is the original project library.

It associated some operations with fixed data types, which made it difficult to extend
the API to newly discovered Maintenance Protocol operations. The newer MiSm libraries
separate transport and feature responsibilities more clearly.

The legacy file remains available while applications move to `MiSmTCP`,
`MiSmSerial`, and the related helper libraries.

---

## Safety and Reliability

PLC communication software can change machine state.

- Verify addresses and data types before writing.
- Treat dotted word-bit writes as read-modify-write operations.
- Use separate client instances when working with several PLCs concurrently.
- Confirm output state after communication timeouts when repeating a write could
  matter.
- Keep emergency stops and safety interlocks independent of this software.
- Test capture-derived and SD-card operations on noncritical equipment before field use.

---

## License

This project is licensed under the [GNU General Public License v2.0](LICENSE).
