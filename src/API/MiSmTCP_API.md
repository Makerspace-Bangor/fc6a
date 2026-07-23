# MiSmSerial API Guide

**Library:** `MiSmSerial.py`  
**Transport:** Serial only  
**Protocol:** IDEC MicroSmart Maintenance Protocol, ASCII framing  
**Source:** `https://github.com/Makerspace-Bangor/fc6a/blob/main/src/MiSmSerial.py`  
**Source reviewed:** Current `main` branch, 888 lines  
**Review date:** 2026-07-23

This guide documents the public behavior actually implemented by `MiSmSerial.py`.

`MiSmSerial` and `MiSmTCP` share some register-access concepts, but their constructors,
connection handling, dependencies, method names, retries, and available operations are
not interchangeable.

---

## 1. What This Library Is

`MiSmSerial` communicates with an IDEC MicroSmart or FC6A PLC through a serial device,
such as:

```text
/dev/ttyACM0
/dev/ttyUSB0
COM3
```

It does **not** use a TCP port. TCP port `2101` is not defined or used anywhere in this
library.

The constructor opens the serial device immediately through `pyserial`.

### Implemented capabilities

- Read and write one 16-bit word
- Read and write one native PLC bit
- Read and modify a bit inside a word
- Read and write consecutive word blocks
- Read and write unsigned multi-register integers
- Read and write 32-bit IEEE-754 floats
- Read timer information
- Write timer current and preset values
- Write counter preset values
- Read Maintenance Protocol error-code words
- Read physical inputs through `I` or `X` aliases
- Write physical outputs through `Q` or `Y` aliases
- Send capture-derived Force I/O commands
- Validate reply BCC
- Automatically try both supported request-BCC conventions

### Not implemented

- Context-manager support
- Automatic serial reconnection
- Extended-memory access

---

## 2. Dependency

The library imports `serial`, which is supplied by `pyserial`.

```bash
python3 -m pip install pyserial
```

On Debian or Ubuntu systems, the distribution package may also be available:

```bash
sudo apt install python3-serial
```

---

## 3. Import

```python
from MiSmSerial import MiSmSerial
```

Recommended use:

```python
plc = MiSmSerial("/dev/ttyACM0")

try:
    value = plc.read("D0100")
    print(value)
finally:
    plc.close()
```

The class does not implement `with MiSmSerial(...) as plc:`.

---

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

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `port` | `str` | required | Serial device path or COM-port name. |
| `device` | `str` | `"FF"` | Two-character PLC communication device value. |
| `baud` | `int` | `9600` | Serial baud rate. |
| `timeout` | `float` | `1.0` | PySerial read timeout in seconds. |
| `bytesize` | `int` | `8` | Serial data-bit setting passed to `serial.Serial`. |
| `parity` | `str` | `"N"` | Serial parity passed to `serial.Serial`. |
| `stopbits` | `int` | `1` | Serial stop-bit setting passed to `serial.Serial`. |
| `debug` | `bool` | `False` | Print transmitted ASCII, transmitted hex, and received hex. |
| `bcc_mode` | `str` | `"auto"` | Request BCC mode: `"auto"`, `"enq"`, or `"no_enq"`. |

### Constructor behavior

The constructor stores:

```python
self.port
self.device
self.baud
self.timeout
self.debug
self.bcc_mode
```

It then immediately opens:

```python
serial.Serial(
    port=port,
    baudrate=baud,
    timeout=timeout,
    bytesize=bytesize,
    parity=parity,
    stopbits=stopbits,
)
```

A missing port, permissions problem, or unavailable device can therefore raise a
PySerial exception during construction.

### Device validation

The source checks only that `device` has a length of two characters, then converts it
to uppercase.

Although the exception text calls it "2 ASCII hex chars", the implementation does not
actually test whether both characters are hexadecimal.

### Example

```python
from MiSmSerial import MiSmSerial


plc = MiSmSerial(
    "/dev/ttyACM0",
    device="FF",
    baud=9600,
    timeout=1.0,
    bytesize=8,
    parity="N",
    stopbits=1,
    debug=False,
    bcc_mode="auto",
)

try:
    print(plc.read("D0100"))
finally:
    plc.close()
```

---

## 5. Module Constants

