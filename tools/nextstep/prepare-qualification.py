#!/usr/bin/env python3
"""Prepare a private flat NIHS GUI/network payload for the external VM runner.

Uses explicit optimized qualification builds and matching runtime libraries.
No baseline is modified. All endpoint keys and entropy seeds are disposable.
"""
import argparse
import base64
import struct
import zlib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
for key in ['project', 'toolchain', 'browser-build', 'helper-dir', 'network-probe',
            'network-server', 'fixture', 'prngd', 'egd-check', 'output']:
    p.add_argument('--' + key, type=Path, required=True)
p.add_argument('--runtime', type=Path, action='append', required=True)
a = p.parse_args()
for key, value in vars(a).items():
    if isinstance(value, Path) and key != 'output':
        setattr(a, key, value.resolve(strict=True))
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
stage = out / 'stage'
stage.mkdir()
bundle = stage / 'NetSurf.app'
subprocess.run(['python3', str(ROOT / 'tools/nextstep/assemble-bundle.py'),
                '--build', str(a.browser_build / 'i386/source'), '--output', str(bundle)], check=True)
subprocess.run([str(a.toolchain / 'libexec/cctools/lipo'), '-create',
                *[str(a.browser_build / arch / 'source/NetSurf')
                  for arch in ['i386', 'm68k', 'hppa', 'sparc']],
                '-output', str(bundle / 'NetSurf')], check=True)
shutil.copy2(a.fixture / 'ca.crt', bundle / 'ca-bundle')
payload = out / 'plain'
payload.mkdir()
with tarfile.open(payload / 'bundle.tar', 'w') as archive:
    archive.add(bundle, arcname='NetSurf.app')
for source, name in [(a.helper_dir / 'desktop-exec', 'desktop-exec'),
                     (a.helper_dir / 'watchdog', 'watchdog'),
                     (a.network_probe, 'network'), (a.network_server, 'network-server'),
                     (a.helper_dir / 'cert-identity', 'cert-identity')]:
    shutil.copy2(source, payload / name)
for name in ['ca.crt', 'valid.crt', 'valid.key', 'wrong-host.crt', 'wrong-host.key',
             'expired.crt', 'expired.key', 'untrusted.crt', 'untrusted.key']:
    shutil.copy2(a.fixture / name, payload / name)
ports = json.loads((a.fixture / 'ports.json').read_text())
(payload / 'servers.txt').write_text(''.join(
    '%s %d %s %s\n' % (name, port, cert + '.crt', cert + '.key')
    for name, port in ports.items()
    for cert in [('valid' if name in ['tls12', 'tls13'] else name)]))
(payload / 'cases.txt').write_text(''.join(
    '%s %s://127.0.0.1:%d%s %d %d %d 0\n' %
    (name, 'http' if endpoint == 'http' else 'https', ports[endpoint], path, code, status, large)
    for name, endpoint, path, code, status, large in [
        ('http', 'http', '/ok', 0, 200, 0), ('redirect', 'http', '/redirect', 0, 200, 0),
        ('chunked', 'http', '/large', 0, 200, 1), ('not-found', 'http', '/missing', 0, 404, 0),
        ('redirect-loop', 'http', '/loop', 47, 0, 0), ('tls12', 'tls12', '/ok', 0, 200, 0),
        ('tls13', 'tls13', '/ok', 0, 200, 0), ('wrong-host', 'wrong-host', '/ok', 60, 0, 0),
        ('expired', 'expired', '/ok', 60, 0, 0), ('untrusted', 'untrusted', '/ok', 60, 0, 0),
        ('reconnect', 'tls13', '/ok', 0, 200, 0)]))
# Use the independently checked host fixtures on Previous to avoid making
# guest-side TLS server performance a browser test prerequisite.
text = (payload / 'cases.txt').read_text().replace('127.0.0.1', '10.0.2.2')
(payload / 'cases.m68k.txt').write_text(text)
(payload / 'urls.m68k.txt').write_text('http://10.0.2.2:%d/page?run=%s\nhttps://10.0.2.2:%d/secure?run=%s\n' %
                                      (ports['http'], out.name, ports['tls13'], out.name))
(payload / 'urls.txt').write_text('http://127.0.0.1:%d/page\nhttps://127.0.0.1:%d/secure\n' %
                                  (ports['http'], ports['tls13']))
