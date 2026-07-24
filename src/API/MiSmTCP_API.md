# MiSmTCP API Guide

**Library:** `MiSmTCP.py`  
**Transport:** TCP/IP  
**Protocol:** IDEC MicroSmart Maintenance Protocol, ASCII framing  
**Default TCP port:** `2101`  
**Source:** `https://github.com/Makerspace-Bangor/fc6a/blob/main/src/MiSmTCP.py`  
**Source reviewed:** Current `main` branch, including the `read_uint()` / `write_uint()` rename  
**Review date:** 2026-07-24

This guide documents the public behavior implemented by the current `MiSmTCP.py`
source. It treats `MiSmTCP` as its own library rather than assuming that every
`MiSmSerial` behavior also applies.

---

## 1. Overview

`MiSmTCP` communicates with an IDEC MicroSmart or FC6A PLC through a Maintenance
Protocol TCP server.

The library:

- uses TCP port `2101` by default;
- requires only the Python standard library;
- can retain one TCP connection or open a new connection per request;
- supports context-manager use;
- validates reply BCC values;
- can automatically select the request-BCC convention;
- reads and writes words, bits, blocks, unsigned integers, and floats;
- includes timer, counter, error-code, physical I/O, and Force I/O helpers;
- automatically reconnects once after a socket failure when using a persistent
  connection.

The PLC Ethernet connection must be configured as a **Maintenance Communication
server**.

### Implemented high-level capabilities

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

### Present but incomplete

The source contains `upload()` and `upload_sha256()`, but the upload implementation
depends on names that are not defined in the library. These methods are not currently
usable as a complete public API.

---

## 2. Dependency and Installation

`MiSmTCP.py` uses only Python's standard library.

Place it in the same directory as the calling program or install it somewhere on
Python's module path.

```python
from MiSmTCP import MiSmTCP
```

No `pip` package is required.

---

## 3. Quick Start

```python
from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    status = plc.read("D8005")
    running = plc.read_bit("M8125")
    temperature = plc.read_float("D0200")

    print(f"D8005: {status}")
    print(f"Running: {running}")
    print(f"Temperature: {temperature}")
```

The context manager opens the connection on entry and closes it on exit.

---

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

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `host` | `str` | required | PLC IP address or hostname. |
| `port` | `int` | `2101` | Maintenance Protocol TCP server port. |
| `device` | `str` | `"FF"` | Two-character PLC communication device value. |
| `timeout` | `float` | `1.0` | Socket connection and receive timeout, in seconds. |
| `debug` | `bool` | `False` | Print transmitted ASCII, transmitted hex, and received hex. |
| `bcc_mode` | `str` | `"auto"` | Request BCC mode: `"auto"`, `"enq"`, or `"no_enq"`. |
| `keep_open` | `bool` | `True` | Retain one TCP connection between requests. |
| `connect_now` | `bool` | `True` | Open the persistent connection during construction. |
| `precision` | `int` | `3` | Decimal places returned by `read_float()`. |

### Constructor behavior

When both `keep_open` and `connect_now` are true, the constructor immediately calls
`connect()`.

```python
plc = MiSmTCP("192.168.1.50")
```

This normally attempts a TCP connection during construction.

To delay the initial connection:

```python
plc = MiSmTCP(
    "192.168.1.50",
    keep_open=True,
    connect_now=False,
)
```

To use a separate TCP connection for every request:

```python
plc = MiSmTCP(
    "192.168.1.50",
    keep_open=False,
)
```

`connect_now` has no practical effect when `keep_open=False`.

### Device validation

The source checks only that `device` has two characters, then converts it to uppercase.

Although the exception text says "2 ASCII hex chars", the implementation does not
actually verify that both characters are hexadecimal.

---

## 5. Module Constants

```python
PLC_PORT = 2101
DEFAULT_DEVICE = "FF"
DEFAULT_TIMEOUT = 1.0
```

Changing `PLC_PORT` after the class has been defined does not change the constructor's
already-created default argument. Pass a nonstandard port explicitly:

