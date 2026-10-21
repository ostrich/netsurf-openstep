#!/usr/bin/env python3
"""Build pristine NetSurf library inputs with an explicitly selected toolchain.

These archives are internal inputs for shared-library construction, not the
application's final static-link policy. Host generators always use host tools.
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
ORDER = ['libwapcaplet', 'libparserutils', 'libhubbub', 'libnsutils', 'libnslog',
         'libnsbmp', 'libnsgif', 'libcss', 'libdom', 'libsvgtiny', 'libnsfb']


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ['toolchain', 'sdk', 'output']:
        p.add_argument('--' + key, required=True, type=Path)
    p.add_argument('--work', type=Path, default=ROOT / 'work')
    p.add_argument('--arch', choices=['i386', 'm68k', 'hppa', 'sparc'], required=True)
    p.add_argument('--only', action='append', choices=ORDER)
    p.add_argument('--jobs', type=int, default=2)
    p.add_argument('--dependency-prefix', action='append', type=Path, default=[],
                   help='Qualified dependency prefix containing include/ and lib/')
    a = p.parse_args()
    tc, sdk, out = a.toolchain.resolve(), a.sdk.resolve(), a.output.resolve()
    if out.exists():
        p.error('Preserve existing build evidence; select a new output directory')
    out.mkdir(parents=True)
    prefix = out / 'prefix'
    prefix.mkdir()
    pins = json.loads((ROOT / 'tools/nextstep/dependencies.json').read_text())['dependencies']
    buildsystem = a.work.resolve() / 'sources/netsurf-buildsystem-1.10/buildsystem-1.10'
    cc = out / 'cc'
    cc.write_text('#!/bin/sh\nexec ' + shlex.join([str(tc / 'bin/nextstep-gcc'),
                  '--sdk', str(sdk), '-arch', a.arch,
                  '--compat-headers', str(tc / 'include/nextstepcompat')]) + ' "$@"\n')
    cc.chmod(0o755)
    dependencies = [x.resolve(strict=True) for x in a.dependency_prefix]
    includes = ' '.join('-I' + shlex.quote(str(x / 'include')) for x in dependencies)
    libraries = ' '.join('-L' + shlex.quote(str(x / 'lib')) for x in dependencies)
    record = {'dependency_prefixes': [str(x) for x in dependencies],
              'toolchain_manifest_sha256': digest(tc / 'toolchain.json'),
              'sdk_import_sha256': digest(sdk / 'lib/libsys_s.a'),
              'architecture': a.arch, 'recipe_sha256': digest(Path(__file__)),
              'purpose': 'internal shared-library inputs', 'components': {}}
    for name in a.only or ORDER:
        pin = pins[name]
        archive = a.work / 'downloads' / pin['archive']
        if digest(archive) != pin['sha256']:
            p.error(name + ': upstream archive hash mismatch')
        container = a.work / 'sources' / (name + '-' + pin['version'])
        pristine = next(x for x in container.iterdir() if x.is_dir())
        source = out / name
        shutil.copytree(pristine, source)
        patches = ROOT / 'tools/nextstep/patches' / name
        if (patches / 'series').exists():
            for patch in (patches / 'series').read_text().splitlines():
                if patch and not patch.startswith('#'):
                    subprocess.run(['patch', '-p1', '--batch', '--fuzz=0', '-i',
                                    str(patches / patch)], cwd=source, check=True)
        env = dict(os.environ, LC_ALL='C', CC=str(cc), BUILD_CC='cc',
                   AR=str(tc / 'libexec/cctools/ar'), RANLIB=str(tc / 'libexec/cctools/ranlib'),
                   CFLAGS='-O2 -fno-builtin-sin -fno-builtin-cos -fno-builtin-ceil -I' + str(prefix / 'include') + ' ' + includes + ' -ffile-prefix-map=' + str(source) + '=' + name,
                   LDFLAGS='-L' + str(prefix / 'lib') + ' ' + libraries, PKG_CONFIG_LIBDIR=str(prefix / 'lib/pkgconfig'))
        version = json.loads((tc / 'toolchain.json').read_text())['gcc_version']
        common = ['make', '-j' + str(a.jobs), 'HOST=' + a.arch + '-next-nextstep3.3',
                  'NSSHARED=' + str(buildsystem), 'PREFIX=' + str(prefix),
                  'CCACHE=', 'toolchain=gcc', 'GCC_VERSION=' + version,
                  'ccvsn=' + version, 'GCCVER=' + version.split('.')[0],
                  'CC_CAN_BUILD_AND_DEP=no', 'CC_CANNOT_DEP=yes',
                  'WARNFLAGS=-Wall -Wextra', 'INSTALL=install']
        if name == 'libdom':
            common += ['WITH_EXPAT_BINDING=yes', 'WITH_LIBXML_BINDING=no']
        if name == 'libnsfb':
            common += [key + '=no' for key in ['NSFB_SDL_AVAILABLE', 'NSFB_XCB_AVAILABLE',
                                              'NSFB_VNC_AVAILABLE', 'NSFB_WLD_AVAILABLE']]
        steps = []
        component = {'source': pin, 'steps': steps}
        record['components'][name] = component
        for operation in [[], ['install']]:
            command = common + operation
            result = subprocess.run(command, cwd=source, env=env, capture_output=True, text=True)
            log = source / ('build.log' if not operation else 'install.log')
            log.write_text(result.stdout + result.stderr)
            steps.append({'command': command, 'exit_code': result.returncode})
            (out / 'BUILD.json').write_text(json.dumps(record, indent=2) + '\n')
            if result.returncode:
                print(log.read_text()[-5000:], flush=True)
                raise SystemExit(name + ': failed; inspect ' + str(log))
        for archive in (prefix / 'lib').glob('*.a'):
            subprocess.run([str(tc / 'libexec/cctools/lipo'), str(archive),
                            '-verify_arch', a.arch], check=True)
        component['status'] = 'built'
        print(name + ': built and staged', flush=True)
    record['status'] = 'built; runtime and shared construction pending'
    (out / 'BUILD.json').write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()
