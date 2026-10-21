#!/usr/bin/env python3
"""Fetch verified baseline dependencies without modifying upstream sources."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, default=ROOT / 'work')
    p.add_argument('--only', action='append', help='Limit to a named dependency')
    p.add_argument('--jobs', type=int, default=6)
    a = p.parse_args()
    pins = json.loads((ROOT / 'tools/nextstep/dependencies.json').read_text())['dependencies']
    names = a.only or list(pins)
    for name in names:
        if name not in pins:
            p.error('Unknown dependency: ' + name)
    downloads = a.work / 'downloads'
    sources = a.work / 'sources'
    downloads.mkdir(parents=True, exist_ok=True)
    sources.mkdir(parents=True, exist_ok=True)

    def prepare(name):
        pin = pins[name]
        archive = downloads / pin['archive']
        if not archive.exists():
            temporary = archive.with_name(archive.name + '.partial')
            try:
                request = urllib.request.Request(pin['url'], headers={'User-Agent': 'NetSurf-NEXTSTEP-build'})
                with urllib.request.urlopen(request, timeout=60) as src, temporary.open('wb') as dst:
                    while block := src.read(1024 * 1024):
                        dst.write(block)
                if digest(temporary) != pin['sha256']:
                    raise ValueError(name + ': downloaded archive checksum mismatch')
                temporary.rename(archive)
            finally:
                temporary.unlink(missing_ok=True)
        if digest(archive) != pin['sha256']:
            raise ValueError(name + ': cached archive checksum mismatch')
        destination = sources / (name + '-' + pin['version'])
        if destination.exists():
            if not (destination / 'INPUT.json').is_file():
                raise ValueError('Unrecorded source directory; preserve and inspect: ' + str(destination))
            if json.loads((destination / 'INPUT.json').read_text()) != pin:
                raise ValueError(name + ': source input record changed')
        else:
            destination.mkdir()
            with tarfile.open(archive) as stream:
                stream.extractall(destination, filter='data')
            (destination / 'INPUT.json').write_text(json.dumps(pin, indent=2) + '\n')
        print(name + ': verified and prepared', flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        list(pool.map(prepare, names))


if __name__ == '__main__':
    main()