```python
plc = MiSmTCP("192.168.1.50", port=2201)
```

---

## 6. Connection Management

### `connect()`

```python
connect() -> None
```

Opens a TCP connection when `_sock` is currently `None`.

```python
plc.connect()
```

Calling it when a socket object already exists returns without opening another
connection.

### `close()`

```python
close() -> None
```

Closes the persistent socket and sets the internal socket reference to `None`.

```python
plc.close()
```

### `disconnect`

Alias of `close()`:

```python
plc.disconnect()
```

### `reconnect()`

```python
reconnect() -> None
```

Closes the current socket and opens a new one.

```python
plc.reconnect()
```

### Context manager

```python
with MiSmTCP("192.168.1.50") as plc:
    print(plc.read("D0100"))
```

`__enter__()` calls `connect()`.  
`__exit__()` calls `close()`.

### Persistent connection

```python
plc = MiSmTCP(
    "192.168.1.50",
    keep_open=True,
)
```

The same socket is reused for requests.

If a persistent socket raises `OSError` or `socket.timeout` during send or receive, the
library:

1. closes the existing socket;
2. reconnects once;
3. sends the same request again;
4. receives one reply.

This retry can repeat a write after an ambiguous communication failure. A timeout does
not prove that the PLC failed to process the first request.

### Per-request connection

```python
plc = MiSmTCP(
    "192.168.1.50",
    keep_open=False,
)
```

Every request opens a temporary socket, sends one frame, receives one reply, and closes
the socket.

The one-time reconnect-and-retry behavior is implemented only in the persistent
connection path.

### Threading

The class has no internal transaction lock. Do not use one `MiSmTCP` instance for
simultaneous requests from several threads. Use one client per worker or protect calls
with an external lock.

---

## 7. Maintenance Protocol Framing

Requests are built as:

```text
ENQ + device + continuation + command + data type + payload + BCC + CR
```

Replies are parsed as:

```text
ACK/NAK + device + command + data + BCC + CR
```

The reply parser calculates the reply BCC over the complete reply before the two ASCII
BCC characters, including the leading ACK or NAK byte.

The receive loop reads one byte at a time until:

- carriage return is received;
- the socket times out;
- the peer closes the connection;
- 8192 bytes have been received;
- the elapsed time exceeds approximately three times `timeout`.

A partial or empty reply is later classified as malformed, empty, or unexpected.

---

## 8. Request BCC Modes

### `bcc_mode="enq"`

The request XOR includes the leading ENQ byte.

```python
plc = MiSmTCP(
    "192.168.1.50",
    bcc_mode="enq",
)
```

### `bcc_mode="no_enq"`

The request XOR excludes ENQ.

```python
plc = MiSmTCP(
    "192.168.1.50",
    bcc_mode="no_enq",
)
```

### `bcc_mode="auto"`

The source:

1. sends the request with ENQ included;
2. checks for NAK code `10`;
3. retries without ENQ when that code is received;
4. stores `"no_enq"` when the retry returns `ACK_OK`;
5. stores `"enq"` when the first request returns `ACK_OK`.

After a successful selection, later requests use the selected mode directly.

### Current auto-mode edge case

When the first reply is NAK `10` and the no-ENQ retry is not `ACK_OK`, `_xfer()` has no
explicit return for that path. A high-level method may receive `None` and fail with an
`AttributeError` rather than a normal protocol `IOError`.

A known fixed mode avoids that edge case.

---

## 9. Address Forms

Most register methods accept either a normal IDEC address string:

```python
plc.read("D0100")
plc.read_bit("M8070")
```

or an integer plus a one-character `dtype`:

```python
plc.read(100, dtype="D")
plc.read_bit(8070, dtype="M")
```

An integer address without `dtype` raises `ValueError`.

### Common data-type examples

| Prefix | Typical use in this library |
|---|---|
| `D` | Data register word |
| `M` | Internal or special relay |
| `X` | Physical input bit |
| `Y` | Physical output bit |
| `R` | Shift-register bit |
| `T` | Timer preset word |
| `t` | Timer current value word |
| `C` | Counter preset word |
| `E` | Error-code read |
| `_` | Timer-information read |

