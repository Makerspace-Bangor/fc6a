# MiSmSerial API Guide

**Library:** `MiSmSerial.py`  
**Purpose:** IDEC MicroSmart / FC6A Maintenance Protocol over a serial connection  
**Source reviewed:** `main` branch of the Makerspace-Bangor `fc6a` repository  
**Review date:** 2026-07-23

> This guide documents the behavior implemented by the current source file. It does
> not claim that every syntactically accepted operand is available or writable on every
> IDEC PLC model. Capture-derived commands are identified where the source identifies
> them that way.

## 1. Overview

`MiSmSerial` is a Python client for communicating with IDEC MicroSmart and FC6A PLCs
through the ASCII Maintenance Protocol over a serial port.

The library:

- defaults to `/dev/ttyACM0`-style serial usage at `9600` baud;
- uses ASCII Maintenance Protocol frames terminated by carriage return;
- validates the XOR BCC in PLC replies;
- can automatically determine whether request BCC calculation includes the ENQ byte;
- reads and writes words, bits, blocks, unsigned integers, and IEEE-754 floats;
- includes timer, counter, error-code, physical I/O, and forced-output helpers;
- requires the third-party `pyserial` package.

Unlike `MiSmTCP`, the serial port is opened immediately by the constructor. The current
class does not provide a public `connect()`, `reconnect()`, or context-manager API.

## 2. Installation

Install `pyserial`:

```bash
python3 -m pip install pyserial
```

Place `MiSmSerial.py` in the same directory as the script using it, or place it
somewhere on Python's module search path.

```python
from MiSmSerial import MiSmSerial
```

## 3. Quick Start

```python
from MiSmSerial import MiSmSerial


plc = MiSmSerial("/dev/ttyACM0")

try:
    d100 = plc.read("D0100")
    running = plc.read_bit("M8125")
    temperature = plc.read_float("D0200")

    print(f"D0100: {d100}")
    print(f"M8125: {running}")
    print(f"D0200 float: {temperature}")
finally:
    plc.close()
```

Always close the serial port when finished.

## 4. Constructor

```python
MiSmSerial(
    port,
    device="FF",
    baud=9600,
    timeout=1.0,
    bytesize=8,
    parity="N",
    stopbits=1,
    debug=False,
    bcc_mode="auto",
)
```

### Parameters

| Parameter | Meaning |
|---|---|
| `port` | Serial device path, such as `"/dev/ttyACM0"`. |
| `device` | Two-character PLC device number. Default: `"FF"` for direct 1:1 communication. |
| `baud` | Serial baud rate. Default: `9600`. |
| `timeout` | PySerial read timeout in seconds. Default: `1.0`. |
| `bytesize` | Serial data-bit setting passed to `serial.Serial`. Default: `8`. |
| `parity` | Serial parity setting passed to `serial.Serial`. Default: `"N"`. |
| `stopbits` | Serial stop-bit setting passed to `serial.Serial`. Default: `1`. |
| `debug` | Prints transmitted ASCII, transmitted hex, and received hex when true. |
| `bcc_mode` | Request BCC mode: `"auto"`, `"enq"`, or `"no_enq"`. |

The constructor immediately creates a `serial.Serial` object and opens the port. A
missing device, unavailable port, permission problem, or invalid serial setting can
therefore raise a PySerial exception during construction.

### Default module constants

```python
BAUD = 9600
DEFAULT_DEVICE = "FF"
DEFAULT_TIMEOUT = 1.0
PRECISION = 3
```

`PRECISION` controls the number of decimal places returned by `read_float()`. It is a
module-level value rather than a constructor parameter.

### BCC modes

- `"auto"` first sends a request with ENQ included in the XOR calculation.
- If the PLC returns NAK code `10`, the request is retried with ENQ excluded.
- After a successful ACK, the selected mode is retained in `plc.bcc_mode`.
- `"enq"` always includes ENQ in the request BCC.
- `"no_enq"` always excludes ENQ from the request BCC.

