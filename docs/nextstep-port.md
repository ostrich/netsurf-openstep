# NEXTSTEP 3.3 port

The first objective is the existing browser on NEXTSTEP 3.3 for NeXT 68k,
Intel, HPPA and SPARC, with the native OPENSTEP build preserved. CSS,
JavaScript and broader engine modernization follow on separate branches.
Source changes must remain compatible with GCC 4.2.

## Baseline and build ownership

The baseline is turbolent's openstep branch at 5fd34769d. Keep the inherited
history and make focused commits suitable for review against that branch.
Application changes and reproduction tools belong in this repository.
SDKs, VM images, compiler builds and generic compatibility-library sources
remain external inputs. Configure paths rather than encoding a development
machine's directory structure in maintained files.

Use the canonical installed Linux-hosted compiler snapshot, resolved once per
build. Record its manifest hash, source revision, dependency hashes, flags and
SDK/library fingerprints. Start with optimized Intel builds, then build all
four architectures. All initial dependencies use pinned source inputs; the
native OPENSTEP recipes are references, not prebuilt target libraries.

## Work sequence

1. Audit frontend APIs, build assumptions, byte order and dependency versions.
   Preserve a baseline of the existing OPENSTEP configuration.
2. Build the dependency graph and browser core against the 3.3 SDK. Reuse
   qualified NIHS libraries where compatible; build missing NetSurf libraries,
   curl and FreeType from their pinned sources. Keep target and host generators
   separate and do not accidentally link Linux libraries into guest code.
3. Add a native NEXTSTEP frontend while sharing renderer and browser callbacks
   where their semantics permit. Use real old-AppKit events, timers, menus,
   pasteboard and scroll views. Do not replace missing APIs with no-op shims.
4. Run an Intel GUI acceptance batch, then NIHS qualification and OPENSTEP
   regression checks. Package only after the observed results support it.

## Initial audit

| Area | Existing implementation | NEXTSTEP work |
| --- | --- | --- |
| Foundation | NSObject, strings, arrays, bundles | 3.3 provides Foundation; audit selectors individually |
| Windowing | NSApplication, NSWindow, NSView, controls | Native Application, Window, View and controls |
| Events | NSEvent, modern responder selectors | NXEvent and native responder methods |
| Scheduling | NSTimer | Native DPS timed entries with cancellation and lifetime checks |
| Graphics | libnsfb RAM surface, FreeType, NSDrawBitmap | NX bitmap upload; retain framebuffer rendering |
| Byte order | Byte-oriented BGRx upload | libnsfb normalizes both byte orders; preserve conversion and test on targets |
| Network | curl and TLS | Cross-build/qualify dependencies, DNS, PRNGD, CA verification |
| Build | Native gcc-4.2 and absolute system paths | Configurable cross-build lane without breaking native lane |

## Acceptance and bounded testing

First run deterministic host tests for pure helpers. Batch build checks across
architectures. In disposable guests, verify Workspace launch, local HTML/CSS,
images, text and links, forms, clipboard, scrolling/resizing, navigation,
multiple windows, close/reopen and clean quit. Test JavaScript at the inherited
feature level, not against an assumed modern-browser baseline. Add a controlled
HTTP/TLS fixture for fetches, redirects, certificate rejection and offline/error
handling. Separate dependency, core, frontend and emulator failures.

Start runtime qualification on Intel NEXTSTEP, then check all four targets and
OPENSTEP. A display-server problem must not turn into an unbounded browser test
loop. Preserve the failing artifact and use focused CLI or native drawing probes
to identify the boundary before repeating a full GUI batch.

## Current status

Optimized executables build and pass startup tests on NEXTSTEP 3.3 Intel,
NeXT 68k, HPPA and SPARC guests. These tests cover URL ownership, strict UTF-8
conversion including surrogate pairs and malformed input, framebuffer
registration and byte order, FreeType font loading and JavaScript heap startup.
All four guests halted natively and passed stopped filesystem checks.

