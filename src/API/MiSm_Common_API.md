# MiSm Common API

**Libraries:** `MiSmSerial.py` and `MiSmTCP.py`  
**Purpose:** Common user-facing methods that can be called the same way with either transport  
**Protocol:** IDEC MicroSmart / FC6A Maintenance Protocol  
**Review date:** 2026-07-24

This document describes only the public methods whose **call syntax and intended
user-facing behavior are shared by both `MiSmSerial` and `MiSmTCP`**.

It does not document transport-specific constructors, connection controls, retries,
dependencies, or features available in only one library.

---

## 1. Transport Setup

The two classes are initialized differently, but after initialization the common
methods in this guide are called through the same `plc` object.

### Serial

```python
from MiSmSerial import MiSmSerial


plc = MiSmSerial("/dev/ttyACM0")
```

### TCP

```python
from MiSmTCP import MiSmTCP


plc = MiSmTCP("192.168.1.50")
```

### Transport-independent cleanup pattern

Both classes provide `close()`:

```python
plc = None

try:
    # Choose one:
    #
    # plc = MiSmSerial("/dev/ttyACM0")
    # plc = MiSmTCP("192.168.1.50")

    print(plc.read("D0100"))
finally:
    if plc is not None:
        plc.close()
```

The constructor itself is not part of the common API because its endpoint and
transport options differ.

---

## 2. Common Method Index

```text
close()

read(addr, endian=0, dtype=None)
write(addr, value, endian=0, dtype=None)

read_bit(addr, endian=0, dtype=None)
write_bit(addr, on, endian=0, dtype=None)

input(bit)
output(bit, on=1)

read_block(addr, count=2, endian=0, dtype=None)
write_block(addr, values, endian=0, dtype=None)

read_uint(addr, count=2, endian=0, dtype=None)
write_uint(addr, value, count=2, endian=0, dtype=None)

read_float(addr, endian=0, dtype=None)
write_float(addr, value, endian=0, dtype=None)

read_timer(tnum, count=1)
write_timer(tnum, value, preset=None)

write_counter(cnum, preset)
read_error(addr=0, nbytes=12)

force_io(enable=True)
force(bit, on=1)
force_output(bit, on=1)
```

---

## 3. Common Addressing

### String addresses

The common methods accept normal IDEC operand strings:

```python
plc.read("D0100")
plc.read_bit("M8070")
plc.write_bit("Y0000", 1)
plc.read_float("D0200")
```

Common examples:

| Address | Typical use |
|---|---|
| `D0100` | Data-register word |
| `M8070` | Internal or special relay |
| `X0000` | Physical input |
| `Y0000` | Physical output |
| `T0001` | Timer preset |
| `C0099` | Counter preset |

Both libraries format operand numbers from `0` through `9999`.

The libraries do not confirm that an operand exists, is writable, or has the same
meaning on every PLC model.

### Integer address with `dtype`

An integer address requires a one-character `dtype`:

```python
value = plc.read(100, dtype="D")
bit = plc.read_bit(8070, dtype="M")
```

Do not omit `dtype` when using an integer address.

### Common dotted-bit syntax

Use dotted word-bit syntax through `read_bit()` and `write_bit()`:

```python
bit_3 = plc.read_bit("D0100.3")
plc.write_bit("D0100.3", 1)

bit_15 = plc.read_bit("M8004.15")
plc.write_bit("M8004.15", 0)
```

Use bit numbers `0` through `15`.

A dotted write performs a read-modify-write of the entire 16-bit word:

1. read the base word;
2. change one bit locally;
3. write the complete word back.

This is not atomic. Avoid it where PLC logic or another client may change another bit
in the same word at the same time.

### Portable dotted-address rule

For code intended to work with either library, do not use dotted addresses with:

```text
read()
write()
read_block()
write_block()
read_uint()
write_uint()
read_float()
write_float()
```

Use `read_bit()` and `write_bit()` for all dotted word-bit access.

---

## 4. `close()`

```python
close() -> None
```

Closes the active transport.

```python
plc.close()
```

The call is common, although reopening and reconnecting are transport-specific.

---

## 5. Word Access

### `read()`

```python
read(addr, endian=0, dtype=None) -> int
```

Reads one 16-bit word.

```python
value = plc.read("D0100")
print(value)
```

Integer-address form:

```python
value = plc.read(100, dtype="D")
```

Return value:

```text
0 through 65535
```

The `endian` argument is accepted for compatibility but has no effect on a single
16-bit word.

