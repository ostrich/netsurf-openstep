#!/usr/bin/env python3
"""Prepare a flat payload for disposable NIHS startup tests.

Use the VM project's existing prepare-guests.py/run-guests.py to run it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

p = argparse.ArgumentParser(description=__doc__)
for name in ['toolchain', 'bundle', 'output']:
    p.add_argument('--' + name, type=Path, required=True)
p.add_argument('--binary', action='append', required=True, help='ARCH=/path/to/NetSurf')
p.add_argument('--runtime', action='append', type=Path, required=True)
p.add_argument('--gui-helpers', type=Path, help='Also test the ordinary m68k desktop; desktop-exec and watchdog directory')
p.add_argument('--gui-fixture', type=Path, help='Matching controls.html and second.html directory')
a = p.parse_args()
if bool(a.gui_helpers) != bool(a.gui_fixture):
    p.error('--gui-helpers and --gui-fixture must be supplied together')
tc = a.toolchain.resolve(strict=True)
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
stage = out / 'stage'
stage.mkdir()
bundle = stage / 'NetSurf.app'
shutil.copytree(a.bundle.resolve(strict=True), bundle)
binaries = {}
for value in a.binary:
    arch, separator, path = value.partition('=')
    if not separator or arch not in ['i386', 'm68k', 'hppa', 'sparc'] or arch in binaries:
        p.error('--binary must specify a unique supported ARCH=PATH')
    binaries[arch] = Path(path).resolve(strict=True)
    subprocess.run([str(tc / 'libexec/cctools/lipo'), str(binaries[arch]), '-verify_arch', arch], check=True)
(bundle / 'NetSurf').unlink()
subprocess.run([str(tc / 'libexec/cctools/lipo'), '-create', *map(str, binaries.values()),
                '-output', str(bundle / 'NetSurf')], check=True)
record = {'purpose': 'NIHS startup tests; not release qualification',
          'targets': {arch: hashlib.sha256(path.read_bytes()).hexdigest() for arch, path in binaries.items()},
          'runtimes': {}}
runtimes = stage / 'runtimes'
runtimes.mkdir()
for path in a.runtime:
    path = path.resolve(strict=True)
    if not re.fullmatch(r'lib[A-Za-z0-9_.-]+\.shlib', path.name):
        p.error('Unexpected runtime name: ' + path.name)
    if path.name in record['runtimes']:
        p.error('Duplicate runtime: ' + path.name)
    shutil.copy2(path, runtimes / path.name)
    record['runtimes'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
(bundle / 'Resources/Build.json').write_text(json.dumps(record, indent=2) + '\n')
payload = out / 'payload'
payload.mkdir()


def normalize(member):
    member.uid = member.gid = 0
    member.uname = member.gname = 'root'
    return member


with tarfile.open(payload / 'bundle.tar', 'w', format=tarfile.USTAR_FORMAT) as archive:
    for path in stage.iterdir():
        archive.add(path, arcname=path.name, filter=normalize)
(payload / 'run.sh').write_text('''#!/bin/sh
# Disposable guest startup tests.
case "$0" in */*) payload=`echo "$0" | /bin/sed 's|/[^/]*$||'` ;; *) payload=. ;; esac
cd "$payload" || exit 80
/bin/tar xf bundle.tar || exit 81
for lib in runtimes/*.shlib; do
  /bin/cp "$lib" /usr/local/lib/ports-runtime.new || exit 82
  name=`echo "$lib" | /bin/sed 's|.*/||'`
  /bin/mv /usr/local/lib/ports-runtime.new /usr/local/lib/"$name" || exit 83
done
./NetSurf.app/NetSurf --smoke-test > smoke.log 2>&1
status=$?
/bin/cat smoke.log
echo NETSURF-EXIT "$status"
test "$status" = 0 || exit 84
echo PORTS-SUITE 0
''')
(payload / 'run.sh').chmod(0o755)
if a.gui_helpers:
    for name in ['desktop-exec', 'watchdog']:
        shutil.copy2(a.gui_helpers / name, payload / name)
    for name in ['controls.html', 'second.html']:
        shutil.copy2(a.gui_fixture / name, payload / name)
    record['gui_inputs_sha256'] = {name: hashlib.sha256((payload / name).read_bytes()).hexdigest()
        for name in ['desktop-exec', 'watchdog', 'controls.html', 'second.html']}
    script = payload / 'run.sh'
    gui = '''if test "`arch`" = m68k; then
 directory=`/bin/pwd` || exit 85
 desktop_pid=''
 attempt=0
 while test "$attempt" -lt 60; do
  attempt=`expr "$attempt" + 1`
  desktop_pid=`./watchdog 5 /bin/ps -ax | awk '$1 ~ /^[0-9]+$/ {for(i=2;i<=NF;i++) if($i == "Workspace" || $i == "(Workspace)" || (length($i)>=10 && substr($i,length($i)-9)=="/Workspace")){print $1;exit}}'`
  if test -n "$desktop_pid"; then break; fi
  sleep 1
 done
 if test -z "$desktop_pid"; then echo ORDINARY-DESKTOP-NOT-READY; exit 85; fi
 ./watchdog 180 ./desktop-exec "$desktop_pid" @root "$directory/NetSurf.app/NetSurf" "file://$directory/controls.html" > ordinary-launch.txt 2>&1
 status=$?
 echo ORDINARY-GUI-EXIT "$status"
 if test "$status" != 0; then cat ordinary-launch.txt; exit 86; fi
fi
'''
    script.write_text(script.read_text().replace('echo PORTS-SUITE 0', gui + 'echo PORTS-SUITE 0'))
(out / 'INPUTS.json').write_text(json.dumps(record, indent=2) + '\n')
print(payload)
