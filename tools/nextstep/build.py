#!/usr/bin/env python3
"""Build the NEXTSTEP port with explicit SDK and qualified dependency inputs.

One output directory holds the host tools, target builds and bundles. Nothing
is installed or published. Original SDKs and external libraries remain private.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import shutil

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
ARCHES = ['m68k', 'i386', 'hppa', 'sparc']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--arch', action='append', choices=ARCHES)
    p.add_argument('--jobs', type=int, default=8)
    a = p.parse_args()
    if a.jobs < 1:
        p.error('--jobs must be positive')
    config = json.loads(a.config.read_text())
    required = {'toolchain', 'sdk', 'appkit', 'foundation', 'external_prefixes'}
    if set(config) != required:
        p.error('config keys must be: ' + ', '.join(sorted(required)))
    selected = list(dict.fromkeys(a.arch or ARCHES))
    missing = [name for name in ['cc', 'make', 'pkg-config', 'perl', 'flex', 'bison', 'gperf', 'patch']
               if shutil.which(name) is None]
    if missing:
        p.error('Missing host tools: ' + ', '.join(missing))
    if any(arch not in config['external_prefixes'] for arch in selected):
        p.error('external_prefixes must contain every selected architecture')
    paths = {key: Path(config[key]).expanduser().resolve(strict=True)
             for key in required - {'external_prefixes'}}
    prefixes = {arch: Path(config['external_prefixes'][arch]).expanduser().resolve(strict=True)
                for arch in selected}
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    record = {'toolchain_manifest_sha256': hashlib.sha256(
              (paths['toolchain'] / 'toolchain.json').read_bytes()).hexdigest(),
              'targets': {}, 'status': 'building', 'purpose': 'integration; not release qualification'}
    (out / 'BUILD.json').write_text(json.dumps(record, indent=2) + '\n')

    def run(command, log):
        with log.open('w') as stream:
            subprocess.run(list(map(str, command)), cwd=ROOT, stdout=stream,
                           stderr=subprocess.STDOUT, check=True)

    run([sys.executable, TOOLS / 'prepare.py'], out / 'prepare.log')
    host = out / 'host'
    host.mkdir()
    shutil.copytree(ROOT / 'work/sources/nsgenbind-0.9/nsgenbind-0.9', host / 'nsgenbind')
    command = ['make', '-C', str(host / 'nsgenbind'), '-j' + str(a.jobs),
               'NSSHARED=' + str(ROOT / 'work/sources/netsurf-buildsystem-1.10/buildsystem-1.10'),
               'PREFIX=' + str(host / 'prefix'), 'WARNFLAGS=-Wall -Wextra']
    run(command, host / 'build.log')
    run(command + ['install'], host / 'install.log')
    workers = min(len(selected), a.jobs)
    per_target = max(1, a.jobs // workers)
    common = ['--toolchain', paths['toolchain'], '--sdk', paths['sdk']]

    def build(arch):
        directory = out / arch
        directory.mkdir()
        print(arch + ': building dependencies', flush=True)
        try:
            run([sys.executable, TOOLS / 'build-libraries.py', *common, '--arch', arch,
                 '--dependency-prefix', prefixes[arch], '--output', directory / 'libraries',
                 '--jobs', str(per_target)], directory / 'libraries.log')
            run([sys.executable, TOOLS / 'build-support.py', *common, '--arch', arch,
                 '--external-prefix', prefixes[arch], '--output', directory / 'support',
                 '--jobs', str(per_target)], directory / 'support.log')
            print(arch + ': building browser', flush=True)
            run([sys.executable, TOOLS / 'build-browser.py', *common, '--arch', arch,
                 '--appkit', paths['appkit'], '--foundation', paths['foundation'],
                 '--host-tools', host / 'prefix', '--prefix', directory / 'libraries/prefix',
                 '--prefix', directory / 'support/prefix', '--prefix', prefixes[arch],
                 '--output', directory / 'browser', '--jobs', str(per_target)], directory / 'browser.log')
            run([sys.executable, TOOLS / 'assemble-bundle.py', '--build', directory / 'browser/source',
                 '--output', directory / 'NetSurf.app'], directory / 'bundle.log')
            print(arch + ': built', flush=True)
            return arch, {'status': 'built; guest tests pending'}
        except subprocess.CalledProcessError as error:
            print(arch + ': failed; inspect ' + str(directory), flush=True)
            return arch, {'status': 'failed', 'command': list(map(str, error.cmd))}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for arch, result in pool.map(build, selected):
            record['targets'][arch] = result
    failed = any(row['status'] == 'failed' for row in record['targets'].values())
    record['status'] = 'failed' if failed else 'built; guest tests pending'
    (out / 'BUILD.json').write_text(json.dumps(record, indent=2) + '\n')
    raise SystemExit(failed)


if __name__ == '__main__':
    main()
