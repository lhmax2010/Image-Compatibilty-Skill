#if defined(PROVIDER)
#include <stdio.h>
static int initialized;
__attribute__((constructor)) static void start(void) { initialized = 1; }
__attribute__((destructor)) static void stop(void) { puts("provider: fini"); }
int probe_alive(void) { return initialized; }
#ifndef OMIT_CONTRACT
int contract_v1(void) { return 21; }
#ifdef PROVIDE_V1
__asm__(".symver contract_v1,sr_contract@SR_PROBE_1");
#endif
int contract_v2(void) { return 42; }
__asm__(".symver contract_v2,sr_contract@@SR_PROBE_2");
#endif
#elif defined(RESIDENT_PROVIDER)
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <sys/types.h>
int main(void) {
    void *local = dlopen("libc.so.6", RTLD_NOLOAD | RTLD_NOW | RTLD_LOCAL);
    if (!local) return 20;
    pid_t (*pid)(void) = (pid_t (*)(void))dlsym(local, "getpid");
    pid_t (*versioned_pid)(void) = (pid_t (*)(void))dlvsym(local, "getpid", "GLIBC_2.4");
    if (!pid || !versioned_pid || pid() <= 0 || pid() != versioned_pid() || dlclose(local)) return 21;

    /* This only requests a handle to a resident system library. */
    void *global = dlopen("libc.so.6", RTLD_NOLOAD | RTLD_NOW | RTLD_GLOBAL);
    if (!global) return 22;
    dlerror();
    if (dlsym(global, "sr_probe_missing_name") || !dlerror() || dlclose(global)) return 23;
    puts("dynamic: resident handles and symbol lookup ok");
}
#elif defined(DYNAMIC)
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
static int call(void *library, const char *symbol, const char *version) {
    int (*fn)(void) = (int (*)(void))dlvsym(library, symbol, version);
    return fn ? fn() : -1;
}
int main(void) {
    if (dlopen("./absent-probe.so", RTLD_NOW)) return 10;
    if (!dlerror()) return 11;
    void *so = dlopen("./libsr_probe.so", RTLD_NOW | RTLD_LOCAL);
    if (!so || dlsym(RTLD_DEFAULT, "sr_contract")) return 12;
    dlerror();
    if (dlsym(so, "sr_no_symbol") || !dlerror()) return 13;
    int (*alive)(void) = (int (*)(void))dlsym(so, "probe_alive");
    if (!alive || alive() != 1 || call(so, "sr_contract", "SR_PROBE_1") != 21
        || call(so, "sr_contract", "SR_PROBE_2") != 42 || dlclose(so)) return 14;
    so = dlopen("./libsr_probe.so", RTLD_NOW | RTLD_GLOBAL);
    int (*fn)(void) = (int (*)(void))dlsym(RTLD_DEFAULT, "sr_contract");
    if (!so || !fn || fn() != 42 || dlclose(so)) return 15;
    puts("dynamic: local global versions and errors ok");
}
#else
extern int required(void);
__asm__(".symver required,sr_contract@SR_PROBE_1");
#include <stdio.h>
int main(void) {
    if (required() != 21) return 19;
    puts("versioned: SR_PROBE_1 ok");
}
#endif
