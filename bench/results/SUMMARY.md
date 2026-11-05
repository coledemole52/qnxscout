# qnxscout benchmark: QNX's own ports

Method: for each package in `qnx-ports/aports`, download the pristine upstream source the recipe builds, scan it with qnxscout, and compare with what QNX engineers changed: their QNX-specific patches (identifiers in changed lines, and code they wrapped in new `#if` blocks) plus APKBUILD changes (extra `-l` flags when the source uses that library, `update_config_sub`, raised C standard). Recall is per (package, issue).

| Metric | Value |
|---|---|
| QNX packages in qnx-ports/aports | 721 |
| Scanned from pristine upstream source | 609 |
| Packages with QNX fixes qnxscout can be checked against | 135 |
| Distinct (package, issue) fixes made by QNX engineers | 211 |
| **Predicted by qnxscout (same rule)** | **155 (74%)** |
| Predicted, counting the right file as a hit | 164 (78%) |
| Effort-score AUC: needed QNX fixes vs. built unchanged | 0.777 |

Not scanned: download-failed-or-too-large (85), extract-failed (1), no-archive-source (22), skipped-too-large (4).

Notes: QNX052 "(null)" heuristic demoted to info after the main run (0 hits); scores recomputed from stored per-rule data. 14 packages re-evaluated after fixing compat-library usage detection in the ground-truth filter.

Ground truth is a conservative lower bound: some QNX recipe flags are redundant (libuv already links `socket` in its upstream QNX branch), and a fix QNX made centrally (one compat header) counts once.

## Per-rule recall

