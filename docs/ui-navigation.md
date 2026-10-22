# Disposable desktop tests

## Launch from a guest-tools agent into the desktop

Verified 2026-10-21 on an isolated OPENSTEP 4.2 Intel clone with a logged-in
Workspace, VMware display, 1600x1200 resolution and the project's guest agent.
This is a test route, not part of the browser installation.

An agent child, including one started with `su`, lacks the logged-in desktop's
Mach bootstrap namespace. Such a child cannot create a DPS connection. Copying
Workspace's bootstrap port to the test child before dropping privileges allowed
NetSurf to create its Application, menu and native window. A different bootstrap
port was observed; the browser reached its event loop. This establishes launch,
not successful rendering or other browser behavior by itself.

`test/nextstep/desktop-exec.c` implements the narrowly scoped test launcher.
Compile it for the selected guest SDK/architecture. Run it as root only inside
the owned disposable clone, passing the freshly observed Workspace PID, its
account and the complete browser executable path. Do not make it setuid or
include it in a release. The target directory must be traversable by the desktop
account, and application resources and shared runtimes must already be present.

`tools/nextstep/test-openstep.py` can use this route through its
`desktop-helper=/path/to/compiled/helper` host-test argument. It captures browser
stderr, screenshots and a separate GUI result. The enclosing VM runner must
perform native halt and stopped filesystem checks even after a failed assertion.
Reacquire the desktop PID and account on every run. The optional temporary login
mode changes only the disposable clone's test account to a random one-use
password held in memory.

The fallback Workspace Finder route is not qualified: path search found the
application, but the attempted result activation did not launch it. Do not
blindly replay that route or treat finding a result as launch success.

## Controlled page and quit

From the launched browser, the test bundle's welcome resource contains a local
HTML/CSS/JavaScript fixture. Wait for both the `Native browser check` heading and
`JavaScript works` in the browser content area, then capture a screenshot.
The 2026-10-21 run showed the styled heading, green CSS block, changed paragraph
and link. Send Alt-Q while the browser is the active application and confirm its
process exits. The enclosing runner then performs native halt and filesystem
checks. This batch passed on the disposable OPENSTEP desktop. The separate
NEXTSTEP qualification route below covers additional browser interactions.


## NEXTSTEP 3.3 automated desktop batch

Verified 2026-10-21 on disposable HPPA and SPARC installed-system copies.
`prepare-qualification.py` stages the local fixture, helpers and bounded test
script. Starting state is a stopped owned clone, with matching shared runtimes.
The runner starts native multiuser services and the script waits for Workspace.
Use bounded `ps -ax` and accept both `Workspace` and `(Workspace)`; the latter
is how a swapped native process appears. Avoid username-resolution-dependent
`ps` output while NetInfo is starting. Acquire the PID afresh.

The root-only helper's `@root` mode is intended for an already real-root test
script and avoids a redundant NetInfo account lookup. The script then launches
NetSurf with its actual resources and qualification-only argument. Expected
window: `Native browser check`, followed by `Second page`, HTTP and HTTPS
fixtures. The test driver exercises view callbacks and browser actions; it is
not a recipe for injecting hardware input.

Use the host monitor for screenshots, and retain a short sequence if OCR misses
a transition. A window title alone is insufficient: the document heading,
styled block and JavaScript-modified paragraph must be visible. Reaching the
desktop does not establish that any assertion passed. The strict result checker
validates those assertions independently.

Intel CD-root copies require additional setup before normal desktop startup:
installed-device aliases, IDE mounts, display/mouse drivers, installer-completion
markers, and a fresh desktop bootstrap namespace. `prepare-desktop.py` changes
only the stopped copy and records hashes and a filesystem check. These settings
are test equipment, not an installation procedure for a user's machine.

Recovery: let the watchdog terminate a failed application, then perform native
halt and collect logs only after the emulator closes its disks. A failed boot
that cannot reach native halt must be labelled unqualified; preserve its logs
and never inspect an image while the emulator owns it.


## 68k native AppKit drawing/resize control

Verified 2026-10-21 on the owned Previous NEXTSTEP 3.3 color guest, 68040,
128 MiB, 1120x880 isolated host X display. Start from a stopped prepared clone;
`prepare-appkit-control.py` stages identical source and the optimized host-built
executable. The native guest compiler builds the other executable. Both inherit
the same freshly observed Workspace bootstrap namespace through desktop-exec.

The native control runs before the cross-built control. Each draws a green
rectangle on a white view, redisplays, resizes and exits automatically. Workspace
can overlap their windows, so capture visible document pixels and compare the
native draw/resize logs; a covered title is not a reliable identification anchor.
The source deliberately avoids Foundation, scroll views and browser code.
Readiness is the explicit draw/resize/completion sequence, not a fixed boot delay.
Normal recovery is the per-process watchdog followed by the runner's native halt.


## 68k browser qualification after the compiler fix

Verified 2026-10-21 with the optimized m68k compiler candidate. The same owned
Previous desktop route passes the 16 GUI, 11 HTTP/TLS and 16 certificate checks.
Capture fixture body text as well as the title: a page title can be present
while the document view is still empty. On dithered displays, `Scrollable
document` or `HTML and CSS rendering` can be more reliable OCR anchors than
the JavaScript line. When live OCR misses a short transition, sample the whole
recorded video and scan the samples from the end, rather than stopping after
an initial set of boot-time scene changes. Pixel review is separate from the
DOM/pasteboard and geometry assertions.

## Everyday 68k browser controls

Verified 2026-10-21. Test setup: NEXTSTEP 3.3, owned Previous color desktop,
unscaled 1120x832 client
plus emulator status strip. Use `monitor-everyday.py` or `monitor-ordinary.py`
with the suite's private display; reacquire its unique visible Previous SDL
window and focus it before host input. Never use the user's running desktop.

From a rendered browser page, Command-L selects the native location field.
Type or paste a URL, then Return; wait for the destination document body, not
just its title. Command-[ returns to the prior page. Command-Q exits the
application. Completion additionally requires the guest's native halt and
collected filesystem check. The monitor records failed transitions rather than
blindly continuing.

For an unexpected retained guest, use the external VM project's bounded
`previous-poweroff.py` with the owned lab and display. It requests native power
off and waits for the ROM monitor before closing Previous. Check image ownership
before any offline filesystem inspection.

Native field editing can enter a nested event loop. Do not synchronously call
`selectText:` from a diagnostic timer and then expect the same callback to post
the keys that end editing. Use normal command dispatch and observe readiness.
Also, `setSelectable:YES` makes a native TextField read-only: use
`setEditable:YES` for input. These are API lessons, separate from GUI test
results.
