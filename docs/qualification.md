# NEXTSTEP qualification

These tests exercise the native NEXTSTEP frontend and its actual networking
libraries in disposable NEXTSTEP 3.3 guests. They use controlled pages and a
private test CA. They do not establish compatibility with arbitrary modern
websites, complete TLS conformance or readiness for release packaging.

## Results, 2026-10-21

| Target | Ordinary startup | Certificate identity | HTTP/TLS | Native GUI |
| --- | --- | --- | --- | --- |
| Intel | 13 passed | 16 passed | 11 passed | Blocked by desktop fixture |
| NeXT 68k | 13 passed | 16 passed | 11 passed | 16 passed with compiler fix, rendered capture |
| HPPA | 13 passed | 16 passed | 11 passed | 16 passed, rendered capture |
| SPARC | 13 passed | 16 passed | 11 passed | 16 passed, rendered capture |

HPPA and SPARC also completed the actual HTTPS page fetch and reload with TLS
1.3, browser exit 0, native halt and clean stopped filesystems. Every ordinary
startup run completed native halt and clean filesystem checks. The test driver
is absent from all four ordinary binaries.

The Intel image is a copied CD-root console fixture, not a qualified installed
desktop. It starts WindowServer, but loginwindow reports bootstrap-registration
and drag-service errors; Workspace does not become a usable desktop. Its GUI
result is a setup failure, not evidence that the browser itself failed to launch.
`prepare-desktop.py` preserves the current experimental setup for reproduction;
its Intel route is not qualified. A proper installed Intel fixture is the next
step rather than further browser changes based on that environment.

The 68k blank window and resize stall came from GCC 16.2 code generation,
not a general VM or AppKit failure. The compiler saved live floating-point
window dimensions in extended format, then copied a low word of that save slot
as a single-precision value. The initial window was 720x480, but subsequent
view rectangles became zero-sized. A two-file C reduction reproduced the
problem without any browser, AppKit or Foundation code.

Native GCC 2.5.8 passed the reduction; the old cross-compiler failed three of
four rectangle checks. Both disabling caller saves and fixing the m68k
floating-register mode-change hook restored correct results. The final browser
uses the actual compiler fix with normal `-O2`, caller saves enabled and no
temporary tracing. All 16 GUI, 11 network and 16 certificate checks passed,
with actual page captures, two server-observed HTTPS requests for fetch/reload,
normal application exit, native halt and a clean stopped filesystem.

The fix belongs in the external compiler toolchain. No application-source
workaround is needed. The corrected compiler has now been promoted in a
coherent NIHS compiler/runtime snapshot after installed-driver and guest
runtime qualification. Its manifest SHA-256 is
`5f965b7f3249ceb37ace506162754dd524269067d1ec58e89c9cdf53a2cc379f`.
The browser results above remain the original candidate-compiler run, rather
than a repeated browser build with the promoted snapshot. The startup column
records earlier ordinary-build startup runs; no browser release is implied.

Minimal AppKit controls also passed with native and cross compilers, including
an Application subclass, View instance-variable offsets and a ScrollView.
These controls were useful in isolating the compiler bug, but did not themselves
exercise live floating-point dimensions across the same opaque calls.

The earlier isolated Intel OPENSTEP 4.2 desktop rendered the controlled page
and quit successfully. That is distinct from NEXTSTEP Intel qualification and
predates this shared TLS change. No release-readiness claim follows from it.

## Coverage

The native GUI batch checks JavaScript-modified document text through the
native pasteboard, document extents, form input, scrolling, window resizing,
a second window, navigation history, HTTP and verified HTTPS page loading,
reload, closing the last window and opening another. There are 16 assertions.
Input is delivered through native view callbacks. Physical keyboard and mouse
routing, URL-field editing and general manual browsing need separate checks.
Transient stale pixels around the toolbar were visible during scripted resizing
and navigation; pixel-perfect repaint behavior is not established by these
geometry and content assertions.
The reload check requires a new content handle and an idle native loading
indicator, so it cannot accept the old page while a reload is pending. Host
screenshots require visible fixture body text, not just a matching title bar.
Video recovery samples the whole run so boot activity cannot exhaust a scene
limit before the browser appears.

Host screenshots establish that the fixture actually reached the display;
DOM assertions alone are not accepted as rendering evidence.

The 11 network checks cover HTTP, redirects, a redirect limit, a 128 KiB chunked
response checked byte by byte, HTTP 404, TLS 1.2, TLS 1.3, reconnecting, and
rejection of wrong-host, expired and untrusted certificates. Certificate and
hostname verification remain enabled throughout. The test executable links
against the browser's curl, LibreSSL and zlib inputs.

