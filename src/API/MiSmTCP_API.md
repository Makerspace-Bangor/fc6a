# MiSmTCP API Guide

**Library:** `MiSmTCP.py`  
**Purpose:** IDEC MicroSmart / FC6A Maintenance Protocol over TCP/IP  
**Source reviewed:** `main` branch of the Makerspace-Bangor `fc6a` repository  
**Review date:** 2026-07-23

> This guide documents the behavior implemented by the current source file. It does
> not claim that every syntactically accepted device type is writable on every PLC,
> nor that every capture-derived command is officially supported by IDEC.

## 1. Overview

`MiSmTCP` is a Python client for communicating with IDEC MicroSmart and FC6A PLCs
through the ASCII Maintenance Protocol over TCP.

The library:

- requires only the Python standard library;
- supports persistent or per-request TCP connections;
- validates the XOR BCC in PLC replies;
- can automatically determine whether request BCC calculation includes the ENQ byte;
- reads and writes words, bits, blocks, multi-register integers, and IEEE-754 floats;
- includes timer, counter, error-code, physical I/O, and forced-output helpers;
- intentionally follows the public calling style of `MiSmSerial` where practical.

The PLC Ethernet connection must be configured as a **Maintenance Communication
server**.

## 2. Installation

`MiSmTCP.py` is a standalone module. Place it in the same directory as the script
using it, or place it somewhere on Python's module search path.

```python
from MiSmTCP import MiSmTCP
```

No third-party Python packages are required.

## 3. Quick Start

```python
from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    d100 = plc.read("D0100")
    running = plc.read_bit("M8125")
    temperature = plc.read_float("D0200")

    print(f"D0100: {d100}")
    print(f"M8125: {running}")
    print(f"D0200 float: {temperature}")
```

The context manager opens the connection on entry and closes it on exit.

A manual connection pattern is also supported:

```python
from MiSmTCP import MiSmTCP


plc = MiSmTCP("192.168.1.50")

try:
    print(plc.read("D8005"))
finally:
    plc.close()
```

## 4. Constructor

```python
MiSmTCP(
    host,
    port=2101,
    device="FF",
    timeout=1.0,
    debug=False,
    bcc_mode="auto",
    keep_open=True,
    connect_now=True,
    precision=3,
)
```

### Parameters

| Parameter | Meaning |
|---|---|
| `host` | PLC hostname or IP address. |
| `port` | Maintenance Protocol TCP port. Default: `2101`. |
| `device` | Two-character PLC device number. Default: `"FF"` for a direct 1:1 connection. |
| `timeout` | Socket timeout in seconds. Default: `1.0`. |
| `debug` | Prints transmitted ASCII, transmitted hex, and received hex when true. |
| `bcc_mode` | Request BCC mode: `"auto"`, `"enq"`, or `"no_enq"`. |
| `keep_open` | Keep one TCP socket open across requests when true. |
| `connect_now` | Connect during construction when both this and `keep_open` are true. |
| `precision` | Decimal places returned by `read_float()`. Default: `3`. |

### BCC modes

- `"auto"` first sends a request with ENQ included in the XOR calculation.
- If the PLC replies with NAK code `10`, the request is retried with ENQ excluded.
- After a successful ACK, the selected mode is retained in `plc.bcc_mode`.
- `"enq"` always includes ENQ.
- `"no_enq"` always excludes ENQ.

For most FC6A Ethernet connections, start with the default `"auto"`.

## 5. Connection Management

### `connect()`

```python
plc.connect()
```

Opens the TCP socket when no socket is already open.

### `close()`

```python
plc.close()
```

Closes the socket and clears the internal socket reference.

### `disconnect`

Alias of `close()`.

```python
plc.disconnect()
```

### `reconnect()`

```python
plc.reconnect()
```

Closes the existing socket and opens a new one.

### Context manager

```python
with MiSmTCP("192.168.1.50") as plc:
    value = plc.read("D0100")
```

`__enter__()` calls `connect()`. `__exit__()` calls `close()`.

### Persistent versus per-request sockets

```python
# Persistent connection
plc = MiSmTCP("192.168.1.50", keep_open=True)

# New connection for each request
plc = MiSmTCP("192.168.1.50", keep_open=False)
```

