#!/usr/bin/env python3
"""Require complete control, rendering-checkpoint and clean-shutdown evidence.

Screenshots are required for separate visual review; their presence alone does
not assert that their pixels are correct.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import re
import subprocess

CHECKS = {
    'command-L-location-editor', 'native-location-paste', 'return-focuses-document',
    'queued-mouse-type-backspace-copy', 'native-paste-and-cut', 'form-tab-focus',
    'form-shift-tab-focus', 'queued-link-click', 'command-history-back',
    'command-history-forward', 'arrow-scroll', 'space-page-scroll',
    'shift-space-page-scroll', 'deep-scroll', 'viewport-sized-framebuffer',
    'resized-viewport', 'window-remains-responsive', 'view-drag-selection-copy',
    'host-keyboard-location-and-type',
    'native-reload-button', 'native-close-during-load', 'native-close-last-window',
}
PHASES = {'deep', 'shrunk', 'restored', 'reference'}


def repaint_comparison(restored, reference):
    """Compare toolbar/header pixels relative to the current native title bar.

    Qualified for the unscaled Previous desktop and native system title font.
    No desktop coordinates or transient window IDs are stored.
    """
    from PIL import Image, ImageChops

    def client_strip(path):
        image = Image.open(path).convert('RGB')
        tsv = subprocess.check_output(['tesseract', str(path), 'stdout', '--psm', '11', 'tsv'],
                                      text=True, stderr=subprocess.DEVNULL, timeout=10)
        rows = list(csv.DictReader(io.StringIO(tsv), delimiter='\t'))
        titles = [r for r in rows if r.get('text', '').lower() == 'paint']
        if len(titles) != 1:
            raise ValueError('Cannot identify one repaint title in ' + path.name)
        title = titles[0]
        y = int(title['top']) - 2
        center = int(title['left']) + int(title['width']) // 2
        left = right = center
        while left > 0 and max(image.getpixel((left - 1, y))) < 32:
            left -= 1
        while right < image.width and max(image.getpixel((right, y))) < 32:
            right += 1
        top = int(title['top']) + int(title['height']) + 8
        bounds = (left + 2, top, right - 2, top + 80)
        if right - left < 300 or bounds[3] > image.height:
            raise ValueError('Repaint title has unexpected window geometry')
        return image.crop(bounds), bounds

    natural, natural_bounds = client_strip(restored)
    forced, forced_bounds = client_strip(reference)
    if natural.size != forced.size:
        raise ValueError('Restored and reference client widths differ')
    difference = ImageChops.difference(natural, forced)
    pixels = (difference.get_flattened_data() if hasattr(difference, 'get_flattened_data')
              else difference.getdata())
    changed = sum(any(pixel) for pixel in pixels)
    return {'changed_pixels': changed, 'compared_pixels': natural.width * natural.height,
            'restored_bounds': natural_bounds, 'reference_bounds': forced_bounds}


def validate(record, text, pictures):
    problems = []
    passed = re.findall(r'^EVERYDAY PASS (\S+)\r?$', text, re.M)
    if len(passed) != len(CHECKS) or set(passed) != CHECKS:
        problems.append('expected exactly one success for each of %d control checks' % len(CHECKS))
    if re.search(r'^EVERYDAY FAIL\b', text, re.M):
        problems.append('an explicit failure was recorded')
    for marker in ['EVERYDAY-SUITE', 'EVERYDAY-EXIT', 'PORTS-BATCH-STATUS']:
        if re.findall(r'^' + marker + r' (\d+)\r?$', text, re.M) != ['0']:
            problems.append(marker + ' did not report exactly one success')
    if not record.get('native_halt') or record.get('result_read_exitcode') != 0:
        problems.append('native halt and successful log collection are required')
    if not record.get('fsck') or any(record['fsck'].values()):
        problems.append('stopped filesystem checks did not pass')
    if set(pictures) != PHASES:
        problems.append('missing repaint checkpoints: ' + ', '.join(sorted(PHASES - set(pictures))))
    return problems


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite', type=Path, required=True)
    a = p.parse_args()
    guest = a.suite / 'm68k/guest'
    record = json.loads((guest / 'collection.json').read_text())
    text = (guest / 'results.txt').read_text()
    pictures = {phase for phase in PHASES if (guest / ('paint-' + phase + '.png')).is_file()}
    problems = validate(record, text, pictures)
    comparison = None
    try:
        comparison = repaint_comparison(guest / 'paint-restored.png', guest / 'paint-reference.png')
        if comparison['changed_pixels']:
            problems.append('natural resize repaint differs from forced full repaint')
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        problems.append('cannot compare repaint pixels: ' + str(error))
    (a.suite / 'everyday-validation.json').write_text(json.dumps({
        'passed': not problems, 'problems': problems, 'visual_review_required': True,
        'repaint_comparison': comparison,
    }, indent=2) + '\n')
    print('PASS; review repaint screenshots separately' if not problems else '\n'.join(problems))
    raise SystemExit(bool(problems))


if __name__ == '__main__':
    main()