Another 16 assertions exercise certificate reference identities, including DNS
names, IPv4 and IPv6 SANs, mismatches and malformed input. This reproduced a
browser bug: treating an IP URL as a DNS name rejected a valid IP SAN. The
fetcher now selects the TLS library's IP-address verifier for IP literals and
its hostname verifier for DNS names. IPv6 identity verification is covered;
IPv6 network transport is not.

Intel, HPPA and SPARC use guest-loopback HTTP/TLS fixture processes. The 68k
client connects through Previous's emulated Ethernet to host-loopback fixtures.
This avoids making a slow native TLS server on 68k a browser prerequisite.
External-network tests also passed on SPARC. Intel PCI PCnet attachment and
HPPA i82596 packet delivery in these particular guest fixtures remain separate
VM limitations; the loopback tests do not qualify those adapters.

## Reproducing a run

Use fresh directories under ignored `work/` for every run. Resolve the compiler
snapshot once. Keep the dependency prefixes and shared runtimes matched; in
particular, the selected PRNGD must have its required NextStepCompat runtime.
The build records retain compiler commands, input hashes and exit codes.

1. Build each target with `tools/nextstep/build-browser.py --qualification`.
   Use the dependency prefixes from the normal `build.py` dependency graph;
   rebuilding those dependencies is unnecessary when their inputs are unchanged.
2. Start `tools/nextstep/network-fixture.py --output work/fixture`. Python's
   `cryptography` package is required. The server binds only to loopback and
   writes its port assignments when ready. Keep this process running for 68k.
3. Build the optimized native test programs with
   `tools/nextstep/build-qualification-helpers.py`. Supply the same private build
   config and dependency build directory used for the browser.
4. Run `tools/nextstep/prepare-qualification.py` with the browser builds,
   helpers, fixture directory, PRNGD, its readiness checker and matching runtimes.
   Its `payload` directory is input to the external VM project's
   `tools/ports/prepare-guests.py --network --native-tests PAYLOAD`.
5. Before launching, run `tools/nextstep/prepare-desktop.py` on the stopped
   Intel and 68k copies. Use `--arch m68k` for Previous. The Intel runner also
   needs `--intel-multiuser`. See [desktop navigation](ui-navigation.md).
6. Start the external guest runner and `tools/nextstep/monitor-qualification.py`
   concurrently, with the same selected architecture list. The monitor uses
   QMP for QEMU and the isolated X display for Previous. It needs ImageMagick,
   Tesseract, Pillow and ffmpeg. Capture only owned test desktops.
7. Run `tools/nextstep/check-qualification.py --suite LAB`. Select only the
   architectures prepared in that lab with repeated `--arch` options. For 68k, also pass
   `--host-fixture FIXTURE --host-token PAYLOAD_DIRECTORY_NAME`; the latter
   identifies this run's HTTPS requests. Each target needs explicit successful
   subtest markers, process exit, rendered-page evidence, native halt and clean
   stopped-filesystem checks. A generic outer runner success is insufficient.
8. Stop the private fixture server. Keep logs, input records and screenshots
   in ignored work output, not in published source or binary archives.

All scripts provide `--help` with their explicit input paths. The VM runner and
SDK are external inputs, not downloadable prerequisites supplied by this fork.
Generated endpoint private keys, CA keys and entropy seeds are private test
material. Never distribute the fixture CA as an application trust store.

Ordinary builds omit `--qualification`, contain no GUI test driver and do not
load the fixture CA. Build and run their independent `--smoke-test` startup
batch after the qualification build. The pre-existing OPENSTEP desktop check
is useful regression evidence, but does not replace rebuilding the original
GCC 4.2 OPENSTEP lane after shared fetcher changes.


## Clean rebuild and everyday controls, 2026-10-21

Fresh optimized browser builds on the promoted compiler passed all 13 startup
checks on each of the four targets. Project dependencies were rebuilt from the
pinned sources; qualified external runtime inputs were reused explicitly.
Ordinary binaries contain no acceptance driver.

The m68k native-control batch passed all 22 checks. The restored toolbar/header
matched a forced full repaint exactly: zero differing pixels out of 54,480.
The deep-scroll page rendered correctly with a 701x421 framebuffer at document
offset 19,000. Stable checkpoint images at both window sizes were also reviewed. A separate ordinary
build passed actual host-keyboard location entry, Return navigation and history
back, then quit normally. All guests halted natively and passed stopped
filesystem checks.

