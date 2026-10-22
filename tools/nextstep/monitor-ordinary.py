#!/usr/bin/env python3
"""Exercise one ordinary browser through an owned Previous SDL keyboard route."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--suite', type=Path, required=True)
p.add_argument('--guest-directory', default='/port-test')
p.add_argument('--timeout', type=int, default=420)
a = p.parse_args()
if not 1 <= a.timeout <= 600 or not re.fullmatch(r'/[A-Za-z0-9_/-]+', a.guest_directory):
    p.error('Use a bounded timeout and a simple absolute guest payload directory')
guest = a.suite.resolve() / 'm68k/guest'
end = time.monotonic() + a.timeout
display_file = a.suite / 'm68k/display.txt'
while not display_file.exists() and time.monotonic() < end:
    time.sleep(0.2)
display = display_file.read_text().strip()
env = dict(os.environ, DISPLAY=display)
phase = 0
checks = []

def key(value):
    # The X server belongs only to this clone. Resolve its SDL window each time.
    windows = subprocess.check_output(['xdotool', 'search', '--onlyvisible', '--name', '^Previous [0-9]'],
                                      env=env, text=True, timeout=5).splitlines()
    if len(windows) != 1:
        raise RuntimeError('Expected one owned Previous window')
    subprocess.run(['xdotool', 'windowfocus', '--sync', windows[0]], env=env, check=True, timeout=5)
    subprocess.run(['xdotool', 'key', '--clearmodifiers', value], env=env, check=True, timeout=5)

while time.monotonic() < end:
    if (guest / 'collection.json').exists():
        break
    try:
        frame = guest / 'ordinary-check.png'
        subprocess.run(['import', '-display', display, '-window', 'root', str(frame)],
                       check=True, capture_output=True, timeout=8)
        text = subprocess.check_output(['tesseract', str(frame), 'stdout', '--psm', '11'],
                                       text=True, stderr=subprocess.DEVNULL, timeout=8)
        if phase in (0, 2) and re.search(r'Everyday\s+controls', text, re.I) and re.search(r'HTML\s+and\s+CSS|Selection\s+sample\s+text', text, re.I):
            (guest / ('ordinary-initial.png' if phase == 0 else 'ordinary-back.png')).write_bytes(frame.read_bytes())
            if phase == 0:
                key('super+l')
                subprocess.run(['xdotool', 'type', '--clearmodifiers', '--delay', '25',
                    'file://' + a.guest_directory + '/second.html'], env=env, check=True, timeout=10)
                key('Return')
                checks.append('initial page rendered')
                print('Initial page rendered; entered destination URL', flush=True)
                phase = 1
            else:
                checks.append('keyboard history back rendered')
                print('History page rendered; quitting', flush=True)
                key('super+q')
                phase = 3
        elif phase == 1 and len(re.findall(r'Second\s+page', text, re.I)) >= 2:
            (guest / 'ordinary-second.png').write_bytes(frame.read_bytes())
            checks.append('host keyboard URL editing and Return rendered destination')
            print('Destination rendered; going back', flush=True)
            key('super+bracketleft')
            phase = 2
    except (OSError, subprocess.SubprocessError):
        pass
    time.sleep(1)
result = {'passed': phase == 3, 'checks': checks, 'phase': phase,
          'scope': 'Ordinary m68k binary, actual host SDL keyboard and rendered page transitions'}
(guest / 'ordinary-host.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
raise SystemExit(phase != 3)
