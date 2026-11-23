#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <net/if.h>
#include <sched.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/statvfs.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

static int private_namespace(const char *name, const char *outer) {
    char path[64], value[64];
    snprintf(path, sizeof path, "/proc/self/ns/%s", name);
    ssize_t n = readlink(path, value, sizeof(value) - 1);
    if (n < 0) return 0;
    value[n] = 0;
    return strcmp(value, outer) != 0;
}

static int valid_limits(void) {
    const int resources[] = {RLIMIT_CPU, RLIMIT_AS, RLIMIT_NOFILE, RLIMIT_FSIZE, RLIMIT_CORE};
    const rlim_t limit[] = {10, 8589934592ULL, 64, 1048576, 0};
    for (size_t i = 0; i < sizeof resources / sizeof *resources; i++) {
        struct rlimit r;
        if (getrlimit(resources[i], &r) || r.rlim_cur != limit[i] || r.rlim_max != limit[i]) return 0;
    }
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 7) return 2;
    long uid = strtol(argv[2], NULL, 10), gid = strtol(argv[3], NULL, 10);
    if (uid <= 0 || gid <= 0 || getuid() != uid || geteuid() != uid || getgid() != gid ||
        getegid() != gid || prctl(PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0) != 1) return 3;
    gid_t groups[8];
    int count = getgroups(8, groups);
    if (count < 0) return 3;
    for (int i = 0; i < count; i++) if (groups[i] != gid) return 3;
    if (!private_namespace("net", argv[4]) || !private_namespace("pid", argv[5]) ||
        !private_namespace("mnt", argv[6]) || unshare(CLONE_NEWUSER) == 0) return 4;
    struct if_nameindex *links = if_nameindex();
    if (!links) return 4;
    for (struct if_nameindex *link = links; link->if_index; ++link)
        if (strcmp(link->if_name, "lo")) return 4;
    if_freenameindex(links);
    FILE *status = fopen("/proc/self/status", "r");
    if (!status) return 5;
    int caps = 0;
    char line[256];
    while (fgets(line, sizeof line, status))
        if (!strcmp(line, "CapEff:\t0000000000000000\n") ||
            !strcmp(line, "CapPrm:\t0000000000000000\n") ||
            !strcmp(line, "CapBnd:\t0000000000000000\n") ||
            !strcmp(line, "CapAmb:\t0000000000000000\n")) caps++;
    fclose(status);
    if (caps != 4 || !valid_limits()) return 5;
    struct statvfs sv;
    const char *inputs[] = {"/runner/probe", "/runner/qemu-arm-static", "/lib/ld-linux.so.3", "/lib/libc.so.6"};
    for (size_t i = 0; i < sizeof inputs / sizeof *inputs; i++) {
        char magic[4];
        int fd = open(inputs[i], O_RDONLY);
        if (fd < 0 || read(fd, magic, sizeof magic) != sizeof magic || memcmp(magic, "\177ELF", 4)) return 6;
        close(fd);
        if (open(inputs[i], O_WRONLY) >= 0 || (errno != EROFS && errno != EACCES) ||
            statvfs(inputs[i], &sv) || !(sv.f_flag & ST_RDONLY)) return 6;
    }
    if (open("/outside-tmp", O_CREAT|O_WRONLY, 0600) >= 0 || errno != EROFS ||
        access("/home", F_OK) == 0 || access("/usr/bin/sudo", F_OK) == 0 ||
        access("/sys/fs/cgroup", F_OK) == 0) return 6;
    int scratch = open("/tmp/host-only", O_CREAT|O_WRONLY|O_EXCL, 0600);
    if (scratch < 0 || write(scratch, "ok", 2) != 2 ||
        statvfs("/tmp", &sv) || sv.f_blocks * sv.f_frsize != 16777216) return 7;
    close(scratch);
    printf("uid=%ld gid=%ld supplementary_count=%d\n", (long)getuid(), (long)getgid(), count);
    puts("HOST_X86_64_ISOLATION_OK");
    fflush(stdout);
    const char *mode = argv[1];
    if (!strcmp(mode, "closed") || !strcmp(mode, "session") || !strcmp(mode, "controller")) {
        int channel[2];
        if (pipe(channel)) return 8;
        pid_t child = fork();
        if (child < 0) return 8;
        if (!child) {
            close(channel[0]);
            if (strcmp(mode, "closed") && setsid() < 0) _exit(9);
            close(1);
            close(2);
            if (write(channel[1], "x", 1) != 1) _exit(9);
            close(channel[1]);
            sleep(30);
            _exit(0);
        }
        char ready;
        close(channel[1]);
        if (read(channel[0], &ready, 1) != 1) return 8;
        close(channel[0]);
        puts("HOST_CHILD_READY");
        fflush(stdout);
    }
    /* Bounded memory and CPU activity under the live cgroup. */
    size_t bytes = 1024 * 1024;
    volatile unsigned char *memory = malloc(bytes);
    if (!memory) return 9;
    for (size_t i = 0; i < bytes; i += 4096) memory[i] = 1;
    for (volatile unsigned int i = 0; i < 1000000; i++) {}
    usleep(800000);
    free((void *)memory);
    if (!strcmp(mode, "nonzero")) return 17;
    if (!strcmp(mode, "timeout") || !strcmp(mode, "controller")) sleep(30);
    if (!strcmp(mode, "sigint")) raise(SIGINT);
    if (!strcmp(mode, "sigterm")) raise(SIGTERM);
    if (!strcmp(mode, "overflow")) {
        char buf[4096];
        memset(buf, 'x', sizeof buf);
        for (int i = 0; i < 300; i++)
            if (write(i % 2 ? 1 : 2, buf, sizeof buf) != sizeof buf) return 10;
    }
    return 0;
}