The library does not verify that an operand exists or is writable on the connected PLC
model.

### Operand range

The formatter accepts operand numbers from `0` through `9999`.

---

## 10. Dotted Word-Bit Addresses

The normal `read()` and `write()` methods route dotted string addresses to the bit
methods:

```python
plc.read("D0100.3")
plc.write("D0100.3", 1)
```

Padded and unpadded bit numbers are equivalent:

```python
plc.read("D0100.1")
plc.read("D0100.01")
```

Explicit bit methods also support dotted syntax:

```python
plc.read_bit("D0100.15")
plc.write_bit("D0100.15", 0)
```

### Dotted write behavior

A dotted write:

1. reads the entire base word;
2. changes one bit locally;
3. writes the complete word.

This is a non-atomic read-modify-write operation. Another PLC task or client could
change another bit between the read and write.

### Dotted addresses with block and numeric methods

The shared `_parse_addr()` helper linearizes dotted syntax as:

```text
word * 16 + bit
```

`read()` and `write()` intercept dotted strings before this happens, but the following
methods do not:

- `read_block()`
- `write_block()`
- `read_uint()`
- `write_uint()`
- `read_float()`
- `write_float()`

Do not pass dotted addresses to those methods.

### Bit validation difference

`write_bit()` explicitly enforces `0..15`.

The dotted branch in `read_bit()` does not explicitly validate the bit number. Use only
`0..15`.

---

## 11. Word API

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

Dotted form:

```python
bit = plc.read("D0100.7")
```

Return values:

- whole word: integer `0..65535`;
- dotted bit: `0` or `1`.

The `endian` argument is accepted but is not used for a one-word read.

### `write()`

```python
write(addr, value, endian=0, dtype=None) -> int
```

Writes one 16-bit word using Write N Bytes with a byte count of `2`.

```python
written = plc.write("D0100", 1234)
```

The value is masked to 16 bits:

```python
plc.write("D0100", -1)       # writes 65535
plc.write("D0100", 0x12345)  # writes 0x2345
```

Dotted form:

```python
plc.write("D0100.4", 1)
```

Return values:

- whole word: masked integer;
- dotted bit: `0` or `1`.

The `endian` argument is accepted but is not used for a one-word write.

---

## 12. Native Bit API

### `read_bit()`

```python
read_bit(addr, endian=0, dtype=None) -> int
```

Reads one native PLC bit or one bit inside a word.

