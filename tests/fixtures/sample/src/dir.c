#include <dirent.h>
#include <fcntl.h>
#include <sys/types.h>
#include <endian.h>

int count_dirs(const char *path)
{
    int n = 0;
    int fd = open(path, O_RDONLY);
    DIR *d = fdopendir(fd);              /* QNX050: fd opened without O_DIRECTORY */
    struct dirent *e;
    while ((e = readdir(d)) != NULL)
        if (e->d_type == DT_DIR)         /* QNX032 */
            n++;
    return n;
}

unsigned big(void)
{
    char buffer[1 << 20];                /* QNX054: 1 MiB on the stack */
    buffer[0] = 1;
    return (unsigned)buffer[0] + (unsigned)makedev(1, 2);   /* QNX037 */
}