Portable usage:

```python
value = plc.read("D0100")
```

Do not use dotted addresses with `read()` in transport-independent code.

### `write()`

```python
write(addr, value, endian=0, dtype=None) -> int
```

Writes one 16-bit word and returns the value encoded by the library.

```python
written = plc.write("D0100", 1234)
```

The value is masked to 16 bits:

```python
plc.write("D0100", -1)       # writes 65535
plc.write("D0100", 0x12345)  # writes 0x2345
```

The `endian` argument has no effect on a single 16-bit word.

Do not use dotted addresses with `write()` in transport-independent code. Use
`write_bit()`.

---

## 6. Bit Access

### `read_bit()`

```python
read_bit(addr, endian=0, dtype=None) -> int
```

Reads one native bit operand or one bit inside a word.

```python
m8070 = plc.read_bit("M8070")
x0 = plc.read_bit("X0000")
y7 = plc.read_bit("Y0007")
word_bit = plc.read_bit("D0100.15")
```

Integer-address form:

```python
m8070 = plc.read_bit(8070, dtype="M")
```

Common native bit types:

```text
X
Y
M
R
```

Return value:

```text
0 or 1
```

The `endian` argument is accepted but is not used.

For portable code, use `X` and `Y` addresses with `read_bit()`. Use the separate
`input()` and `output()` helpers when using `I` and `Q` aliases.

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

Integer-address form:

```python
plc.write_bit(8010, 1, dtype="M")
```

Return value:

```text
0 or 1
```

For native bit devices, the method sends a Maintenance Protocol Write 1 Bit request.

For dotted syntax, the method performs a whole-word read-modify-write.

The `endian` argument is accepted but is not used.

---

## 7. Physical I/O Helpers

### `input()`

```python
input(bit) -> int
```

Reads one physical input.

Accepted portable forms:

```python
state = plc.input(0)
state = plc.input("I0")
state = plc.input("X0000")
```

Returns `0` or `1`.

`input()` accepts input-style `I` or `X` addresses.

### `output()`

```python
output(bit, on=1) -> int
```

Writes one physical output.

Accepted portable forms:

```python
plc.output(0, 1)
plc.output("Q0", 0)
plc.output("Y0007", 1)
```

Returns `0` or `1`.

`output()` accepts output-style `Q` or `Y` addresses.

Both libraries intentionally use the observed five-character output payload:

```text
Q0 ON  -> 00001
Q0 OFF -> 00000
Q7 ON  -> 00071
```

This helper is distinct from the general `write_bit()` path.

---

## 8. Block Access

### `read_block()`

```python
read_block(addr, count=2, endian=0, dtype=None) -> list[int]
```

Reads consecutive 16-bit words.

```python
words = plc.read_block("D0100", count=4)
```

Result:

```python
[
    value_at_D0100,
    value_at_D0101,
    value_at_D0102,
    value_at_D0103,
]
```

Constraints:

```text
count: 1 through 127 registers
```

Word order:

```text
endian=0 -> PLC reply order
endian=1 -> reverse the complete word list
```

Example:

```python
normal = plc.read_block("D0100", count=4, endian=0)
reversed_words = plc.read_block("D0100", count=4, endian=1)
```

`endian` changes register word order. It does not reverse bytes inside each word.

### `write_block()`

```python
write_block(addr, values, endian=0, dtype=None) -> list[int]
```

Writes consecutive 16-bit words.

```python
written = plc.write_block(
    "D0100",
    [1, 2, 3, 4],
)
```

Constraints:

```text
values must not be empty
maximum 127 registers
```

Each input is converted to an integer and masked to 16 bits:

```python
plc.write_block("D0100", [0x1234, -1])
# Writes 0x1234 and 0xFFFF
```

Word order:

```text
endian=0 -> transmit caller order
endian=1 -> transmit reversed order
```

The return value is the masked list in the caller's original order.

---

## 9. Unsigned Multi-register Integers

### `read_uint()`

```python
read_uint(addr, count=2, endian=0, dtype=None) -> int
```

Reads several 16-bit registers and combines them into one unsigned integer.

```python
serial_number = plc.read_uint(
    "D0105",
    count=2,
    endian=1,
)
```

After `read_block()` applies the selected word order, the value is combined from left
to right.

For two words:

```text
result = (word_0 << 16) | word_1
```

Use the `endian` value that matches the PLC program's storage convention.

### `write_uint()`

