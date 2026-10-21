#!/usr/bin/env python3
"""Cross-build pinned browser support libraries as internal shared-build inputs."""
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
    for key in ['toolchain', 'sdk', 'external-prefix', 'output']:
        p.add_argument('--' + key, type=Path, required=True)
    p.add_argument('--arch', choices=['i386', 'm68k', 'hppa', 'sparc'], required=True)
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--dependency-prefix', action='append', type=Path, default=[])
    p.add_argument('--only', action='append', choices=['jpeg', 'libpng', 'freetype', 'utf8proc', 'duktape', 'curl'])
    a = p.parse_args()
    tc, sdk, external, out = (x.resolve() for x in
                             [a.toolchain, a.sdk, a.external_prefix, a.output])
    out.mkdir(parents=True, exist_ok=False)
    prefix = out / 'prefix'
    prefix.mkdir()
    cc = out / 'cc'
    cc.write_text('#!/bin/sh\nexec ' + shlex.join([str(tc / 'bin/nextstep-gcc'),
                  '--sdk', str(sdk), '-arch', a.arch, '--compat-headers',
                  str(tc / 'include/nextstepcompat')]) + ' "$@"\n')
    cc.chmod(0o755)
    pins = json.loads((ROOT / 'tools/nextstep/dependencies.json').read_text())['dependencies']
    record = {'architecture': a.arch, 'toolchain_manifest_sha256':
              hashlib.sha256((tc / 'toolchain.json').read_bytes()).hexdigest(),
              'recipe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'components': {}, 'purpose': 'internal shared-library inputs'}
    prefixes = [prefix, external] + [x.resolve(strict=True) for x in a.dependency_prefix]
    includes = ' '.join('-I' + shlex.quote(str(x / 'include')) for x in prefixes)
    libraries = ' '.join('-L' + shlex.quote(str(x / 'lib')) for x in prefixes)
    env = dict(os.environ, LC_ALL='C', CC=str(cc),
               AR=str(tc / 'libexec/cctools/ar'), RANLIB=str(tc / 'libexec/cctools/ranlib'),
               CFLAGS='-O2', CPPFLAGS=includes,
               LDFLAGS=libraries,
               PKG_CONFIG_LIBDIR=':'.join(str(x / 'lib/pkgconfig') for x in prefixes),
               ZLIB_CFLAGS=includes, ZLIB_LIBS=libraries + ' -lz',
               LIBPNG_CFLAGS=includes, LIBPNG_LIBS=libraries + ' -lpng16 -lz',
               LIBS=str(tc / 'lib' / a.arch / 'libnextstepcompat.a'))
    for name in a.only or ['jpeg', 'libpng', 'freetype', 'utf8proc', 'curl']:
        pin = pins[name]
        source_input = ROOT / 'work/sources' / (name + '-' + pin['version'])
        source = out / name
        shutil.copytree(next(x for x in source_input.iterdir() if x.is_dir()), source)
        patches = ROOT / 'tools/nextstep/patches' / name
        if (patches / 'series').exists():
            for patch in (patches / 'series').read_text().splitlines():
                if patch and not patch.startswith('#'):
                    subprocess.run(['patch', '-p1', '--batch', '--fuzz=0', '-i', str(patches / patch)], cwd=source, check=True)
        steps = []
        record['components'][name] = {'source': pin, 'steps': steps}

        def run(command):
            index = len(steps)
            result = subprocess.run(command, cwd=source, env=env, capture_output=True, text=True)
            (source / ('step-' + str(index) + '.log')).write_text(result.stdout + result.stderr)
            steps.append({'command': command, 'exit_code': result.returncode})
            (out / 'BUILD.json').write_text(json.dumps(record, indent=2) + '\n')
            if result.returncode:
                print((result.stdout + result.stderr)[-5000:], flush=True)
                raise SystemExit(name + ': failed, see ' + str(source))

        if name in ['duktape', 'utf8proc']:
            src = 'src/duktape.c' if name == 'duktape' else 'utf8proc.c'
            run([str(cc), '-O2', '-std=gnu99', '-c', src, '-o', name + '.o'])
            lib = 'lib' + name + '.a'
            run([env['AR'], 'rcs', lib, name + '.o'])
            (prefix / 'lib').mkdir(exist_ok=True)
            (prefix / 'include').mkdir(exist_ok=True)
            shutil.copy2(source / lib, prefix / 'lib' / lib)
            for header in (['src/duktape.h', 'src/duk_config.h'] if name == 'duktape' else ['utf8proc.h']):
                shutil.copy2(source / header, prefix / 'include' / Path(header).name)
            if name == 'utf8proc':
                run(['make', 'libutf8proc.pc', 'prefix=' + str(prefix)])
                pc = prefix / 'lib/pkgconfig'; pc.mkdir(exist_ok=True)
                shutil.copy2(source / 'libutf8proc.pc', pc)
        else:
            configure = ['./configure', '--host=' + a.arch + '-next-nextstep3.3',
                         '--prefix=' + str(prefix), '--disable-shared', '--enable-static']
            if name == 'libpng': configure += ['--disable-arm-neon', '--disable-powerpc-vsx', '--disable-tools']
            if name == 'freetype':
                configure += ['--with-zlib=yes', '--with-png=yes', '--with-bzip2=no',
                              '--with-harfbuzz=no', '--with-brotli=no', '--with-librsvg=no']
            if name == 'curl':
                configure += ['--disable-docs', '--disable-ipv6', '--disable-ldap',
                              '--disable-threaded-resolver', '--without-libpsl',
                              '--without-libidn2', '--without-brotli', '--without-zstd',
                              '--without-nghttp2', '--without-nghttp3', '--without-libssh2',
                              '--with-openssl=' + str(external), '--with-zlib=' + str(external),
                              '--with-ca-bundle=/usr/local/ssl/cert.pem', '--without-ca-path']
            run(configure)
            run(['make', '-j' + str(a.jobs)])
            run(['make', 'install'])
        print(name + ': built and staged', flush=True)
    record['status'] = 'compiled; runtime and shared construction pending'
    (out / 'BUILD.json').write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()
