/*
 * HG2J screen-to-SCPI test.
 * Reads LSD31 from the HMI's own maintenance service via TCP 2537.
 * Screen 1 or unknown => output OFF. Screen 2 => 1000 Hz sine, output ON.
 * Only writes to an instrument if USBTMC device is explicitly supplied.
 * Does not modify HMI mode, registers, project, or firmware.
 *
 * Build: arm-linux-gnueabihf-gcc -O2 -static -s -Wall -Wextra \
 *            -o hg2j_screen_scpi_arm hg2j_screen_scpi.c
 * HMI dry run: ./hg2j_screen_scpi_arm 192.168.1.20 60
 * Real USBTMC: ./hg2j_screen_scpi_arm 192.168.1.20 60 /dev/usbtmc0
 * Poll count 0 = run until Ctrl+C.
 */
#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#define MAINT_PORT 2537
#define FRAME_MAX 2048

static int write_all(int fd, const unsigned char *p, size_t n)
{
    while (n) {
        ssize_t k = send(fd, p, n, 0);
        if (k < 0 && errno == EINTR) continue;
        if (k == 0) errno = EPIPE;
        if (k <= 0) return -1;
        p += (size_t)k;
        n -= (size_t)k;
    }
    return 0;
}

static int read_all(int fd, unsigned char *p, size_t n)
{
    while (n) {
        ssize_t k = recv(fd, p, n, 0);
        if (k < 0 && errno == EINTR) continue;
        if (k == 0) errno = EPIPE;
        if (k <= 0) return -1;
        p += (size_t)k;
        n -= (size_t)k;
    }
    return 0;
}

static int send_command(int fd, const char *command)
{
    static const unsigned char prefix[18] = {
        0x01, 0x00, 0x00, 0x00, 0x00, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x01, 0x01, 0x01
    };
    unsigned char out[256];
    size_t cmdlen = strlen(command);
    size_t len = 18 + 1 + cmdlen + 2 + 1;
    unsigned char bcc = 0x05; /* XOR includes ENQ */
    static const char hex[] = "0123456789ABCDEF";

    if (len > sizeof(out)) return -1;
    memcpy(out, prefix, sizeof(prefix));
    out[2] = (unsigned char)(len >> 8);
    out[3] = (unsigned char)(len & 255);
    out[18] = 0x05;
    memcpy(out + 19, command, cmdlen);
    for (size_t i = 0; i < cmdlen; i++) bcc ^= (unsigned char)command[i];
    out[19 + cmdlen] = (unsigned char)hex[bcc >> 4];
    out[20 + cmdlen] = (unsigned char)hex[bcc & 15];
    out[21 + cmdlen] = '\r';
    return write_all(fd, out, len);
}

static int read_frame(int fd, unsigned char *buf, size_t size)
{
    unsigned int total;
    if (size < 18 || read_all(fd, buf, 18) < 0) return -1;
    total = ((unsigned int)buf[2] << 8) | buf[3];
    if (total < 19 || total > size) {
        fprintf(stderr, "Bad received frame length: %u\n", total);
        errno = EPROTO;
        return -1;
    }
    if (read_all(fd, buf + 18, total - 18) < 0) return -1;
    return (int)total;
}

static void dump_reply(const unsigned char *buf, int len)
{
    int end = len < 100 ? len : 100;
    fprintf(stderr, "Reply (%d bytes), inner bytes:", len);
    for (int i = 18; i < end; i++) fprintf(stderr, " %02X", buf[i]);
    if (end < len) fprintf(stderr, " ...");
    fputc('\n', stderr);
}

