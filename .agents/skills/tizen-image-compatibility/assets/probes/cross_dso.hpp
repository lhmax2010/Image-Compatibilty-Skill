#pragma once
#include <string>

struct ProbeBase {
    virtual ~ProbeBase();
    virtual int value() const = 0;
};

struct ProbeObject final : ProbeBase {
    int *destroyed;
    explicit ProbeObject(int *counter) : destroyed(counter) {}
    ~ProbeObject() override;
    int value() const override;
};

ProbeBase *probe_create(int *destroyed);
void probe_throw(const std::string &message);
void probe_touch_tls(int *destroyed);
