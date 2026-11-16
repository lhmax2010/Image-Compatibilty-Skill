#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <locale.h>
#include <math.h>
#include <pthread.h>
#include <semaphore.h>
#include <signal.h>
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include <wchar.h>
static _Thread_local int tls = 7;
static atomic_int count;
static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t cond = PTHREAD_COND_INITIALIZER;
static int ready;
static volatile sig_atomic_t caught;
static void handler(int sig) { caught = sig; }
static void *worker(void *arg) {
    (void)arg;
    assert(tls == 7); tls = 11;
    assert(pthread_mutex_lock(&mutex) == 0);
    ready = 1; atomic_fetch_add(&count, 1);
    assert(pthread_cond_signal(&cond) == 0);
    assert(pthread_mutex_unlock(&mutex) == 0);
    return NULL;
}
int main(void) {
    void *p = NULL;
    assert(posix_memalign(&p, 64, 128) == 0 && (uintptr_t)p % 64 == 0);
    memset(p, 1, 128); free(p);
    pthread_t thread;
    assert(pthread_mutex_lock(&mutex) == 0);
    assert(pthread_create(&thread, NULL, worker, NULL) == 0);
    while (!ready) assert(pthread_cond_wait(&cond, &mutex) == 0);
    assert(pthread_mutex_unlock(&mutex) == 0);
    assert(pthread_join(thread, NULL) == 0 && tls == 7 && atomic_load(&count) == 1);
    sem_t sem; assert(sem_init(&sem, 0, 0) == 0);
    assert(sem_post(&sem) == 0 && sem_wait(&sem) == 0 && sem_destroy(&sem) == 0);
    assert(signal(SIGUSR1, handler) != SIG_ERR && raise(SIGUSR1) == 0 && caught == SIGUSR1);
    void *dl = dlopen(NULL, RTLD_NOW); assert(dl && dlsym(dl, "malloc")); assert(dlclose(dl) == 0);
    FILE *f = tmpfile(); assert(f); assert(fwrite("abc", 1, 3, f) == 3);
    rewind(f); char buf[4] = {0}; assert(fread(buf, 1, 3, f) == 3 && strcmp(buf, "abc") == 0); fclose(f);
    int pair[2]; assert(socketpair(AF_UNIX, SOCK_STREAM, 0, pair) == 0);
    assert(write(pair[0], "a", 1) == 1 && read(pair[1], buf, 1) == 1 && buf[0] == 'a'); close(pair[0]); close(pair[1]);
    pid_t pid = fork(); assert(pid >= 0); if (!pid) _exit(23);
    int status; assert(waitpid(pid, &status, 0) == pid && WIFEXITED(status) && WEXITSTATUS(status) == 23);
    struct timespec t; assert(clock_gettime(CLOCK_MONOTONIC, &t) == 0);
    struct timespec delay = {0, 1000000}; assert(nanosleep(&delay, NULL) == 0);
    assert(setlocale(LC_ALL, "C")); assert(fabs(sqrt(4.0) - 2.0) < 1e-12);
    struct layout { char c; int i; double d; };
    printf("{\"probe\":\"c-behavior\",\"ok\":true,\"int_size\":%zu,\"pointer_size\":%zu,\"layout_size\":%zu,\"layout_align\":%zu,\"member_offset\":%zu}\n",
           sizeof(int), sizeof(void *), sizeof(struct layout), _Alignof(struct layout), offsetof(struct layout, d));
    return 0;
}