static int nibble(unsigned char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

static int parse_ch_lsd31(const unsigned char *buf, int len, unsigned int *result)
{
    const unsigned char *stx = NULL;
    const unsigned char *etx = NULL;
    const unsigned char *p = buf + 18;
    const unsigned char *end = buf + len;
    for (; p < end; p++) {
        if (*p == 0x02 && stx == NULL) stx = p;
        if (*p == 0x03 && stx != NULL) {
            etx = p;
            break;
        }
    }
    if (!stx || !etx || etx - stx < 5) return -1;
    p = etx - 4; /* Last registered device: four ASCII hex characters */
    *result = 0;
    for (int i = 0; i < 4; i++) {
        int v = nibble(p[i]);
        if (v < 0) return -1;
        *result = (*result << 4) | (unsigned int)v;
    }
    return 0;
}

static volatile sig_atomic_t stop_requested = 0;

static void stop_handler(int sig)
{
    (void)sig;
    stop_requested = 1;
}

/* An individual USBTMC write represents one instrument message. */
static int scpi_send(int usb_fd, const char *command)
{
    char line[96];
    size_t n = strlen(command);
    ssize_t written;

    if (n + 1 >= sizeof(line)) return -1;
    memcpy(line, command, n);
    line[n++] = '\n';
    line[n] = '\0';
    printf("%sSCPI: %s\n", usb_fd < 0 ? "[DRY RUN] " : "", command);
    if (usb_fd < 0) return 0;
    do {
        written = write(usb_fd, line, n);
    } while (written < 0 && errno == EINTR && !stop_requested);
    if (written != (ssize_t)n) {
        if (written >= 0) errno = EIO;
        perror("USBTMC write");
        return -1;
    }
    return 0;
}

static int scpi_initialize(int usb_fd)
{
    static const char *setup[] = {
        "OUTP OFF",         /* Never enable output during setup. */
        "FUNC SIN",
        "FREQ 1000",
        "VOLT:UNIT VPP",
        "VOLT 1.0",         /* 1 Vpp at instrument's configured load. */
        "VOLT:OFFS 0"
    };
    for (size_t i = 0; i < sizeof(setup) / sizeof(setup[0]); i++) {
        if (scpi_send(usb_fd, setup[i]) < 0) return -1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    const char *host = argc > 1 ? argv[1] : "192.168.1.20";
    long polls = argc > 2 ? strtol(argv[2], NULL, 10) : 60;
    const char *usb_device = argc > 3 ? argv[3] : NULL;
    int fd = -1, usb_fd = -1, rc = 1, len, last_state = 0;
    unsigned long i = 0;
    struct sockaddr_in addr;
    struct timeval timeout = {3, 0};
    struct timespec one_second = {1, 0};
    unsigned char reply[FRAME_MAX];
    struct sigaction sa;

    if (argc > 4 || polls < 0 || polls > 86400) {
        fprintf(stderr, "Usage: %s [HMI IPv4] [polls 0..86400] [USBTMC device]\n", argv[0]);
        fprintf(stderr, "  No USBTMC device = dry run; polls=0 runs until Ctrl+C.\n");
        return 2;
    }
    setvbuf(stdout, NULL, _IONBF, 0);
    signal(SIGPIPE, SIG_IGN);
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = stop_handler;
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);

    printf("Mode: %s\n", usb_device ? usb_device : "DRY RUN (SCPI printed only)");
    if (usb_device) {
        usb_fd = open(usb_device, O_RDWR);
        if (usb_fd < 0) {
            perror("open USBTMC device");
            fprintf(stderr, "USBTMC device not available; try dry-run mode first.\n");
            return 1;
        }
    }

    fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) { perror("socket"); goto cleanup; }
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(MAINT_PORT);
    if (inet_pton(AF_INET, host, &addr.sin_addr) != 1) {
        fprintf(stderr, "Invalid IPv4 address: %s\n", host);
        goto cleanup;
    }
    printf("Connecting to %s:%d ...\n", host, MAINT_PORT);
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("connect");
        goto cleanup;
    }
    if (send_command(fd, "00FFCG010100F5FF00000031") < 0 ||
        (len = read_frame(fd, reply, sizeof(reply))) < 0) {
        perror("CG request/reply");
        goto cleanup;
    }
    if (reply[18] != 0x06) {
        fprintf(stderr, "CG was not ACKed\n");
        dump_reply(reply, len);
        goto cleanup;
    }
    puts("CG accepted; initializing SCPI output OFF, 1000 Hz, 1 Vpp ...");
    if (scpi_initialize(usb_fd) < 0) goto cleanup;
    puts("Polling LSD31 once per second; touch NV4 screens 1 and 2:");

    while (!stop_requested && (polls == 0 || i < (unsigned long)polls)) {
        unsigned int screen;
        int desired_state;
        if (send_command(fd, "00FFCH01") < 0 ||
            (len = read_frame(fd, reply, sizeof(reply))) < 0) {
            perror("CH request/reply");
            goto cleanup;
        }
        if (parse_ch_lsd31(reply, len, &screen) < 0) {
            fprintf(stderr, "Could not parse CH response\n");
            dump_reply(reply, len);
            goto cleanup;
        }
        desired_state = screen == 2 ? 1 : 0;
        if (i == 0 || desired_state != last_state) {
            printf("LSD31=%u => output %s\n", screen,
                   desired_state ? "ON (1000 Hz)" : "OFF");
        }
        if (desired_state != last_state) {
            if (scpi_send(usb_fd, desired_state ? "OUTP ON" : "OUTP OFF") < 0)
                goto cleanup;
            last_state = desired_state;
        }
        i++;
        if (!stop_requested && (polls == 0 || i < (unsigned long)polls))
            nanosleep(&one_second, NULL);
    }
    rc = 0;

cleanup:
    /* This is a best-effort stop, not a guarantee if power/USB is lost. */
    if (usb_fd >= 0) {
        puts("Leaving generator output OFF.");
        if (scpi_send(usb_fd, "OUTP OFF") < 0) rc = 1;
        close(usb_fd);
    }
    if (fd >= 0) close(fd);
    return rc;
}
