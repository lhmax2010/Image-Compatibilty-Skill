#include <atomic>
#include <cstdio>
#include <pthread.h>
#include <sched.h>

struct Counters {
    std::atomic<bool> ready{false};
    unsigned destroyed = 0;
};

static void *worker(void *argument) {
    auto &state = *static_cast<Counters *>(argument);
    struct Guard { unsigned &count; ~Guard() { ++count; } } guard{state.destroyed};
    if (pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, nullptr) != 0 ||
        pthread_setcanceltype(PTHREAD_CANCEL_DEFERRED, nullptr) != 0) return nullptr;
    state.ready.store(true, std::memory_order_release);
    for (;;) {
        pthread_testcancel();
        sched_yield();
    }
}

int main() {
    Counters state;
    pthread_t thread;
    if (pthread_create(&thread, nullptr, worker, &state) != 0) return 10;
    for (unsigned spins = 0; !state.ready.load(std::memory_order_acquire); ++spins) {
        if (spins == 1000000) return 11;
        sched_yield();
    }
    if (pthread_cancel(thread) != 0) return 12;
    void *result = nullptr;
    if (pthread_join(thread, &result) != 0 || result != PTHREAD_CANCELED || state.destroyed != 1) return 13;
    std::puts("cancel: deferred cancellation and forced unwind ok");
}