Start with the default `"auto"` unless the required mode is already known.

## 5. Serial-Port Lifecycle

### `close()`

```python
plc.close()
```

Closes the underlying PySerial port when it is open.

The current class does not define:

- `connect()`;
- `disconnect()`;
- `reconnect()`;
- `__enter__()` or `__exit__()`.

After calling `close()`, the documented high-level pattern is to create a new
`MiSmSerial` instance when another session is needed.

### Recommended cleanup pattern

```python
from MiSmSerial import MiSmSerial


plc = None

try:
    plc = MiSmSerial("/dev/ttyACM0", timeout=2.0)
    print(plc.read("D8005"))
finally:
    if plc is not None:
        plc.close()
```

### Threading

The library has no internal transaction lock. Do not issue simultaneous requests from
multiple threads through the same `MiSmSerial` instance. Use one client per worker or
protect all calls with an external lock.

## 6. Addressing

### String addresses

Most calls accept an IDEC device address consisting of one data-type character followed
by a decimal operand number:

```python
plc.read("D0100")
plc.read_bit("M8070")
plc.write_bit("Y0000", 1)
plc.read_float("D0200")
```

Common examples include:

| Address | Typical meaning |
|---|---|
| `D0100` | Data register |
| `M8070` | Internal or special relay |
| `X0000` | Physical input |
| `Y0000` | Physical output |
| `T0001` | Timer preset register |
| `C0099` | Counter preset register |

The library does not contain a PLC-model-specific allocation map. A syntactically
accepted address may still be unavailable, read-only, or inappropriate on the connected
PLC.

### Integer address plus `dtype`

An integer operand requires a one-character `dtype`:

```python
value = plc.read(100, dtype="D")
bit = plc.read_bit(8070, dtype="M")
```

Without `dtype`, integer addressing raises `ValueError`.

### Dotted word-bit syntax

Use dotted syntax only with `read_bit()` and `write_bit()`:

```python
bit_3 = plc.read_bit("D0100.3")
plc.write_bit("D0100.3", 1)

bit_15 = plc.read_bit("M8004.15")
plc.write_bit("M8004.15", 0)
```

`write_bit()` validates a dotted bit number as `0` through `15` and performs a
read-modify-write of the entire base word.

Do **not** pass dotted syntax to `read()` or `write()`. The shared address parser converts
a dotted address to a linear operand number rather than reading or writing a bit. For
some addresses this can target a different register; for larger addresses it can fail
the `0..9999` operand check.

```python
# Correct:
value = plc.read_bit("D0100.3")

# Do not use:
value = plc.read("D0100.3")
```

The current `read_bit()` dotted path does not explicitly reject bit numbers above `15`.
Treat `0..15` as the supported range.

### Dotted writes are not atomic

A dotted write:

1. reads the complete 16-bit word;
2. modifies one bit locally;
3. writes the complete word back.

Avoid it when PLC logic or another client may change another bit in the same word
between the read and write.

### I/O aliases

The physical I/O helpers accept:

- `Q0` as an alias for `Y0000`;
- `I0` as an alias for `X0000`;
- integer `0` as input or output zero according to the method being called.

## 7. Word Access

### `read()`

```python
read(addr, endian=0, dtype=None) -> int
```

Reads one 16-bit word with the Maintenance Protocol Read N Bytes command.

```python
value = plc.read("D0100")
print(value)  # 0 through 65535
```

Integer form:

```python
value = plc.read(100, dtype="D")
```

The `endian` argument is accepted for compatibility but is not used for a single word.

Do not use dotted addresses with this method.

### `write()`

```python
write(addr, value, endian=0, dtype=None) -> int
```

Writes one 16-bit word with the Maintenance Protocol Write N Bytes command and returns
the value actually encoded.

```python
written = plc.write("D0100", 1234)
```

The input is masked to 16 bits:

