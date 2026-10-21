#!/usr/bin/env python3
"""Configure an owned Intel or Previous test clone for a bounded desktop batch.

Run only after the external prepare-guests.py for the selected target. Intel
is an experimental CD-root desktop profile, not yet GUI-qualified. This updates the
copied fixture, never its baseline. It bypasses CD-install detection, uses its
IDE root/work disks and lets init start the native WindowServer/loginwindow.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--suite', type=Path, required=True)
p.add_argument('--nextufs', type=Path, required=True)
p.add_argument('--arch', choices=['i386','m68k'], default='i386')
a = p.parse_args()
guest = a.suite.resolve(strict=True) / a.arch / 'guest'
ufs = a.nextufs.resolve(strict=True)
for image in (['root.raw', 'work.raw'] if a.arch == 'i386' else ['disk.img']):
    if subprocess.run(['fuser', '-s', str(guest / image)], capture_output=True).returncode != 1:
        p.error('Owned clone must be stopped')
image = guest / ('root.raw' if a.arch == 'i386' else 'disk.img')
changes = {}


def read(path):
    return subprocess.check_output([str(ufs), 'browse', '--raw', str(image), path])


def put(path, text, mode='0644'):
    source = guest / ('desktop-' + path.replace('/', '_'))
    source.write_bytes(text)
    old = subprocess.run([str(ufs), 'browse', '--raw', str(image), path], capture_output=True)
    if old.returncode == 0:
        subprocess.run([str(ufs), 'mkfile', '--unlink', str(image), path], check=True, capture_output=True)
    subprocess.run([str(ufs), 'mkfile', '--from-file', str(image), path, str(source)], check=True, capture_output=True)
    subprocess.run([str(ufs), 'mkfile', '--chmod', str(image), path, mode], check=True, capture_output=True)
    if read(path) != text:
        raise RuntimeError('Readback mismatch: ' + path)
    changes[path] = hashlib.sha256(text).hexdigest()


if a.arch == 'm68k':
    rc = read('/private/etc/rc.local')
    if b'/bin/sh /port-test/run.sh &' not in rc:
        p.error('Expected owned Previous batch hook')
    prefix = b"""# Disposable desktop identity; never apply to a user guest.