```python
BAUD = 9600
DEFAULT_DEVICE = "FF"
DEFAULT_TIMEOUT = 1.0
PRECISION = 3
```

`PRECISION` controls rounding in `read_float()`.

It is a module-level setting, not a constructor parameter.

```python
import MiSmSerial


MiSmSerial.PRECISION = 4
plc = MiSmSerial.MiSmSerial("/dev/ttyACM0")
```

---

## 6. Connection Lifecycle

### `close()`

```python
close() -> None
```

Closes the PySerial object when it exists and is open.

```python
plc.close()
```

There is no public reopen method. Create another `MiSmSerial` object to start a new
session after closing.

### Recommended pattern

```python
from MiSmSerial import MiSmSerial


plc = None

try:
    plc = MiSmSerial("/dev/ttyACM0")
    print(plc.read("D8005"))
finally:
    if plc is not None:
        plc.close()
```

---

## 7. Serial Framing and BCC

Requests use this form:

```text
ENQ + device + continuation + command + data-type + payload + BCC + CR
```

Replies use:

```text
ACK/NAK + device + command + data + BCC + CR
```

The reply parser includes the leading ACK or NAK byte in the reply BCC calculation.

### `bcc_mode="enq"`

The request XOR includes the ENQ byte.

### `bcc_mode="no_enq"`

The request XOR excludes the ENQ byte.

### `bcc_mode="auto"`

The source:

1. sends the request with ENQ included;
2. retries without ENQ only when the first reply is NAK code `10`;
3. changes `self.bcc_mode` to `"no_enq"` when the retry returns `ACK_OK`;
4. changes it to `"enq"` when the first request returns `ACK_OK`.

### Current `auto`-mode edge case

If the first response is NAK `10` and the no-ENQ retry returns anything other than
`ACK_OK`, `_xfer()` has no explicit return for that path. A high-level method may then
receive `None` instead of a `Reply` and fail with `AttributeError`.

Using a known BCC mode avoids this edge case:

```python
plc = MiSmSerial("/dev/ttyACM0", bcc_mode="enq")
```

or:

```python
plc = MiSmSerial("/dev/ttyACM0", bcc_mode="no_enq")
```

---

## 8. Address Forms

Most register methods accept either a string address:

```python
plc.read("D0100")
plc.read_bit("M8070")
```

or an integer plus `dtype`:

```python
plc.read(100, dtype="D")
plc.read_bit(8070, dtype="M")
```

An integer without `dtype` raises `ValueError`.

### Common data-type examples

| Prefix | Typical use in this library |
|---|---|
| `D` | Data register word |
| `M` | Internal relay word or bit |
| `X` | Physical input bit |
| `Y` | Physical output bit |
| `R` | Shift-register bit |
| `T` | Timer preset word |
| `t` | Timer current value word |
| `C` | Counter preset word |
| `E` | Error-code read |
| `_` | Timer-information read |

The library does not validate the address against the connected PLC model's actual
operand allocation.

### Operand range

The protocol formatter accepts operand numbers from `0` through `9999`.

---

## 9. Dotted Word-Bit Syntax

`read_bit()` and `write_bit()` have explicit support for addresses such as:

```python
plc.read_bit("D0100.3")
plc.write_bit("D0100.3", 1)
plc.read_bit("M8004.15")
```

### `write_bit()` dotted behavior

The method:

1. reads the entire base word;
2. changes the requested bit;
3. writes the entire word back.

This is a read-modify-write operation and is not atomic.

### Important parser behavior

The shared `_parse_addr()` helper also recognizes dotted syntax and converts it to:

```text
linear operand = word * 16 + bit
```

Therefore, dotted addresses must not be passed to normal word methods such as
`read()`, `write()`, `read_block()`, or `write_block()`.

For example:

```python
plc.read("D0100.3")
```

does not mean "read bit 3 of D0100" to `read()`. The parser converts it to operand
`1603`.

Use:

```python
plc.read_bit("D0100.3")
```

### Bit validation difference

`write_bit()` explicitly checks that dotted bit numbers are `0..15`.

The dotted path inside `read_bit()` converts the bit text to an integer but does not
explicitly check the range before shifting. Use only `0..15`.

---

## 10. Word API

### `read()`

```python
read(addr, endian=0, dtype=None) -> int
```