Native bit types accepted:

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
word_bit = plc.read_bit("D0100.15")
```

Integer-address form:

```python
m8070 = plc.read_bit(8070, dtype="M")
```

`Q` and `I` aliases are also accepted:

```python
q0 = plc.read_bit("Q0")  # maps to Y0000
i0 = plc.read_bit("I0")  # maps to X0000
```

Returns `0` or `1`.

The `endian` argument is accepted but is not used.

### `write_bit()`

```python
write_bit(addr, on, endian=0, dtype=None) -> int
```

Writes one native PLC bit or modifies one bit inside a word.

```python
plc.write_bit("M8010", 1)
plc.write_bit("Y0000", 0)
plc.write_bit("D0100.4", 1)
```

Integer-address form:

```python
plc.write_bit(8010, 1, dtype="M")
```

`Q` and `I` aliases are accepted and mapped to `Y` and `X`:

```python
plc.write_bit("Q0", 1)
plc.write_bit("I0", 0)
```

Whether an input can actually be written depends on the PLC and operand behavior; the
library only builds and sends the request.

Native bit writes use lowercase protocol data types.

Dotted writes perform whole-word read-modify-write.

Returns `0` or `1`.

The `endian` argument is accepted but is not used.

---

## 13. Physical I/O Convenience API

The convenience API uses:

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

The method maps the address to an `X` operand and calls `read_bit()`.

Returns `0` or `1`.

It rejects `Q` and `Y` output-style addresses.

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

The method intentionally emits a five-character payload:

```text
Q0 ON  -> 00001
Q0 OFF -> 00000
Q7 ON  -> 00071
```

The source explicitly distinguishes this payload from the general `write_bit()` path.

Returns `0` or `1`.

It rejects `I` and `X` input-style addresses.

---

## 14. Block API

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
- expected reply length is exactly `count * 4` ASCII hex characters;
- each result is returned as an integer.

Word-order handling:

```text
endian=0 -> order returned by the PLC
endian=1 -> reverse the complete word list
```

Example:

```python
words = plc.read_block("D0105", count=2, endian=1)
```

`endian` changes word order, not byte order inside each 16-bit word.

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
- each item is converted with `int()` and masked to 16 bits.

Word-order handling:

```text
endian=0 -> transmit caller order
endian=1 -> transmit reversed order
```

The return value is the masked list in the caller's original order, not necessarily
the transmission order.

---

## 15. Unsigned Multi-register Integer API

The current TCP library uses the corrected method names:

```text
read_uint()
write_uint()
```

### `read_uint()`

```python
read_uint(addr, count=2, endian=0, dtype=None) -> int
```

Calls `read_block()` and combines the words from left to right:

```text
value = (value << 16) | word
```

Example:

```python
serial_number = plc.read_uint(
    "D0105",
    count=2,
    endian=1,
)
```

For two words after `read_block()` applies the selected order:

```text
result = (word_0 << 16) | word_1
```

### `write_uint()`

```python
write_uint(addr, value, count=2, endian=0, dtype=None) -> list[int]
```

Splits one unsigned integer into `count` 16-bit words and calls `write_block()`.

```python
written = plc.write_uint(
    "D0105",
    69420,
    count=2,
    endian=1,
)
```

Constraints:

- `count` must be `1..127`;
- `value` must be nonnegative;
- `value` must fit within `count * 16` bits.

Unlike `write()` and `write_block()`, the complete integer is rejected when it does not
fit rather than being truncated.

The return value is the list returned by `write_block()`.

The old `read_unit()` and `write_unit()` names are no longer defined in the current
source.

---

## 16. Float API

### `read_float()`

```python
read_float(addr, endian=0, dtype=None) -> float
```

Reads four bytes from two consecutive words and decodes an IEEE-754 single-precision
float.

Word order:

```text
endian=0 -> low word at addr, high word at addr + 1
endian=1 -> high word at addr, low word at addr + 1
```

Example:

```python
temperature = plc.read_float(
    "D0200",
    endian=0,
)
```

The return value is rounded using the instance setting:

```python
round(value, self.precision)
```

The default precision is three decimal places.

```python
plc = MiSmTCP(
    "192.168.1.50",
    precision=4,
)
```

### `write_float()`

```python
write_float(addr, value, endian=0, dtype=None) -> float
```

Encodes `value` as a single-precision IEEE-754 float and writes two words.

```python
plc.write_float("D0200", 77.25)
plc.write_float("D0200", 77.25, endian=1)
```

Returns `float(value)`.

The `precision` setting affects only the rounded result from `read_float()`. It does
not round before writing.

---

## 17. Timer API

### `read_timer()`

```python
read_timer(tnum, count=1) -> list[dict]
```

Reads Timer Information through protocol data type `_`.

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

The fields are raw integers. The library does not decode the timer status byte.

### `write_timer()`

```python
write_timer(tnum, value, preset=None) -> int
```

Writes the timer current value through lowercase `t`.

When `preset` is supplied, the implementation writes the preset through uppercase `T`
first, then writes the current value through lowercase `t`.

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

## 18. Counter API

### `write_counter()`

```python
write_counter(cnum, preset) -> int
```

Convenience wrapper for:

```python
self.write(cnum, preset, dtype="C")
```

Example:

```python
plc.write_counter(10, 500)
```

There is no dedicated `read_counter()` method.

The value is handled by `write()` and masked to 16 bits.

---

## 19. Error-Code API

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

The return value contains one 16-bit integer for every two requested bytes.

The library does not translate the returned words into named IDEC error descriptions.

---

## 20. Force I/O API

These methods use capture-derived Maintenance Protocol commands.

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

The method:

1. enables Force I/O mode;
2. sends data type `]` with the output number and state;
3. sends data type `^` with the output number and final `1`;
4. returns the requested state.

### `release_force()`

```python
release_force() -> int
```

Disables Force I/O mode by calling:

```python
self.force_io(False)
```

Example:

```python
plc.release_force()
```

Returns `0`.

### Force aliases

```python
plc.force_output("Q0", 1)
plc.force_release()
```

`force_output` aliases `force()`.  
`force_release` aliases `release_force()`.

### Cleanup pattern

```python
from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    try:
        plc.force("Q0", 1)
        # Controlled test work here.
    finally:
        plc.release_force()
