#!/usr/bin/env python3
"""Build an optimized native NEXTSTEP browser in an isolated work directory.

Dependency prefixes and original SDK import libraries are explicit inputs.
This integration build is not a release or shared-library qualification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ['toolchain', 'sdk', 'appkit', 'foundation', 'host-tools', 'output']:
        p.add_argument('--' + key, required=True, type=Path)
    p.add_argument('--prefix', required=True, action='append', type=Path)
    p.add_argument('--arch', choices=['i386', 'm68k', 'hppa', 'sparc'], required=True)
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--qualification', action='store_true', help='Include the opt-in native GUI test driver')
    a = p.parse_args()
    tc, sdk = a.toolchain.resolve(strict=True), a.sdk.resolve(strict=True)
    prefixes = [x.resolve(strict=True) for x in a.prefix]
    # Check actual archive slices, not the names of their directories. Fail
    # before compiling if a parallel lane selected the wrong target inputs.
    input_hashes = {}
    for prefix in prefixes:
        for archive in sorted((prefix / 'lib').glob('*.a')):
            result = subprocess.run([str(tc / 'libexec/cctools/lipo'), str(archive),
                                     '-verify_arch', a.arch], capture_output=True)
            if result.returncode:
                p.error(str(archive) + ': no ' + a.arch + ' slice')
            input_hashes[str(archive)] = hashlib.sha256(archive.read_bytes()).hexdigest()
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    tree = out / 'source'
    shutil.copytree(ROOT, tree, symlinks=True, ignore=shutil.ignore_patterns('.git', 'work', 'build', '__pycache__', 'NetSurf', 'NetSurf.app'))
    source_hashes = {str(path.relative_to(tree)): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sorted(tree.rglob('*')) if path.is_file()}
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    cc = out / 'cc'
    cc.write_text('#!/bin/sh\nexec ' + shlex.join([str(tc / 'bin/nextstep-gcc'),
                  '--sdk', str(sdk), '-arch', a.arch, '--compat-headers',
                  str(tc / 'include/nextstepcompat')]) + ' "$@"\n')
    cc.chmod(0o755)
    manifest = json.loads((tc / 'toolchain.json').read_text())
    version = manifest['gcc_version']
    command = ['make', '-k', '-j' + str(a.jobs), 'TARGET=nextstep', 'HOST=NeXT',
               'NEXTSTEP_CC=' + str(cc), 'CC=' + str(cc), 'BUILD_CC=cc', 'CCACHE=',
               'CC_SPECS=libgcc', 'CC_VERSION=' + version, 'TOOLCHAIN=gcc',
               'CC_MAJOR=' + version.split('.')[0], 'CC_MINOR=' + version.split('.')[1],
               'NEXTSTEP_DEP_CFLAGS=' + ' '.join('-I' + str(x / 'include') for x in prefixes),
               'NEXTSTEP_DEP_LDFLAGS=' + ' '.join('-L' + str(x / 'lib') for x in prefixes),
               'NEXTSTEP_APPKIT=' + str(a.appkit.resolve(strict=True)),
               'NEXTSTEP_FOUNDATION=' + str(a.foundation.resolve(strict=True))]
    if a.qualification:
        command += ['NEXTSTEP_QUALIFY=YES']
    env = dict(os.environ, LC_ALL='C',
               PATH=str(a.host_tools.resolve(strict=True) / 'bin') + ':' + os.environ['PATH'],
               PKG_CONFIG_LIBDIR=':'.join(str(x / 'lib/pkgconfig') for x in prefixes))
    record = {'toolchain_manifest_sha256': hashlib.sha256((tc / 'toolchain.json').read_bytes()).hexdigest(),
              'source_revision': revision, 'source_files_sha256': source_hashes,
              'architecture': a.arch, 'command': command,
              'archive_sha256': input_hashes,
              'prefixes': [str(x) for x in prefixes], 'purpose': 'integration build'}
    (out / 'BUILD.json').write_text(json.dumps(record, indent=2) + '\n')
    with (out / 'build.log').open('w') as log:
        run = subprocess.run(command, cwd=tree, env=env, stdout=log, stderr=subprocess.STDOUT)
    record['exit_code'] = run.returncode
    (out / 'BUILD.json').write_text(json.dumps(record, indent=2) + '\n')
    if run.returncode:
        print((out / 'build.log').read_text()[-7000:])
    raise SystemExit(run.returncode)


if __name__ == '__main__':
    main()
