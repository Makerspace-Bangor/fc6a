/*
 * HG2J local maintenance-protocol read test.
 * Registers LSD31 with CG01, then reads it with CH01.
 * Uses the existing IDEC NV3-style 18-byte TCP frame and XOR BCC.
 * Read-only: does not change HMI mode, registers, or project.
 *
 * Build on Linux with an ARM hard-float cross compiler:
 *   arm-linux-gnueabihf-gcc -O2 -static -s -Wall -Wextra \
 *       -o hg2j_self_register hg2j_self_register.c
 * Run on HMI:
 *   ./hg2j_self_register 127.0.0.1 20
 *   ./hg2j_self_register 192.168.1.20 20
 *
 * sn@ker:~/fc6a/HMI/selfTest$ gcc -O2 -Wall -Wextra -o hg2j_self_register_pc hg2j_self_register.c
 * sn@ker:~/fc6a/HMI/selfTest$ ./hg2j_self_register_pc 192.168.1.20 5
 * Connecting to 192.168.1.20:2537 ...
 * TCP connected; registering LSD31 with CG01
 * CG was not ACKed (expected inner 06)
 * Reply (26 bytes), inner bytes: 15 30 30 46 46 30 33 0D
 * NAK 00FF03 CR
 * Which is a FAIL, but its a Maintenance Protocol Fail. :D
 */
#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <errno.h>
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

int main(int argc, char **argv)
{
    const char *host = argc > 1 ? argv[1] : "127.0.0.1";
    int polls = argc > 2 ? atoi(argv[2]) : 20;
    int fd;
    struct sockaddr_in addr;
    struct timeval timeout = {3, 0};
    struct timespec one_second = {1, 0};
    unsigned char reply[FRAME_MAX];
    int len;

    if (polls < 1 || polls > 600) {
        fprintf(stderr, "Usage: %s [IPv4 address] [polls 1..600]\n", argv[0]);
        return 2;
    }
    setvbuf(stdout, NULL, _IONBF, 0);
    signal(SIGPIPE, SIG_IGN);
    fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) { perror("socket"); return 1; }
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(MAINT_PORT);
    if (inet_pton(AF_INET, host, &addr.sin_addr) != 1) {
        fprintf(stderr, "Invalid IPv4 address: %s\n", host);
        close(fd);
        return 2;
    }
    printf("Connecting to %s:%d ...\n", host, MAINT_PORT);
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("connect");
        close(fd);
        return 1;
    }
    puts("TCP connected; registering LSD31 with CG01");

    /* Register one special register: port 00, LSD device F5, bit FF, LSD31. */
    if (send_command(fd, "00FFCG010100F5FF00000031") < 0 ||
        (len = read_frame(fd, reply, sizeof(reply))) < 0) {
        perror("CG request/reply");
        close(fd);
        return 1;
    }
    if (reply[18] != 0x06) {
        fprintf(stderr, "CG was not ACKed (expected inner 06)\n");
        dump_reply(reply, len);
        close(fd);
        return 1;
    }
    puts("CG accepted; touch/change NV4 screens while polling:");
    for (int i = 0; i < polls; i++) {
        unsigned int screen;
        if (send_command(fd, "00FFCH01") < 0 ||
            (len = read_frame(fd, reply, sizeof(reply))) < 0) {
            perror("CH request/reply");
            close(fd);
            return 1;
        }
        if (parse_ch_lsd31(reply, len, &screen) < 0) {
            fprintf(stderr, "Could not parse CH response\n");
            dump_reply(reply, len);
            close(fd);
            return 1;
        }
        printf("%02d  LSD31 = %u (0x%04X)\n", i + 1, screen, screen);
        if (i + 1 < polls) nanosleep(&one_second, NULL);
    }
    close(fd);
    return 0;
}
