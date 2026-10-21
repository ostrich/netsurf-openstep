#!/usr/bin/env python3
"""Prepare a disposable 68k native-vs-cross-compiler AppKit control batch."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
for name in ['project', 'toolchain', 'sdk', 'appkit', 'helpers', 'runtime-dir', 'nextufs', 'output']:
    p.add_argument('--' + name, type=Path, required=True)
p.add_argument('--display', type=int, default=256)
a = p.parse_args()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
payload = out / 'payload'
payload.mkdir()
tc = a.toolchain.resolve(strict=True)
src = ROOT / 'test/nextstep/appkit-probe.m'
command = [str(tc / 'bin/nextstep-gcc'), '--sdk', str(a.sdk.resolve(strict=True)),
           '-arch', 'm68k', '-O2', str(src), str(a.appkit.resolve(strict=True)),
           '-o', str(payload / 'cross-probe')]
result = subprocess.run(command, capture_output=True, text=True)
(out / 'cross-build.txt').write_text(result.stdout + result.stderr)
if result.returncode:
    raise SystemExit('Cross build failed; inspect cross-build.txt')
shutil.copy2(src, payload / 'probe.m')
shutil.copy2(ROOT / 'test/nextstep/run-appkit-control.sh', payload / 'run.sh')
for name in ['desktop-exec', 'watchdog']:
    shutil.copy2(a.helpers.resolve(strict=True) / name, payload / name)
(out / 'inputs.json').write_text(json.dumps({
    'command': command,
    'probe_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
    'cross_binary_sha256': hashlib.sha256((payload / 'cross-probe').read_bytes()).hexdigest(),
    'toolchain_manifest_sha256': hashlib.sha256((tc / 'toolchain.json').read_bytes()).hexdigest(),
    'purpose': 'Native AppKit control, no browser or Foundation dependency'
}, indent=2) + '\n')
subprocess.run(['python3', str(a.project.resolve() / 'tools/ports/prepare-guests.py'),
    '--output', str(out / 'lab'), '--compat', str(a.runtime_dir.resolve(strict=True)),
    '--native-tests', str(payload), '--nextufs', str(a.nextufs.resolve()),
    '--arch', 'm68k', '--display', str(a.display)], check=True)
subprocess.run(['python3', str(ROOT / 'tools/nextstep/prepare-desktop.py'),
    '--suite', str(out / 'lab'), '--arch', 'm68k', '--nextufs', str(a.nextufs.resolve())], check=True)
print('Prepared:', out / 'lab')
print('Run the external run-guests.py with --arch m68k --timeout 400.')