Reads one 16-bit word using Read N Bytes with a byte count of `2`.

```python
value = plc.read("D0100")
```

Integer-address form:

```python
value = plc.read(100, dtype="D")
```

Return value:

```text
0 through 65535
```

The `endian` argument is accepted but is not used in this method.

### `write()`

```python
write(addr, value, endian=0, dtype=None) -> int
```

Writes one 16-bit word using Write N Bytes with a byte count of `2`.

```python
written = plc.write("D0100", 1234)
```

The source masks the value to 16 bits:

```python
plc.write("D0100", -1)       # writes 65535
plc.write("D0100", 0x12345)  # writes 0x2345
```

The return value is the masked word.

The `endian` argument is accepted but is not used in this method.

---

## 11. Native Bit API

### `read_bit()`

```python
read_bit(addr, endian=0, dtype=None) -> int
```

Reads one native PLC bit or one dotted bit inside a word.

Native bit types accepted by `_dtype_for_bit()`:

```text
X, Y, M, R
x, y, m, r
```

Examples:

```python
m8070 = plc.read_bit("M8070")
x0 = plc.read_bit("X0000")
y7 = plc.read_bit("Y0007")
r10 = plc.read_bit("R0010")
```

Integer-address form:

```python
m8070 = plc.read_bit(8070, dtype="M")
```

Dotted word bit:

```python
bit_15 = plc.read_bit("D0100.15")
```

Returns `0` or `1`.

The `endian` argument is accepted but is not used.

### `write_bit()`

```python
write_bit(addr, on, endian=0, dtype=None) -> int
```

Writes one native bit or modifies one bit inside a word.

```python
plc.write_bit("M8010", 1)
plc.write_bit("Y0000", 0)
plc.write_bit("D0100.4", 1)
```

Native bit writes use lowercase protocol data types.

Dotted writes use whole-word read-modify-write.

Returns `0` or `1`.

The `endian` argument is accepted but is not used.

---

## 12. Physical I/O Convenience API

The library uses `Q` and `I` as convenience aliases:

```text
Q -> Y output
I -> X input
```

### `input()`

```python
input(bit) -> int
```

Accepted forms:

```python
plc.input(0)
plc.input("I0")
plc.input("X0000")
```

The method maps the address to an `X` bit and calls `read_bit()`.

Returns `0` or `1`.

It rejects output-style `Q` and `Y` addresses.

### `output()`

```python
output(bit, on=1) -> int
```

Accepted forms:

```python
plc.output(0, 1)
plc.output("Q0", 0)
plc.output("Y0007", 1)
```

The method intentionally sends a five-character payload:

```text
Q0 ON  -> 00001
Q0 OFF -> 00000
Q7 ON  -> 00071
```

The source explicitly notes that this payload shape differs from the general
`write_bit()` implementation.

Returns `0` or `1`.

It rejects input-style `I` and `X` addresses.

---

## 13. Block API

### `read_block()`

```python
read_block(addr, count=2, endian=0, dtype=None) -> list[int]
```

Reads consecutive 16-bit words.

```python
words = plc.read_block("D0100", count=4)
```

Constraints:

- `count` must be `1..127`;
- each word is returned as an integer;
- expected reply data is exactly `count * 4` ASCII hex characters.

Word-order handling:

```text
endian=0 -> order returned by the PLC
endian=1 -> reverse the complete word list
```

Example:

```python
words = plc.read_block("D0105", count=2, endian=1)
```

### `write_block()`

```python
write_block(addr, values, endian=0, dtype=None) -> list[int]
```

Writes consecutive 16-bit words.

```python
written = plc.write_block("D0100", [1, 2, 3, 4])
```

Constraints:

- `values` must not be empty;
- maximum length is `127`;
- each value is converted with `int()` and masked to 16 bits.

Word-order handling:

```text
endian=0 -> transmit caller order
endian=1 -> transmit reversed order
```

The return value is the masked list in the caller's original order, not necessarily
the transmission order.

---

## 14. Unsigned Integer API

The Serial library names these methods `read_uint()` and `write_uint()`.

It does not use the TCP guide's `read_unit()` or `write_unit()` spelling.

### `read_uint()`

```python
read_uint(addr, count=2, endian=0, dtype=None) -> int
```