/port-test/watchdog 10 /usr/bin/niutil -createprop . /users/root passwd ""
/port-test/watchdog 10 /usr/bin/niutil -createprop . /users/root shell /bin/csh
/port-test/watchdog 5 /usr/bin/dwrite loginwindow DefaultUser root
/port-test/watchdog 5 /usr/bin/dwrite loginwindow LoginPanel NO
"""
    put('/private/etc/rc.local', rc.replace(b'/bin/sh /port-test/run.sh &', prefix + b'/bin/sh /port-test/run.sh &'), '0755')
    result = subprocess.run([str(ufs), 'fsck', '-n', str(image)], capture_output=True)
    (guest / 'desktop-preboot.fsck.log').write_bytes(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError('Desktop preparation filesystem check failed')
    (guest / 'desktop-profile.json').write_text(json.dumps({'changes_sha256': changes,
        'scope': 'Owned Previous copy; temporary passwordless root desktop'}, indent=2) + '\n')
    print(guest)
    raise SystemExit(0)


for name in ['rc', 'rc.boot']:
    path = '/private/etc/' + name
    content = read(path)
    marker = b'if [ -d /NextCD -a -f /private/etc/rc.cdrom ]; then'
    if content.count(marker) != 1:
        p.error('Unexpected copied CD-detection script: ' + name)
    put(path, content.replace(marker, b'if false; then # Disposable installed-root fixture'), '0755')
# The CD-root copy lacks the installed-system alias required by driverLoader.
if subprocess.run([str(ufs), 'browse', '--json', str(image), '/private/Devices'], capture_output=True).returncode:
    subprocess.run([str(ufs), 'mkfile', '--symlink', str(image), 'Drivers/i386', '/private/Devices'], check=True, capture_output=True)
put('/private/Drivers/i386/System.config/Instance0.table',
    b'"Version" = "3.30";\n"Boot Drivers" = "PS2Keyboard EISABus PCIBus";\n'
    b'"Active Drivers" = "VGA PS2Mouse";\n"Kernel" = "mach_kernel";\n'
    b'"Kernel Flags" = "rootdev=hd0a";\n"Boot Graphics" = "No";\n"Install Mode" = "No";\n')
if subprocess.run([str(ufs), 'browse', '--json', str(image), '/ports-work'], capture_output=True).returncode:
    subprocess.run([str(ufs), 'mkfile', '--mkdir', str(image), '/ports-work'], check=True, capture_output=True)
# loginwindow treats missing installer-completion markers as a CD session.
put('/private/adm/BuildDisk.custom', b'')
put('/private/adm/CDIS.custom', b'')
put('/private/etc/fstab', b'/dev/hd0a / 4.3 rw,noquota,noauto 0 1\n')
put('/private/etc/hostconfig', b'HOSTNAME=ns33-test\nINETADDR=127.0.0.1\nROUTER=-NO-\nIPNETMASK=-AUTOMATIC-\nIPBROADCAST=-AUTOMATIC-\nNETMASTER=-NO-\nYPDOMAIN=-NO-\nTIME=-NO-\n')
put('/private/etc/rc.local', b'''#!/bin/sh
# Owned disposable desktop batch, after native startup.
/ports-work/ports-test/watchdog 10 /usr/bin/niutil -createprop . /users/root passwd ""
/ports-work/ports-test/watchdog 10 /usr/bin/niutil -createprop . /users/root shell /bin/csh
/ports-work/ports-test/watchdog 5 /usr/bin/dremove loginwindow Install
/ports-work/ports-test/watchdog 5 /usr/bin/dwrite loginwindow DefaultUser root
/ports-work/ports-test/watchdog 5 /usr/bin/dwrite loginwindow LoginPanel NO
/usr/etc/driverLoader D=VGA > /ports-work/ports-test/display-driver.txt 2>&1
/usr/etc/driverLoader D=PS2Mouse >> /ports-work/ports-test/display-driver.txt 2>&1
(
 # This copied CD root has no installed user's desktop registration.
 # Start a real Workspace in loginwindow's freshly acquired namespace.
 for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  loginpid=`/bin/ps -ax | awk '/[(]loginwindow[)]/ {print $1;exit}'`
  if test -n "$loginpid"; then break; fi
  sleep 1
 done
 if test -n "$loginpid"; then
  /ports-work/ports-test/desktop-exec "$loginpid" @root /usr/lib/NextStep/Workspace.app/Workspace -LoginProgram YES > /ports-work/ports-test/workspace-launch.txt 2>&1 &
 fi
 /bin/sh /ports-work/ports-test/run.sh > /ports-work/ports-test/results.txt 2>&1
 /bin/sync
 /usr/etc/halt -l -e
) &
''', '0755')
put('/ports-tests.sh', b'''#!/bin/sh
/etc/mount -n -o remount,rw /dev/hd0a / || exit 90
/etc/mount -n /dev/hd1a /ports-work || exit 90
/bin/chmod 1777 /private/tmp
/usr/bin/touch /private/vm/swapfile || exit 91
/bin/chmod 1600 /private/vm/swapfile || exit 91
# The host then exits the single-user parent shell, so init continues normally.
''', '0755')
result = subprocess.run([str(ufs), 'fsck', '-n', str(image)], capture_output=True)
(guest / 'desktop-preboot.fsck.log').write_bytes(result.stdout + result.stderr)
if result.returncode:
    raise RuntimeError('Desktop preparation filesystem check failed')
(guest / 'desktop-profile.json').write_text(json.dumps({'changes_sha256': changes,
    'run_argument': '--intel-multiuser', 'scope': 'Owned copied fixture only'}, indent=2) + '\n')
print(guest)
