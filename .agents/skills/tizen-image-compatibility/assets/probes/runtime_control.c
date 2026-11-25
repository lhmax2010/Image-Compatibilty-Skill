#include <stdio.h>
#include <unistd.h>
int main(void) {
#ifdef WAIT_FOR_SCOPE
    sleep(20);
    return 18;
#else
    puts("control: expected nonzero");
    return 17;
#endif
}
