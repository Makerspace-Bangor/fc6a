/*
 * Minimal, read-only Agilent 33220A USBTMC test for Linux usbfs.
 * No libusb, usbtmc kernel driver, Python, or other libraries required.
 * Uses raw /dev/bus/usb/BBB/DDD via USBDEVFS_* ioctls.
 *
 * Build for HG2J (ARMv7 hard-float):
 *   arm-linux-gnueabihf-gcc -O2 -Wall -Wextra -static -s \
 *       -o hg2j_usbtmc_idn_arm hg2j_usbtmc_idn.c
 *
 * Usage on HG2J:
 *   ./hg2j_usbtmc_idn_arm /dev/bus/usb/002/003
 *
 * Sends only *IDN?\n. Does not change the generator output.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <linux/usbdevice_fs.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define VENDOR_ID   0x0957u
#define PRODUCT_ID  0x0407u
#define IFACE       0u
#define EP_BULK_OUT 0x02u
#define EP_BULK_IN  0x86u
#define TIMEOUT_MS  4000u

static unsigned next_tag = 1;

static uint32_t get_u32le(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
        ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void put_u32le(unsigned char *p, uint32_t value)
{
    p[0] = value & 0xffu;
    p[1] = (value >> 8) & 0xffu;
    p[2] = (value >> 16) & 0xffu;
    p[3] = (value >> 24) & 0xffu;
}

static int bulk(int fd, unsigned ep, void *data, unsigned len)
{
    struct usbdevfs_bulktransfer req;
    memset(&req, 0, sizeof(req));
    req.ep = ep;
    req.len = len;
    req.timeout = TIMEOUT_MS;
    req.data = data;
    int n;
    do { n = ioctl(fd, USBDEVFS_BULK, &req); } while (n < 0 && errno == EINTR);
    if (n < 0) {
        fprintf(stderr, "USB bulk ep 0x%02X: %s\n", ep, strerror(errno));
    } else if ((ep & 0x80u) == 0 && (unsigned)n != len) {
        fprintf(stderr, "USB bulk short write: %d/%u\n", n, len);
        errno = EIO;
        return -1;
    }
    return n;
}

static int verify_agilent(int fd)
{
    unsigned char desc[18] = {0};
    struct usbdevfs_ctrltransfer req;
    memset(&req, 0, sizeof(req));
    req.bRequestType = 0x80; /* Standard IN to device */
    req.bRequest = 6;        /* GET_DESCRIPTOR */
    req.wValue = 0x0100;     /* Device descriptor */
    req.wLength = sizeof(desc);
    req.timeout = TIMEOUT_MS;
    req.data = desc;
    int n = ioctl(fd, USBDEVFS_CONTROL, &req);
    if (n < 0) { perror("USB device descriptor"); return -1; }
    if (n != (int)sizeof(desc)) {
        fprintf(stderr, "Short USB device descriptor (%d bytes)\n", n);
        return -1;
    }
    unsigned vid = desc[8] | ((unsigned)desc[9] << 8);
    unsigned pid = desc[10] | ((unsigned)desc[11] << 8);
    printf("USB identity: %04x:%04x\n", vid, pid);
    if (vid != VENDOR_ID || pid != PRODUCT_ID) {
        fprintf(stderr, "Not the expected Agilent 33220A; refusing test.\n");
        return -1;
    }
    return 0;
}

static int send_tmc(int fd, const char *command, unsigned char msg_id, uint32_t read_size,
                    unsigned *used_tag)
{
    unsigned char packet[256] = {0};
    size_t data_len = msg_id == 1 ? strlen(command) : 0;
    if (data_len > sizeof(packet) - 12u) return -1;
    unsigned tag = next_tag++;
    if (next_tag > 255) next_tag = 1;
    packet[0] = msg_id;
    packet[1] = tag;
    packet[2] = (unsigned char)~tag;
    /* packet[3] reserved = 0 */
    put_u32le(packet + 4, msg_id == 1 ? (uint32_t)data_len : read_size);
    packet[8] = msg_id == 1 ? 1 : 0; /* EOM=1 for a complete command */
    if (msg_id == 1) memcpy(packet + 12, command, data_len);
    size_t packet_size = msg_id == 1 ? ((12u + data_len + 3u) & ~(size_t)3u) : 12u;
    int n = bulk(fd, EP_BULK_OUT, packet, (unsigned)packet_size);
    if (n < 0) return -1;
    *used_tag = tag;
    return 0;
}

static int query_idn(int fd)
{
    unsigned cmd_tag = 0, read_tag = 0;
    if (send_tmc(fd, "*IDN?\n", 1, 0, &cmd_tag) < 0) return -1;
    printf("USBTMC DEV_DEP_MSG_OUT sent, tag=%u: *IDN?\n", cmd_tag);
    if (send_tmc(fd, NULL, 2, 512, &read_tag) < 0) return -1;
    unsigned char reply[1024];
    int n = bulk(fd, EP_BULK_IN, reply, sizeof(reply));
    if (n < 0) return -1;
    if (n < 12) { fprintf(stderr, "USBTMC reply shorter than header (%d)\n", n); return -1; }
    unsigned count = get_u32le(reply + 4);
    printf("USBTMC response: %d bytes, msg=%u, tag=%u, payload=%u, EOM=%u\n",
           n, reply[0], reply[1], count, reply[8] & 1u);
    if (reply[0] != 2 || reply[1] != read_tag ||
        reply[2] != (unsigned char)(read_tag ^ 0xffu)) {
        fprintf(stderr, "Unexpected USBTMC response header\n");
        return -1;
    }
    if (count > (unsigned)n - 12u) {
        fprintf(stderr, "Incomplete IDN response (%u of %u bytes); report this output.\n",
                (unsigned)n - 12u, count);
        return -1;
    }
    printf("33220A identification: ");
    if (fwrite(reply + 12, 1, count, stdout) != count) return -1;
    if (count == 0 || reply[12 + count - 1] != '\n') putchar('\n');
    return 0;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "Usage: %s /dev/bus/usb/BBB/DDD\n", argv[0]);
        return 2;
    }
    setvbuf(stdout, NULL, _IONBF, 0);
    int fd = open(argv[1], O_RDWR | O_CLOEXEC);
    if (fd < 0) { perror("open raw USB device"); return 1; }
    if (verify_agilent(fd) < 0) { close(fd); return 1; }
    unsigned interface = IFACE;
    if (ioctl(fd, USBDEVFS_CLAIMINTERFACE, &interface) < 0) {
        perror("USBDEVFS_CLAIMINTERFACE (interface 0)");
        close(fd);
        return 1;
    }
    printf("Claimed interface 0, bulk OUT 0x%02X, bulk IN 0x%02X\n",
           EP_BULK_OUT, EP_BULK_IN);
    int rc = query_idn(fd) == 0 ? 0 : 1;
    if (ioctl(fd, USBDEVFS_RELEASEINTERFACE, &interface) < 0) {
        perror("USBDEVFS_RELEASEINTERFACE");
    }
    close(fd);
    return rc;
}