A separate disposable OPENSTEP 4.2 desktop test launches the NEXTSTEP frontend,
visibly renders a controlled HTML/CSS page, displays JavaScript-updated DOM text
and quits cleanly. The clone halts natively and passes its filesystem check.
This checks the old-AppKit frontend on OPENSTEP; it does not substitute for GUI
qualification on NEXTSTEP 3.3 itself.

Controlled NEXTSTEP GUI and HTTP/TLS batches passed on NeXT 68k, HPPA and
SPARC. Intel networking passed through guest loopback; its copied CD-root
desktop fixture remains unqualified. The additional everyday-control batch
and ordinary-host-keyboard checks are described in
[qualification](qualification.md), with their specific scope and results.

Release work still includes a proper installed Intel desktop fixture and
rebuilding the original OPENSTEP frontend with GCC 4.2. The icon produces an
old-AppKit TIFF alpha warning. No release is qualified yet; the original
OPENSTEP frontend remains a separate build lane.

## Reproducing integration builds

On a Linux host, install Python 3.12 or newer, a C compiler, GNU make,
pkg-config, Perl, flex, bison, gperf and patch. Use a qualified installed
NEXTSTEP toolchain, the private 3.3 SDK and original NIHS AppKit/Foundation
import archives. SDK contents must not be redistributed with this source.

Copy `tools/nextstep/config.example.json` into ignored `work/` and set its
paths. Each external prefix needs `include/`, `lib/` and `lib/pkgconfig/` for
qualified NextStepCompat, zlib, GNU libiconv, LibreSSL and Expat. Include the
corresponding shared-library import archives, not Linux archives. Fat imports
are acceptable when they contain the selected architecture. Keep matching
runtime `.shlib` files for guest tests.

Run from the repository root:

```sh
python3 tools/nextstep/build.py --config work/build-inputs.json \
  --output work/build-1 --jobs 12
```

Add `--arch i386` for an Intel-only iteration. Architecture selection is
explicit in each underlying build, and the browser recipe checks real archive
slices before compiling. The selected toolchain is resolved once by the main
recipe. Each output directory holds its own host generator, dependency builds,
compiler commands, logs and application bundles. Select a fresh output path
for a new build; do not treat an old experiment as another current toolchain.

The small scripts beside `build.py` implement individual stages for diagnosis.
`check-frontend.py` compiles the native frontend for all four targets. The
application's `--smoke-test` performs startup checks without opening a window;
this does not establish GUI or network correctness. It must be run in a guest
with its matching shared runtimes and complete application resources.

## Adaptations retained from the existing port

The pinned libwapcaplet release asserts on a null unref, while this browser
uses nullable URL components. Retain the existing port's nullable-unref
behavior, without its old-compiler integer typedefs. A focused test in
`test/nextstep/wapcaplet.c` exercises null handling and repeated intern,
case-fold and destruction cycles. Both statement-expression modes have been
checked with host address and undefined-behavior sanitizers.

libnsutils already documents that its offset read/write helpers may change
the descriptor position. NEXTSTEP uses its existing seek-based implementation;
this is not offered as a replacement for POSIX atomic `pread`/`pwrite`.
libsvgtiny uses available double-precision math calls in place of missing
float variants. A private libpng test-utility structure is renamed to avoid
colliding with `getopt.h`. Duktape can use its own C89 math fallbacks; its
optional locale-dependent date parser cannot call missing `strptime`. ISO
8601 parsing remains available at the inherited browser feature level.

The cross-build uses NextStepCompat instead of the native OPENSTEP fallback
file. This supplies real regex, string, path and system-identity behavior.
Native directory scanning uses the actual BSD `struct direct` ABI. URL IPv4
validation uses the compatibility library's dotted-quad `inet_pton` interface.

Math optimizations are kept at `-O2`, with builtin recognition disabled for
sin, cos and ceil. This prevents the current compiler from introducing cexp
or ceilf calls unavailable in NEXTSTEP's system library. This should eventually
be represented in the compiler target's libc-capability hooks. Compiler query
support also needs a separately qualified toolchain update; the maintained
recipes provide explicit compiler-version metadata meanwhile.

The RAM framebuffer's constructor lives in a separate archive member. The
integration link explicitly retains that member so startup can register it.
Release packaging with a separately built framebuffer shared runtime must
qualify constructor registration again.

