#include <cassert>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>
#include <typeinfo>
#include <vector>
struct Base { virtual ~Base() = default; };
struct Derived : Base { int value = 42; };
thread_local int local = 9;
int main() {
    bool unwound = false;
    struct Guard { bool &flag; ~Guard() { flag = true; } };
    try { Guard g{unwound}; throw std::runtime_error("expected"); }
    catch (const std::exception &e) { assert(std::string(e.what()) == "expected"); }
    assert(unwound);
    Derived d; Base *b = &d;
    assert(dynamic_cast<Derived *>(b)->value == 42 && typeid(*b) == typeid(Derived));
    std::thread t([] { assert(local == 9); local = 15; }); t.join(); assert(local == 9);
    std::vector<std::string> strings{"Tizen", "UTF-8: \xc3\xa9"}; assert(strings.size() == 2);
    std::cout << "{\"probe\":\"cpp-behavior\",\"ok\":true,\"string_size\":" << sizeof(std::string)
              << ",\"derived_size\":" << sizeof(Derived) << "}\n";
}