With a persistent connection, a socket error or timeout causes the library to reconnect
once and retry the same request.

Because there is no internal transaction lock, do not issue concurrent requests through
the same `MiSmTCP` instance from multiple threads. Use one instance per worker or add
external locking.

## 6. Addressing

### String addresses

Most calls accept a normal IDEC device address:

```python
plc.read("D0100")
plc.read_bit("M8070")
plc.write_bit("Y0000", 1)
plc.read_float("D0200")
```

The first character is passed as the Maintenance Protocol data type. The remaining
characters must be decimal digits.

Common examples include:

| Address | Typical meaning |
|---|---|
| `D0100` | Data register |
| `M8070` | Internal or special relay |
| `X0000` | Physical input |
| `Y0000` | Physical output |
| `T0001` | Timer preset register |
| `C0099` | Counter preset register |

The library does not maintain a PLC-model-specific allocation table. An address can be
syntactically valid to the library and still be unavailable, read-only, or inappropriate
for the connected PLC.

### Integer address plus `dtype`

An integer address requires an explicit one-character `dtype`:

```python
value = plc.read(100, dtype="D")
bit = plc.read_bit(8070, dtype="M")
```

Without `dtype`, integer addressing raises `ValueError`.

### Dotted word-bit syntax

Bits inside a word can be addressed with `.0` through `.15`:

```python
bit_3 = plc.read("D0100.3")
plc.write("D0100.3", 1)

bit_15 = plc.read_bit("D0100.15")
plc.write_bit("D0100.15", 0)
```

Padded and unpadded bit numbers are equivalent:

```python
plc.read("D0100.1")
plc.read("D0100.01")
```

A dotted write is a **read-modify-write of the entire 16-bit word**. It reads the base
word, changes one bit locally, and writes the whole word back. Avoid this pattern when
other logic may change another bit in that word between the read and write.

### I/O aliases

The physical I/O helpers accept these aliases:

- `Q0` maps to `Y0000`;
- `I0` maps to `X0000`;
- integer `0` means output or input zero according to the method being called.

## 7. Word Access

### `read()`

```python
read(addr, endian=0, dtype=None) -> int
```

Reads one 16-bit word.

```python
value = plc.read("D0100")
print(value)  # 0 through 65535
```

Integer form:

```python
value = plc.read(100, dtype="D")
```

Dotted form returns one bit:

```python
enabled = plc.read("D0100.7")
```

The `endian` parameter is accepted for compatibility but is not used for a single
16-bit word.

### `write()`

```python
write(addr, value, endian=0, dtype=None) -> int
```

Writes one 16-bit word and returns the value actually encoded.

```python
written = plc.write("D0100", 1234)
```

The value is masked to 16 bits:

```python
plc.write("D0100", -1)       # writes 65535
plc.write("D0100", 0x12345)  # writes 0x2345
```

Dotted form writes one word bit through read-modify-write:

```python
plc.write("D0100.5", 1)
```

The `endian` parameter is accepted for compatibility but is not used for a single
16-bit word.

## 8. Bit Access

### `read_bit()`

```python
read_bit(addr, endian=0, dtype=None) -> int
```

Reads a native bit device or a bit inside a word. Returns `0` or `1`.

```python
mounted = plc.read_bit("M8070")
input_0 = plc.read_bit("X0000")
output_7 = plc.read_bit("Y0007")
word_bit = plc.read_bit("D0100.15")
```

Aliases are accepted:

```python
input_0 = plc.read_bit("I0")
output_0 = plc.read_bit("Q0")
```

Integer form:

```python
mounted = plc.read_bit(8070, dtype="M")
```

For a dotted address, the method reads the base word and masks the requested bit.

### `write_bit()`

```python
write_bit(addr, on, endian=0, dtype=None) -> int
```

Writes a native bit or changes one bit in a word. Returns `0` or `1`.

```python
plc.write_bit("M8010", 1)
plc.write_bit("Y0000", 0)
plc.write_bit("Q0", 1)
plc.write_bit("D0100.4", 1)
```

For native `M`, `X`, `Y`, or `R` addressing, the library uses the one-bit protocol
data types `m`, `x`, `y`, and `r`.