def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
rows = b''.join(b'\0' + bytes(v for x in range(32) for v in
               ((0, 0, 255) if ((x//8) ^ (y//8)) & 1 else (255, 255, 255))) for y in range(32))
png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 32, 32, 8, 2, 0, 0, 0)) +
       chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))
(payload / 'fixture.html').write_text(('''<html><head><title>Native browser check</title>
<style>body{margin:0;font:18px sans-serif;color:black;background:white}
h1{color:#204080;margin:10px} .sample{background:#80c080;padding:12px}
#entry{position:absolute;left:20px;top:150px;width:200px;height:24px}</style></head>
<body><h1>Native browser check</h1><p class="sample">HTML and CSS rendering</p>
<p id="js">JavaScript pending</p><script>document.getElementById('js').textContent='JavaScript works';</script>
<img style="position:absolute;left:340px;top:110px" width="32" height="32" alt="PNG" src="data:image/png;base64,PNG_DATA">
<input id="entry" value=""><p style="margin-top:100px"><a href="second.html">Second page</a></p>
<div style="height:1300px">Scrollable document</div></body></html>''').replace('PNG_DATA', base64.b64encode(png).decode()))
(payload / 'second.html').write_text('<html><head><title>Second page</title></head><body>Second page</body></html>')
(payload / 'run.sh').write_text('''#!/bin/sh
case "$0" in */*) payload=`echo "$0" | /bin/sed 's|/[^/]*$||'` ;; *) payload=. ;; esac
cd "$payload" || exit 90
directory=`/bin/pwd` || exit 90
PATH=/bin:/usr/bin:/usr/ucb:/usr/etc:/etc;export PATH
/bin/tar xf bundle.tar || exit 90
/bin/chmod 755 "$directory"
/bin/chmod -R a+rX NetSurf.app
/bin/chmod 644 fixture.html second.html urls.txt ca.crt
ifconfig lo0 inet 127.0.0.1 up || exit 90
machine=`arch`
echo GUI-MACHINE "$machine"
if test "$machine" = m68k; then
 /bin/cp cases.m68k.txt cases.txt
 /bin/cp urls.m68k.txt urls.txt
 ifconfig en0 inet 10.0.2.15 netmask 255.255.255.0 up || exit 90
fi
pids=''
test_result=1
cleanup() {
 trap 0
 for pid in $pids; do /bin/kill "$pid" 2>/dev/null; done
 for pid in $pids; do wait "$pid" 2>/dev/null; done
 exit "$test_result"
}
trap cleanup 0
if test "$machine" != m68k; then
while read name port cert key; do
 ./network-server "$port" "$name" "$cert" "$key" > server-"$name".log 2>&1 &
 pids="$pids $!"
done < servers.txt
ready=no
for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
 count=`grep -l 'SERVER READY' server-*.log | wc -l`
 if test "$count" -eq 6; then ready=yes; break; fi
 sleep 1
done
if test "$ready" != yes; then cat server-*.log; exit 91; fi
fi
failed=0
./cert-identity ca.crt valid.crt || failed=1
./watchdog 120 ./network cases.txt ca.crt || failed=1
desktop_pid=''
for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
 desktop_pid=`./watchdog 5 /bin/ps -ax | awk '$1 ~ /^[0-9]+$/ {for(i=2;i<=NF;i++) if($i == "Workspace" || $i == "(Workspace)" || (length($i)>=10 && substr($i,length($i)-9)=="/Workspace")){print $1;exit}}'`
 if test -n "$desktop_pid"; then break; fi
 sleep 1
done
if test -n "$desktop_pid"; then
 NETSURF_STARTUP_TRACE=1 ./watchdog 220 ./desktop-exec "$desktop_pid" @root "$directory/NetSurf.app/NetSurf" -v --qualification "$directory" > gui-launch.txt 2>&1
 result=$?
 echo GUI-EXIT "$result"
 cat gui-results.txt
 grep '^GUI-SUITE 0$' gui-results.txt >/dev/null
 gui_status=$?
 if test "$result" != 0 || test "$gui_status" != 0; then failed=1; fi
else
 echo GUI-DESKTOP-NOT-READY
 ps -auxw
 failed=1
fi
if test "$machine" != m68k; then cat server-*.log; fi
test_result=$failed
if test "$failed" = 0; then echo PORTS-SUITE 0; fi
exit "$test_result"
''')
command = ['python3', str(a.project / 'tools/ports/with-prngd.py'), '--payload', str(payload),
           '--daemon', str(a.prngd), '--check', str(a.egd_check), '--output', str(out / 'payload')]
for library in a.runtime:
    command += ['--library', str(library.resolve(strict=True))]
subprocess.run(command, check=True)
private = [f.name for f in (out / 'payload').iterdir()
           if f.name.endswith('.key') or f.name == 'private-entropy-seed']
(out / 'suite.json').write_text(json.dumps({'private_assets': private,
    'purpose': 'Disposable NIHS GUI and HTTP/TLS qualification',
    'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
                       for f in [Path(__file__).resolve(), ROOT / 'test/nextstep/network.c',
                                 ROOT / 'test/nextstep/network-server.c',
                                 ROOT / 'frontends/nextstep/qualification.m']}}, indent=2) + '\n')
print(out / 'payload')