```python
plc.write("D0100", -1)       # writes 65535
plc.write("D0100", 0x12345)  # writes 0x2345
```

The `endian` argument is accepted for compatibility but is not used for a single word.

Do not use dotted addresses with this method. Use `write_bit()` for a word bit.

## 8. Bit Access

### `read_bit()`

```python
read_bit(addr, endian=0, dtype=None) -> int
```

Reads a native bit operand or one bit inside a word. Returns `0` or `1`.

```python
mounted = plc.read_bit("M8070")
input_0 = plc.read_bit("X0000")
output_7 = plc.read_bit("Y0007")
word_bit = plc.read_bit("D0100.15")
```

Integer form:

```python
mounted = plc.read_bit(8070, dtype="M")
```

Native bit addressing supports `X`, `Y`, `M`, and `R`, which are converted to the
lowercase Maintenance Protocol data types `x`, `y`, `m`, and `r`.

For a dotted address, the base word is read and the selected bit is masked locally.

The `endian` argument is accepted for compatibility and is not used.

### `write_bit()`

```python
write_bit(addr, on, endian=0, dtype=None) -> int
```

Writes a native bit operand or changes one bit inside a word. Returns `0` or `1`.

```python
plc.write_bit("M8010", 1)
plc.write_bit("Y0000", 0)
plc.write_bit("D0100.4", 1)
```

Integer form:

```python
plc.write_bit(8010, 1, dtype="M")
```

For native bit devices, the method emits a Write 1 Bit request.

For dotted syntax, it performs a whole-word read-modify-write.

The `endian` argument is accepted for compatibility and is not used.

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

The source intentionally builds the observed five-character output payload:

```text
Q0 ON  -> 00001
Q0 OFF -> 00000
Q7 ON  -> 00071
```

This method accepts only output-style `Q` or `Y` addresses.

The source notes that this helper's payload shape is intentionally distinct from the
general `write_bit()` implementation.

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

Constraints and behavior:

- `count` must be `1` through `127`;
- each result is an integer from `0` through `65535`;
- `endian=0` preserves PLC reply order;
- `endian=1` reverses the complete returned word list.

```python
normal = plc.read_block("D0100", 4, endian=0)
reversed_words = plc.read_block("D0100", 4, endian=1)
```

`endian` changes word order, not byte order inside each 16-bit word.

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
- each value is masked to 16 bits;
- `endian=1` reverses transmission order;
- the returned list is the masked input in the caller's original order.

```python
plc.write_block("D0100", [0x1234, -1])
# Writes 0x1234 and 0xFFFF
```

## 11. Multi-register Unsigned Integers

### `read_uint()`

```python
read_uint(addr, count=2, endian=0, dtype=None) -> int
```

Reads multiple words and combines them into one unsigned integer.

```python
serial_raw = plc.read_uint("D0105", count=2, endian=1)
```

After `read_block()` applies the requested word order, the first word becomes the most
significant word of the result.

For two words:

```text
result = (word_0 << 16) | word_1
```

Use the `endian` value that matches the PLC program's word-storage convention.

### `write_uint()`

```python
write_uint(addr, value, count=2, endian=0, dtype=None) -> list[int]
```

Splits an unsigned integer into `count` 16-bit words and writes them.

```python
plc.write_uint("D0105", 69420, count=2, endian=1)
```

Constraints:

- `count` must be `1` through `127`;
- `value` must be nonnegative;
- `value` must fit within `16 * count` bits.

Unlike `write()` and `write_block()`, the complete integer is rejected if it does not
fit rather than being silently truncated.

The return value is the list returned by `write_block()`.

> The method names in `MiSmSerial` are `read_uint()` and `write_uint()`. They are not
> named `read_unit()` or `write_unit()`.

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

The returned value is rounded with the module-level `PRECISION`, which defaults to
three decimal places.

To change it:

