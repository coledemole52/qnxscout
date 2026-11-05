"""The QNX 8.0 porting knowledge base.

Every rule here is backed by at least one piece of public evidence:

* ``libref:<function>``  the QNX SDP 8.0 C Library Reference page for a function
                         (presence, header, and which library provides it);
* ``guide:<page>``       the QNX Porting Guide (QNX Everywhere docs);
* ``skill:facts``        QNX's own porting knowledge, qnx/qnx-agent-skills;
* ``port:<path>``        a patch QNX engineers had to write in qnx-ports/aports;
* ``apkbuild:<path>``    an APKBUILD in qnx-ports/aports (e.g. link lines);
* ``repo:<owner/name>``  a QNX-maintained compatibility library.

"Missing" claims are deliberately conservative: a function is only reported as
missing when it is absent from the QNX 8.0 C Library Reference *and* it is a
Linux/glibc-specific interface (or a QNX port had to work around it).  Run
``qnxscout scan --sdp $QNX_TARGET`` to confirm against your installed SDP.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources

SEVERITIES = ["blocker", "runtime", "link", "review", "info"]
SEVERITY_WEIGHT = {"blocker": 10, "runtime": 6, "link": 3, "review": 2, "info": 0}
SEVERITY_LABEL = {
    "blocker": "Blocker - will not compile or link on QNX 8.0 as written",
    "runtime": "Runtime - builds, but is known to misbehave on QNX",
    "link": "Link fix - needs a QNX library or a link flag, no code change",
    "review": "Review - platform-dependent logic that needs a porting decision",
    "info": "Info - background a porter should know",
}

AP = "https://github.com/qnx-ports/aports/blob/main/"
GUIDE = "https://www.qnx.com/developers/docs/qnxeverywhere/com.qnx.doc.qpg/topic/"
LIBREF = "https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/"
SKILL = "https://github.com/qnx/qnx-agent-skills/blob/main/skills/qnx-platform-facts/SKILL.md"


@lru_cache(maxsize=1)
def libc_index() -> dict:
    """{function: [headers, library, doc page]} from the QNX 8.0 C Library Reference."""
    with resources.files("qnxscout.data").joinpath("qnx80_libc_index.json").open() as fh:
        return json.load(fh)["functions"]


def evidence_url(ref: str) -> tuple[str, str]:
    kind, _, arg = ref.partition(":")
    if kind == "libref":
        entry = libc_index().get(arg)
        page = entry[2] if entry else arg
        return f"QNX 8.0 C Library Reference: {arg}()", LIBREF + page
    if kind == "guide":
        pages = {"shim": "sysarch_Create_shim.html", "issues": "sysarch_Issues.html",
                 "ipc": "sysarch_IPC_and_resmgr.html", "about": "about.html"}
        return f"QNX Porting Guide ({arg})", GUIDE + pages.get(arg, "about.html")
    if kind == "skill":
        return "QNX agent skills: qnx-platform-facts", SKILL
    if kind == "port":
        pkg = arg.split("/")[1] if "/" in arg else arg
        return f"QNX port patch ({pkg}): {arg.rsplit('/', 1)[-1]}", AP + arg
    if kind == "apkbuild":
        pkg = arg.split("/")[1] if "/" in arg else arg
        return f"QNX port recipe ({pkg})", AP + arg
    if kind == "repo":
        return f"QNX compatibility library: {arg}", "https://github.com/" + arg
    return ref, ref


@dataclass
class Rule:
    id: str
    title: str
    severity: str
    category: str
    why: str
    fix: str
    evidence: list[str]
    calls: list[str] = field(default_factory=list)      # function-call names: name(
    words: list[str] = field(default_factory=list)      # identifiers (macros, types)
    members: list[str] = field(default_factory=list)    # struct members: .x / ->x
    headers: list[str] = field(default_factory=list)    # #include <...> paths (regex ok)
    link: str = ""                                       # library hint, e.g. "-lepoll"
    effort: str = "small"                                # trivial | small | medium | large
    guards: list[str] = field(default_factory=list)     # extra macro names that mean "already guarded"
    header_severity: str = ""                            # severity for the header include (default: severity)

    def evidence_links(self) -> list[tuple[str, str]]:
        return [evidence_url(e) for e in self.evidence]


R = Rule
RULES: list[Rule] = [
    # ---------------------------------------------------------------- Linux fd notification APIs
    R("QNX001", "epoll is not in QNX libc", "link", "linux-api",
      "QNX has no kernel epoll. QNX's own ports link a compatibility library instead "
      "(wayland, foot and python3 link -lepoll).",
      "Link the QNX epoll compatibility library (-lepoll, github.com/qnx-ports/epoll). "
      "For simple loops poll() is enough; the native QNX model is ionotify() with pulses.",
      ["skill:facts", "repo:qnx-ports/epoll", "apkbuild:extra/wayland/APKBUILD", "apkbuild:extra/foot/APKBUILD"],
      calls=["epoll_create", "epoll_create1", "epoll_ctl", "epoll_wait", "epoll_pwait", "epoll_pwait2"],
      headers=["sys/epoll.h"], link="-lepoll", effort="trivial",
      guards=["HAVE_EPOLL", "HAVE_SYS_EPOLL_H", "EPOLLIN", "USE_EPOLL"]),
    R("QNX002", "eventfd is not in QNX libc", "link", "linux-api",
      "eventfd() is a Linux kernel object; QNX's microkernel has no equivalent. The QNX Porting Guide "
      "recommends a shim, and QNX ships one (-leventfd, used by the wayland, foot and python3 ports).",
      "Link -leventfd, or replace with a pipe()/socketpair() pair for wake-ups.",
      ["guide:shim", "skill:facts", "apkbuild:extra/wayland/APKBUILD", "apkbuild:core/python3/APKBUILD"],
      calls=["eventfd", "eventfd_read", "eventfd_write"], headers=["sys/eventfd.h"],
      link="-leventfd", effort="trivial", guards=["HAVE_EVENTFD", "HAVE_SYS_EVENTFD_H", "EFD_CLOEXEC"]),
    R("QNX003", "timerfd is not in QNX libc", "link", "linux-api",
      "timerfd_*() has no direct QNX equivalent; QNX provides a shim (-ltimerfd, used by wayland and foot).",
      "Link -ltimerfd. The native QNX design is timer_create()/TimerCreate() delivering a pulse (SIGEV_PULSE).",
      ["guide:shim", "skill:facts", "apkbuild:extra/wayland/APKBUILD", "libref:timer_create"],
      calls=["timerfd_create", "timerfd_settime", "timerfd_gettime"], headers=["sys/timerfd.h"],
      link="-ltimerfd", effort="trivial", guards=["HAVE_TIMERFD", "HAVE_SYS_TIMERFD_H", "TFD_CLOEXEC"]),
    R("QNX004", "signalfd is not in QNX libc", "link", "linux-api",
      "signalfd() has no direct QNX equivalent; QNX provides a shim (-lsignalfd, used by wayland).",
      "Link -lsignalfd, or use the classic self-pipe trick / sigwaitinfo() in a dedicated thread.",
      ["guide:shim", "apkbuild:extra/wayland/APKBUILD", "port:extra/libevent/fix-qnx.patch"],
      calls=["signalfd"], headers=["sys/signalfd.h"], link="-lsignalfd", effort="trivial",
      guards=["HAVE_SIGNALFD", "HAVE_SYS_SIGNALFD_H", "SFD_CLOEXEC"]),
    R("QNX005", "inotify lives in libfsnotify, not libc", "link", "linux-api",
      "QNX 8.0 does implement inotify_init()/inotify_add_watch(), but in libfsnotify. Code that "
      "builds fine fails at link time with undefined inotify_* symbols.",
      "Add -lfsnotify to the link line (and make configure checks link it).",
      ["libref:inotify_init", "libref:inotify_add_watch"],
      calls=["inotify_init", "inotify_init1", "inotify_add_watch", "inotify_rm_watch"],
      link="-lfsnotify", effort="trivial"),
    R("QNX006", "open_memstream needs QNX's memstream library", "link", "linux-api",
      "open_memstream() is not in QNX libc; QNX ports link -lmemstream (wayland) or carry a header shim.",
      "Link -lmemstream.",
      ["apkbuild:extra/wayland/APKBUILD", "port:extra/libdisplay-info/add-qnx-memstream-header.patch"],
      calls=["open_memstream", "open_wmemstream"], link="-lmemstream", effort="trivial",
      guards=["HAVE_OPEN_MEMSTREAM"]),
    R("QNX007", "System V shared memory needs the QNX shim", "link", "linux-api",
      "shmget()/shmat()/shmdt()/shmctl() are not in QNX libc. QNX publishes libsysv-ipc-shim "
      "(core/libsysv-ipc-shim) which implements them on POSIX shared memory.",
      "Depend on libsysv-ipc-shim, or move to shm_open()+mmap() (native on QNX).",
      ["repo:qnx-ports/libsysv-ipc-shim", "apkbuild:core/libsysv-ipc-shim/APKBUILD", "libref:shm_open"],
      calls=["shmget", "shmat", "shmdt", "shmctl"], headers=["sys/shm.h"], link="libsysv-ipc-shim",
      effort="small", guards=["HAVE_SYS_SHM_H", "HAVE_SHMGET"]),
    R("QNX008", "System V semaphores/message queues are not available", "blocker", "linux-api",
      "semget()/semop()/msgget()/msgsnd() are absent from the QNX 8.0 C Library Reference, and QNX's "
      "SysV shim only covers shared memory.",
      "Use POSIX semaphores (sem_open) and message queues (mq_open), or QNX message passing.",
      ["libref:sem_open", "libref:mq_open", "repo:qnx-ports/libsysv-ipc-shim"],
      calls=["semget", "semop", "semtimedop", "semctl", "msgget", "msgsnd", "msgrcv", "msgctl"],
      headers=["sys/sem.h", "sys/msg.h"], effort="medium", guards=["HAVE_SYS_SEM_H", "HAVE_SYS_MSG_H"]),
    R("QNX009", "Thread-local locale API needs liblocale-shim", "link", "linux-api",
      "newlocale()/uselocale()/freelocale() and the *_l() variants are not in QNX libc; QNX ships "
      "liblocale-shim (core/liblocale-shim) for them.",
      "Depend on liblocale-shim, or fall back to setlocale() where thread-safety allows.",
      ["apkbuild:core/liblocale-shim/APKBUILD"],
      calls=["newlocale", "uselocale", "freelocale", "duplocale", "strtod_l", "strtof_l", "strtold_l",
             "strcoll_l", "strxfrm_l", "strftime_l", "isalpha_l", "isdigit_l", "isspace_l", "tolower_l",
             "toupper_l", "snprintf_l", "nl_langinfo_l"],
      link="liblocale-shim", effort="small", guards=["HAVE_NEWLOCALE", "HAVE_USELOCALE", "HAVE_XLOCALE_H"]),
    R("QNX010", "iconv is not part of QNX libc", "link", "linux-api",
      "glibc ships iconv in libc; QNX does not. QNX's package set provides GNU libiconv (core/libiconv).",
      "Depend on libiconv and link -liconv (most configure scripts handle this via AM_ICONV).",
      ["apkbuild:core/libiconv/APKBUILD"], calls=["iconv_open", "iconv", "iconv_close"],
      link="-liconv", effort="trivial", guards=["HAVE_ICONV", "HAVE_ICONV_H"]),
    # ---------------------------------------------------------------- missing Linux/glibc calls
    R("QNX011", "getrandom()/getentropy() are not available", "blocker", "linux-api",
      "Neither function is in the QNX 8.0 C Library Reference. The epiphany port replaced getrandom() "
      "with a read from /dev/urandom.",
      "Read /dev/urandom (QNX provides it), or use your crypto library's RNG (e.g. OpenSSL RAND_bytes).",
      ["port:extra/epiphany/001-fix-missing-function-getrandom.patch"],
      calls=["getrandom", "getentropy", "arc4random", "arc4random_buf", "arc4random_uniform"],
      headers=["sys/random.h"], effort="small",
      guards=["HAVE_GETRANDOM", "HAVE_SYS_RANDOM_H", "HAVE_GETENTROPY", "HAVE_ARC4RANDOM", "GRND_NONBLOCK"]),
    R("QNX012", "CPU affinity uses ThreadCtl() on QNX", "blocker", "linux-api",
      "sched_setaffinity()/pthread_setaffinity_np()/cpu_set_t are Linux interfaces (the onnxruntime port "
      "had to drop them). QNX sets affinity with run masks.",
      "Use ThreadCtl(_NTO_TCTL_RUNMASK, ...) or _NTO_TCTL_RUNMASK_GET_AND_SET_INHERIT for the calling thread.",
      ["libref:ThreadCtl", "port:extra/onnxruntime/0001-add-qnx-build.patch"],
      calls=["sched_setaffinity", "sched_getaffinity", "pthread_setaffinity_np", "pthread_getaffinity_np",
             "pthread_attr_setaffinity_np", "sched_getcpu"],
      words=["cpu_set_t", "CPU_SET", "CPU_ZERO", "CPU_ISSET", "CPU_COUNT"], effort="small",
      guards=["HAVE_SCHED_SETAFFINITY", "HAVE_PTHREAD_SETAFFINITY_NP", "HAVE_SCHED_GETCPU", "CPU_SETSIZE"]),
    R("QNX013", "prctl() does not exist on QNX", "blocker", "linux-api",
      "prctl() and <sys/prctl.h> are Linux-only.",
      "For PR_SET_NAME use pthread_setname_np() (QNX has it); drop PR_SET_PDEATHSIG/PR_SET_DUMPABLE logic.",
      ["libref:pthread_setname_np"], calls=["prctl"], headers=["sys/prctl.h"], effort="small",
      guards=["HAVE_PRCTL", "HAVE_SYS_PRCTL_H", "PR_SET_NAME"]),
    R("QNX014", "Raw Linux syscalls are not available", "blocker", "linux-api",
      "QNX has no Linux syscall table: syscall(), SYS_* and __NR_* do not exist. The onnxruntime and "
      "python3 ports had to replace syscall(SYS_gettid).",
      "Call the libc function instead; for thread ids QNX has gettid() in <process.h>.",
      ["libref:gettid", "port:extra/onnxruntime/0001-add-qnx-build.patch"],
      calls=["syscall"], words=["SYS_gettid", "SYS_getrandom", "SYS_futex", "SYS_membarrier",
                                "SYS_memfd_create", "SYS_pidfd_open", "__NR_gettid", "__NR_futex"],
      headers=["sys/syscall.h", "syscall.h"], effort="small", guards=["HAVE_SYSCALL", "HAVE_SYS_SYSCALL_H"]),
    R("QNX015", "Linux futex is not available", "blocker", "linux-api",
      "futex(2) is a Linux kernel interface. QNX synchronisation goes through POSIX primitives "
      "(and SyncCondvarWait/SyncMutexLock underneath).",
      "Use pthread mutexes/condition variables or C11 atomics + pthread_cond.",
      ["skill:facts"], words=["FUTEX_WAIT", "FUTEX_WAKE", "FUTEX_WAIT_PRIVATE", "FUTEX_WAKE_PRIVATE"],
      headers=["linux/futex.h"], effort="medium", guards=["HAVE_FUTEX", "HAVE_LINUX_FUTEX_H"]),
    R("QNX016", "sysinfo()/get_nprocs() are not available", "blocker", "linux-api",
      "sysinfo() and get_nprocs() are glibc/Linux-only.",
      "CPU count: sysconf(_SC_NPROCESSORS_ONLN) or _syspage_ptr->num_cpu (<sys/syspage.h>). "
      "Memory: see QNX016-related note on _SC_PHYS_PAGES.",
      ["libref:SYSPAGE_ENTRY", "port:extra/openblas/0001-add-qnx-build.patch"],
      calls=["sysinfo", "get_nprocs", "get_nprocs_conf", "get_phys_pages", "get_avphys_pages"],
      headers=["sys/sysinfo.h"], effort="small", guards=["HAVE_SYSINFO", "HAVE_SYS_SYSINFO_H", "HAVE_GET_NPROCS"]),
    R("QNX017", "sysconf(_SC_PHYS_PAGES) returns -1 on QNX", "runtime", "runtime",
      "QNX engineers confirmed sysconf(_SC_PHYS_PAGES) returns -1 on QNX 8.0, so memory-sizing code "
      "silently gets a negative or zero total (llama.cpp and WebKit needed QNX paths).",
      "Read total memory from /proc/vm/stats or the memory manager (see the WebKit port); treat -1 as unknown.",
      ["skill:facts", "port:extra/llama.cpp/0003-qnx-platform-compat.patch",
       "port:extra/webkit2gtk-4.1/013-add-qnx-memory-pressure-monitor.patch"],
      words=["_SC_PHYS_PAGES", "_SC_AVPHYS_PAGES"], effort="small"),
    R("QNX018", "execinfo backtrace() is not available", "blocker", "linux-api",
      "backtrace()/backtrace_symbols() and <execinfo.h> are glibc extensions (g3log, onnxruntime and "
      "s2n-tls ports had to disable them).",
      "Guard with a feature check, or unwind with _Unwind_Backtrace() from libgcc_s.",
      ["port:extra/g3log/g3log-2.6_qnx.patch", "port:extra/s2n-tls/0001-add-qnx-build.patch"],
      calls=["backtrace", "backtrace_symbols", "backtrace_symbols_fd"], headers=["execinfo.h"],
      effort="small", guards=["HAVE_EXECINFO_H", "HAVE_BACKTRACE", "HAVE_BACKTRACE_SYMBOLS", "S2N_STACKTRACE"]),
    R("QNX019", "statfs() is Linux/BSD-only; use statvfs()", "blocker", "linux-api",
      "statfs()/fstatfs() and <sys/vfs.h>/<sys/statfs.h> are not in QNX 8.0 (the bazel port switched).",
      "Use statvfs()/fstatvfs(), which QNX implements (POSIX).",
      ["libref:statvfs", "port:extra/bazel6/qnx.patch"], calls=["statfs", "fstatfs", "statfs64", "fstatfs64"],
      headers=["sys/vfs.h", "sys/statfs.h"], effort="small",
      guards=["HAVE_STATFS", "HAVE_SYS_VFS_H", "HAVE_SYS_STATFS_H", "HAVE_FSTATFS"]),
    R("QNX020", "mntent API is not available", "blocker", "linux-api",
      "getmntent()/setmntent() and <mntent.h> are glibc-specific.",
      "Enumerate mounts via /proc/mount on QNX or drop the feature on QNX.",
      ["skill:facts"], calls=["getmntent", "setmntent", "endmntent", "getmntent_r", "addmntent", "hasmntopt"],
      headers=["mntent.h"], effort="medium", guards=["HAVE_MNTENT_H", "HAVE_GETMNTENT", "HAVE_SETMNTENT"]),
    R("QNX021", "GNU string/sort extensions are missing", "blocker", "linux-api",
      "These GNU extensions are not in QNX libc (the wayland and ros2 ports had to supply memrchr()).",
      "Provide a small fallback implementation (gnulib has portable versions) behind a configure check.",
      ["port:extra/wayland/0001-fix-missing-symbols-and-headers.patch", "port:extra/ros2-jazzy/rcutils.patch"],
      calls=["strchrnul", "memrchr", "mempcpy", "wmempcpy", "rawmemchr", "strverscmp", "versionsort",
             "qsort_r", "explicit_bzero", "strerrordesc_np", "strerrorname_np", "sigabbrev_np",
             "sigdescr_np", "canonicalize_file_name", "get_current_dir_name", "euidaccess", "eaccess"],
      effort="small"),
    R("QNX022", "glibc error()/program_invocation_name are missing", "blocker", "linux-api",
      "error()/error_at_line() (<error.h>) and program_invocation_name are glibc-only.",
      "Use err()/warn() from <err.h> (QNX has them) and getprogname()/_cmdname().",
      ["libref:err", "libref:getprogname", "port:extra/gnutls/fix-qnx.patch"],
      calls=["error", "error_at_line", "gnu_get_libc_version", "gnu_get_libc_release"],
      words=["program_invocation_name", "program_invocation_short_name"],
      headers=["error.h", "gnu/libc-version.h"], effort="small",
      guards=["HAVE_ERROR_H", "HAVE_ERROR", "HAVE_PROGRAM_INVOCATION_NAME"]),
    R("QNX023", "glibc-only process/thread helpers are missing", "blocker", "linux-api",
      "These glibc/Linux helpers are absent from the QNX 8.0 C Library Reference.",
      "pthread_tryjoin_np/timedjoin_np: use a condition variable or pthread_join in a helper thread; "
      "setresuid/getresuid: use setreuid/seteuid; getauxval: QNX exposes CPU info via the system page; "
      "malloc_trim: drop on QNX; getloadavg: not available (the colcon port stubs it).",
      ["port:extra/python3-colcon-common-extensions/0000-colcon-cmake-getloadavg.patch", "libref:SYSPAGE_ENTRY"],
      calls=["pthread_tryjoin_np", "pthread_timedjoin_np", "setresuid", "getresuid", "setresgid",
             "getresgid", "getauxval", "malloc_trim", "getloadavg", "setproctitle", "pidfd_open",
             "pidfd_send_signal", "clone", "clone3", "unshare", "setns", "personality"],
      headers=["sys/auxv.h", "sys/personality.h", "sys/fsuid.h"], effort="small",
      guards=["HAVE_GETAUXVAL", "HAVE_SYS_AUXV_H", "HAVE_MALLOC_TRIM", "HAVE_GETLOADAVG", "HAVE_SETRESUID",
              "HAVE_PTHREAD_TRYJOIN_NP", "HAVE_PTHREAD_TIMEDJOIN_NP"]),
    R("QNX024", "Linux file-I/O extensions are missing", "blocker", "linux-api",
      "These Linux-specific file calls are not in QNX 8.0.",
      "fallocate -> posix_fallocate; futimes/lutimes -> futimens/utimensat; syncfs -> fsync/sync; "
      "madvise -> posix_madvise; dup3 -> dup2 + fcntl(FD_CLOEXEC); splice/sendfile/copy_file_range -> "
      "read/write loop; renameat2 -> renameat; memfd_create -> shm_open(SHM_ANON).",
      ["libref:posix_fallocate", "libref:utimensat", "libref:posix_madvise", "libref:shm_open", "port:extra/gnutls/skip-ktls.patch"],
      calls=["fallocate", "futimes", "lutimes", "syncfs", "madvise", "mremap", "dup3", "splice", "tee",
             "vmsplice", "sendfile", "sendfile64", "copy_file_range", "renameat2", "memfd_create",
             "readahead", "sync_file_range", "name_to_handle_at", "open_by_handle_at", "statx",
             "closefrom", "close_range", "fdwalk"],
      words=["MAP_POPULATE", "MAP_NORESERVE", "MADV_DONTNEED", "MADV_FREE", "MREMAP_MAYMOVE", "O_TMPFILE",
             "O_PATH"],
      headers=["sys/sendfile.h"], effort="small",
      guards=["HAVE_FALLOCATE", "HAVE_FUTIMES", "HAVE_LUTIMES", "HAVE_SYNCFS", "HAVE_MADVISE", "HAVE_DUP3",
              "HAVE_SPLICE", "HAVE_SENDFILE", "HAVE_SYS_SENDFILE_H", "HAVE_COPY_FILE_RANGE", "HAVE_RENAMEAT2",
              "HAVE_MEMFD_CREATE", "HAVE_STATX", "HAVE_CLOSEFROM", "HAVE_CLOSE_RANGE", "HAVE_FDWALK",
              "HAVE_MREMAP", "HAVE_READAHEAD"]),
    R("QNX025", "ucontext coroutine API is not available", "blocker", "linux-api",
      "getcontext()/makecontext()/swapcontext() are not in QNX 8.0 (the capnproto port disabled fibers).",
      "Disable the ucontext backend on QNX, or use threads / a hand-written context switch.",
      ["port:extra/capnproto/0001-add-qnx-build.patch"],
      calls=["getcontext", "setcontext", "makecontext", "swapcontext"], effort="medium",
      guards=["HAVE_UCONTEXT_H", "HAVE_GETCONTEXT", "HAVE_MAKECONTEXT", "KJ_USE_FIBERS"]),
    R("QNX026", "Linux mcontext register layout does not apply", "blocker", "linux-api",
      "Code that reads uc_mcontext.gregs[REG_RIP] (crash handlers, profilers, GC) uses the Linux "
      "layout. QNX's mcontext_t is different (abseil and WebKit needed QNX code paths).",
      "Add a __QNX__ branch reading the QNX register context (see the WebKit/abseil patches).",
      ["port:extra/abseil-cpp/0002-abseil.patch", "port:extra/webkit2gtk-4.1/001-add_mcontext_support.patch"],
      words=["REG_RIP", "REG_EIP", "REG_RSP", "REG_RBP", "REG_PC"], members=["gregs", "__gregs"],
      effort="small"),
    # ---------------------------------------------------------------- macros / types / members
    R("QNX030", "SA_RESTART is not defined on QNX", "blocker", "posix-gap",
      "QNX 8.0 does not define SA_RESTART; five QNX ports (libevent, tmux, tftp-hpa, chrony, python3) "
      "add '#define SA_RESTART 0'.",
      "Guard it: #ifndef SA_RESTART / #define SA_RESTART 0 / #endif, and make sure the code retries on EINTR.",
      ["port:extra/libevent/fix-qnx.patch", "port:extra/tmux/qnx-compat.patch", "port:extra/tftp-hpa/qnx-sa-restart.patch"],
      words=["SA_RESTART"], effort="trivial"),
    R("QNX031", "IOV_MAX is not defined on QNX", "blocker", "posix-gap",
      "QNX 8.0 does not define IOV_MAX (tmux, valkey, capnproto and libuv ports had to supply it).",
      "Use UIO_MAXIOV from <sys/uio.h> (what the tmux port does) or a 1024 fallback.",
      ["port:extra/tmux/qnx-compat.patch", "port:extra/valkey/fix-IOV_MAX.patch", "port:extra/capnproto/0001-add-qnx-build.patch"],
      words=["IOV_MAX"], effort="trivial"),
    R("QNX032", "struct dirent has no d_type on QNX", "blocker", "posix-gap",
      "QNX's struct dirent does not carry d_type/DT_* (the tflite-runtime and bazel ports switched to stat).",
      "Call fstatat(dirfd(dir), ent->d_name, &st, AT_SYMLINK_NOFOLLOW) and test S_ISDIR()/S_ISREG().",
      ["port:extra/tflite-runtime/qnx-dirent.patch", "port:extra/bazel6/qnx.patch"],
      words=["DT_DIR", "DT_REG", "DT_LNK", "DT_UNKNOWN", "DT_FIFO", "DT_SOCK", "DT_CHR", "DT_BLK"],
      members=["d_type"], effort="small",
      guards=["HAVE_STRUCT_DIRENT_D_TYPE", "HAVE_DIRENT_D_TYPE", "_DIRENT_HAVE_D_TYPE", "HAVE_D_TYPE"]),
    R("QNX033", "sig_t/sighandler_t are not defined on QNX", "blocker", "posix-gap",
      "QNX does not define the BSD sig_t or glibc sighandler_t typedefs (abseil, vala and gdb ports).",
      "Declare your own: typedef void (*sighandler_fn)(int);",
      ["port:extra/abseil-cpp/0001-qnx-sig-t.patch", "port:extra/vala/0001-posix-Define-_XOPEN_SOURCE-_GNU_SOURCE-for-signal-fu.patch"],
      words=["sig_t", "sighandler_t", "__sighandler_t"], effort="trivial"),
    R("QNX034", "W_EXITCODE is not defined on QNX", "blocker", "posix-gap",
      "W_EXITCODE() is a glibc/BSD convenience macro (the vte3 port defines it).",
      "#define W_EXITCODE(ret, sig) ((ret) << 8 | (sig))",
      ["port:extra/vte3/fix-W_EXITCODE.patch"], words=["W_EXITCODE"], effort="trivial"),
    R("QNX035", "TIOCSCTTY/TIOCPKT terminal ioctls are unsupported", "blocker", "posix-gap",
      "The vte3 and emacs ports had to disable TIOCSCTTY and TIOCPKT on QNX.",
      "On QNX the controlling terminal is acquired by opening the pty after setsid(); drop TIOCPKT mode.",
      ["port:extra/vte3/0004-disable-TIOCSCTTY-on-QNX.patch", "port:extra/vte3/0002-disable-TIOCPKT-on-QNX.patch",
       "port:extra/emacs/fix-qnx-pty-shell.patch"],
      words=["TIOCSCTTY", "TIOCPKT"], effort="small"),
    R("QNX036", "SO_PEERCRED/struct ucred are Linux-only", "blocker", "posix-gap",
      "QNX's socket stack follows BSD conventions; the dbus and glib ports switched to the FreeBSD "
      "credential code paths.",
      "Use the project's FreeBSD branch (LOCAL_PEERCRED / getpeereid style) for QNX.",
      ["port:extra/dbus/add-freebsd-cred.patch", "port:extra/glib/use-freebsd-gcred.patch"],
      words=["SO_PEERCRED", "SCM_CREDENTIALS", "SO_PASSCRED"], effort="small"),
    R("QNX037", "makedev() takes three arguments on QNX", "blocker", "posix-gap",
      "QNX's makedev(node, major, minor) has an extra node argument (the tar port passes 0); "
      "<sys/sysmacros.h> does not exist.",
      "Call makedev(0, major, minor) under #ifdef __QNX__.",
      ["port:core/tar/fix-qnx-makedev.patch", "port:extra/libuuid/00-qnx-build.patch"],
      headers=["sys/sysmacros.h"], effort="trivial"),  # 2-argument calls detected in rules_c
    R("QNX038", "glibc byte-order headers are not available", "blocker", "posix-gap",
      "<endian.h>/<byteswap.h> and htole32()/bswap_32() are glibc headers; five QNX ports "
      "(sentencepiece, openexr, libfyaml, chrpath, neovim) needed replacements.",
      "On QNX include <sys/param.h> for BYTE_ORDER (fakeroot port) or <gulliver.h> for ENDIAN_LE32()/"
      "ENDIAN_BE64(); __builtin_bswap32() works with the QNX compilers.",
      ["port:extra/sentencepiece/qnx-no-endian_h.patch", "port:extra/openexr/add-qnx-endian.patch",
       "port:core/fakeroot/fix-qnx.patch", "libref:ENDIAN_LE32"],
      calls=["bswap_16", "bswap_32", "bswap_64", "htole16", "htole32", "htole64", "le16toh", "le32toh",
             "le64toh", "htobe16", "htobe32", "htobe64", "be16toh", "be32toh", "be64toh"],
      headers=["endian.h", "byteswap.h"], effort="small",
      guards=["HAVE_ENDIAN_H", "HAVE_BYTESWAP_H", "HAVE_BSWAP_32", "HAVE_HTOLE32", "HAVE_LE32TOH"]),
    # ---------------------------------------------------------------- header location differences
    R("QNX040", "<elf.h> is <sys/elf.h> on QNX", "blocker", "header",
      "QNX ships the ELF definitions as <sys/elf.h> (the chrpath port).",
      "#ifdef __QNX__ / #include <sys/elf.h> / #else / #include <elf.h> / #endif",
      ["port:extra/chrpath/sys-elf.patch"], headers=["elf.h"], effort="trivial",
      guards=["HAVE_ELF_H"]),
    R("QNX041", "<sys/syslimits.h> does not exist; PATH_MAX is in <limits.h>", "blocker", "header",
      "QNX defines PATH_MAX in <limits.h>; code that includes the BSD/macOS <sys/syslimits.h> fails.",
      "Include <limits.h> on QNX.",
      ["skill:facts", "port:extra/llama.cpp/0003-qnx-platform-compat.patch"], headers=["sys/syslimits.h"],
      effort="trivial"),
    R("QNX042", "forkpty/openpty live in <unix.h> on QNX", "blocker", "header",
      "QNX implements forkpty()/openpty()/login_tty() in libc but declares them in <unix.h>, not "
      "<pty.h>/<util.h>/<libutil.h>, and there is no libutil (see QNX052).",
      "#ifdef __QNX__ / #include <unix.h> (the neovim port does exactly this).",
      ["libref:forkpty", "libref:openpty", "port:extra/neovim/qnx-forkpty.patch"],
      headers=["pty.h", "util.h", "libutil.h"], effort="trivial", guards=["HAVE_PTY_H", "HAVE_UTIL_H", "HAVE_LIBUTIL_H"]),
    R("QNX048", "SocketCAN: use QNX's io-sock SocketCAN", "link", "header",
      "QNX implements Linux SocketCAN (AF_CAN, CAN_RAW) as an io-sock module. Its can-utils port builds "
      "can-utils with no source changes, only a few thunk headers (linux/can.h, linux/sockios.h, "
      "linux/types.h, ...) that map to QNX's definitions. CAN_BCM is not supported. The project is marked "
      "Experimental by QNX.",
      "Build against github.com/qnx/socketcan: add its apps/can-utils/include directory to the include path and "
      "load the SocketCAN io-sock module on the target.",
      ["repo:qnx/socketcan"], headers=[r"linux/can\.h", r"linux/can/.+"], link="qnx/socketcan", effort="small"),
    R("QNX043", "Linux kernel headers are not available", "blocker", "header",
      "<linux/...> and <asm/...> are Linux kernel UAPI headers; nothing equivalent exists on QNX.",
      "Isolate the Linux-only feature behind #ifdef __linux__ and provide a QNX (or generic POSIX) path.",
      ["skill:facts"], headers=[r"linux/.+", r"asm/.+", r"asm-generic/.+"], effort="medium",
      guards=["HAVE_LINUX_.*"]),
    R("QNX044", "glibc-internal / Linux-only system headers", "blocker", "header",
      "These headers are glibc- or Linux-specific and do not exist in the QNX SDP.",
      "<features.h>: a glibc-internal header, drop it; <sys/io.h>: use <hw/inout.h> (in8/out8); "
      "<sys/ptrace.h>: QNX debugs via /proc (devctl DCMD_PROC_*); others: guard the feature.",
      ["libref:in8", "skill:facts"],
      headers=["features.h", "sys/io.h", "sys/ptrace.h", "sys/user.h", "sys/reg.h", "sys/klog.h",
               "sys/fanotify.h", "sys/capability.h", "sys/inotify_ext.h__never", "netpacket/packet.h",
               "sys/kd.h", "sys/vt.h", "sys/swap.h", "sys/quota.h", "sys/timex.h", "sys/xattr.h",
               "attr/xattr.h", "sys/epoll_ext.h__never"],
      effort="medium",
      guards=["HAVE_FEATURES_H", "HAVE_SYS_IO_H", "HAVE_SYS_PTRACE_H", "HAVE_SYS_XATTR_H", "HAVE_SYS_CAPABILITY_H"]),
    R("QNX045", "select() needs <sys/select.h> on QNX", "review", "header",
      "On QNX, select()/fd_set are declared in <sys/select.h> and are not pulled in by <sys/time.h> "
      "the way glibc does (the libassuan port had to add the include).",
      "Include <sys/select.h> explicitly in files that use select()/fd_set.",
      ["port:extra/libassuan/0001-qnx-include-sys-select.patch", "libref:pselect"], effort="trivial"),
    R("QNX046", "flock() is in <fcntl.h> and does not survive fork() on QNX", "runtime", "runtime",
      "QNX declares flock() in <fcntl.h>. More importantly, a fork() drops the parent's flock(), so lock "
      "files used to detect a running instance stop working (the wayland port switched to lockf()).",
      "For lock files held across fork()/daemon(), use lockf() or fcntl(F_SETLK) record locks.",
      ["libref:flock", "port:extra/wayland/0003-qnx-flock.patch"], effort="small"),
    R("QNX047", "gettid() is declared in <process.h> on QNX", "blocker", "header",
      "QNX has gettid(), but declares it in <process.h> (glibc uses <unistd.h>). Without the include the "
      "call is an implicit declaration, which current compilers reject.",
      "#ifdef __QNX__ / #include <process.h> / #endif",
      ["libref:gettid"], effort="trivial"),
    # ---------------------------------------------------------------- runtime pitfalls
    R("QNX050", "Directory fds must be opened with O_DIRECTORY", "runtime", "runtime",
      "On QNX a descriptor that will be used as a directory (openat()/fdopendir()/fchdir()/*at()) must "
      "be opened with O_DIRECTORY. Nine QNX ports (tar, xz, diffutils, capnproto, python3, ...) fixed this.",
      "Add O_DIRECTORY to the open() flags when the target is a directory. Note: on QNX fsync() on an "
      "O_DIRECTORY descriptor fails (see the xz port).",
      ["guide:issues", "skill:facts", "port:core/tar/dir_open.patch", "port:extra/capnproto/0001-add-qnx-build.patch",
       "port:core/xz/fix-qnx.patch"], effort="small"),
    R("QNX051", "/proc and /sys paths differ on QNX", "review", "runtime",
      "QNX has a /proc filesystem, but not Linux's layout: /proc/self/exe, /proc/meminfo, "
      "/proc/cpuinfo, /proc/self/maps and /sys do not exist (protobuf, libuv, gdb, webkit ports).",
      "Executable path: _cmdname() (what the protobuf port uses); CPU count: _syspage_ptr->num_cpu; "
      "memory: /proc/vm/stats; keep the Linux path behind #ifdef __linux__.",
      ["libref:_cmdname", "port:extra/protobuf/0001-qnx-fix-protoc-abs-path.patch",
       "port:extra/webkit2gtk-4.1/002-add-exe-path-support.patch"], effort="small"),
    R("QNX052", "printf(\"%s\", NULL) crashes on QNX", "runtime", "runtime",
      "glibc prints \"(null)\" for a NULL %s argument; QNX's libc dereferences it. glib, json-glib, "
      "libxcrypt and libsndfile all needed patches. Code or tests that expect \"(null)\" will crash or fail.",
      "Guard NULL strings before formatting (x ? x : \"(null)\").",
      ["port:extra/glib/fix-printf-null-segfault.patch", "port:extra/json-glib/fix-printf-null.patch",
       "port:core/libxcrypt/printf-null.patch"], effort="small"),
    R("QNX053", "Bare _XOPEN_SOURCE hides QNX APIs", "review", "build",
      "QNX headers honour feature-test macros strictly: '#define _XOPEN_SOURCE' with no value (or an old "
      "value) hides interfaces the code then uses. Nine QNX ports (jq, gthumb, ccache, vte3, libvterm, vala, "
      "valkey, s2n-tls, gawk) changed these defines.",
      "Use _XOPEN_SOURCE 700 / _POSIX_C_SOURCE 200809L, or skip the define on QNX; add _QNX_SOURCE for QNX extensions.",
      ["skill:facts", "port:extra/jq/undef_xopen_source.patch", "port:extra/gthumb/002-fix-xopen-source.patch",
       "port:extra/ccache/remove-xopen-source-defines.patch"], effort="trivial"),
    R("QNX054", "Large stack buffers overflow QNX's default stack", "runtime", "runtime",
      "QNX binaries get a much smaller default stack than Linux's 8 MB; large local arrays that are fine "
      "on Linux segfault on QNX (QNX Porting Guide).",
      "Link with -Wl,-z,stack-size=8388608 as the QNX guide shows, size thread stacks explicitly, or move "
      "the buffer to the heap.",
      ["guide:issues", "skill:facts"], effort="trivial"),
    R("QNX055", "mlock()/mlockall() need a process ability on QNX", "runtime", "runtime",
      "Locking memory needs PROCMGR_AID_MEM_LOCK on QNX; unprivileged calls fail (the libgcrypt port "
      "turned mlock into a no-op).",
      "Treat failure as non-fatal, or grant the ability with procmgr_ability().",
      ["port:extra/libgcrypt/0001-qnx-mlock-noop.patch", "libref:procmgr_ability"],
      calls=["mlock", "mlockall"], effort="trivial"),
    R("QNX056", "Prefer posix_spawn() over fork()+exec on QNX", "info", "runtime",
      "QNX supports fork(), but spawn is the native, cheaper path and avoids fork-safety deadlocks in "
      "threaded programs (the epiphany port switched to posix_spawn).",
      "Use posix_spawn()/posix_spawnp() where the child immediately execs.",
      ["skill:facts", "port:extra/epiphany/003-use-posix-spawn-for-fork-safety.patch", "libref:posix_spawn"],
      effort="small"),
    R("QNX057", "vfork() is not documented for QNX 8.0", "review", "linux-api",
      "vfork() is absent from the QNX 8.0 C Library Reference (fakeroot and gdb ports touched it).",
      "Use posix_spawn() or fork().",
      ["libref:posix_spawn", "port:core/fakeroot/fix-qnx.patch"], calls=["vfork"], effort="trivial",
      guards=["HAVE_VFORK", "HAVE_WORKING_VFORK"]),
    # ---------------------------------------------------------------- platform dispatch (preprocessor)
    R("QNX060", "#error is reachable when compiling for QNX", "blocker", "platform",
      "QNX is not one of the platforms this #if chain recognises, so the compiler reaches the #error. "
      "This is the most common first failure when porting (capnproto, chrony, fakeroot ports).",
      "Add a '#elif defined(__QNX__)' branch; QNX is POSIX, so the BSD or generic-POSIX branch is usually right.",
      ["port:extra/chrony/01-sys-c.patch", "port:extra/capnproto/0001-add-qnx-build.patch", "port:core/fakeroot/fix-qnx.patch"],
      effort="small"),
    R("QNX061", "QNX falls into the Windows branch", "blocker", "platform",
      "The #if chain only recognises Linux/macOS/BSD as POSIX, so QNX compiles the Windows (#else) code path.",
      "Test for POSIX (defined(__unix__) || defined(__QNX__)) instead of listing Unix flavours.",
      ["skill:facts"], effort="small"),
    R("QNX062", "No QNX branch in a platform #if chain", "review", "platform",
      "This chain has branches for specific platforms (Linux, macOS, BSD, ...) but none matches QNX and "
      "there is no #else, so QNX silently gets none of these definitions.",
      "Add a '#elif defined(__QNX__)' branch, usually by reusing the generic POSIX/BSD implementation.",
      ["port:extra/chrony/01-sys-c.patch", "skill:facts"], effort="small"),
    R("QNX063", "Per-OS source files have no QNX variant", "review", "platform",
      "The project keeps one implementation file per operating system (e.g. osdep-linux.c, "
      "osdep-freebsd.c) and the build picks one by host OS. There is no QNX variant, so the QNX build "
      "falls back to a generic file if one exists, or fails to link.",
      "Add a QNX variant, usually by starting from the FreeBSD or generic/unknown implementation, and teach "
      "the build to select it for QNX.",
      ["port:extra/chrony/01-sys-c.patch", "port:extra/tmux/qnx-compat.patch"], effort="medium"),
    # ---------------------------------------------------------------- build systems
    R("QNX070", "Linking libpthread: QNX has no separate pthread library", "blocker", "build",
      "Threads are part of QNX libc; an explicit -lpthread / 'pthread' link item fails "
      "(the svt-av1 port removed it).",
      "Use -pthread or CMake's Threads::Threads (find_package(Threads)), or drop the library on QNX.",
      ["port:extra/svt-av1/do-not-link-libpthread.patch", "port:extra/valkey/fix-IOV_MAX.patch"], effort="trivial"),
    R("QNX071", "Linking libdl: dlopen() is in QNX libc", "blocker", "build",
      "There is no libdl on QNX; dlopen()/dlsym() are in libc (the g3log and datefudge ports dropped -ldl).",
      "Use ${CMAKE_DL_LIBS} (empty on QNX) or drop -ldl on QNX.",
      ["port:extra/g3log/g3log-2.6_qnx.patch", "port:extra/datefudge/fix-qnx.patch"], effort="trivial"),
    R("QNX072", "Linking libutil: forkpty() is in QNX libc", "blocker", "build",
      "QNX has no libutil; forkpty()/openpty() are in libc (the neovim port skips the util library).",
      "Do not link util on QNX; include <unix.h> instead of <pty.h>.",
      ["port:extra/neovim/qnx-remove-util.patch", "libref:forkpty"], effort="trivial"),
    R("QNX073", "Linking librt", "review", "build",
      "On QNX the POSIX realtime functions (clock_gettime, timer_create, shm_open, mq_open) are in libc; "
      "check whether an explicit -lrt is needed or resolves at all on your target.",
      "Prefer a link check (CheckLibraryExists / AC_SEARCH_LIBS) over a hard-coded -lrt.",
      ["libref:clock_gettime", "libref:timer_create"], effort="trivial"),
    R("QNX074", "C90 language standard: QNX headers require C99", "blocker", "build",
      "QNX system headers use the C99 'inline' keyword; any translation unit compiled with -std=c90/c89/"
      "gnu89 fails on the first #include <stdlib.h> with \"unknown type name 'inline'\".",
      "Build with -std=c99 or newer (CMake: -DCMAKE_C_STANDARD=99 often works without a patch).",
      ["skill:facts", "port:extra/cJSON/00-c99.patch", "port:extra/opusfile/c89.patch"], effort="trivial"),
    R("QNX075", "Linux-only branch in the build system", "review", "build",
      "QNX does not enter this Linux-specific build branch (CMAKE_SYSTEM_NAME is \"QNX\", Meson's system "
      "is 'qnx'). Sources, libraries or definitions it sets up may be missing on QNX. This is the "
      "single most common thing QNX ports patch (22 packages patch CMAKE_SYSTEM_NAME checks).",
      "Add a QNX case (CMake: if(QNX) / CMAKE_SYSTEM_NAME STREQUAL \"QNX\"), usually sharing the "
      "generic UNIX or FreeBSD settings.",
      ["port:extra/aws-c-common/0001-add-qnx-build.patch", "port:extra/xnnpack/001-system-name.patch",
       "port:extra/mimalloc/0001-add-qnx-build.patch"], effort="small"),
    R("QNX076", "Build stops with a fatal error on QNX", "blocker", "build",
      "With the QNX platform model this FATAL_ERROR/error() is reached: the project refuses to configure "
      "for an unknown OS.",
      "Add QNX to the supported-platform list (it usually behaves like FreeBSD/generic UNIX).",
      ["port:extra/aws-c-io/0001-add-qnx-build.patch", "port:extra/onnxruntime/0001-add-qnx-build.patch"],
      effort="small"),
    R("QNX077", "Architecture detection via CMAKE_SYSTEM_PROCESSOR", "review", "build",
      "On the self-hosted QNX toolchain CMAKE_SYSTEM_PROCESSOR is 'unknown', and QNX names 64-bit ARM "
      "'aarch64le', so exact matches on \"aarch64\"/\"x86_64\" select the wrong (or no) SIMD code. "
      "Seven QNX ports patched this.",
      "Match QNX names too (aarch64le, x86_64) and fall back to `uname -m` (x86pc) on self-hosted builds.",
      ["skill:facts", "port:extra/xnnpack/002-system-processor.patch",
       "port:extra/libjpeg-turbo/allow-aarch64le-as-aarch64.patch"], effort="small"),
    R("QNX078", "-fsplit-stack is not supported", "blocker", "build",
      "The QNX toolchain cannot build split (growing) stacks.",
      "Remove -fsplit-stack and size stacks explicitly (-Wl,-z,stack-size=...).",
      ["guide:issues", "skill:facts"], effort="trivial"),
    R("QNX079", "Stale config.sub/config.guess", "review", "build",
      "Old autotools helper scripts may reject or mis-parse the QNX 8 host triplet (nto-qnx8.0.0). "
      "Refreshing them is routine for QNX ports: 30 QNX APKBUILDs call update_config_sub.",
      "Refresh config.sub/config.guess (abuild's update_config_sub, or autoreconf -fi).",
      ["apkbuild:core/flex/APKBUILD", "apkbuild:extra/fftw/APKBUILD", "port:core/binutils/0008.patch"],
      effort="trivial"),
    R("QNX080", "Sockets live in libsocket", "link", "build",
      "QNX keeps the BSD socket API in libsocket, not libc. The code uses sockets but the build does not link "
      "socket explicitly, so linking can fail with undefined socket()/connect()/getaddrinfo(). QNX's recipes add "
      "-lsocket even for projects whose configure searches for it (bash, python3, glib, dbus, exiv2, valkey).",
      "Link -lsocket on QNX (QNX recipes pass it through LDFLAGS, e.g. LDFLAGS=\"$LDFLAGS -lsocket\").",
      ["skill:facts", "port:extra/exiv2/003-add-socket-linker-flags.patch",
       "port:extra/gcr/set-_XOPEN_SOURCE-a-vlaue-and-link-libsocket.patch", "apkbuild:extra/glib/APKBUILD",
       "apkbuild:core/python3/APKBUILD"], effort="trivial"),
    R("QNX081", "POSIX regex lives in libregex", "link", "build",
      "QNX keeps regcomp()/regexec() in libregex, not libc (QNX 8.0 C Library Reference).",
      "Link -lregex on QNX (QNX recipes pass it through LDFLAGS).",
      ["libref:regcomp", "skill:facts"], effort="trivial"),
    R("QNX082", "crypt() lives in liblogin", "link", "build",
      "QNX provides crypt() in liblogin.",
      "Add -llogin on QNX.",
      ["libref:crypt"], effort="trivial"),
]

RULES_BY_ID = {r.id: r for r in RULES}

# Functions QNX provides in libc but declares in a different header than glibc.
QNX_HEADER_HOME = {
    "forkpty": ("unix.h", "QNX042"), "openpty": ("unix.h", "QNX042"), "login_tty": ("unix.h", "QNX042"),
    "gettid": ("process.h", "QNX047"),
}

# Library-provided APIs: for project-level "is it linked?" checks.
#   rule id -> (names that indicate use, regex that indicates the build links it)
LINK_CHECKS = {
    "QNX080": (["socket", "connect", "bind", "listen", "accept", "getaddrinfo", "freeaddrinfo",
                "gethostbyname", "getnameinfo", "inet_ntop", "inet_pton", "inet_addr", "inet_ntoa",
                "setsockopt", "getsockopt", "recvfrom", "sendto", "recvmsg", "sendmsg", "socketpair",
                "getpeername", "getsockname", "if_nametoindex", "getifaddrs"], "socket"),
    "QNX081": (["regcomp", "regexec", "regfree", "regerror"], "regex"),
    "QNX082": (["crypt"], "login"),
}


def build_links(lib: str, blob: str, explicit_only: bool = False) -> bool:
    """Does the build text link library ``lib``?

    explicit_only: only count unconditional link items (-lsocket, target_link_libraries(... socket));
    otherwise configure-style searches (AC_SEARCH_LIBS, find_library, check_library_exists) count too.
    """
    L = re.escape(lib)
    explicit = (r"-l\s*" + L + r"\b|(?:target_)?link_libraries\([^)]*\b" + L + r"\b(?![./_])"
                r"|list\(\s*APPEND\s+\w*(?:LIB|LINK)\w*[^)]*\b" + L + r"\b(?![./_])")
    searched = (r"|['\"]" + L + r"['\"]|\blib" + L + r"\b(?![./])"
                r"|AC_(?:SEARCH|CHECK)_LIBS?\(\s*\[?\w+\]?\s*,\s*\[?[^)]*\b" + L + r"\b"
                r"|find_library\([^)]*\b" + L + r"\b|check_library_exists\(\s*" + L + r"\b"
                r"|find_library\(\s*'" + L + r"'")
    rx = explicit if explicit_only else explicit + searched
    return re.search(rx, blob, re.I) is not None

# ----------------------------------------------------------------------------- target model
# What the QNX 8.0 compilers predefine (qcc/gcc 12 and clang), and what they don't.
TARGET_DEFINED = {
    "__QNX__": 1, "__QNXNTO__": 1, "__unix__": 1, "__unix": 1, "__ELF__": 1,
    "_LP64": 1, "__LP64__": 1, "__STDC__": 1, "__GNUC__": 12, "__GNUC_MINOR__": 2,
    "__CHAR_BIT__": 8, "__SIZEOF_POINTER__": 8, "__SIZEOF_LONG__": 8, "__SIZEOF_INT__": 4,
    "__SIZEOF_LONG_LONG__": 8, "__SIZEOF_SHORT__": 2, "__SIZEOF_SIZE_T__": 8,
    "__ORDER_LITTLE_ENDIAN__": 1234, "__ORDER_BIG_ENDIAN__": 4321, "__ORDER_PDP_ENDIAN__": 3412,
    "__BYTE_ORDER__": 1234, "__LITTLEENDIAN__": 1,
    "_POSIX_THREADS": 1,
}
TARGET_UNDEFINED = set("""
__linux__ __linux linux __gnu_linux__ __ANDROID__ ANDROID __ANDROID_API__
__APPLE__ __MACH__ __OSX__ TARGET_OS_IPHONE TARGET_OS_MAC
_WIN32 _WIN64 WIN32 WIN64 _WINDOWS __WINDOWS__ __CYGWIN__ __CYGWIN32__ __MINGW32__ __MINGW64__ _MSC_VER
__MSYS__ __INTERIX _WIN32_WCE
__FreeBSD__ __FreeBSD_kernel__ __NetBSD__ __OpenBSD__ __DragonFly__ __bsdi__
__sun __sun__ sun __SVR4 __svr4__ _AIX __hpux __HAIKU__ __BEOS__ __EMSCRIPTEN__ __wasi__ __wasm__
__wasm32__ __wasm64__ __Fuchsia__ __GNU__ __minix __vxworks __VXWORKS__ __ZEPHYR__ __OS2__ __ILLUMOS__
__CloudABI__ __rtems__ __NuttX__
__GLIBC__ __GNU_LIBRARY__ __UCLIBC__ __BIONIC__ __NEWLIB__ _NEWLIB_VERSION __MUSL__ __DJGPP__
__INTEL_COMPILER __SUNPRO_C __SUNPRO_CC __IBMC__ __xlC__ __NVCC__ __CUDACC__ __PGI __HP_aCC
__i386__ __i386 _M_IX86 i386 __i686__ __arm__ _M_ARM __thumb__ __powerpc__ __powerpc64__ __ppc__ __PPC__
__ppc64__ _ARCH_PPC __mips__ __mips __riscv __s390__ __s390x__ __sparc__ __sparc __alpha__ __ia64__
__hppa__ __m68k__ __sh__ __loongarch__ __loongarch64 __e2k__ __ve__ _M_X64 _M_AMD64 _M_ARM64
SA_RESTART IOV_MAX SO_PEERCRED W_EXITCODE
EPOLLIN EPOLLOUT EPOLL_CLOEXEC EFD_CLOEXEC EFD_NONBLOCK TFD_CLOEXEC TFD_NONBLOCK SFD_CLOEXEC SFD_NONBLOCK
DT_DIR DT_REG DT_LNK DT_UNKNOWN _DIRENT_HAVE_D_TYPE
SYS_gettid SYS_getrandom SYS_futex __NR_gettid __NR_futex GRND_NONBLOCK GRND_RANDOM
MAP_POPULATE O_TMPFILE MFD_CLOEXEC PR_SET_NAME PR_SET_PDEATHSIG CPU_SETSIZE
__GLIBC_PREREQ __GNUC_PREREQ __USE_GNU __USE_MISC
""".split())
ARCH_MACROS = {
    "x86_64": {"__x86_64__": 1, "__x86_64": 1, "__amd64__": 1, "__amd64": 1, "__SSE2__": 1, "__SSE__": 1},
    "aarch64le": {"__aarch64__": 1, "__ARM_ARCH": 8, "__ARM_64BIT_STATE": 1, "__ARM_NEON": 1, "__ARM_NEON__": 1,
                  "__AARCH64EL__": 1},
}
ALL_ARCH_MACROS = set().union(*ARCH_MACROS.values())

# Headers that are known to exist / not exist in the QNX 8.0 SDP (beyond the rule headers).
# Present: every header named in a QNX 8.0 C Library Reference synopsis, plus common POSIX ones.
HEADERS_PRESENT_EXTRA = set("""
netinet/in.h netinet/tcp.h arpa/inet.h sys/un.h poll.h sys/param.h sys/elf.h gulliver.h unix.h
process.h sys/neutrino.h hw/inout.h sys/syspage.h sys/procmgr.h libgen.h stdbool.h iso646.h
""".split())


SOCKETCAN_THUNKS = {"linux/socket.h", "linux/sockios.h", "linux/types.h", "linux/stddef.h"}


def _rule_header_patterns():
    pats = []
    for r in sorted(RULES, key=lambda r: r.id != "QNX048"):
        for h in r.headers:
            if h.endswith("__never"):
                continue
            pats.append((re.compile("^" + h + "$"), r))
    return pats


HEADER_RULES = _rule_header_patterns()


@lru_cache(maxsize=1)
def headers_present() -> frozenset:
    hs = set()
    for headers, _lib, _page in libc_index().values():
        hs.update(headers)
    hs.update(h for h in HEADERS_PRESENT_EXTRA if not h.endswith("__unknown"))
    return frozenset(hs)


def header_known(path: str):
    """True if the header exists on QNX 8.0, False if it is known missing, None if unknown."""
    for pat, rule in HEADER_RULES:
        if pat.match(path):
            return False
    if path in headers_present():
        return True
    return None


def _have_macro_facts() -> dict:
    """HAVE_* style configure results we can predict for QNX 8.0.

    Code guarded by e.g. ``#ifdef HAVE_EPOLL`` is excluded on QNX because the
    configure check fails there; code guarded by ``HAVE_PIPE2`` is included.
    """
    facts: dict = {}
    for r in RULES:
        if r.severity not in ("blocker", "link") or r.category not in ("linux-api", "posix-gap", "header"):
            continue
        for g in r.guards:
            if not g.startswith("HAVE_") or "*" in g or "." in g:
                continue
            if r.severity == "link":
                continue        # available via an extra library: configure may or may not find it
            facts[g] = "undef"
        for c in r.calls:
            facts.setdefault("HAVE_" + c.upper(), "undef" if r.severity == "blocker" else "unknown")
        for h in r.headers:
            if h.endswith("__never") or not re.fullmatch(r"[A-Za-z0-9_/.-]+", h):
                continue
            facts.setdefault("HAVE_" + re.sub(r"[^A-Za-z0-9]", "_", h).upper(),
                             "undef" if r.severity == "blocker" else "unknown")
    for name in ("pipe2", "posix_fallocate", "posix_memalign", "strlcpy", "strlcat", "reallocarray",
                 "clock_gettime", "clock_nanosleep", "pthread_setname_np", "pthread_getname_np",
                 "strndup", "getline", "asprintf", "vasprintf", "memmem", "strsep", "mkostemp", "timegm",
                 "statvfs", "fstatvfs", "utimensat", "futimens", "openat", "fdopendir", "posix_spawn",
                 "nanosleep", "poll", "ppoll", "pselect", "mallinfo", "malloc_usable_size", "gettid",
                 "forkpty", "openpty", "getprogname", "err", "warn", "flock", "lockf", "mlock", "fork",
                 "getpagesize", "sysconf", "dladdr", "dl_iterate_phdr", "strerror_r", "sigaction",
                 "posix_madvise", "accept", "inotify_init1"):
        facts.setdefault("HAVE_" + name.upper(), "def")
    return facts


HAVE_FACTS = _have_macro_facts()

# Platform-identifying macro names: used to recognise "platform dispatch" #if chains.
PLATFORM_MACRO_RE = re.compile(
    r"^(__linux__|__linux|linux|__gnu_linux__|__ANDROID__|ANDROID|__APPLE__|__MACH__|_WIN32|_WIN64|WIN32|"
    r"__CYGWIN__|__MINGW32__|__MINGW64__|_MSC_VER|__FreeBSD__|__NetBSD__|__OpenBSD__|__DragonFly__|__sun|"
    r"__sun__|_AIX|__hpux|__HAIKU__|__EMSCRIPTEN__|__wasi__|__Fuchsia__|__GNU__|__unix__|__unix|unix|"
    r"__QNX__|__QNXNTO__|__GLIBC__|__BIONIC__|__UCLIBC__|__FreeBSD_kernel__|__bsdi__|__minix|"
    r"(?:[A-Z0-9_]*_)?(?:OS|PLATFORM|SYSTEM|TARGET)_(?:LINUX|ANDROID|APPLE|MAC|MACOS|MACOSX|DARWIN|IOS|WIN32|"
    r"WIN|WINDOWS|FREEBSD|NETBSD|OPENBSD|BSD|SOLARIS|AIX|HAIKU|QNX|UNIX|POSIX|EMSCRIPTEN|FUCHSIA|CYGWIN)"
    r"(?:_[A-Z0-9_]*)?|(?:LINUX|MACOSX|MACOS|DARWIN|WINDOWS|SOLARIS|FREEBSD|NETBSD|OPENBSD))$")

WINDOWS_HEADERS = re.compile(r"^(windows\.h|winsock2?\.h|ws2tcpip\.h|io\.h|direct\.h|winbase\.h|"
                             r"winnt\.h|windef\.h|tchar\.h|shlobj\.h|objbase\.h|wincrypt\.h|"
                             r"processthreadsapi\.h|synchapi\.h|intrin\.h|malloc_win\.h)$", re.I)
