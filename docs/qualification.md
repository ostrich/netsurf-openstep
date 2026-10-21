# NEXTSTEP qualification

These tests exercise the native NEXTSTEP frontend and its actual networking
libraries in disposable NEXTSTEP 3.3 guests. They use controlled pages and a
private test CA. They do not establish compatibility with arbitrary modern
websites, complete TLS conformance or readiness for release packaging.

## Results, 2026-10-21

| Target | Ordinary startup | Certificate identity | HTTP/TLS | Native GUI |
| --- | --- | --- | --- | --- |
| Intel | 13 passed | 16 passed | 11 passed | Blocked by desktop fixture |
| NeXT 68k | 13 passed | 16 passed | 11 passed | Incomplete: display/resize stall |
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

On 68k, document loading, JavaScript/pasteboard assertions and form callbacks
succeeded, but the displayed window remained blank and the resize operation
stalled until the watchdog. The ordinary startup and real external HTTP/TLS
checks passed. This remains an application/AppKit/compiler/emulator boundary
to isolate; it is not attributed to Previous without further evidence. The GUI
batch correctly reports failure and performs native shutdown afterward.

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
