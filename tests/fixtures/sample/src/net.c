/* Sample code exercising qnxscout rules. */
#include <sys/epoll.h>
#include <sys/socket.h>
#include <signal.h>
#include <string.h>
#ifdef HAVE_GETRANDOM
#include <sys/random.h>
#endif
#ifndef IOV_MAX
#define IOV_MAX 1024
#endif

static int loop(int fd)
{
    struct sigaction sa;
    struct epoll_event ev;
    int ep = epoll_create1(0);           /* QNX001 */
    memset(&sa, 0, sizeof sa);
    sa.sa_flags = SA_RESTART;            /* QNX030 */
    int s = socket(AF_INET, SOCK_STREAM, 0);   /* QNX080 (build never links socket) */
    const char *msg = "epoll_wait( in a string is ignored";
    // epoll_ctl( in a comment is ignored
    (void)msg;
    return epoll_ctl(ep, EPOLL_CTL_ADD, fd, &ev) + s + IOV_MAX;   /* IOV_MAX provided above: no finding */
}

int rnd(void *buf, int n)
{
#ifdef HAVE_GETRANDOM
    return getrandom(buf, n, 0);         /* guarded: info only */
#else
    return n;
#endif
}
