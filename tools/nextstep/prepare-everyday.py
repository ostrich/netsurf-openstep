#!/usr/bin/env python3
"""Stage offline event-queue tests using an existing disposable PRNGD payload.

The support payload is a private, previously prepared qualification payload.
Its matching runtimes and entropy setup are reused; no host or guest is changed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--browser', type=Path, required=True, help='Qualification browser source build')
p.add_argument('--support-payload', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
payload = out / 'payload'
shutil.copytree(a.support_payload.resolve(strict=True), payload)
# Reuse only entropy preparation and owned desktop launch equipment. No old
# browser, network results, certificates or fixture endpoints are test inputs.
for f in payload.iterdir():
    if f.name in {'bundle.tar', 'run.sh', 'entropy-body.sh', 'private-entropy-seed',
                  'desktop-exec', 'watchdog', 'suite-prngd', 'suite-egd-check'} or f.name.startswith('entropy-library-'):
        continue
    if f.is_dir():
        shutil.rmtree(f)
    else:
        f.unlink()
subprocess.run(['python3', str(ROOT/'tools/nextstep/assemble-bundle.py'),
                '--build', str(a.browser.resolve(strict=True)),
                '--output', str(out/'NetSurf.app')], check=True)
with tarfile.open(payload/'bundle.tar', 'w') as archive:
    archive.add(out/'NetSurf.app', arcname='NetSurf.app')
(payload/'controls.html').write_text('''<html><head><title>Everyday controls</title>
<style>body{margin:0;font:18px sans-serif;color:black;background:white;height:20200px}
h1{font-size:26px;color:#204080;margin:10px}.sample{background:#80c080;padding:12px}
input{position:absolute;left:20px;width:200px;height:24px}
a{position:absolute;left:20px;top:240px}
#selection{position:absolute;left:20px;top:300px}
#deep{position:absolute;top:19000px;left:0;background:#e0a040;width:100%;height:180px}</style>
</head><body><h1>Everyday controls</h1><p class="sample">HTML and CSS rendering</p>
<form action="second.html"><input id="one" style="top:150px" value=""><input id="two" style="top:190px" value=""></form>
<a href="second.html">Second page</a><div id="selection">Selection sample text</div><div id="deep">Deep scroll rendering</div>
</body></html>''')
(payload/'location.html').write_bytes((payload/'controls.html').read_bytes())
(payload/'second.html').write_text('<html><head><title>Second page</title></head><body><h1>Second page</h1></body></html>')
(payload/'entropy-body.sh').write_text('''#!/bin/sh
case "$0" in */*) payload=`echo "$0" | /bin/sed 's|/[^/]*$||'` ;; *) payload=. ;; esac
cd "$payload" || exit 90
directory=`/bin/pwd` || exit 90
PATH=/bin:/usr/bin:/usr/ucb:/usr/etc:/etc;export PATH
/bin/tar xf bundle.tar || exit 90
/bin/chmod 755 "$directory"
/bin/chmod -R a+rX NetSurf.app
/bin/chmod 644 controls.html location.html second.html
desktop_pid=''
for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
 desktop_pid=`./watchdog 5 /bin/ps -ax | awk '$1 ~ /^[0-9]+$/ {for(i=2;i<=NF;i++) if($i == "Workspace" || $i == "(Workspace)" || (length($i)>=10 && substr($i,length($i)-9)=="/Workspace")){print $1;exit}}'`
 if test -n "$desktop_pid"; then break; fi
 sleep 1
done
if test -z "$desktop_pid"; then echo EVERYDAY-DESKTOP-NOT-READY; exit 91; fi
./watchdog 270 ./desktop-exec "$desktop_pid" @root "$directory/NetSurf.app/NetSurf" --everyday "$directory" > everyday-launch.txt 2>&1
result=$?
echo EVERYDAY-EXIT "$result"
cat everyday-results.txt
grep '^EVERYDAY-SUITE 0$' everyday-results.txt >/dev/null
status=$?
if test "$result" != 0 || test "$status" != 0; then cat everyday-launch.txt; exit 1; fi
echo PORTS-SUITE 0
exit 0
''')
record = {'purpose':'Private offline event-queue test; never distribute entropy seed',
          'files_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest()
                          for f in payload.iterdir() if f.is_file()}}
(out/'inputs.json').write_text(json.dumps(record,indent=2)+'\n')
print(payload)