```python
write_uint(addr, value, count=2, endian=0, dtype=None) -> list[int]
```

Splits an unsigned integer into `count` 16-bit words and writes them.

```python
written = plc.write_uint(
    "D0105",
    69420,
    count=2,
    endian=1,
)
```

Constraints:

```text
count: 1 through 127
value must be nonnegative
value must fit in count * 16 bits
```

The method rejects a complete integer that does not fit rather than silently truncating
it.

The return value is the list returned by `write_block()`.

---

## 10. Floating-point Access

### `read_float()`

```python
read_float(addr, endian=0, dtype=None) -> float
```

Reads an IEEE-754 single-precision float from two consecutive 16-bit registers.

```python
temperature = plc.read_float("D0200")
```

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

Both libraries return a Python float rounded to three decimal places by default.

The mechanism for changing that precision differs between the libraries and is not
part of this common API.

### `write_float()`

```python
write_float(addr, value, endian=0, dtype=None) -> float
```

Writes an IEEE-754 single-precision float into two consecutive registers.

```python
plc.write_float("D0200", 77.25)
plc.write_float("D0200", 77.25, endian=1)
```

Returns:

```python
float(value)
```

---

## 11. Timer Access

### `read_timer()`

```python
read_timer(tnum, count=1) -> list[dict]
```

Reads timer information.

```python
timers = plc.read_timer(0, count=2)
```

`count` must be `1` through `48`.

Each timer dictionary contains:

```python
{
    "timer": 0,
    "current": 150,
    "preset": 300,
    "status": 0,
}
```

The values are returned as raw integers. The status byte is not decoded into named
flags.

### `write_timer()`

```python
write_timer(tnum, value, preset=None) -> int
```

Writes the timer current value.

```python
plc.write_timer(0, 150)
```

When `preset` is supplied, the preset is also written:

```python
plc.write_timer(
    0,
    150,
    preset=300,
)
```

Constraints:

```text
timer number: 0 through 9999
current value: 0 through 65535
preset value: 0 through 65535
```

The return value is the current value written.

---

## 12. Counter Access

### `write_counter()`

```python
write_counter(cnum, preset) -> int
```

Writes one counter preset value.

```python
plc.write_counter(10, 500)
```

This is equivalent to:

```python
plc.write(10, 500, dtype="C")
```

The return value is the 16-bit value written.

Neither common API provides a dedicated `read_counter()` method.

---

## 13. Error-code Access

### `read_error()`

```python
read_error(addr=0, nbytes=12) -> list[int]
```

Reads raw Maintenance Protocol error-code words.

```python
errors = plc.read_error()
errors = plc.read_error(addr=0, nbytes=4)
```

Constraints:

```text
nbytes must be even
nbytes must be 2 through 12
```

The return value contains:

```text
nbytes / 2 words
```

Example:

```python
errors = plc.read_error(nbytes=4)
# Two raw 16-bit error-code words
```

The method does not convert the values into named IDEC error descriptions.

---

## 14. Common Force I/O Methods

> Force I/O can override normal PLC-program control. Use it only during controlled
> testing where energizing or de-energizing an output is safe. Software force commands
> are not safety functions.

### `force_io()`

```python
force_io(enable=True) -> int
```

Enables or disables Force I/O mode.

```python
plc.force_io(True)
plc.force_io(False)
```

Returns:

```text
1 when enabled
0 when disabled
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

Both current implementations limit this helper to:

```text
Q0 through Q7
```

The method enables Force I/O mode, sends the output state, sends the observed
force-control request, and returns `0` or `1`.

### `force_output`

Alias of `force()`:

```python
plc.force_output("Q0", 1)
```

### Portable force cleanup

`release_force()` and `force_release()` are intentionally excluded from this common
API because their signatures and behavior differ between the reviewed libraries.

Use the shared working call:

```python
plc.force_io(False)
```

Portable cleanup pattern:

```python
try:
    plc.force("Q0", 1)
    # Controlled test work.
finally:
    plc.force_io(False)
```

---

## 15. Common Module-level Wrappers

Both modules provide optional wrappers:

```python
input(plc, bit) -> int
output(plc, bit, on=1) -> int
```

Serial example:

```python
from MiSmSerial import MiSmSerial, input, output


plc = MiSmSerial("/dev/ttyACM0")

try:
    x0 = input(plc, "I0")
    output(plc, "Q0", 1)
finally:
    plc.close()
```

TCP example:

```python
from MiSmTCP import MiSmTCP, input, output


