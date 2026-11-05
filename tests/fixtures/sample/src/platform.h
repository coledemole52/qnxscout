#ifndef PLATFORM_H
#define PLATFORM_H
#if defined(__linux__)
#  define OS_NAME "linux"
#elif defined(__APPLE__)
#  define OS_NAME "darwin"
#elif defined(__FreeBSD__)
#  define OS_NAME "freebsd"
#else
#  error "unsupported platform"
#endif
#if defined(__linux__)
#  include <linux/futex.h>
#endif
#endif