Calls `read_block()`, then combines the words from left to right:

```text
value = (value << 16) | word
```

Example:

```python
serial_number = plc.read_uint("D0105", count=2, endian=1)
```

The selected `endian` is first applied by `read_block()`.

### `write_uint()`

```python
write_uint(addr, value, count=2, endian=0, dtype=None) -> list[int]
```

Splits one unsigned integer into `count` 16-bit words.

```python
written = plc.write_uint("D0105", 69420, count=2, endian=1)
```

Constraints:

- `count` must be `1..127`;
- `value` must be nonnegative;
- `value` must fit in `count * 16` bits.

The method returns the list returned by `write_block()`.

---

## 15. Float API

### `read_float()`

```python
read_float(addr, endian=0, dtype=None) -> float
```

Reads four bytes from two consecutive registers and decodes an IEEE-754 single-
precision float.

Word order:

```text
endian=0 -> low word at addr, high word at addr + 1
endian=1 -> high word at addr, low word at addr + 1
```

Example:

```python
temperature = plc.read_float("D0200", endian=0)
```

The result is rounded with:

```python
round(value, PRECISION)
```

The default `PRECISION` is `3`.

### `write_float()`

```python
write_float(addr, value, endian=0, dtype=None) -> float
```

Encodes `value` as an IEEE-754 single-precision float and writes two words.

```python
plc.write_float("D0200", 77.25)
plc.write_float("D0200", 77.25, endian=1)
```

Returns `float(value)`.

---

## 16. Timer API

### `read_timer()`

```python
read_timer(tnum, count=1) -> list[dict]
```

Reads Timer Information with protocol data type `_`.

```python
timers = plc.read_timer(0, count=2)
```

`count` must be `1..48`.

Each returned dictionary has:

```python
{
    "timer": 0,
    "current": 150,
    "preset": 300,
    "status": 0,
}
```

The fields are raw integers. The library does not decode the status byte.

### `write_timer()`

```python
write_timer(tnum, value, preset=None) -> int
```

Writes the current timer value through lowercase `t`.

When `preset` is supplied, it first writes the preset through uppercase `T`.

```python
plc.write_timer(420, 100)
plc.write_timer(421, 100, preset=30)
```

Constraints:

```text
timer number: 0..9999
current value: 0..65535
preset value: 0..65535
```

The return value is the result of the current-value write.

---

## 17. Counter API

### `write_counter()`

```python
write_counter(cnum, preset) -> int
```

A convenience wrapper for:

```python
self.write(cnum, preset, dtype="C")
```

Example:

```python
plc.write_counter(10, 500)
```

The method does not perform separate counter-specific range validation. The value is
handled by `write()` and masked to 16 bits.

There is no dedicated `read_counter()` method.

---

## 18. Error-Code API

### `read_error()`

```python
read_error(addr=0, nbytes=12) -> list[int]
```

Reads protocol data type `E`.

```python
errors = plc.read_error()
errors = plc.read_error(addr=0, nbytes=4)
```

Constraints:

```text
nbytes must be even
nbytes must be 2..12
```

The method returns one 16-bit integer for every two requested bytes.

It does not decode the words into named IDEC errors.

---

## 19. Force I/O API

These methods use capture-derived commands.

Forced I/O can override normal PLC-program control. It must not be treated as a safety
function.

### `force_io()`

```python
force_io(enable=True) -> int
```

Sends:

```text
enable  -> W O 1
disable -> W O 0
```

Examples:

```python
plc.force_io(True)
plc.force_io(False)
```

Returns `1` or `0`.

### `force()`

```python
force(bit, on=1) -> int
```

Supports only `Q0..Q7`.

```python
plc.force("Q0", 1)
plc.force(0, 0)
```

The source:

1. enables Force I/O mode;
2. sends data type `]` with the output and state;
3. sends data type `^` with the output and a final `1`;
4. returns the requested state.

### `force_output`

Alias of `force()`:

```python
plc.force_output("Q0", 1)
```

### `release_force()` is broken in the reviewed source

Implemented signature:

```python
release_force(bit) -> int
```

Current implementation:

```python
return self.force(False)
```

The `bit` argument is ignored.

Because `False` is also integer zero in Python, this calls:

```python
self.force(0)
```

