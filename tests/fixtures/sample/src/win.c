#if defined(__linux__) || defined(__APPLE__)
#include <unistd.h>
static void nap(void) { usleep(1000); }
#else
#include <windows.h>
static void nap(void) { Sleep(1); }
#endif
