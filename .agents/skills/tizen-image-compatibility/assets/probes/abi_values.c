#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

struct values { uint32_t i; uint64_t wide; float f; double d; };
__attribute__((noinline)) static struct values exchange(struct values v, float x, uint64_t n, double y) {
    v.i += 3;
    v.wide ^= n;
    v.f += x;
    v.d += y;
    return v;
}

int main(void) {
    struct values *v = malloc(sizeof(*v));
    if (!v) return 10;
    *v = exchange((struct values){7, UINT64_C(0x100000000), 1.5f, 2.25}, 0.5f, UINT64_C(0x200000007), 0.75);
    int okay = v->i == 10 && v->wide == UINT64_C(0x300000007) && v->f == 2.0f && v->d == 3.0;
    free(v);
    if (!okay) return 11;
    puts("abi: integers fp aggregate allocation ok");
}