```

A process crash, network loss, or PLC power event can prevent cleanup from reaching the
PLC.

---

## 21. Upload Methods: Incomplete

### `upload()`

```python
upload(filename=None) -> bytes
```

The source presents this as a PLC program upload operation, but it calls names not
defined in `MiSmTCP.py`:

```text
PLCPasswordRequired
_upload_begin()
_unlock_upload()
_upload_next_block()
```

As currently written, the method cannot complete successfully without additional code.

Depending on the path reached, it can raise `AttributeError` or `NameError`.

Do not treat `upload()` as an operational API yet.

### `upload_sha256()`

```python
upload_sha256() -> str
```

Calls `upload()` and hashes the returned bytes with SHA-256.

Because `upload()` is incomplete, `upload_sha256()` is also not currently operational.

It starts a new upload internally and does not accept an already-uploaded blob or
filename.

---

## 22. Class and Module Aliases

### Class aliases

```python
PLC = MiSmTCP
Client = MiSmTCP
```

Examples:

```python
from MiSmTCP import PLC, Client


plc1 = PLC("192.168.1.50")
plc2 = Client("192.168.1.51")
```

### Module-level I/O wrappers

```python
input(plc, bit) -> int
output(plc, bit, on=1) -> int
```

Example:

```python
from MiSmTCP import MiSmTCP, input, output


plc = MiSmTCP("192.168.1.50")

try:
    state = input(plc, "I0")
    output(plc, "Q0", 1)
finally:
    plc.close()
```

Importing `input` directly shadows Python's built-in `input()` function.

Prefer object methods:

```python
from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    state = plc.input("I0")
    plc.output("Q0", 1)
```

---

## 23. Reply Object and Predicate Helpers

The module exposes a `Reply` dataclass used by the low-level parser:

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

The high-level methods normally turn unsuccessful replies into exceptions rather than
returning a `Reply` to the application.

---

## 24. Exceptions and Failure Behavior

### `ValueError`

Can be raised for:

- invalid `bcc_mode`;
- device string length other than two;
- integer address without `dtype`;
- malformed address text;
- operand outside `0..9999`;
- unsupported native bit type;
- invalid I/O alias;
- invalid dotted write bit;
- invalid timer count;
- invalid timer number or timer value;
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
- invalid native-bit payload.

### Socket exceptions

Connection failures may surface as:

```text
ConnectionRefusedError
TimeoutError
socket.timeout
OSError
```

Example:

```python
import socket

from MiSmTCP import MiSmTCP


plc = None

try:
    plc = MiSmTCP(
        "192.168.1.50",
        timeout=2.0,
    )
    print(plc.read("D8005"))
except (ConnectionRefusedError, TimeoutError, socket.timeout, OSError) as exc:
    print(f"TCP communication failed: {exc}")
except IOError as exc:
    print(f"Maintenance Protocol request failed: {exc}")
finally:
    if plc is not None:
        plc.close()
