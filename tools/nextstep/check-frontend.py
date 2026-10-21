#!/usr/bin/env python3
"""Compile the native frontend against the selected SDK on all four targets.

This is an API/build check, not a replacement for guest runtime tests.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ['frontends/nextstep/' + x + '.m' for x in
           ['schedule', 'clipboard', 'PlotView', 'BrowserWindowController', 'main', 'smoke', 'text']]
SOURCES += ['frontends/openstep/' + x + '.m' for x in
            ['FrameBufferRenderer', 'tables/fetch', 'tables/window']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ['toolchain', 'sdk', 'include-prefix', 'output']:
        parser.add_argument('--' + option, required=True, type=Path,
                            **({'action': 'append'} if option == 'include-prefix' else {}))
    args = parser.parse_args()
    tc = args.toolchain.resolve(strict=True)
    sdk = args.sdk.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    includes = [ROOT, ROOT / 'include', ROOT / 'frontends',
                ROOT / 'frontends/openstep']
    includes += [x.resolve() / 'include' for x in args.include_prefix]
    includes += [x.resolve() / 'include/freetype2' for x in args.include_prefix
                 if (x / 'include/freetype2').is_dir()]
    base = [str(tc / 'bin/nextstep-gcc'), '--sdk', str(sdk), '-O2', '-std=gnu99',
            '-DNETSURF_NEXTSTEP', '-DFB_USE_FREETYPE', '-Wall', '-Wextra', '-Werror=implicit-function-declaration']
    base += ['-I' + str(path) for path in includes]

    def compile_arch(arch):
        results = []
        for source in SOURCES:
            stem = source.replace('/', '_').removesuffix('.m')
            command = base + ['-arch', arch, '-c', str(ROOT / source),
                              '-o', str(output / (arch + '-' + stem + '.o'))]
            run = subprocess.run(command, capture_output=True, text=True)
            (output / (arch + '-' + stem + '.log')).write_text(run.stdout + run.stderr)
            results.append({'source': source, 'command': command, 'exit_code': run.returncode})
        print(arch + ': ' + str(sum(x['exit_code'] == 0 for x in results)) +
              '/' + str(len(results)) + ' compiled', flush=True)
        return arch, results

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        targets = dict(pool.map(compile_arch, ['i386', 'm68k', 'hppa', 'sparc']))
    record = {'toolchain_manifest_sha256': hashlib.sha256((tc / 'toolchain.json').read_bytes()).hexdigest(),
              'source_sha256': {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in SOURCES},
              'targets': targets}
    (output / 'BUILD.json').write_text(json.dumps(record, indent=2) + '\n')
    raise SystemExit(any(row['exit_code'] for rows in targets.values() for row in rows))


if __name__ == '__main__':
    main()