For a dotted address, the method performs a whole-word read-modify-write.

The `endian` parameter is accepted for compatibility and is not used.

## 9. Physical I/O Convenience Methods

### `input()`

```python
input(bit) -> int
```

Reads one physical input and returns `0` or `1`.

```python
state = plc.input(0)
state = plc.input("I0")
state = plc.input("X0000")
```

This method accepts only input-style `I` or `X` addresses.

### `output()`

```python
output(bit, on=1) -> int
```

Writes one physical output and returns `0` or `1`.

```python
plc.output(0, 1)
plc.output("Q0", 0)
plc.output("Y0007", 1)
```

The method emits the five-character payload used by the observed HMI/PLC I/O command,
such as `00001` for output zero on.

This method accepts only output-style `Q` or `Y` addresses.

## 10. Block Access

### `read_block()`

```python
read_block(addr, count=2, endian=0, dtype=None) -> list[int]
```

Reads `count` consecutive 16-bit registers.

```python
words = plc.read_block("D0100", count=4)
# [D0100, D0101, D0102, D0103]
```

Constraints:

- `count` must be `1` through `127`;
- each returned element is `0` through `65535`;
- `endian=0` preserves PLC reply order;
- `endian=1` reverses the complete returned word list.

```python
normal = plc.read_block("D0100", 4, endian=0)
reversed_words = plc.read_block("D0100", 4, endian=1)
```

### `write_block()`

```python
write_block(addr, values, endian=0, dtype=None) -> list[int]
```

Writes consecutive 16-bit registers.

```python
written = plc.write_block("D0100", [1, 2, 3, 4])
```

Constraints and behavior:

- `values` must not be empty;
- at most `127` registers can be written;
- every value is masked to 16 bits;
- `endian=1` reverses transmission order;
- the return value is the masked list in the caller's original order.

```python
plc.write_block("D0100", [0x1234, -1])
# Writes 0x1234 and 0xFFFF
```

## 11. Multi-register Unsigned Integers

### `read_unit()`

```python
read_unit(addr, count=2, endian=0, dtype=None) -> int
```

Reads multiple words and combines them into one unsigned integer.

```python
serial_raw = plc.read_unit("D0105", count=2)
```

After `read_block()` applies the requested word order, the first word becomes the most
significant word of the returned integer.

For two words:

```text
result = (word_0 << 16) | word_1
```

Use `endian=1` when the PLC stores the low and high words in the opposite order from
the result you need.

### `write_unit()`

```python
write_unit(addr, value, count=2, endian=0, dtype=None) -> list[int]
```

Splits an unsigned integer into `count` 16-bit words and writes them.

```python
plc.write_unit("D0100", 0x12345678, count=2)
```

Constraints:

- `count` must be `1` through `127`;
- `value` must be nonnegative;
- `value` must fit within `16 * count` bits.

Unlike `write()` and `write_block()`, this method rejects values that do not fit rather
than silently masking the complete integer.

## 12. Floating-point Access

### `read_float()`

```python
read_float(addr, endian=0, dtype=None) -> float
```

Reads an IEEE-754 single-precision float from two consecutive registers.

```python
temperature = plc.read_float("D0200")
```

Word order:

- `endian=0`: low word at `addr`, high word at `addr + 1`;
- `endian=1`: high word at `addr`, low word at `addr + 1`.

The result is rounded with Python `round()` using `plc.precision`, which defaults to
three decimal places.

```python
plc = MiSmTCP("192.168.1.50", precision=4)
value = plc.read_float("D0200", endian=0)
```

### `write_float()`

```python
write_float(addr, value, endian=0, dtype=None) -> float
```

Writes an IEEE-754 single-precision float into two consecutive registers and returns
`float(value)`.

```python
plc.write_float("D0200", 77.25)
plc.write_float("D0200", 77.25, endian=1)
```

The `precision` setting affects only `read_float()`. It does not round before writing.

## 13. Timers, Counters, and Error Codes

### `read_timer()`

```python
read_timer(tnum, count=1) -> list[dict]
```

Reads IDEC timer information.