```python
import MiSmSerial as mism


mism.PRECISION = 4
plc = mism.MiSmSerial("/dev/ttyACM0")

try:
    print(plc.read_float("D0200"))
finally:
    plc.close()
```

Changing a separately imported local name does not modify the module variable used by
`read_float()`.

### `write_float()`

```python
write_float(addr, value, endian=0, dtype=None) -> float
```

Writes an IEEE-754 single-precision float to two consecutive registers and returns
`float(value)`.

```python
plc.write_float("D0200", 77.25)
plc.write_float("D0200", 77.25, endian=1)
```

`PRECISION` affects only returned values from `read_float()`. It does not round the
value before writing.

## 13. Timers, Counters, and Error Codes

### `read_timer()`

```python
read_timer(tnum, count=1) -> list[dict]
```

Reads IDEC timer information using data type `_`.

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

The status byte is returned as a raw integer. The library does not decode it into named
flags.

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

The method returns the current value written through lowercase timer data type `t`.

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

Reads raw Maintenance Protocol error-code words through data type `E`.

```python
errors = plc.read_error()
errors = plc.read_error(addr=0, nbytes=4)
```

Constraints:

- `nbytes` must be even;
- valid range is `2` through `12`;
- the result contains `nbytes // 2` integers.

The library does not map returned words to IDEC error descriptions.

## 14. Forced Output Control

> Forced I/O can override normal PLC program control. Use it only when the machine is
> in a condition where energizing or de-energizing an output is safe. A software force
> is not a safety function.

### `force_io()`

```python
force_io(enable=True) -> int
```

Enables or disables/suspends the capture-derived IDEC Force I/O mode.

```python
plc.force_io(True)
plc.force_io(False)
```

Returns `1` when enabled and `0` when disabled.

The source identifies the underlying frames as:

```text
Enable  -> W O 1
Disable -> W O 0
```

### `force()`

```python
force(bit, on=1) -> int
```

Forces one physical output on or off.

```python
plc.force("Q0", 1)
plc.force(0, 0)
```

Current implementation limits forced outputs to `Q0` through `Q7`.

The method:

1. enables Force I/O mode;
2. sends the selected output state using data type `]`;
3. sends the observed force-control request using data type `^`;
4. returns `0` or `1`.

### `release_force()` is broken in the current source

The current implementation is:

```python
def release_force(self, bit):
    return self.force(False)
```

This method:

- requires a `bit` argument but ignores it;
- passes `False` as the `bit` argument to `force()`;
- leaves `force()`'s `on` argument at its default of `1`;
- consequently treats `False` as output number `0` and issues a force-on sequence for
  `Q0`.

Do **not** call `release_force()` or its alias `force_release()` in the current version.

Use the working global Force I/O disable method instead:

```python
plc.force_io(False)
```

### `force_output`

`force_output` is an alias of `force()`:

```python
plc.force_output("Q0", 1)
```

### Safer cleanup pattern for the current source

```python
from MiSmSerial import MiSmSerial


plc = MiSmSerial("/dev/ttyACM0")

try:
    plc.force("Q0", 1)
    # Perform the required controlled test.
finally:
    plc.force_io(False)
    plc.close()
```

A process crash, disconnected cable, PLC power event, or failed serial transaction can
prevent cleanup from reaching the PLC. Machine-level test procedures must account for
that possibility.

## 15. Module-level Helpers

### Module-level I/O wrappers

```python
from MiSmSerial import MiSmSerial, input, output


plc = MiSmSerial("/dev/ttyACM0")

try:
    x0 = input(plc, "I0")
    output(plc, "Q0", 1)
finally:
    plc.close()
```

These functions call `plc.input()` and `plc.output()`.

Importing the module-level function named `input` shadows Python's built-in `input()`.
The clearer import style is:

```python
from MiSmSerial import MiSmSerial
```

and then:

```python
plc.input("I0")
plc.output("Q0", 1)
```

### `Reply`

The module defines a `Reply` dataclass used by the low-level parser.

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

