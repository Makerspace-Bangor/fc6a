# MiSmHMI maintenance client

`src/MiSmHMI.py` now provides two separate interfaces:

| Class | Direction | Default port | Purpose |
| --- | --- | --- | --- |
| `MiSmHMI` | HMI connects to this server | 2101 | Existing PLC register emulator |
| `MiSmHMIClient` | This client connects to the HMI | 2537 | HMI diagnostics and monitor access |

Existing emulator methods and its command-line entry point retain their behavior.
This addition implements ordinary direct-target maintenance transactions. It does
not claim support for every token in the protocol reference.

## Read registers

With `src` on your Python import path:

```python
from MiSmHMI import MiSmHMIClient, MODE_NAMES

with MiSmHMIClient("192.168.1.20") as hmi:
    mode = hmi.read_mode()
    print(MODE_NAMES.get(mode, f"Unknown mode {mode}"))
    print(hmi.read_system_xml())
    screen, brightness = hmi.read_devices(["LSD31", "LSD51"])
    print(screen, brightness)

    # For repeated polling, register once and reuse the same connection.
    hmi.register_devices(["LSD31", "LSM6"], registration=2)
    print(hmi.read_registered(2))
```

Values are returned in input order. An invalid CH word containing question marks
is returned as `None`, not zero. Reads do not change operating mode. LSD227 is a
service-port bit mask; RTC words remain raw BCD values.

LSD and LSM are the only named device families added here. Their printed digits
are preserved in the address field: LSD31 becomes `00000031`. Other mappings can
be supplied with `HMIDevice(device_id, address, port=0, bit=0xFF)` once verified;
`address` is the encoded wire integer. No LDR mapping is guessed.

## Methods and evidence

| Method | Commands | Notes |
| --- | --- | --- |
| `read_mode()` | AB | Returns decimal mode number |
| `set_mode(mode)` | AA | Closes connection afterward; reconnect and confirm AB |
| `read_system_xml()` | LA | Extracts SystemInfoCDC XML; preserves original fields |
| `read_screens()` | DM | Returns base and five overlay numbers; mode-dependent |
| `change_screen(number)` | DL | ACK is acceptance only; verify DM or LSD31 |
| `register_devices(devices, registration=1)` | CG | Registration belongs to this connection |
| `read_registered(registration=1)` | CH | Returns a list of word values or None |
| `read_devices(devices, registration=1)` | CG, CH | Serialized compound operation |
| `read(device)` | CG, CH | Single value; replaces registration 1 |
| `write_devices(devices, values)` / `write(device, value)` | CI | Explicit addressed writes; verify effect by reading back |
| `authenticate(user, password, work_item=0)` | AO | Source-supported format; no default credentials or login attempts |
| `provision_ftp(user, password, create_znv=True)` | LB | Creates temporary credentials; does not open an FTP connection |
| `keepalive_ftp()` | LF | Caller schedules periodic calls while FTP is active |
| `finish_ftp()` | LD | Ends temporary transfer session |
| `command(token, payload=b"")` | Ordinary commands | Raw escape hatch; returns HMIResponse |

AO encoding and CI layouts are supported by the reference's desktop-source
analysis; this update has not tested authentication or register writes on an HMI.
All operations remain subject to model, project permissions and current mode.
NAK 02 and 03 are preserved without assigning universal meanings.

FTP file operations remain the caller's responsibility, for example through
standard-library `ftplib` on the maintenance control port 2539, honoring PASV.
Call LF periodically (the existing downloader uses about five seconds), and
serialize/stop keepalive activity before apply operations. This client does not
implement an automatic deployment workflow, staged-file checks, or recovery.

`command()` preserves case and accepts binary payloads, including the documented
LC/LG little-endian fields. The caller must implement the relevant workflow and
choose an adequate constructor timeout for long operations. EG/EH/FD/GH/GP and
other block-transfer state machines are not supported by this ordinary parser.
The raw API is not evidence that an arbitrary token works on a given HMI.

## Transport and failure behavior

The client builds the 18-byte direct-target wrapper and ENQ/00FF command frame.
It reads exactly the advertised packet length, so fragmented or adjacent TCP
packets and binary CR bytes do not corrupt framing. Packet sizes are bounded to
65535 bytes because larger framing behavior is unresolved in the reference.

Transactions are serialized by a reentrant lock. On EOF, timeout, malformed
framing, or transport failure, the client closes the socket and clears monitor
registrations. It never retries a write automatically. A valid NAK raises
`HMICommandError` with `command`, `code`, and `raw` attributes and leaves the
connection available. A lost reply does not prove a write failed.

The constructor's `verify_bcc=False` and `check_sequence=False` defaults follow
the permissive response handling of the existing research scripts. Request BCC
is always generated. Header shape, direct-target prefix, response type, suffix,
and hexadecimal check-field syntax are checked even with these options off.
For a verified target profile, `verify_bcc=True` requires response XOR including
the initial control byte and ETX; `check_sequence=True` requires the request
sequence to be echoed. Neither strict profile has been validated on hardware by
this change. Raw response bytes are retained for comparison with captures.

When running on the HG2J itself, use its configured Ethernet IP. Prior project
hardware tests found that the maintenance endpoint accepted that address but
rejected 127.0.0.1. This Python client runs on a host with Python installed; it
does not add Python to the stock HMI OS.

## Validation and sources

Run from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

The 18 offline tests cover reference request examples, fragmented and adjacent
replies, monitor registration lifecycle, question-mark values, binary payloads,
XML, NAKs, malformed/truncated/oversized replies, checksum/sequence checks,
timeout without retry, credential layout, and an existing emulator RD request.
Responses are synthetic fixtures, not newly captured HMI traffic. Next hardware
check: AB and LA, then CG/CH for LSD31 and LSD51. Compare the raw replies before
enabling strict checks or exercising writes.

Primary basis: `HMI_Maintenance_Protocol_Reference.docx` (4 October 2026), plus
`HMI/TOOLS/hg2j_alarms.py`, `hmi_info.py`, `hmi_mode_test.py`, `hmi_dl_test.py`, and
`hmi_znx_download.py`. Existing server semantics were deliberately retained:
the reference distinguishes the PLC-facing NAK/ACK conventions from HMI replies.