```python
timers = plc.read_timer(0, count=2)

for timer in timers:
    print(timer["timer"])
    print(timer["current"])
    print(timer["preset"])
    print(timer["status"])
```

Each result has this form:

```python
{
    "timer": 0,
    "current": 150,
    "preset": 300,
    "status": 0,
}
```

`count` must be `1` through `48`.

The method returns raw numeric fields. It does not decode the timer status byte into
named flags.

### `write_timer()`

```python
write_timer(tnum, value, preset=None) -> int
```

Writes the timer current/present value. When `preset` is supplied, the preset is written
first.

```python
plc.write_timer(0, 150)
plc.write_timer(0, 150, preset=300)
```

Constraints:

- timer number: `0` through `9999`;
- current value: `0` through `65535`;
- preset value: `0` through `65535`.

The method returns the current value written through the lowercase `t` data type.

### `write_counter()`

```python
write_counter(cnum, preset) -> int
```

Writes one counter preset through data type `C`.

```python
plc.write_counter(10, 500)
```

This is a convenience wrapper around:

```python
plc.write(10, 500, dtype="C")
```

### `read_error()`

```python
read_error(addr=0, nbytes=12) -> list[int]
```

Reads Maintenance Protocol error-code words.

```python
errors = plc.read_error()
errors = plc.read_error(addr=0, nbytes=4)
```

Constraints:

- `nbytes` must be even;
- valid range is `2` through `12`;
- the result contains `nbytes // 2` integers.

This method returns raw words. It does not map the values to IDEC error names.

## 14. Forced Output Control

> Forced I/O can override normal PLC program control. Use it only when the machine is
> in a condition where energizing or de-energizing an output is safe. Do not treat a
> software force as a safety function.

### `force_io()`

```python
force_io(enable=True) -> int
```

Enables or disables the capture-derived IDEC Force I/O mode.

```python
plc.force_io(True)
plc.force_io(False)
```

Returns `1` when enabled and `0` when disabled.

### `force()`

```python
force(bit, on=1) -> int
```

Forces one physical output on or off.

```python
plc.force("Q0", 1)
plc.force(0, 0)
```

Current implementation limits this method to `Q0` through `Q7`.

The method:

1. enables Force I/O mode;
2. sends the output state;
3. sends the observed force-control command;
4. returns `0` or `1`.

### `release_force()`

```python
release_force() -> int
```

Disables Force I/O mode.

```python
plc.release_force()
```

This is a global release operation in the current API. It does not accept an individual
output address.

### Force aliases

```python
plc.force_output("Q0", 1)  # alias of force()
plc.force_release()        # alias of release_force()
```

### Safe cleanup pattern

```python
from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    try:
        plc.force("Q0", 1)
        # Perform the required test.
    finally:
        plc.release_force()
```

A process crash, cable loss, PLC power event, or protocol failure can prevent the
`finally` block from reaching the PLC. Machine-level test procedures must account for
that possibility.

## 15. Upload API Status

### `upload()`

```python
upload(filename=None) -> bytes
```

The source presents this as a PLC-program upload method that optionally writes the
received bytes to a file.

However, in the current source it calls names that are not implemented or defined in
the module:

- `PLCPasswordRequired`;
- `_upload_begin()`;
- `_unlock_upload()`;
- `_upload_next_block()`.

Therefore, `upload()` is currently an incomplete API and should not be listed as
operational.

Depending on the first failing path, calling it will raise `AttributeError` or
`NameError`.

### `upload_sha256()`

```python
upload_sha256() -> str
```

This method calls `upload()` and hashes the returned bytes with SHA-256. Because
`upload()` is incomplete, this method is also not currently operational.

It also performs a new upload internally and does not accept a previously downloaded
blob or filename.

## 16. Module-level Helpers and Aliases

### Class aliases

```python
from MiSmTCP import PLC, Client

plc1 = PLC("192.168.1.50")
plc2 = Client("192.168.1.51")
```

Both `PLC` and `Client` are aliases of `MiSmTCP`.

### Module-level I/O wrappers

```python
from MiSmTCP import MiSmTCP, input, output


plc = MiSmTCP("192.168.1.50")

try:
    x0 = input(plc, "I0")
    output(plc, "Q0", 1)
finally:
    plc.close()
```