High-level methods normally convert unsuccessful replies into exceptions, so most
applications do not interact with `Reply` directly.

### Reply predicates

```python
is_ack(reply)
is_nak(reply)
ack_ok(reply)
ack_ng(reply)
```

These helpers are mainly useful when extending the low-level protocol code.

## 16. Return Value Summary

| Method | Return value |
|---|---|
| `read()` | Integer `0..65535` |
| `write()` | Masked 16-bit integer |
| `read_bit()` | `0` or `1` |
| `write_bit()` | `0` or `1` |
| `input()` | `0` or `1` |
| `output()` | `0` or `1` |
| `read_block()` | List of 16-bit integers |
| `write_block()` | Masked input list in original caller order |
| `read_uint()` | Unsigned multi-register integer |
| `write_uint()` | List returned by `write_block()` |
| `read_float()` | Rounded Python float |
| `write_float()` | `float(value)` |
| `read_timer()` | List of timer dictionaries |
| `write_timer()` | Timer current value written |
| `write_counter()` | Counter preset value written |
| `read_error()` | List of raw error-code words |
| `force_io()` | `0` or `1` |
| `force()` | `0` or `1` |
| `release_force()` | Broken; do not use in the current source |

## 17. Exceptions and Failure Behavior

### `ValueError`

Used for invalid local arguments, including:

- malformed addresses;
- integer addresses without `dtype`;
- invalid output or input aliases;
- invalid BCC mode;
- invalid block counts;
- invalid timer ranges;
- unsupported forced-output numbers;
- values too large for `write_uint()`.

### `IOError`

Used for Maintenance Protocol failures, including:

- NAK replies;
- ACK/NG replies;
- unexpected reply kinds;
- reply BCC mismatch;
- unexpected data length;
- non-hexadecimal payload data.

The exception text includes NAK or NG codes and often the raw reply in hexadecimal.

### PySerial exceptions

Serial failures can surface through PySerial exceptions, commonly including
`serial.SerialException`.

```python
import serial

from MiSmSerial import MiSmSerial


plc = None

try:
    plc = MiSmSerial("/dev/ttyACM0", timeout=2.0)
    print(plc.read("D8005"))
except serial.SerialException as exc:
    print(f"Serial connection failed: {exc}")
except IOError as exc:
    print(f"Maintenance Protocol request failed: {exc}")
finally:
    if plc is not None:
        plc.close()
```

### No automatic transport retry

The serial client does not reconnect or retry a request after a PySerial transport
failure. Recreate the client after restoring the serial connection.

The BCC `"auto"` fallback is a protocol-format retry specifically for NAK code `10`; it
is not a general serial retry mechanism.

## 18. Practical Examples

### Read PLC status-related operands

```python
from MiSmSerial import MiSmSerial


plc = MiSmSerial("/dev/ttyACM0")

try:
    running = plc.read_bit("M8125")
    error_word = plc.read("D8005")

    print(f"Running: {running}")
    print(f"D8005: {error_word} (0x{error_word:04X})")
finally:
    plc.close()
```

### Read and write a two-register serial-number field

```python
from MiSmSerial import MiSmSerial


plc = MiSmSerial("/dev/ttyACM0")

try:
    before = plc.read_uint("D0105", count=2, endian=1)
    written_words = plc.write_uint("D0105", 69420, count=2, endian=1)
    after_words = plc.read_block("D0105", count=2, endian=1)
    after_value = plc.read_uint("D0105", count=2, endian=1)

    print(f"Before: {before}")
    print(f"Written words: {written_words}")
    print(f"After words: {after_words}")
    print(f"After value: {after_value}")
finally:
    plc.close()
```

This follows the demonstration in the current module's `__main__` block.

### Blink an internal relay