```

### Retry ambiguity

With `keep_open=True`, the library may retransmit the same request after a socket
failure. For write operations, verify the resulting PLC state when duplicate execution
could matter.

---

## 25. Return-Value Summary

| Method | Return value |
|---|---|
| `connect()` | `None` |
| `close()` | `None` |
| `disconnect()` | `None` |
| `reconnect()` | `None` |
| `read()` | Unsigned 16-bit integer, or `0/1` for dotted syntax |
| `write()` | Masked 16-bit integer, or `0/1` for dotted syntax |
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
| `release_force()` | `0` |
| `upload()` | Intended bytes result, but incomplete |
| `upload_sha256()` | Intended SHA-256 string, but depends on incomplete upload |

---

## 26. Compact API Reference

```text
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

Connection:
    connect()
    close()
    disconnect()
    reconnect()

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
    release_force()
    force_output(bit, on=1)
    force_release()

Present but incomplete:
    upload(filename=None)
    upload_sha256()

Module aliases:
    PLC
    Client

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

## 27. Practical Examples

### Read a status word and running relay

```python
from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    error_status = plc.read("D8005")
    running = plc.read_bit("M8125")

    print(f"D8005: {error_status}")
    print(f"Running: {running}")
```

### Read and write an unsigned two-register value

```python
from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    before = plc.read_uint(
        "D0105",
        count=2,
        endian=1,
    )

    written = plc.write_uint(
        "D0105",
        69420,
        count=2,
        endian=1,
    )

    after = plc.read_uint(
        "D0105",
        count=2,
        endian=1,
    )

    print(f"Before: {before}")
    print(f"Words returned by write: {written}")
    print(f"After: {after}")
```

### Read a register block

```python
from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    words = plc.read_block("D3500", count=3)

    for offset, word in enumerate(words):
        active_bits = [
            bit
            for bit in range(16)
            if word & (1 << bit)
        ]

        print(
            f"D{3500 + offset:04d}: "
            f"0x{word:04X}, bits={active_bits}"
        )
```

### Read and write a float

```python
from MiSmTCP import MiSmTCP


with MiSmTCP(
    "192.168.1.50",
    precision=4,
) as plc:
    before = plc.read_float("D0200", endian=0)
    plc.write_float("D0200", 77.25, endian=0)
    after = plc.read_float("D0200", endian=0)

    print(f"Before: {before}")
    print(f"After: {after}")
```

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

### Use a non-persistent connection

```python
from MiSmTCP import MiSmTCP


plc = MiSmTCP(
    "192.168.1.50",
    keep_open=False,
)

try:
    print(plc.read("D8005"))
    print(plc.read_bit("M8125"))
finally:
    plc.close()
```

`close()` is harmless here because each request already closes its temporary socket.

### Controlled Force I/O test

```python
from MiSmTCP import MiSmTCP


with MiSmTCP("192.168.1.50") as plc:
    try:
        plc.force("Q0", 1)
        # Controlled test work here.
    finally:
        plc.release_force()
```

---

## 28. Current Implementation Notes

1. `read_uint()` and `write_uint()` are the current corrected method names.
2. `upload()` and `upload_sha256()` are incomplete.
3. `bcc_mode="auto"` has a missing-return edge case after a failed fallback.
4. Persistent connections retry once after socket failure; per-request connections do
   not.
5. A retried write can be executed twice after an ambiguous transport failure.
6. Dotted reads and writes use non-atomic whole-word read-modify-write behavior.
7. The dotted `read_bit()` path does not explicitly validate `0..15`.
8. Dotted addresses should not be passed to block, unsigned-integer, or float methods.
9. The device value is checked for length but not actual hexadecimal content.
10. The class has no internal thread synchronization.
11. Timer status and error-code values are returned without named decoding.
12. Force I/O support is limited to `Q0..Q7`.
13. Module-level `input()` can shadow Python's built-in `input()`.

---

## Source Authority

This guide describes the current source at:

`https://github.com/Makerspace-Bangor/fc6a/blob/main/src/MiSmTCP.py`

The July 24, 2026 source change renamed:

```text
read_unit()  -> read_uint()
write_unit() -> write_uint()
```

When a later source revision differs from this guide, the source code is authoritative.# MiSmSerial API Guide

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

The TCP library names these methods `read_uint()` and `write_uint()`.

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