NEXTSTEP Foundation's UTF string conversion did not decode UTF-8 correctly on
any of the four guest targets. The frontend uses utf8proc and Foundation's
working UTF-16 constructor, following the approach used by the GSTerminal port.
This applies to clipboard contents, callback text and typed URLs. The browser's
own content encoding and FreeType text rendering remain shared with NetSurf.

## Native desktop integration

A guest-agent child lacks the logged-in desktop's Mach bootstrap namespace.
Changing its Unix account alone does not supply a WindowServer connection.
The disposable GUI test uses a root-only helper to copy Workspace's namespace,
drop to the desktop account and exec the browser. This helper is test equipment,
not part of the application. See [desktop test navigation](ui-navigation.md).

Native AppKit also needs explicit repaint coalescing. The document view records
pending redraws; the frontend paints and flushes them after DPS callbacks and
normal window updates. Merely marking a document subview dirty left the loaded
page invisible. Workspace's `-NX...` argument pairs are kept separate from
navigation URLs, and core-initiated window closure avoids a second release from
the native close delegate.

The native bitmap upload uses opaque packed RGB. The original OPENSTEP renderer
retains RGBA. Both reject excessive framebuffer dimensions before signed size
arithmetic can overflow. NEXTSTEP renders only the visible viewport, translating
the browser origin and caret before uploading the bitmap. Scrolling far down a
document no longer allocates or repacks all the hidden rows above it.


## GUI and HTTP/TLS qualification

The opt-in native GUI driver, network probes and strict result checker are
separate from ordinary application builds. See [qualification](qualification.md)
for coverage, reproduction and limits. HTTP/TLS checks include valid TLS 1.2
and 1.3 connections and certificate rejection cases. A shared fetcher fix uses
IP SAN verification for IP URLs instead of treating them as DNS names.

Native initial window dimensions now fit smaller screens, including the
Intel fixture's 640x480 VGA desktop. Larger desktops retain the existing
720x480 content size.


The 68k drawing/resize failure was traced to GCC 16.2's m68k floating-point
caller-save handling. A compiler-level fix, retaining normal optimization,
passes the controlled GUI and HTTP/TLS batch. The external canonical toolchain
now includes that fix in a qualified NIHS compiler/runtime snapshot. This fork
carries no browser source workaround for that compiler defect.

## Everyday window controls

Command-L selects the location field; Return navigates and returns keyboard
focus to the page. The location remains editable while a background load updates
the browser. Native AppKit's `setSelectable:YES` clears editability, so the field
uses `setEditable:YES` alone, which also enables selection. This differs from
modern Cocoa assumptions; see the [NeXT TextField reference](https://www.bitsavers.org/pdf/next/Release_1_Dec90/NEXTstep_Reference_Volume_2_Dec90.pdf).

Native `Object` adapters deliver toolbar actions and window notifications to
the Foundation controller. The location field, Cut/Copy/Paste menu and page
responder retain their separate native editing roles. HTML form fields receive
Tab and backward Tab; outside editable content, arrows and Space/Shift-Space
scroll, and Escape stops a load.

The native frontend retains the OPENSTEP File/Edit/Navigate/View menu structure
and the bundled Back, Forward, Reload and Stop images. Reload/Stop sits to the
right of the address field. A thin activity bar below the address advances on
load/status callbacks and clears when loading completes or is stopped; it is an
activity estimate, not a byte-count percentage. Image lookup explicitly checks
Resources/ because the NEXTSTEP Foundation bundle search differs from OPENSTEP.

The toolbar paints its own background. Content-view size changes coalesce a
browser reformat and a full window repaint before the document upload. This
covers programmatic resizing as well as the window delegate notification, and
avoids stale or white strips around moved controls. Windows initially leave
the application menu unobstructed and have a usable minimum size.

Text-hit searching now considers the nearest line even when a selection drag
jumps outside its inline container or between lines. Previously a single long
movement beyond a short line could leave no selection. The shared search also
returns defined relative coordinates when no text exists. A focused geometry
regression exercises the actual search routines, alongside the guest drag/copy
check.