with the default `on=1`, which can issue a force-on operation for `Q0`.

Do not use:

```python
plc.release_force(...)
plc.force_release(...)
```

in the reviewed version.

Use the working global Force I/O disable operation:

```python
plc.force_io(False)
```

### `force_release`

Alias of the broken `release_force()` method.

---

## 20. Module-Level Wrappers

The module defines:

```python
input(plc, bit) -> int
output(plc, bit, on=1) -> int
```

Example:

```python
from MiSmSerial import MiSmSerial, input, output


plc = MiSmSerial("/dev/ttyACM0")

try:
    state = input(plc, "I0")
    output(plc, "Q0", 1)
finally:
    plc.close()
```

Importing `input` directly shadows Python's built-in `input()` function.

Prefer:

```python
from MiSmSerial import MiSmSerial
```

and:

```python
plc.input("I0")
plc.output("Q0", 1)
```

---

## 21. Reply Object and Predicate Helpers

The module exposes a `Reply` dataclass used internally:

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

Possible `kind` values:

```text
ACK_OK
ACK_NG
NAK
MALFORMED
EMPTY
UNKNOWN
```

Module-level predicate helpers:

```python
is_ack(reply)
is_nak(reply)
ack_ok(reply)
ack_ng(reply)
```

The normal high-level API raises errors before returning a `Reply` object to the caller.

---

## 22. Exceptions

### `ValueError`

Can be raised for:

- invalid `bcc_mode`;
- device string length other than two;
- integer address without `dtype`;
- malformed address text;
- operand outside `0..9999`;
- unsupported native bit data type;
- invalid I/O alias;
- invalid dotted write bit;
- invalid timer count;
- invalid timer number or value;
- invalid error-read byte count;
- invalid block count;
- empty block write;
- invalid endian value;
- unsigned integer too large;
- forced output outside `Q0..Q7`.

### `IOError`

Can be raised for:

- reply BCC mismatch;
- NAK reply;
- ACK/NG reply;
- malformed or unexpected reply kind;
- unexpected payload length;
- non-hexadecimal word, block, float, timer, or error payload;
- invalid native bit payload.

### PySerial errors

Opening, reading, or writing the serial device can raise exceptions from `pyserial`,
including `serial.SerialException`.

```python
import serial

from MiSmSerial import MiSmSerial


plc = None

try:
    plc = MiSmSerial("/dev/ttyACM0")
    print(plc.read("D8005"))
except serial.SerialException as exc:
    print(f"Serial failure: {exc}")
except IOError as exc:
    print(f"Protocol failure: {exc}")
finally:
    if plc is not None:
        plc.close()
```

---

## 23. Return-Value Summary

| Method | Return value |
|---|---|
| `close()` | `None` |
| `read()` | One unsigned 16-bit integer |
| `write()` | Written value masked to 16 bits |
| `read_bit()` | `0` or `1` |
| `write_bit()` | `0` or `1` |
| `input()` | `0` or `1` |
| `output()` | `0` or `1` |
| `read_block()` | List of 16-bit integers |
| `write_block()` | Masked caller-order list |
| `read_uint()` | Unsigned combined integer |
| `write_uint()` | Result from `write_block()` |
| `read_float()` | Rounded Python float |
| `write_float()` | `float(value)` |
| `read_timer()` | List of timer dictionaries |
| `write_timer()` | Current timer value written |
| `write_counter()` | Counter preset after 16-bit masking |
| `read_error()` | List of raw 16-bit error words |
| `force_io()` | `0` or `1` |
| `force()` | `0` or `1` |
| `release_force()` | Broken in reviewed source |

---

## 24. Compact API Reference

