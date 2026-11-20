#include "cross_dso.hpp"
#include <stdexcept>

ProbeBase::~ProbeBase() = default;
ProbeObject::~ProbeObject() { ++*destroyed; }
int ProbeObject::value() const { return 42; }
ProbeBase *probe_create(int *destroyed) { return new ProbeObject(destroyed); }
void probe_throw(const std::string &message) {
#ifdef COMPAT_PROBE_NEGATIVE
    throw std::runtime_error("changed contract");
#else
    throw std::runtime_error(message + ":dso");
#endif
}

void probe_touch_tls(int *destroyed) {
    struct Lifetime {
        int *destroyed;
        ~Lifetime() { ++*destroyed; }
    };
    thread_local Lifetime lifetime{destroyed};
    (void)lifetime;
}
