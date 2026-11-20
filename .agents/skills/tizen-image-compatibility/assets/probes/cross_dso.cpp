#include "cross_dso.hpp"
#include <cstdio>
#include <memory>
#include <stdexcept>
#include <thread>
#include <typeinfo>

int main() {
    int destroyed = 0;
    {
        std::unique_ptr<ProbeBase> object(probe_create(&destroyed));
        if (!object || !dynamic_cast<ProbeObject *>(object.get()) ||
            typeid(*object) != typeid(ProbeObject) || object->value() != 42) return 10;
    }
    if (destroyed != 1) return 11;
    int tls_destroyed = 0;
    std::thread worker([&] { probe_touch_tls(&tls_destroyed); });
    worker.join();
    if (tls_destroyed != 1) return 12;
    bool unwound = false;
    struct Guard { bool &unwound; ~Guard() { unwound = true; } };
    try {
        Guard guard{unwound};
        probe_throw("cross-library long string to exercise allocation");
        return 13;
    } catch (const std::runtime_error &error) {
        if (std::string(error.what()) != "cross-library long string to exercise allocation:dso") return 14;
    }
    if (!unwound) return 15;
    std::puts("cross-dso: rtti lifetime string exception unwind tls ok");
}
