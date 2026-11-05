#include <sys/prctl.h>
void name(void) { prctl(15, "x"); }