```text
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

Lifecycle:
    close()

Word access:
    read(addr, endian=0, dtype=None)
    write(addr, value, endian=0, dtype=None)

Bit access:
    read_bit(addr, endian=0, dtype=None)
    write_bit(addr, on, endian=0, dtype=None)

Physical I/O aliases:
    input(bit)
    output(bit, on=1)

Block access:
    read_block(addr, count=2, endian=0, dtype=None)
    write_block(addr, values, endian=0, dtype=None)

Unsigned integers:
    read_uint(addr, count=2, endian=0, dtype=None)
    write_uint(addr, value, count=2, endian=0, dtype=None)

Floats:
    read_float(addr, endian=0, dtype=None)
    write_float(addr, value, endian=0, dtype=None)

Timers, counters, and errors:
    read_timer(tnum, count=1)
    write_timer(tnum, value, preset=None)
    write_counter(cnum, preset)
    read_error(addr=0, nbytes=12)

Force I/O:
    force_io(enable=True)
    force(bit, on=1)
    force_output(bit, on=1)

Present but broken:
    release_force(bit)
    force_release(bit)

Module-level wrappers:
    input(plc, bit)
    output(plc, bit, on=1)

Reply helpers:
    Reply
    is_ack(reply)
    is_nak(reply)
    ack_ok(reply)
    ack_ng(reply)
```

---

## 25. Practical Examples

### Read a word and bit

```python
from MiSmSerial import MiSmSerial


plc = MiSmSerial("/dev/ttyACM0")

try:
    status = plc.read("D8005")
    running = plc.read_bit("M8125")

    print(f"D8005: {status}")
    print(f"Running: {running}")
finally:
    plc.close()
```

### Read and write a two-register unsigned integer

```python
from MiSmSerial import MiSmSerial


plc = MiSmSerial("/dev/ttyACM0")

try:
    before = plc.read_uint("D0105", count=2, endian=1)
    written = plc.write_uint("D0105", 69420, count=2, endian=1)
    after = plc.read_uint("D0105", count=2, endian=1)

    print(f"Before: {before}")
    print(f"Words returned by write: {written}")
    print(f"After: {after}")
finally:
    plc.close()
```

### Read a float

```python
from MiSmSerial import MiSmSerial


plc = MiSmSerial("/dev/ttyACM0")

try:
    value = plc.read_float("D0200", endian=0)
    print(value)
finally:
    plc.close()
```

### Blink an internal relay

```python
import time

from MiSmSerial import MiSmSerial


plc = MiSmSerial("/dev/ttyACM0")

try:
    original = plc.read_bit("M8010")

    try:
        for _ in range(10):
            plc.write_bit("M8010", 1)
            time.sleep(0.25)
            plc.write_bit("M8010", 0)
            time.sleep(0.25)
    finally:
        plc.write_bit("M8010", original)
finally:
    plc.close()
```

### Force-output cleanup with the current implementation

```python
from MiSmSerial import MiSmSerial


plc = MiSmSerial("/dev/ttyACM0")

try:
    plc.force("Q0", 1)
    # Controlled test work here.
finally:
    plc.force_io(False)
    plc.close()
```

Do not substitute `release_force()` in this example until that method is corrected.

---

## 26. MiSmSerial-Specific Implementation Issues

The following findings come directly from reviewing this Serial source:

1. `release_force()` ignores its parameter and can force `Q0` on.
2. `force_release` aliases the same broken method.
3. `bcc_mode="auto"` can return `None` if the no-ENQ retry is not `ACK_OK`.
4. Dotted addresses passed to normal word/block methods are linearized rather than
   treated as word bits.
5. The dotted `read_bit()` path does not explicitly validate `0..15`.
6. There is no automatic serial reconnect or retry after a transport failure.
7. There is no context-manager implementation.
8. `PRECISION` is global rather than per client.
9. The device string is checked for length but not actual hexadecimal content.
10. The class is not internally synchronized for multi-threaded use.

These are implementation observations, not features inherited from `MiSmTCP`.

---

## 27. Key Differences from MiSmTCP

| Area | MiSmSerial |
|---|---|
| Endpoint | Serial device path |
| Default transport setting | `9600` baud |
| TCP port | None |
| External dependency | `pyserial` |
| Connection opening | Immediate in constructor |
| `connect()` | Not present |
| `reconnect()` | Not present |
| Context manager | Not present |
| Persistent-socket option | Not applicable |
| Automatic transport retry | Not present |
| Multi-register method names | `read_uint()`, `write_uint()` |
| Program upload methods | Not present |
| Float precision | Module-global `PRECISION` |
| Force release | Present but broken |

---

## Source Authority

This guide describes the reviewed source at:

`https://github.com/Makerspace-Bangor/fc6a/blob/main/src/MiSmSerial.py`

When a later source revision differs from this guide, the source code is authoritative.
