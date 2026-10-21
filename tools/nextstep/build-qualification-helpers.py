#!/usr/bin/env python3
"""Build optimized NIHS test helpers against the browser's dependency inputs."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--config', type=Path, required=True, help='Same private config used by build.py')
p.add_argument('--dependencies', type=Path, required=True, help='Build root with ARCH/support/prefix')
p.add_argument('--project', type=Path, required=True, help='External VM project with tools/ports/timeout.c')
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
config = json.loads(a.config.read_text())
tc = Path(config['toolchain']).resolve(strict=True)
sdk = Path(config['sdk']).resolve(strict=True)
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
sources = {'network': ROOT / 'test/nextstep/network.c',
           'network-server': ROOT / 'test/nextstep/network-server.c',
           'cert-identity': ROOT / 'test/nextstep/cert-identity.c',
           'desktop-exec': ROOT / 'test/nextstep/desktop-exec.c',
           'watchdog': a.project.resolve() / 'tools/ports/timeout.c'}


def build(arch):
    directory = out / arch
    directory.mkdir()
    support = a.dependencies.resolve() / arch / 'support/prefix'
    external = Path(config['external_prefixes'][arch]).resolve(strict=True)
    records = []
    for name, source in sources.items():
        command = [str(tc / 'bin/nextstep-gcc'), '--sdk', str(sdk), '-arch', arch,
                   '-O2', '-std=gnu99', '-Wall', '-Wextra']
        if name.startswith('network') or name == 'cert-identity':
            command += ['--compat-headers', str(tc / 'include/nextstepcompat'),
                        '-I' + str(support / 'include'), '-I' + str(external / 'include'), '-I' + str(ROOT), '-DNeXT']
        command += [str(source)]
        if name == 'network':
            command += [str(support / 'lib/libcurl.a')]
        if name.startswith('network') or name == 'cert-identity':
            command += ['-L' + str(external / 'lib'), '-lssl', '-lcrypto', '-lz',
                        str(tc / 'lib' / arch / 'libnextstepcompat.a')]
        command += ['-o', str(directory / name)]
        run = subprocess.run(command, capture_output=True, text=True)
        (directory / (name + '.log')).write_text(run.stdout + run.stderr)
        records.append({'command': command, 'exit_code': run.returncode})
        if run.returncode:
            raise RuntimeError(arch + ': ' + name + ' failed; inspect helper log')
    print(arch + ': helpers built', flush=True)
    return arch, records


with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    targets = dict(pool.map(build, ['i386', 'm68k', 'hppa', 'sparc']))
for name in sources:
    subprocess.run([str(tc / 'libexec/cctools/lipo'), '-create',
                    *[str(out / arch / name) for arch in targets], '-output', str(out / name)], check=True)
(out / 'BUILD.json').write_text(json.dumps({
    'toolchain_manifest_sha256': hashlib.sha256((tc / 'toolchain.json').read_bytes()).hexdigest(),
    'source_sha256': {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sources.items()},
    'targets': targets}, indent=2) + '\n')