```python
import time

from MiSmSerial import MiSmSerial


plc = MiSmSerial("/dev/ttyACM0")

try:
    original = plc.read_bit("M8010")

    for _ in range(10):
        plc.write_bit("M8010", 1)
        time.sleep(0.25)
        plc.write_bit("M8010", 0)
        time.sleep(0.25)

    plc.write_bit("M8010", original)
finally:
    plc.close()
```

For production code, place restoration in a nested `finally` block so it is attempted
even when the blink loop fails.

### Decode active bits from register words

```python
from MiSmSerial import MiSmSerial


plc = MiSmSerial("/dev/ttyACM0")

try:
    alarm_words = plc.read_block("D3500", count=3)

    for word_offset, word in enumerate(alarm_words):
        active_bits = [bit for bit in range(16) if word & (1 << bit)]
        print(f"D{3500 + word_offset:04d}: 0x{word:04X}, bits={active_bits}")
finally:
    plc.close()
```

### Explicit serial settings

```python
from MiSmSerial import MiSmSerial


plc = MiSmSerial(
    "/dev/ttyACM0",
    device="FF",
    baud=9600,
    timeout=1.5,
    bytesize=8,
    parity="N",
    stopbits=1,
    bcc_mode="auto",
)

try:
    print(plc.read("D0100"))
finally:
    plc.close()
```

## 19. Current Limitations and Design Notes

1. **The constructor opens the serial port immediately.**
2. **There is no public connect, reconnect, or context-manager interface.**
3. **There is no automatic serial reconnect or general request retry.**
4. **No PLC-model-specific operand validation is performed.**
5. **Dotted syntax is safe only with `read_bit()` and `write_bit()`.**
6. **Dotted writes use a non-atomic whole-word read-modify-write.**
7. **The dotted `read_bit()` path does not validate the bit as `0..15`.**
8. **Single-word and native-bit `endian` arguments are compatibility placeholders.**
9. **Block `endian=1` reverses the complete word list.**
10. **`read_float()` uses a module-global precision value rather than an instance
    setting.**
11. **Forced output support is limited to `Q0..Q7`.**
12. **`release_force()` and `force_release()` are broken and can force `Q0` on.**
13. **The client is not internally thread-safe.**
14. **Timer status and error-code words are returned without named decoding.**
15. **Protocol failures use generic `IOError`; no public protocol-specific exception
    classes are defined.**
16. **The module-level `input()` wrapper can shadow Python's built-in `input()`.**
17. **No PLC program upload or download API is present.**

## 20. Recommended Import and Usage Style

```python
from MiSmSerial import MiSmSerial
```

Use explicit object methods and guaranteed cleanup:

```python
plc = MiSmSerial("/dev/ttyACM0")

try:
    input_0 = plc.input("I0")
    plc.output("Q0", 1)
finally:
    plc.close()
```

For forced-output cleanup in the current version, call:

```python
plc.force_io(False)
```

Do not call `release_force()` until its implementation is corrected.

## 21. Compact API Index

```text
MiSmSerial(port, device="FF", baud=9600, timeout=1.0, bytesize=8,
           parity="N", stopbits=1, debug=False, bcc_mode="auto")

Lifecycle:
    close()

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
    read_uint(addr, count=2, endian=0, dtype=None)
    write_uint(addr, value, count=2, endian=0, dtype=None)
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
    force_output(bit, on=1)

Broken in current source:
    release_force(bit)
    force_release(bit)
```

## 22. Suggested Fix for `release_force()`

The current implementation should not call `force(False)`. To retain a global Force I/O
release API consistent with the implemented protocol, the minimal correction would be:

```python
def release_force(self) -> int:
    """Disable/suspend Force I/O mode."""
    return self.force_io(False)
```

The alias can then remain:

```python
force_release = release_force
```

This suggested correction is not part of the reviewed source; it is included here
because the current implementation can energize `Q0` instead of releasing force mode.

## Source

This guide was produced by reviewing:

- `https://github.com/Makerspace-Bangor/fc6a/blob/main/src/MiSmSerial.py`

The implementation is the authority when this guide and a later source revision differ.