plc = MiSmTCP("192.168.1.50")

try:
    x0 = input(plc, "I0")
    output(plc, "Q0", 1)
finally:
    plc.close()
```

Importing a function named `input` shadows Python's built-in `input()`.

The recommended common style is:

```python
plc.input("I0")
plc.output("Q0", 1)
```

---

## 16. Common Reply Helpers

Both modules expose the same low-level reply predicates:

```python
is_ack(reply)
is_nak(reply)
ack_ok(reply)
ack_ng(reply)
```

They also expose a compatible `Reply` dataclass containing fields such as:

```python
reply.kind
reply.raw
reply.device
reply.command
reply.data
reply.bcc_recv
reply.bcc_calc
reply.bcc_ok
reply.ng_code
reply.nak_code
```

Normal high-level application code generally does not need these objects because the
public methods raise exceptions when a reply is unsuccessful.

---

## 17. Common Return-value Summary

| Method | Common return value |
|---|---|
| `close()` | `None` |
| `read()` | Unsigned 16-bit integer |
| `write()` | Value masked to 16 bits |
| `read_bit()` | `0` or `1` |
| `write_bit()` | `0` or `1` |
| `input()` | `0` or `1` |
| `output()` | `0` or `1` |
| `read_block()` | List of unsigned 16-bit integers |
| `write_block()` | Masked input list in caller order |
| `read_uint()` | Unsigned multi-register integer |
| `write_uint()` | List returned by `write_block()` |
| `read_float()` | Rounded Python float |
| `write_float()` | `float(value)` |
| `read_timer()` | List of timer dictionaries |
| `write_timer()` | Timer current value written |
| `write_counter()` | Counter preset value written |
| `read_error()` | List of raw 16-bit error words |
| `force_io()` | `0` or `1` |
| `force()` | `0` or `1` |
| `force_output()` | `0` or `1` |

---

## 18. Common Exceptions

### `ValueError`

Both libraries use `ValueError` for invalid local arguments, including examples such as:

- malformed operand addresses;
- integer addresses without `dtype`;
- invalid bit numbers;
- invalid block counts;
- invalid endian values;
- timer values outside supported ranges;
- unsigned integers that do not fit;
- unsupported forced-output numbers.

### `IOError`

Both libraries use `IOError` for Maintenance Protocol failures, including:

- NAK replies;
- ACK/NG replies;
- reply BCC mismatches;
- unexpected reply kinds;
- unexpected payload lengths;
- malformed hexadecimal payload data.

Transport failures are not part of the common exception API:

- Serial can raise PySerial exceptions.
- TCP can raise socket-related exceptions.

---

## 19. Transport-independent Example

Only the setup lines differ:

```python
# Serial:
from MiSmSerial import MiSmSerial
plc = MiSmSerial("/dev/ttyACM0")

# TCP:
# from MiSmTCP import MiSmTCP
# plc = MiSmTCP("192.168.1.50")
```

The remaining application code is common:

```python
try:
    status = plc.read("D8005")
    running = plc.read_bit("M8125")
    serial_number = plc.read_uint(
        "D0105",
        count=2,
        endian=1,
    )
    temperature = plc.read_float("D0200")

    print(f"D8005: {status}")
    print(f"Running: {running}")
    print(f"Serial number: {serial_number}")
    print(f"Temperature: {temperature}")
finally:
    plc.close()
```

---

## 20. Methods Intentionally Excluded

The following are not part of this common API.

### Transport-specific connection methods

```text
connect()
disconnect()
reconnect()
context-manager entry and exit
```

These are available through `MiSmTCP`, not through the same Serial interface.

### Transport-specific constructors and options

Serial uses a serial device, baud rate, byte size, parity, and stop bits.

TCP uses a host, TCP port, persistent-connection options, and TCP-specific connection
behavior.

### `release_force()` and `force_release()`

The reviewed APIs do not expose the same safe call signature and behavior. Portable
code should use:

```python
plc.force_io(False)
```

### TCP upload methods

```text
upload()
upload_sha256()
```

These are not shared with `MiSmSerial` and are incomplete in the reviewed TCP source.

### Precision configuration

The default float-read behavior is compatible, but precision configuration is
transport-specific:

- Serial uses a module-level `PRECISION`.
- TCP uses an instance constructor option.

---

## Source Documents

This common API was derived from:

- `src/API/MiSmSerial_API.md`
- `src/API/MiSmTCP_API.md`

The source libraries remain authoritative when their implementations change.
