import com.fazecast.jSerialComm.SerialPort
import java.io.ByteArrayOutputStream
import java.nio.charset.StandardCharsets
import kotlin.math.min

data class Reply(
    val kind: Kind,
    val raw: ByteArray,
    val ctrl: Byte = 0,
    val device: String = "",
    val command: Char = '\u0000',
    val data: ByteArray = byteArrayOf(),
    val bccRecv: Int? = null,
    val bccCalc: Int? = null,
    val bccOk: Boolean = false,
    val ngCode: String = "",
    val nakCode: String = ""
) {
    enum class Kind { ACK_OK, ACK_NG, NAK, MALFORMED, EMPTY, UNKNOWN }
}

class MiSmSerial(
    portName: String,
    device: String = "FF",
    baud: Int = 19200,
    private val timeoutMs: Int = 1000,
    private val debug: Boolean = false,
    bccMode: BccMode = BccMode.AUTO, // AUTO | ENQ | NO_ENQ
) : AutoCloseable {

    enum class BccMode { AUTO, ENQ, NO_ENQ }

    private val dev = device.uppercase().also {
        require(it.length == 2) { "device must be 2 ASCII hex chars, e.g. FF" }
    }

    private var mode = bccMode
    private val port: SerialPort = SerialPort.getCommPort(portName).apply {
        setComPortParameters(baud, 8, SerialPort.ONE_STOP_BIT, SerialPort.NO_PARITY)
        setComPortTimeouts(SerialPort.TIMEOUT_READ_BLOCKING, timeoutMs, timeoutMs)
        if (!openPort()) error("Failed to open port $portName")
    }

    override fun close() {
        if (port.isOpen) port.closePort()
    }

    // -------------------------
    // Helpers
    // -------------------------

    private fun xorBcc(data: ByteArray): Int {
        var x = 0
        for (b in data) x = x xor (b.toInt() and 0xFF)
        return x and 0xFF
    }

    private fun toAsciiHexByte(b: Int): ByteArray =
        String.format("%02X", b and 0xFF).toByteArray(StandardCharsets.US_ASCII)

    private fun asciiHexToInt(twoAscii: ByteArray): Int =
        twoAscii.toString(StandardCharsets.US_ASCII).toInt(16)

    private fun isHexAscii(data: ByteArray): Boolean =
        data.all { (it in '0'.code.toByte()..'9'.code.toByte()) || (it in 'A'.code.toByte()..'F'.code.toByte()) }

    private fun pad4(n: Int): String {
        require(n in 0..9999) { "operand number must be 0..9999" }
        return String.format("%04d", n)
    }

    private fun dtypeForBit(dtype: Char): Char = when (dtype.uppercaseChar()) {
        'X' -> 'x'
        'Y' -> 'y'
        'M' -> 'm'
        'R' -> 'r'
        else -> error("bit dtype must be X/Y/M/R")
    }

    private fun parseAddr(addr: String): Pair<Char, Int> {
        val s = addr.trim()
        require(s.length >= 2) { "addr must look like D0100, M8070, X0007, ..." }
        val d = s[0]
        val n = s.substring(1)
        require(n.all { it.isDigit() }) { "addr numeric portion must be digits" }
        return d to n.toInt()
    }

    private fun parseIo(io: Any, isOut: Boolean): Pair<Char, Int> {
        if (io is Int) {
            require(io in 0..9999) { "bit index must be 0..9999" }
            return (if (isOut) 'Y' else 'X') to io
        }
        val s = io.toString().trim().uppercase()
        require(s.isNotEmpty()) { "empty IO address" }
        val head = s[0]
        val tail = s.substring(1)

        return when (head) {
            'Q' -> {
                require(isOut) { "input() does not accept Q addresses" }
                require(tail.all { it.isDigit() }) { "Q address must be like Q0, Q7" }
                'Y' to tail.toInt()
            }
            'I' -> {
                require(!isOut) { "output() does not accept I addresses" }
                require(tail.all { it.isDigit() }) { "I address must be like I0, I7" }
                'X' to tail.toInt()
            }
            'X', 'Y' -> {
                require((head == 'Y') == isOut) { "output() expects Y/Q; input() expects X/I" }
                require(tail.all { it.isDigit() }) { "X/Y address must be numeric like X0007, Y0" }
                head to tail.toInt()
            }
            else -> error("IO must start with Q/I or X/Y")
        }
    }

    // -------------------------
    // Framing + transport
    // -------------------------

    private fun frameReq(cont: Char, cmd: Char, dtype: Char, payload: ByteArray, includeEnq: Boolean): ByteArray {
        require(cont == '0' || cont == '1') { "cont must be '0' or '1'" }

        val body = ByteArrayOutputStream().apply {
            write(dev.toByteArray(StandardCharsets.US_ASCII))
            write(cont.code)
            write(cmd.code)
            write(dtype.code)
            write(payload)
        }.toByteArray()

        val bcc = if (includeEnq) xorBcc(byteArrayOf(0x05) + body) else xorBcc(body)
        val framed = byteArrayOf(0x05) + body + toAsciiHexByte(bcc) + byteArrayOf(0x0D)

        if (debug) {
            runCatching { println("TX(ascii): " + body.toString(StandardCharsets.US_ASCII)) }
            println("TX(hex):   " + framed.joinToString("") { "%02x".format(it) })
        }
        return framed
    }

    private fun recvUntilCr(limit: Int = 8192): ByteArray {
        val out = ByteArrayOutputStream()
        val buf = ByteArray(1)
        val start = System.currentTimeMillis()

        while (out.size() < limit) {
            val n = port.readBytes(buf, 1)
            if (n <= 0) break
            out.write(buf, 0, n)
            if (buf[0] == 0x0D.toByte()) break
            if (System.currentTimeMillis() - start > timeoutMs * 3L) break
        }
        return out.toByteArray()
    }

    private fun parseReply(raw: ByteArray): Reply {
        if (raw.isEmpty()) return Reply(Reply.Kind.EMPTY, raw)
        if (raw.last() != 0x0D.toByte() || raw.size < 6) return Reply(Reply.Kind.MALFORMED, raw)

        val ctrl = raw[0]
        val dev = raw.copyOfRange(1, 3).toString(StandardCharsets.US_ASCII)
        val cmd = raw[3].toInt().toChar()
        val bccAscii = raw.copyOfRange(raw.size - 3, raw.size - 1)
        val data = raw.copyOfRange(4, raw.size - 3)

        val bccRecv = runCatching { asciiHexToInt(bccAscii) }.getOrElse {
            return Reply(Reply.Kind.MALFORMED, raw)
        }
        val bccCalc = xorBcc(raw.copyOfRange(0, raw.size - 3))
        val ok = bccCalc == bccRecv

        val base = Reply(
            kind = Reply.Kind.UNKNOWN,
            raw = raw,
            ctrl = ctrl,
            device = dev,
            command = cmd,
            data = data,
            bccRecv = bccRecv,
            bccCalc = bccCalc,
            bccOk = ok
        )

        return when (ctrl) {
            0x15.toByte() -> base.copy(
                kind = Reply.Kind.NAK,
                nakCode = if (data.size >= 2) data.copyOfRange(0, 2).toString(StandardCharsets.US_ASCII) else ""
            )
            0x06.toByte() -> {
                if (cmd == '2') base.copy(
                    kind = Reply.Kind.ACK_NG,
                    ngCode = if (data.size >= 2) data.copyOfRange(0, 2).toString(StandardCharsets.US_ASCII) else ""
                ) else base.copy(kind = Reply.Kind.ACK_OK)
            }
            else -> base
        }
    }

    private fun xferOnce(cont: Char, cmd: Char, dtype: Char, payload: ByteArray, includeEnq: Boolean): Reply {
        val req = frameReq(cont, cmd, dtype, payload, includeEnq)
        port.purgePort(SerialPort.PURGE_RXCLEAR or SerialPort.PURGE_TXCLEAR)
        port.writeBytes(req, req.size)

        val raw = recvUntilCr()
        if (debug) println("RX(hex):   " + raw.joinToString("") { "%02x".format(it) })

        val rep = parseReply(raw)

        if (rep.kind in setOf(Reply.Kind.ACK_OK, Reply.Kind.ACK_NG, Reply.Kind.NAK) && !rep.bccOk) {
            error("Reply BCC mismatch: recv=${rep.bccRecv} calc=${rep.bccCalc} raw=${raw.joinToString("") { "%02x".format(it) }}")
        }
        return rep
    }

    private fun xfer(cont: Char, cmd: Char, dtype: Char, payload: ByteArray = byteArrayOf()): Reply {
        return when (mode) {
            BccMode.ENQ -> xferOnce(cont, cmd, dtype, payload, includeEnq = true)
            BccMode.NO_ENQ -> xferOnce(cont, cmd, dtype, payload, includeEnq = false)
            BccMode.AUTO -> {
                val rep = xferOnce(cont, cmd, dtype, payload, includeEnq = true)
                if (rep.kind == Reply.Kind.NAK && rep.nakCode == "10") {
                    val rep2 = xferOnce(cont, cmd, dtype, payload, includeEnq = false)
                    if (rep2.kind == Reply.Kind.ACK_OK) mode = BccMode.NO_ENQ
                    rep2
                } else {
                    if (rep.kind == Reply.Kind.ACK_OK) mode = BccMode.ENQ
                    rep
                }
            }
        }
    }

    private fun raiseIfErr(rep: Reply) {
        when (rep.kind) {
            Reply.Kind.NAK -> error("NAK code=${rep.nakCode} raw=${rep.raw.joinToString("") { "%02x".format(it) }}")
            Reply.Kind.ACK_NG -> error("ACK NG code=${rep.ngCode} raw=${rep.raw.joinToString("") { "%02x".format(it) }}")
            Reply.Kind.ACK_OK -> return
            else -> error("Unexpected reply kind=${rep.kind} raw=${rep.raw.joinToString("") { "%02x".format(it) }}")
        }
    }

    // -------------------------
    // Public API (subset like your Python)
    // -------------------------

    fun readBit(addr: String): Int {
        val (dt, op) = parseAddr(addr)
        val bitDt = dtypeForBit(dt)
        val payload = pad4(op).toByteArray(StandardCharsets.US_ASCII)

        val rep = xfer('0', 'R', bitDt, payload)
        raiseIfErr(rep)

        require(rep.data.size == 1 && (rep.data[0] == '0'.code.toByte() || rep.data[0] == '1'.code.toByte())) {
            "Unexpected bit payload: ${rep.data.toString(StandardCharsets.US_ASCII)}"
        }
        return if (rep.data[0] == '1'.code.toByte()) 1 else 0
    }

    fun writeBit(addr: String, on: Boolean): Int {
        val (dt, op) = parseAddr(addr)
        val bitDt = dtypeForBit(dt)
        val status = if (on) '1' else '0'
        val payload = (pad4(op) + status).toByteArray(StandardCharsets.US_ASCII)

        val rep = xfer('0', 'W', bitDt, payload)
        raiseIfErr(rep)
        return if (on) 1 else 0
    }

    fun output(bit: Any, on: Boolean = true): Int {
        val (_, b) = parseIo(bit, isOut = true)
        val v = if (on) 1 else 0
        val payload = String.format("%04d%d", b, v).toByteArray(StandardCharsets.US_ASCII) // EXACT "00001"
        val rep = xfer('0', 'W', 'y', payload)
        raiseIfErr(rep)
        return v
    }

    fun input(bit: Any): Int {
        val (_, b) = parseIo(bit, isOut = false)
        return readBit("X" + String.format("%04d", b))
    }
}