These wrappers call `plc.input()` and `plc.output()`.

Because the module-level function is named `input`, importing it directly shadows
Python's built-in `input()` function. Explicitly importing only `MiSmTCP` avoids that
conflict.

### `Reply`

The module defines a `Reply` dataclass used by the low-level parser.

Fields:

```python
Reply(
    kind,
    raw,
    ctrl=b"",
    device="",
    command="",
    data=b"",
    bcc_recv=None,
    bcc_calc=None,
    bcc_ok=False,
    ng_code="",
    nak_code="",
)
```

Possible `kind` values include:

- `"ACK_OK"`;
- `"ACK_NG"`;
- `"NAK"`;
- `"MALFORMED"`;
- `"EMPTY"`;
- `"UNKNOWN"`.

Normal high-level methods convert unsuccessful replies into exceptions, so most users
do not interact with `Reply` directly.

### Reply predicates

```python
is_ack(reply)
is_nak(reply)
ack_ok(reply)
ack_ng(reply)
```

These operate on a `Reply` object. They are mainly useful when extending the low-level
protocol implementation.

## 17. Return Value Summary

| Method | Return value |
|---|---|
| `read()` | Integer `0..65535`, or `0/1` for dotted bit syntax |
| `write()` | Masked 16-bit integer, or `0/1` for dotted bit syntax |
| `read_bit()` | `0` or `1` |
| `write_bit()` | `0` or `1` |
| `input()` | `0` or `1` |
| `output()` | `0` or `1` |
| `read_block()` | List of 16-bit integers |
| `write_block()` | Masked input list in original caller order |
| `read_unit()` | Unsigned multi-register integer |
| `write_unit()` | List returned by `write_block()` |
| `read_float()` | Rounded Python float |
| `write_float()` | `float(value)` |
| `read_timer()` | List of timer dictionaries |
| `write_timer()` | Timer current value written |
| `write_counter()` | Counter preset value written |
| `read_error()` | List of raw error-code words |
| `force_io()` | `0` or `1` |
| `force()` | `0` or `1` |
| `release_force()` | `0` |
| `upload()` | Intended to return bytes, but incomplete |
| `upload_sha256()` | Intended to return SHA-256 hex, but depends on incomplete upload |

## 18. Exceptions and Failure Behavior

### `ValueError`

Used for invalid local arguments, including:

- malformed addresses;
- integer addresses without `dtype`;
- invalid bit numbers;
- invalid BCC mode;
- invalid block counts;
- invalid timer ranges;
- unsupported forced-output number;
- values too large for `write_unit()`.

### `IOError`

Used for protocol-level failures, including:

- NAK replies;
- ACK/NG replies;
- unexpected reply kind;
- reply BCC mismatch;
- unexpected data length or non-hex payload.

The error text includes the NAK or NG code and often the raw reply in hex.

### Socket exceptions

Connection failures and timeouts can surface as:

- `ConnectionRefusedError`;
- `TimeoutError`;
- `socket.timeout`;
- other `OSError` subclasses.

Example:

```python
import socket

from MiSmTCP import MiSmTCP


plc = None

try:
    plc = MiSmTCP("192.168.1.50", timeout=2.0)
    print(plc.read("D8005"))
except (ConnectionRefusedError, TimeoutError, socket.timeout, OSError) as exc:
    print(f"PLC communication failed: {exc}")
finally:
    if plc is not None:
        plc.close()
```

### Automatic retry

With `keep_open=True`, a socket error or timeout causes one reconnect and one retry of
the same request. This helps after cable changes or PLC power cycles.

For commands with side effects, remember that a timeout does not prove the PLC failed
to process the first request. Design higher-level operations so that repeating a command
is safe or can be verified afterward.

## 19. Practical Examples

### Read PLC status-related registers

```python
from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    running = plc.read_bit("M8125")
    error_word = plc.read("D8005")

    print(f"Running: {running}")
    print(f"D8005: {error_word} (0x{error_word:04X})")
```

### Read a two-register serial number field