Selection uses direct view callbacks; form and link clicks use native Window
hit testing. Physical mouse drag delivery remains unqualified. The earlier
HTTP/TLS results above were not repeated for these rendering and input changes.
Intel desktop qualification and the original GCC 4.2 OPENSTEP build remain
separate work. Input hashes, result scope and exact checks are recorded in
[the build validation record](everyday-controls-2026-10-21.json).

## Minimal 68k AppKit control

`test/nextstep/appkit-probe.m` uses only native AppKit and system libraries.
It creates a buffered window, a custom drawing view and a TextField, then
redisplays and resizes it using bounded timed entries. There is no NetSurf,
Foundation or NextStepCompat implementation in the probe. The guest helper
supplies the freshly acquired Workspace bootstrap namespace to both binaries.

`tools/nextstep/prepare-appkit-control.py --help` lists the explicit compiler,
SDK/import library, test-helper, runtime-directory and external VM-project
inputs. It prepares one stopped disposable clone. The guest compiles the same
source with `/bin/cc -O2 -lNeXT_s` and runs native and cross-built executables
sequentially. Invoke the external `run-guests.py` with `--arch m68k --timeout 400`
and capture its isolated X display if pixel evidence is required. Each program
has a 60-second watchdog. Check both completion/draw logs, actual screenshots,
native halt and the collected filesystem check.

The 2026-10-21 control batch passed, exited through native halt and had a clean
stopped filesystem. The result checks require successful drawing and resize markers in addition
to application exit status.

## Everyday controls and repaint regression

`--everyday DIRECTORY` is available only in qualification builds.
`prepare-everyday.py` stages offline pages and an application into a fresh private
payload, reusing explicit matching runtime and entropy support. Prepare a fresh
68k clone, apply `prepare-desktop.py`, then run the guest runner and
`monitor-everyday.py` concurrently. Run `check-everyday.py` on the collected suite.
All these tools accept `--help`. No fixture seeds or guest images belong in a
distribution archive.

The batch checks location editing and Return, HTML form editing and traversal,
clipboard actions, history, scrolling, viewport-sized buffers, resize, reload,
selection and window closure. Key events use the native DPS queue; mouse
clicks use native Window hit testing. The selection test invokes the custom
view's mouse callbacks directly: synthetic WindowServer drag tracking after a
native control click is unreliable. This does not qualify the emulator's
physical mouse device or native drag delivery. The host monitor separately
uses the owned Previous SDL window to check host keyboard input. Readiness uses
observable content and clipboard changes, rather than assuming a fixed delay
means editing has completed.

Four screen checkpoints cover deep scrolling, shrink, restore and a forced full
repaint. The monitor saves each phase once after two identical pixel frames;
it must not overwrite a checkpoint while the next resize starts. The checker compares the restored toolbar/header against the forced
reference, anchored to the current native title bar. A known broken white-strip
image is a negative control; screenshot existence alone is insufficient. Review
the full images separately for page and deep-scroll correctness. The pixel
comparison is qualified for the unscaled Previous desktop and native font.

For an independent ordinary build, `prepare-smoke.py` accepts paired
`--gui-helpers` and `--gui-fixture` directories. It adds a bounded m68k desktop
launch to the four-target startup batch. `monitor-ordinary.py` enters a local
URL through actual host keys, checks destination and history-page rendering,
then quits. Require its host result together with native process exit, halt and
stopped-filesystem checks. Ordinary binaries contain no acceptance driver.

`python3 test/text-hit.py` compiles the actual nearest-text search
routines with small geometry fixtures. It covers an interior hit, both ends of
a short line, directional selection between lines, list markers, floating text and a
document without text.
The past-container case failed before the search fix. This test isolates
geometry; it does not substitute for rendering, font loading or native input.

An additional OPENSTEP 4.2 test uses ordinary host input on a disposable
VMware-framebuffer desktop. This exposed a gap in the timed acceptance batch:
its explicit display passes could hide missing repaint dispatch in the ordinary
application. Native AppKit did not invoke the application's `updateWindows`
override after input. Browser invalidations now flush after `sendEvent:` returns;
core timed callbacks retain their separate display pass. Tracking loops finish
before this event-boundary pass runs.

For the controlled input/checkbox page, temporary timing instrumentation measured
about 2–3 ms for a 701x421 raster, conversion, upload and WindowServer round trip.
Before the fix, key events completed without a subsequent document draw. With
the fix, key and checkbox changes were drawn within the same dispatch, about
2–14 ms after event entry. The ordinary optimized build was then checked without
instrumentation: typed text, a checked checkbox and a vertically resized viewport
were visible without an additional input event to trigger painting. These are
local-page latency checks, not a performance claim for arbitrary websites.