| Rule | Issue | QNX fixed | Predicted | Recall | Packages flagged |
|---|---|---|---|---|---|
| QNX080 | Sockets live in libsocket | 62 | 50 | 81% | 119 |
| QNX079 | Stale config.sub/config.guess | 26 | 25 | 96% | 37 |
| QNX075 | Linux-only branch in the build system | 15 | 9 | 60% | 60 |
| QNX081 | POSIX regex lives in libregex | 15 | 15 | 100% | 50 |
| QNX054 | Large stack buffers overflow QNX's default stack | 10 | 2 | 20% | 18 |
| QNX009 | Thread-local locale API needs liblocale-shim | 6 | 2 | 33% | 34 |
| QNX042 | forkpty/openpty live in <unix.h> on QNX | 6 | 3 | 50% | 9 |
| QNX050 | Directory fds must be opened with O_DIRECTORY | 6 | 4 | 67% | 28 |
| QNX002 | eventfd is not in QNX libc | 5 | 3 | 60% | 13 |
| QNX053 | Bare _XOPEN_SOURCE hides QNX APIs | 5 | 4 | 80% | 39 |
| QNX001 | epoll is not in QNX libc | 4 | 3 | 75% | 11 |
| QNX003 | timerfd is not in QNX libc | 4 | 4 | 100% | 13 |
| QNX006 | open_memstream needs QNX's memstream library | 4 | 4 | 100% | 6 |
| QNX074 | C90 language standard: QNX headers require C99 | 4 | 0 | 0% | 14 |
| QNX030 | SA_RESTART is not defined on QNX | 3 | 3 | 100% | 14 |
| QNX038 | glibc byte-order headers are not available | 3 | 2 | 67% | 23 |
| QNX044 | glibc-internal / Linux-only system headers | 3 | 2 | 67% | 43 |
| QNX047 | gettid() is declared in <process.h> on QNX | 3 | 0 | 0% | 3 |
| QNX004 | signalfd is not in QNX libc | 2 | 2 | 100% | 3 |
| QNX007 | System V shared memory needs the QNX shim | 2 | 1 | 50% | 13 |
| QNX014 | Raw Linux syscalls are not available | 2 | 2 | 100% | 41 |
| QNX021 | GNU string/sort extensions are missing | 2 | 1 | 50% | 25 |
| QNX024 | Linux file-I/O extensions are missing | 2 | 2 | 100% | 41 |
| QNX031 | IOV_MAX is not defined on QNX | 2 | 2 | 100% | 5 |
| QNX037 | makedev() takes three arguments on QNX | 2 | 2 | 100% | 16 |
| QNX052 | printf("%s", NULL) crashes on QNX | 2 | 0 | 0% | 0 |
| QNX071 | Linking libdl: dlopen() is in QNX libc | 2 | 2 | 100% | 38 |
| QNX011 | getrandom()/getentropy() are not available | 1 | 1 | 100% | 34 |
| QNX018 | execinfo backtrace() is not available | 1 | 1 | 100% | 11 |
| QNX025 | ucontext coroutine API is not available | 1 | 0 | 0% | 7 |
| QNX035 | TIOCSCTTY/TIOCPKT terminal ioctls are unsupported | 1 | 0 | 0% | 4 |
| QNX040 | <elf.h> is <sys/elf.h> on QNX | 1 | 1 | 100% | 10 |
| QNX046 | flock() is in <fcntl.h> and does not survive fork() on QNX | 1 | 1 | 100% | 15 |
| QNX051 | /proc and /sys paths differ on QNX | 1 | 1 | 100% | 73 |
| QNX056 | Prefer posix_spawn() over fork()+exec on QNX | 1 | 0 | 0% | 0 |
| QNX070 | Linking libpthread: QNX has no separate pthread library | 1 | 1 | 100% | 43 |
| QNX005 | inotify lives in libfsnotify, not libc | 0 | 0 | - | 9 |
| QNX008 | System V semaphores/message queues are not available | 0 | 0 | - | 5 |
| QNX010 | iconv is not part of QNX libc | 0 | 0 | - | 7 |
| QNX012 | CPU affinity uses ThreadCtl() on QNX | 0 | 0 | - | 20 |
| QNX013 | prctl() does not exist on QNX | 0 | 0 | - | 15 |
| QNX015 | Linux futex is not available | 0 | 0 | - | 5 |
| QNX016 | sysinfo()/get_nprocs() are not available | 0 | 0 | - | 9 |
| QNX017 | sysconf(_SC_PHYS_PAGES) returns -1 on QNX | 0 | 0 | - | 4 |
| QNX019 | statfs() is Linux/BSD-only; use statvfs() | 0 | 0 | - | 10 |
| QNX020 | mntent API is not available | 0 | 0 | - | 5 |
| QNX022 | glibc error()/program_invocation_name are missing | 0 | 0 | - | 41 |
| QNX023 | glibc-only process/thread helpers are missing | 0 | 0 | - | 36 |
| QNX026 | Linux mcontext register layout does not apply | 0 | 0 | - | 2 |
| QNX032 | struct dirent has no d_type on QNX | 0 | 0 | - | 37 |
| QNX033 | sig_t/sighandler_t are not defined on QNX | 0 | 0 | - | 6 |
| QNX034 | W_EXITCODE is not defined on QNX | 0 | 0 | - | 1 |
| QNX036 | SO_PEERCRED/struct ucred are Linux-only | 0 | 0 | - | 5 |
| QNX041 | <sys/syslimits.h> does not exist; PATH_MAX is in <limits.h> | 0 | 0 | - | 6 |
| QNX043 | Linux kernel headers are not available | 0 | 0 | - | 59 |
| QNX048 | SocketCAN: use QNX's io-sock SocketCAN | 0 | 0 | - | 1 |
| QNX055 | mlock()/mlockall() need a process ability on QNX | 0 | 0 | - | 1 |
| QNX057 | vfork() is not documented for QNX 8.0 | 0 | 0 | - | 7 |
| QNX060 | #error is reachable when compiling for QNX | 0 | 0 | - | 124 |
| QNX061 | QNX falls into the Windows branch | 0 | 0 | - | 82 |
| QNX062 | No QNX branch in a platform #if chain | 0 | 0 | - | 61 |
| QNX063 | Per-OS source files have no QNX variant | 0 | 0 | - | 21 |
| QNX072 | Linking libutil: forkpty() is in QNX libc | 0 | 0 | - | 5 |
| QNX073 | Linking librt | 0 | 0 | - | 30 |
| QNX076 | Build stops with a fatal error on QNX | 0 | 0 | - | 4 |
| QNX077 | Architecture detection via CMAKE_SYSTEM_PROCESSOR | 0 | 0 | - | 39 |
| QNX082 | crypt() lives in liblogin | 0 | 0 | - | 10 |

## Grade vs. actual QNX patch size

| Grade | Packages | Median QNX patch lines | Share needing any QNX source patch |
|---|---|---|---|
| A | 274 | 0 | 5% |
| B | 125 | 0 | 16% |
| C | 102 | 0 | 31% |
| D | 65 | 0 | 22% |
| E | 43 | 0 | 49% |

## Every package

