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
checks. This batch passed on the disposable OPENSTEP desktop; NEXTSTEP 3.3 GUI
sessions and other browser interactions are not yet qualified.
