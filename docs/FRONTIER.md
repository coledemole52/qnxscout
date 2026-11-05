# The QNX porting frontier

Generated 2026-11-05 by `bench/frontier.py`. Alpine (edge) packages that are **not yet in qnx-ports/aports**: 4969 with C/C++-style builds. Of those, **1559** already have every build and runtime dependency ported to QNX. Each was scanned from pristine upstream source and ranked by predicted QNX porting effort.

| Grade | Packages |
|---|---|
| A | 218 |
| B | 309 |
| C | 228 |
| D | 131 |
| E | 71 |

## Easiest 150 (at least 5 C/C++ files)

| # | Package | Grade | Points | C/C++ files | What qnxscout expects you to fix | Description |
|---|---|---|---|---|---|---|
| 1 | [acpi](https://sourceforge.net/projects/acpiclient/files/acpiclient/) | A | 0.0 | 5 | nothing | ACPI client for battery, power, and thermal readings |
| 2 | [bdftopcf](https://xorg.freedesktop.org/) | A | 0.0 | 27 | nothing | X.Org font utility |
| 3 | [cksfv](http://zakalwe.fi/~shd/foss/cksfv) | A | 0.0 | 8 | nothing | Simple File Verification |
| 4 | [byacc](https://invisible-island.net/byacc/byacc.html) | A | 0.0 | 299 | nothing | The Berkeley Yacc general-purpose parser generator |
| 5 | [darkhttpd](https://unix4lyfe.org/darkhttpd/) | A | 0.0 | 7 | nothing | A simple, single-threaded, static content webserver |
| 6 | [email](http://www.cleancode.org/projects/email) | A | 0.0 | 45 | nothing | command line SMTP client that's simple |
| 7 | [gettext-tiny](https://github.com/sabotage-linux/gettext-tiny) | A | 0.0 | 11 | nothing | Tiny Internationalized Message Handling Library and tools |
| 8 | [haserl](https://haserl.sourceforge.net/) | A | 0.0 | 21 | nothing | Html And Shell Embedded Report Language |
| 9 | [libconfig](https://www.hyperrealm.com/libconfig/libconfig.html) | A | 0.0 | 48 | nothing | A simple library for manipulating structured configuration files |
| 10 | [libfastjson](https://www.rsyslog.com/) | A | 0.0 | 40 | nothing | fork of the json-c library for rsyslog, optimized for liblognorm proce |
| 11 | [libeconf](https://github.com/openSUSE/libeconf) | A | 0.0 | 86 | nothing | Enhanced Config File Parser |
| 12 | [libnet](https://sourceforge.net/projects/libnet-dev/) | A | 0.0 | 128 | nothing | A generic networking API that provides access to several protocols. |
| 13 | [libverto](https://github.com/latchset/libverto) | A | 0.0 | 18 | nothing | Main loop abstraction library |
| 14 | [libxft](https://xorg.freedesktop.org/) | A | 0.0 | 19 | nothing | FreeType-based font drawing library for X |
| 15 | [mpdecimal](https://www.bytereef.org/mpdecimal/index.html) | A | 0.0 | 57 | nothing | complete implementation of the General Decimal Arithmetic Specificatio |
| 16 | [makedepend](https://www.freedesktop.org/) | A | 0.0 | 12 | nothing | utility for making makefile dependencies |
| 17 | [mpfr4](https://www.mpfr.org/) | A | 0.0 | 507 | nothing | multiple-precision floating-point library |
| 18 | [ncdu](https://dev.yorhel.nl/ncdu) | A | 0.0 | 29 | nothing | Text-based disk usage viewer |
| 19 | [neon](https://notroj.github.io/neon/) | A | 0.0 | 88 | nothing | HTTP and WebDAV client library with a C interface |
| 20 | [patchelf](https://nixos.org/patchelf.html) | A | 0.0 | 13 | nothing | Small utility to modify the dynamic linker and RPATH of ELF executable |
| 21 | [pwgen](https://github.com/tytso/pwgen) | A | 0.0 | 8 | nothing | A Password Generator |
| 22 | [pkcs11-helper](https://github.com/OpenSC/pkcs11-helper) | A | 0.0 | 47 | nothing | Library that simplifies the interaction with PKCS#11 providers |
| 23 | [s6-dns](https://skarnet.org/software/s6-dns/) | A | 0.0 | 150 | nothing | skarnet.org's DNS client libraries and command-line DNS client utiliti |
| 24 | [sipcalc](https://www.routemeister.net/projects/sipcalc/) | A | 0.0 | 6 | nothing | Advanced console based ip subnet calculator |
| 25 | [skytraq-datalogger](https://code.google.com/p/skytraq-datalogger/) | A | 0.0 | 8 | nothing | Configuration and download tool for GPS data loggers based on Skytraq  |
| 26 | [snowball](https://snowballstem.org/) | A | 0.0 | 30 | nothing | Snowball rule-based stemming algorithms |
| 27 | [spice-protocol](http://www.spice-space.org/) | A | 0.0 | 13 | nothing | Spice protocol header files |
| 28 | [tree](https://oldmanprogrammer.net/source.php?dir=projects/tree) | A | 0.0 | 14 | nothing | Recursive directory indented listing of files |
| 29 | [tolua++](https://github.com/LuaDist/toluapp) | A | 0.0 | 27 | nothing | a tool to integrate C/C++ code with Lua |
| 30 | [xmlindent](https://xmlindent.sourceforge.net/) | A | 0.0 | 8 | nothing | An XML indenting utility |
| 31 | [zd1211-firmware](https://sourceforge.net/projects/zd1211/) | A | 0.0 | 6 | nothing | Firmware for ZyDAS ZD1211 USB-WLAN devices supported by the zd1211rw d |
| 32 | [a52dec](https://liba52.sourceforge.net/) | A | 0.0 | 34 | nothing | A free library for decoding ATSC A/52 streams. |
| 33 | [antiword](http://www.winfield.demon.nl) | A | 0.0 | 78 | nothing | A free MS Word reader |
| 34 | [arpack](https://github.com/opencollab/arpack-ng) | A | 0.0 | 41 | nothing | Collection of Fortran77 subroutines designed to solve large scale eige |
| 35 | [blind](https://tools.suckless.org/blind/) | A | 0.0 | 52 | nothing | blind is a collection of command line video editing utilities |
| 36 | [c-stdaux](https://github.com/c-util/c-stdaux) | A | 0.0 | 6 | nothing | Auxiliary macros and functions for the C standard library |
| 37 | [caps](http://quitte.de/dsp/caps.html) | A | 0.0 | 72 | nothing | the C* Audio Plugin Suite |
| 38 | [cglm](http://cglm.readthedocs.io) | A | 0.0 | 275 | nothing | Highly Optimized Graphics Math (glm) for C |
| 39 | [chntpw](https://pogostick.net/~pnh/ntpasswd/) | A | 0.0 | 12 | nothing | Change passwords in Windows SAM files |
| 40 | [cln](https://www.ginac.de/CLN/) | A | 0.0 | 1174 | nothing | C++ class library for numbers |
| 41 | [cuetools](https://github.com/svend/cuetools) | A | 0.0 | 17 | nothing | cuetools is a set of utilities for working with cue files and toc file |
| 42 | [darts-clone](https://github.com/s-yata/darts-clone) | A | 0.0 | 10 | nothing | C++ header library for a static double-array trie structure |
| 43 | [dcadec](https://github.com/foo86/dcadec) | A | 0.0 | 42 | nothing | DTS Coherent Acoustics decoder with support for HD extensions |
| 44 | [dfu-util](https://dfu-util.sourceforge.net/) | A | 0.0 | 19 | nothing | Host side implementation of the DFU 1.0 and DFU 1.1 specifications |
| 45 | [deutex](https://github.com/Doom-Utils/deutex) | A | 0.0 | 39 | nothing | WAD composer for Doom, Heretic, Hexen, and Strife |
| 46 | [dhex](https://www.dettus.net/dhex/) | A | 0.0 | 27 | nothing | ncurses hex editor with diff mode for binary file comparison, supports |
| 47 | [epub2txt](https://github.com/kevinboone/epub2txt2) | A | 0.0 | 24 | nothing | CLI utility for extracting text from EPUB documents |
| 48 | [farbfeld](https://tools.suckless.org/farbfeld/) | A | 0.0 | 9 | nothing | Lossless image format which is easy to parse, pipe and compress |
| 49 | [ffnvcodec-headers](https://git.videolan.org/?p=ffmpeg/nv-codec-headers.git) | A | 0.0 | 5 | nothing | FFmpeg version of headers required to interface with Nvidias codec API |
| 50 | [gupnp-av](https://gitlab.gnome.org/GNOME/gupnp-av) | A | 0.0 | 64 | nothing | Small utility library that aims to ease the handling and implementatio |
| 51 | [hexagonrpcd](https://github.com/linux-msm/hexagonrpc) | A | 0.0 | 33 | nothing | Qualcomm HexagonFS daemon |
| 52 | [hexdiff](http://tboudet.free.fr/hexdiff/) | A | 0.0 | 7 | nothing | ncurses hex editor with diff mode for binary file comparison |
| 53 | [howard-bc](https://github.com/gavinhoward/bc) | A | 0.0 | 46 | nothing | POSIX bc with GNU extensions |
| 54 | [jo](https://github.com/jpmens/jo) | A | 0.0 | 5 | nothing | JSON output from a shell |
| 55 | [jose](https://github.com/latchset/jose) | A | 0.0 | 76 | nothing | C-language implementation of Javascript Object Signing and Encryption |
| 56 | [libgepub](https://gitlab.gnome.org/GNOME/libgepub) | A | 0.0 | 12 | nothing | GObject based library for handling epub documents |
| 57 | [libgee](https://gitlab.gnome.org/GNOME/libgee) | A | 0.0 | 119 | nothing | GObject collection library |
| 58 | [liblzf](http://software.schmorp.de/pkg/liblzf.html) | A | 0.0 | 6 | nothing | A very small data compression library |
| 59 | [lapack](https://www.netlib.org/lapack/) | A | 0.0 | 2882 | nothing | Linear Algebra PACKage |
| 60 | [libngf](https://github.com/sailfishos/libngf) | A | 0.0 | 9 | nothing | Nemo's libngf |
| 61 | [libqd](https://www.davidhbailey.com/dhbsoftware) | A | 0.0 | 32 | nothing | Double-double and quad-double library for Fortran and C++ |
| 62 | [libspiro](https://github.com/fontforge/libspiro) | A | 0.0 | 33 | nothing | Library to simplify the drawing of beautiful curves |
| 63 | [libtickit](https://www.leonerd.org.uk/code/libtickit/) | A | 0.0 | 81 | nothing | library that provides an abstracted mechanism for building interactive |
| 64 | [libxdg-basedir](https://github.com/davmac314/libxdg-basedir) | A | 0.0 | 6 | nothing | library for XDG base dir specification |
| 65 | [libxaw3d](https://gitlab.freedesktop.org/xorg/lib/libxaw3d) | A | 0.0 | 126 | nothing | 3D appearance variant of the X Athena Widget Set |
| 66 | [lzlib](https://www.nongnu.org/lzip/lzlib.html) | A | 0.0 | 18 | nothing | Library for the lzip compression file format |
| 67 | [mdp](https://github.com/visit1985/mdp) | A | 0.0 | 17 | nothing | Command-line based markdown presentation tool |
| 68 | [meson-tools](https://github.com/afaerber/meson-tools) | A | 0.0 | 6 | nothing | Tools for Amlogic Meson ARM platforms |
| 69 | [nawk](https://github.com/onetrueawk/awk/) | A | 0.0 | 12 | nothing | The one, true implementation of AWK |
| 70 | [nextvi](https://github.com/kyx0r/nextvi/) | A | 0.0 | 12 | nothing | A small vi/ex terminal text editor (neatvi rewrite) |
| 71 | [npapi-sdk](https://github.com/mgorny/npapi-sdk) | A | 0.0 | 8 | nothing | Netscape Plugin API (NPAPI) |
| 72 | [nvim-treesitter](https://github.com/nvim-treesitter/nvim-treesitter/) | A | 0.0 | 34 | nothing | nvim treesitter configurations and abstraction layer |
| 73 | [oed](https://github.com/ibara/oed) | A | 0.0 | 21 | nothing | Portable version of the OpenBSD ed text editor |
| 74 | [opencl-icd-loader](https://github.com/OCL-dev/ocl-icd) | A | 0.0 | 26 | nothing | Generic OpenCL ICD Loader |
| 75 | [oils-for-unix](https://www.oils.pub/) | A | 0.0 | 106 | nothing | Unix shell with JSON-compatible structured data |
| 76 | [opencore-amr](https://sourceforge.net/projects/opencore-amr/) | A | 0.0 | 410 | nothing | Implementation of Adaptive Multi Rate speech codec |
| 77 | [opensmtpd-table-passwd](https://github.com/OpenSMTPD/table-passwd) | A | 0.0 | 19 | nothing | OpenSMTPD passwd tables |
| 78 | [opensmtpd-table-redis](https://github.com/OpenSMTPD/table-redis) | A | 0.0 | 19 | nothing | OpenSMTPD Redis tables |
| 79 | [opensmtpd-table-sqlite](https://github.com/OpenSMTPD/table-sqlite) | A | 0.0 | 19 | nothing | OpenSMTPD SQLite tables |
| 80 | [osinfo-db-tools](https://libosinfo.org/) | A | 0.0 | 6 | nothing | Tools for managing the osinfo database |
| 81 | [openv2g](https://openv2g.sourceforge.net/) | A | 0.0 | 56 | nothing | Implements ISO IEC 15118 and also the DIN 70121 vehicle to grid (V2G)  |
| 82 | [playerctl](https://github.com/altdesktop/playerctl) | A | 0.0 | 14 | nothing | MPRIS command-line controller for music players |
| 83 | [planarity](https://github.com/graph-algorithms/edge-addition-planarity-suite) | A | 0.0 | 70 | nothing | Edge addition planar graph embedding related algorithms |
| 84 | [progress](https://github.com/Xfennec/progress) | A | 0.0 | 6 | nothing | Coreutils Progress Viewer |
| 85 | [psutils](http://knackered.org/angus/psutils) | A | 0.0 | 14 | nothing | A set of postscript utilities |
| 86 | [pystring](https://github.com/imageworks/pystring) | A | 0.0 | 6 | nothing | C++ functions matching the interface and behavior of python string met |
| 87 | [qpage](https://web.archive.org/web/20241213130709/http://www.qpage.org/) | A | 0.0 | 11 | nothing | Sends messages to an alphanumeric pager via TAP protocol. |
| 88 | [qbe](https://c9x.me/compile/) | A | 0.0 | 47 | nothing | Quick compiler backend |
| 89 | [qrcodegen](https://www.nayuki.io/page/qr-code-generator-library) | A | 0.0 | 7 | nothing | High-quality QR Code generator library |
| 90 | [ragel](https://www.colm.net/open-source/ragel/) | A | 0.0 | 165 | nothing | Finite state machine compiler |
| 91 | [ratpoison](https://ratpoison.nongnu.org/) | A | 0.0 | 52 | nothing | Minimalistic window manager |
| 92 | [raspberrypi-usbboot](https://github.com/raspberrypi/usbboot) | A | 0.0 | 7 | nothing | rpiboot and bin2c from Raspberry Pi |
| 93 | [rgbds](https://rgbds.gbdev.io/) | A | 0.0 | 118 | nothing | An assembly toolchain for the Nintendo Game Boy and Game Boy Color |
| 94 | [roswell](https://roswell.github.io/) | A | 0.0 | 43 | nothing | Common Lisp environment setup Utility |
| 95 | [sqlite3pp](https://github.com/iwongu/sqlite3pp) | A | 0.0 | 21 | nothing | SQLite3++ - C++ wrapper of SQLite3 API  |
| 96 | [stoken](https://github.com/cernekee/stoken) | A | 0.0 | 16 | nothing | RSA SecurID-compatible software token for Linux/UNIX systems |
| 97 | [sunwait](https://sourceforge.net/projects/sunwait4windows/) | A | 0.0 | 6 | nothing | Sunwait calculates sunrise or sunset times with civil, nautical, astro |
| 98 | [swuniq](https://github.com/mterron/swuniq) | A | 0.0 | 5 | nothing | Streaming sliding window uniq |
| 99 | [tcl-lib](https://www.tcl-lang.org/software/tcllib/) | A | 0.0 | 87 | nothing | Tcl standard library |
| 100 | [template-glib](https://gitlab.gnome.org/GNOME/template-glib) | A | 0.0 | 49 | nothing | library for template expansion which supports calling into GObject Int |
| 101 | [tinyxml](https://sourceforge.net/projects/tinyxml/) | A | 0.0 | 7 | nothing | A simple, small, C++ XML parser |
| 102 | [tree-sitter-comment](https://github.com/stsewd/tree-sitter-comment) | A | 0.0 | 14 | nothing | Tree-sitter grammar for comment tags like TODO, FIXME(user) |
| 103 | [tree-sitter-c-sharp](https://github.com/tree-sitter/tree-sitter-c-sharp) | A | 0.0 | 9 | nothing | C# Grammar for tree-sitter |
| 104 | [tree-sitter-css](https://github.com/tree-sitter/tree-sitter-css) | A | 0.0 | 9 | nothing | CSS grammar for tree-sitter |
| 105 | [tree-sitter-elixir](https://github.com/elixir-lang/tree-sitter-elixir) | A | 0.0 | 8 | nothing | Elixir grammar for tree-sitter |
| 106 | [tree-sitter-embedded-template](https://github.com/tree-sitter/tree-sitter-embedded-template) | A | 0.0 | 8 | nothing | Tree-sitter grammar for embedded template languages like ERB, EJS |
| 107 | [tree-sitter-elm](https://github.com/elm-tooling/tree-sitter-elm) | A | 0.0 | 9 | nothing | Elm grammar for tree-sitter |
| 108 | [tree-sitter-html](https://github.com/tree-sitter/tree-sitter-html) | A | 0.0 | 10 | nothing | HTML grammar for tree-sitter |
| 109 | [tree-sitter-ini](https://github.com/justinmk/tree-sitter-ini) | A | 0.0 | 9 | nothing | tree-sitter grammar/parser for INI files |
| 110 | [tree-sitter-go](https://github.com/tree-sitter/tree-sitter-go) | A | 0.0 | 8 | nothing | Go grammar for tree-sitter |
| 111 | [tree-sitter-jsdoc](https://github.com/tree-sitter/tree-sitter-jsdoc) | A | 0.0 | 9 | nothing | JSDoc grammar for tree-sitter |
| 112 | [tree-sitter-json](https://github.com/tree-sitter/tree-sitter-json) | A | 0.0 | 8 | nothing | JSON grammar for tree-sitter |
| 113 | [tree-sitter-julia](https://github.com/tree-sitter/tree-sitter-julia) | A | 0.0 | 9 | nothing | Julia grammar for tree-sitter |
| 114 | [tree-sitter-java](https://github.com/tree-sitter/tree-sitter-java) | A | 0.0 | 8 | nothing | Java grammar for tree-sitter |
| 115 | [tree-sitter-javascript](https://github.com/tree-sitter/tree-sitter-javascript) | A | 0.0 | 9 | nothing | JavaScript grammar for tree-sitter |
| 116 | [tree-sitter-kotlin](https://github.com/fwcd/tree-sitter-kotlin) | A | 0.0 | 8 | nothing | Kotlin grammar for Tree-Sitter |
| 117 | [tree-sitter-php](https://github.com/tree-sitter/tree-sitter-php) | A | 0.0 | 16 | nothing | PHP grammar for tree-sitter |
| 118 | [tree-sitter-ron](https://github.com/tree-sitter-grammars/tree-sitter-ron) | A | 0.0 | 5 | nothing | Rusty Object Notation (RON) grammar for tree-sitter |
| 119 | [tree-sitter-ruby](https://github.com/tree-sitter/tree-sitter-ruby) | A | 0.0 | 9 | nothing | Ruby grammar for tree-sitter |
| 120 | [tree-sitter-rust](https://github.com/tree-sitter/tree-sitter-rust) | A | 0.0 | 9 | nothing | Rust grammar for tree-sitter |
| 121 | [tree-sitter-scheme](https://github.com/6cdh/tree-sitter-scheme) | A | 0.0 | 8 | nothing | Scheme grammar for tree-sitter |
| 122 | [tree-sitter-scala](https://github.com/tree-sitter/tree-sitter-scala) | A | 0.0 | 10 | nothing | Scala grammar for tree-sitter |
| 123 | [tree-sitter-ssh-client-config](https://github.com/metio/tree-sitter-ssh-client-config) | A | 0.0 | 8 | nothing | tree-sitter grammar for SSH client configuration files |
| 124 | [tree-sitter-typescript](https://github.com/tree-sitter/tree-sitter-typescript) | A | 0.0 | 17 | nothing | TypeScript grammar for tree-sitter |
| 125 | [tree-sitter-xml](https://github.com/ObserverOfTime/tree-sitter-xml) | A | 0.0 | 17 | nothing | XML & DTD grammars for tree-sitter |
| 126 | [tree-sitter-yaml](https://github.com/tree-sitter-grammars/tree-sitter-yaml) | A | 0.0 | 24 | nothing | YAML grammar for tree-sitter |
| 127 | [tty-solitaire](https://github.com/mpereira/tty-solitaire) | A | 0.0 | 32 | nothing | ncurses-based klondike solitaire game |
| 128 | [ttf2ufm](https://acko.net/blog/ufpdf-unicode-utf-8-extension-for-fpdf/) | A | 0.0 | 21 | nothing | A True Type to PostScript Type 1 Converter |
| 129 | [uhttpmock](https://gitlab.freedesktop.org/pwithnall/uhttpmock/) | A | 0.0 | 11 | nothing | HTTP web service mocking library |
| 130 | [udpcast](https://www.udpcast.linux.lu/) | A | 0.0 | 46 | nothing | Multicast file transfer tool |
| 131 | [unclutter-xfixes](https://github.com/Airblader/unclutter-xfixes) | A | 0.0 | 13 | nothing | Hides mouse pointer while not in use |
| 132 | [twm](https://www.x.org/archive/X11R6.8.1/doc/twm.1.html) | A | 0.0 | 30 | nothing | Tom's or Tab Window Manager for the X Window System |
| 133 | [vbindiff](https://www.cjmweb.net/vbindiff/) | A | 0.0 | 14 | nothing | ncurses hex editor with diff mode for binary file comparison, supports |
| 134 | [vamp-sdk](https://vamp-plugins.org/develop.html) | A | 0.0 | 64 | nothing | Framework for audio analysis and feature extraction |
| 135 | [wl-kbptr](https://github.com/moverest/wl-kbptr) | A | 0.0 | 27 | nothing | Control the mouse pointer with the keyboard on Wayland |
| 136 | [xclip](https://github.com/astrand/xclip) | A | 0.0 | 6 | nothing | Command line interface to the X11 clipboard |
| 137 | [xeyes](https://www.x.org) | A | 0.0 | 6 | nothing | Pair of eyes that follow your mouse in X11 |
| 138 | [xisxwayland](https://gitlab.freedesktop.org/xorg/app/xisxwayland) | A | 0.0 | 5 | nothing | Detect if X is XWayland |
| 139 | [xmodmap](https://xorg.freedesktop.org/) | A | 0.0 | 6 | nothing | Utility for modifying keymaps and pointer button mappings in X |
| 140 | [xprop](https://cgit.freedesktop.org/xorg/app/xprop) | A | 0.0 | 5 | nothing | Property displayer for X |
| 141 | [xwd](https://gitlab.freedesktop.org/xorg/app/xwd) | A | 0.0 | 10 | nothing | Utility to dump an image of an X window in XWD format |
| 142 | [xwininfo](https://cgit.freedesktop.org/xorg/app/xwininfo) | A | 0.0 | 7 | nothing | Window information utility for X |
| 143 | [xmlsec](https://github.com/lsh123/xmlsec/) | A | 0.0 | 247 | nothing | C based implementation for XML Signature Syntax and Processing and XML |
| 144 | [ytnef](https://github.com/Yeraze/ytnef) | A | 0.0 | 15 | nothing | TNEF Stream Reader - for winmail.dat files |
| 145 | [iniparser](https://github.com/ndevilla/iniparser) | A | 0.0 | 10 | nothing | C library for parsing INI-style files |
| 146 | [dtc](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/) | A | 0.0 | 106 | nothing | Device Tree Compiler |
| 147 | [libid3tag](https://codeberg.org/tenacityteam/libid3tag) | A | 0.0 | 31 | nothing | MAD ID3 tagger for MP3 audio files |
| 148 | [libical](https://libical.github.io/libical/) | A | 0.0 | 158 | nothing | Reference implementation of the iCalendar format |
| 149 | [snappy](https://github.com/google/snappy) | A | 0.0 | 18 | nothing | Fast compression and decompression library |
| 150 | [yajl](https://lloyd.github.io/yajl/) | A | 0.0 | 26 | nothing | Yet Another JSON Library (YAJL) |

## Most wanted dependencies

Dependencies that are not yet on QNX, ranked by how many unported packages each one blocks.

| Dependency | Packages waiting on it |
|---|---|
| extra-cmake-modules | 428 |
| ki18n | 279 |
| kcoreaddons | 278 |
| kconfig | 252 |
| kwidgetsaddons | 189 |
| kio | 173 |
| ocaml | 173 |
| kconfigwidgets | 165 |
| kcrash | 160 |
| kxmlgui | 160 |
| kdoctools | 149 |
| mesa | 148 |
| eudev | 143 |
| kiconthemes | 137 |
| dune | 135 |
| util-linux | 130 |
| boost1.84 | 129 |
| qt5-qtbase | 125 |
| kdbusaddons | 121 |
| kwindowsystem | 110 |
| alsa-lib | 94 |
| kcompletion | 90 |
| coreutils | 80 |
| knotifications | 80 |
| libdrm | 78 |
| kcolorscheme | 78 |
| bsd-compat-headers | 77 |
| kservice | 77 |
| pulseaudio | 72 |
| libcap | 68 |