| Package | Grade | QNX fixed | qnxscout predicted | Missed |
|---|---|---|---|---|
| apriltag | A | QNX054 | - | QNX054 |
| asio | C | QNX080 | - | QNX080 |
| aspell | B | QNX079 | QNX079 | - |
| aws-c-common | C | QNX075 | QNX075 | - |
| aws-c-io | C | QNX001, QNX075 | QNX001, QNX075 | - |
| bash | D | QNX037, QNX080, QNX081 | QNX037, QNX081 | QNX080 |
| bullet | D | QNX007, QNX080 | QNX007, QNX080 | - |
| busybox | E | QNX054, QNX080, QNX081 | QNX080, QNX081 | QNX054 |
| capnproto | E | QNX025, QNX050, QNX075 | QNX050 | QNX025, QNX075 |
| capstone | C | QNX052 | - | QNX052 |
| ccache | D | QNX080 | QNX080 | - |
| chrpath | C | QNX038, QNX040 | QNX040 | QNX038 |
| computelibrary | D | QNX081 | QNX081 | - |
| datefudge | C | QNX044, QNX071 | QNX044, QNX071 | - |
| dhcpcd | D | QNX042 | - | QNX042 |
| diffutils | E | QNX050 | QNX050 | - |
| epiphany | C | QNX009, QNX011, QNX056, QNX080 | QNX009, QNX011, QNX080 | QNX056 |
| exiv2 | C | QNX047, QNX051, QNX080 | QNX051, QNX080 | QNX047 |
| fcft | B | QNX009 | QNX009 | - |
| fftw | B | QNX079 | QNX079 | - |
| file | C | QNX081 | QNX081 | - |
| flex | B | QNX079, QNX081 | QNX079, QNX081 | - |
| fmt | B | QNX081 | QNX081 | - |
| foot | E | QNX001, QNX002, QNX003, QNX080, QNX081 | QNX001, QNX002, QNX003, QNX080, QNX081 | - |
| fribidi | A | QNX074 | - | QNX074 |
| g3log | C | QNX018, QNX071, QNX075 | QNX018, QNX071, QNX075 | - |
| gawk | D | QNX081 | QNX081 | - |
| gcr | B | QNX080 | QNX080 | - |
| gd | C | QNX079 | QNX079 | - |
| geany-plugins | C | QNX042 | QNX042 | - |
| geoip | C | QNX079, QNX080 | QNX079 | QNX080 |
| glfw | D | QNX075 | QNX075 | - |
| glib | E | QNX080 | - | QNX080 |
| gnome-keyring | B | QNX080 | QNX080 | - |
| gnutls | E | QNX038 | QNX038 | - |
| graphicsmagick | C | QNX047 | - | QNX047 |
| graphviz | D | QNX079 | - | QNX079 |
| grep | E | QNX081 | QNX081 | - |
| gsm | A | QNX074 | - | QNX074 |
| gst-plugins-bad | E | QNX080 | QNX080 | - |
| gst-plugins-base | B | QNX080 | QNX080 | - |
| gthumb | B | QNX053 | QNX053 | - |
| gtk3 | D | QNX014, QNX080 | QNX014, QNX080 | - |
| hiredis | B | QNX080 | - | QNX080 |
| hunspell | B | QNX079 | QNX079 | - |
| hyphen | B | QNX079 | QNX079 | - |
| jq | B | QNX053 | QNX053 | - |
| labwc | D | QNX003, QNX004 | QNX003, QNX004 | - |
| lcm | C | QNX080 | QNX080 | - |
| lely-core | C | QNX080 | QNX080 | - |
| libasyncns | B | QNX079 | QNX079 | - |
| libb2 | B | QNX079 | QNX079 | - |
| libcaca | B | QNX080 | QNX080 | - |
| libdaemon | B | QNX079 | QNX079 | - |
| libdatrie | B | QNX079 | QNX079 | - |
| libdisplay-info | B | QNX006 | QNX006 | - |
| libev | E | QNX079 | QNX079 | - |
| libevent | E | QNX002, QNX003, QNX030, QNX079 | QNX002, QNX003, QNX030, QNX079 | - |
| libfyaml | C | QNX006 | QNX006 | - |
| libgcrypt | D | QNX079 | QNX079 | - |
| libsoup | B | QNX080 | QNX080 | - |
| libsysv-ipc-shim | A | QNX007 | - | QNX007 |
| libthai | B | QNX079 | QNX079 | - |
| libunibreak | B | QNX079 | QNX079 | - |
| libuv | E | QNX075, QNX080 | QNX075 | QNX080 |
| libvalkey | C | QNX080 | - | QNX080 |
| libwebsockets | D | QNX070, QNX075 | QNX070, QNX075 | - |
| libxcrypt | C | QNX052 | - | QNX052 |
| libxfont2 | A | QNX042 | - | QNX042 |
| libxml2.13 | C | QNX054 | - | QNX054 |
| libxslt | C | QNX054 | - | QNX054 |
| log4cpp | C | QNX079 | QNX079 | - |
| m4 | E | QNX080, QNX081 | QNX081 | QNX080 |
| mpg123 | D | QNX042 | - | QNX042 |
| mujoco | E | QNX053, QNX075 | QNX075 | QNX053 |
| mythes | B | QNX079 | QNX079 | - |
| nginx | E | QNX080 | QNX080 | - |
| openexr | C | QNX038, QNX074 | QNX038 | QNX074 |
| openrc | E | QNX006, QNX080 | QNX006, QNX080 | - |
| openttd | D | QNX054 | - | QNX054 |
| p11-kit | C | QNX080 | - | QNX080 |
| patch | E | QNX050, QNX054 | QNX050 | QNX054 |
| pax-utils | D | QNX081 | QNX081 | - |
| pcre | C | QNX079 | QNX079 | - |
| perl | E | QNX080 | QNX080 | - |
| pistache | D | QNX080 | QNX080 | - |
| pixman | B | QNX054 | QNX054 | - |
| portaudio | E | QNX079 | QNX079 | - |
| python3 | E | QNX001, QNX002, QNX014, QNX024, QNX030, QNX042, QNX047, QNX050, QNX080 | QNX014, QNX024, QNX030, QNX042 | QNX001, QNX002, QNX047, QNX050, QNX080 |
| qt6-charts | B | QNX080 | QNX080 | - |
| qt6-datavis3d | B | QNX080 | QNX080 | - |
| qt6-graphs | B | QNX080 | QNX080 | - |
| qt6-httpserver | B | QNX080 | QNX080 | - |
| qt6-languageserver | B | QNX080 | QNX080 | - |
| qt6-location | B | QNX080 | QNX080 | - |
| qt6-lottie | B | QNX080 | QNX080 | - |
| qt6-multimedia | E | QNX075, QNX080 | QNX075, QNX080 | - |
| qt6-networkauth | B | QNX080 | QNX080 | - |
| qt6-positioning | B | QNX080 | QNX080 | - |
| qt6-quickeffectmaker | B | QNX075, QNX080 | QNX080 | QNX075 |
| qt6-quicktimeline | C | QNX080 | QNX080 | - |
| qt6-remoteobjects | B | QNX075, QNX080 | QNX080 | QNX075 |
| qt6-scxml | B | QNX080 | QNX080 | - |
| qt6-sensors | B | QNX080 | QNX080 | - |
| qt6-serialbus | D | QNX080 | QNX080 | - |
| qt6-serialport | B | QNX080 | QNX080 | - |
| qt6-shadertools | B | QNX080 | QNX080 | - |
| qt6-svg | B | QNX080 | QNX080 | - |
| qt6-tools | D | QNX080 | QNX080 | - |
| qt6-wayland | B | QNX080 | QNX080 | - |
| qt6-webchannel | B | QNX080 | QNX080 | - |
| qt6-websockets | B | QNX080 | QNX080 | - |
| ros2-jazzy | A | QNX009, QNX021 | - | QNX009, QNX021 |
| ros2-jazzy-control | A | QNX009, QNX044, QNX075 | - | QNX009, QNX044, QNX075 |
| ros2-jazzy-moveit2 | B | QNX009, QNX080 | QNX080 | QNX009 |
| ros2-jazzy-nav2 | B | QNX009, QNX075, QNX080 | QNX080 | QNX009, QNX075 |
| ruby | E | QNX054 | - | QNX054 |
| ruckig | B | QNX080 | QNX080 | - |
| s2n-tls | E | QNX053, QNX075, QNX080 | QNX053, QNX080 | QNX075 |
| sudo | E | QNX054, QNX081 | QNX054, QNX081 | - |
| svt-av1 | D | QNX054 | - | QNX054 |
| tar | E | QNX037, QNX050, QNX080, QNX081 | QNX037, QNX050, QNX081 | QNX080 |
| tdb | C | QNX080 | QNX080 | - |
| tmux | D | QNX030, QNX031, QNX042, QNX079, QNX080, QNX081 | QNX030, QNX031, QNX042, QNX079, QNX080, QNX081 | - |
| tree-sitter-cpp | A | QNX074 | - | QNX074 |
| valkey | E | QNX031, QNX053, QNX075 | QNX031, QNX053, QNX075 | - |
| vte3 | C | QNX024, QNX035 | QNX024 | QNX035 |
| wayland | E | QNX001, QNX002, QNX003, QNX004, QNX006, QNX021, QNX044, QNX046, QNX080 | QNX001, QNX002, QNX003, QNX004, QNX006, QNX021, QNX044, QNX046, QNX080 | - |
| wlroots0.20 | D | QNX002, QNX080 | QNX080 | QNX002 |
| xvidcore | D | QNX079 | QNX079 | - |
| xz | D | QNX050 | - | QNX050 |
| yaml | B | QNX079 | QNX079 | - |
| yubico-c-client | B | QNX079 | QNX079 | - |
| zeromq | D | QNX080 | - | QNX080 |
| zsh | C | QNX079, QNX081 | QNX079, QNX081 | - |