```python
from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    words = plc.read_block("D0105", count=2)
    serial_a = plc.read_unit("D0105", count=2, endian=0)
    serial_b = plc.read_unit("D0105", count=2, endian=1)

    print(f"Raw words: {words}")
    print(f"Normal combined value: {serial_a}")
    print(f"Reversed combined value: {serial_b}")
```

Use the word order that matches the PLC program's storage convention.

### Blink an internal relay

```python
import time

from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    original = plc.read_bit("M8010")

    try:
        for _ in range(10):
            plc.write_bit("M8010", 1)
            time.sleep(0.25)
            plc.write_bit("M8010", 0)
            time.sleep(0.25)
    finally:
        plc.write_bit("M8010", original)
```

### Read a register block and decode bits

```python
from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    alarm_words = plc.read_block("D3500", count=3)

    for word_offset, word in enumerate(alarm_words):
        active_bits = [bit for bit in range(16) if word & (1 << bit)]
        print(f"D{3500 + word_offset:04d}: 0x{word:04X}, bits={active_bits}")
```

### Adjust timeout after construction

```python
plc = MiSmTCP("192.168.1.50", timeout=1.0)

try:
    plc.timeout = 3.0
    plc.reconnect()
    print(plc.read("D8005"))
finally:
    plc.close()
```

Changing `plc.timeout` updates the value used by future connection and receive logic.
An already-open socket retains its prior socket timeout until reconnecting or manually
calling `plc._sock.settimeout()`. Prefer `reconnect()` after changing it.

## 20. Current Limitations and Design Notes

1. **Program upload is incomplete.** The required internal methods and password
   exception are absent.
2. **No program download API is present.**
3. **No model-specific device validation is performed.**
4. **Single-word `endian` arguments are compatibility placeholders.**
5. **Dotted writes use whole-word read-modify-write.**
6. **`read_float()` rounds the returned value by default.**
7. **Block `endian=1` reverses the complete list, not byte order inside each word.**
8. **Forced output support is limited to `Q0..Q7`.**
9. **`release_force()` is global rather than per output.**
10. **The client is not internally thread-safe.**
11. **The library does not decode timer status or error-code words into named meanings.**
12. **High-level methods raise generic `IOError`; there are no distinct public protocol
    exception classes.**
13. **Request retry can repeat a command after an ambiguous timeout.**
14. **The module-level `input()` wrapper can shadow Python's built-in `input()`.**

## 21. Recommended Import Style

```python
from MiSmTCP import MiSmTCP
```

Prefer using methods on the object:

```python
with MiSmTCP("192.168.1.50") as plc:
    x0 = plc.input("I0")
    plc.output("Q0", 1)
```

This is clearer than importing the module-level `input()` and `output()` wrappers and
avoids shadowing Python's built-in `input()`.

## 22. Compact API Index

```text
MiSmTCP(host, port=2101, device="FF", timeout=1.0, debug=False,
        bcc_mode="auto", keep_open=True, connect_now=True, precision=3)

Connection:
    connect()
    close()
    disconnect()
    reconnect()

Words and bits:
    read(addr, endian=0, dtype=None)
    write(addr, value, endian=0, dtype=None)
    read_bit(addr, endian=0, dtype=None)
    write_bit(addr, on, endian=0, dtype=None)

Physical I/O:
    input(bit)
    output(bit, on=1)

Blocks and numeric types:
    read_block(addr, count=2, endian=0, dtype=None)
    write_block(addr, values, endian=0, dtype=None)
    read_unit(addr, count=2, endian=0, dtype=None)
    write_unit(addr, value, count=2, endian=0, dtype=None)
    read_float(addr, endian=0, dtype=None)
    write_float(addr, value, endian=0, dtype=None)

Timers, counters, and errors:
    read_timer(tnum, count=1)
    write_timer(tnum, value, preset=None)
    write_counter(cnum, preset)
    read_error(addr=0, nbytes=12)

Forced I/O:
    force_io(enable=True)
    force(bit, on=1)
    release_force()
    force_output(bit, on=1)
    force_release()

Incomplete:
    upload(filename=None)
    upload_sha256()
```

## Source

This guide was produced by reviewing:

- `https://github.com/Makerspace-Bangor/fc6a/blob/main/src/MiSmTCP.py`

The implementation is the authority when this guide and a later source revision differ.
