#!/usr/bin/env python3
"""Assemble an integration-test application bundle from a successful build."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--build', type=Path, required=True, help='Integration source tree containing NetSurf')
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
source = a.build.resolve(strict=True)
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
resources = out / 'Resources'
resources.mkdir()
shutil.copy2(source / 'NetSurf', out / 'NetSurf')
res = source / 'frontends/openstep/res'
for name in ['NetSurf.tiff', 'ca-bundle']:
    shutil.copy2(res / name, out / name)
for name in ['Left.tiff', 'Right.tiff', 'Reload.tiff', 'Stop.tiff']:
    shutil.copy2(res / name, resources / name)
shutil.copytree(res / 'fonts', resources / 'Fonts')
for path in (source / 'resources').glob('*'):
    if path.is_file() and path.suffix in ['.css', '.png', '.html']:
        shutil.copy2(path, out / path.name)
for name in ['Messages', 'welcome.html', 'credits.html', 'licence.html']:
    shutil.copy2(source / 'resources/en' / name, out / name)
shutil.copytree(res / 'licenses', resources / 'Licenses')
shutil.copy2(source / 'COPYING', resources / 'Licenses/NetSurf-COPYING')
(out / 'Info.table').write_text('{\n  "ApplicationName" = "NetSurf";\n  "ApplicationIcon" = "NetSurf.tiff";\n}\n')
record = {'purpose': 'integration test; not a qualified release',
          'files': {str(x.relative_to(out)): hashlib.sha256(x.read_bytes()).hexdigest()
                    for x in sorted(out.rglob('*')) if x.is_file()}}
(resources / 'Build.json').write_text(json.dumps(record, indent=2) + '\n')
print(out)
