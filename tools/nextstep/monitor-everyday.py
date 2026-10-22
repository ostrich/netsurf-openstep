#!/usr/bin/env python3
"""Capture repaint checkpoints from one owned Previous desktop test."""
import argparse
import hashlib
from PIL import Image
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--suite',type=Path,required=True)
p.add_argument('--timeout',type=int,default=420)
a=p.parse_args()
if not 1 <= a.timeout <= 600:
    p.error('Timeout must be 1..600 seconds')
guest=a.suite.resolve()/'m68k/guest'
end=time.monotonic()+a.timeout
display_file=a.suite/'m68k/display.txt'
while not display_file.exists() and time.monotonic()<end:
    time.sleep(0.2)
display=display_file.read_text().strip()
saved=set()
pending={}
keyboard_sent=False
while time.monotonic()<end:
    if (guest/'collection.json').exists():
        break
    try:
        frame=guest/'everyday-check.png'
        subprocess.run(['import','-display',display,'-window','root',str(frame)],
                       check=True,capture_output=True,timeout=8)
        text=subprocess.check_output(['tesseract',str(frame),'stdout','--psm','11'],
                                     text=True,stderr=subprocess.DEVNULL,timeout=8)
        if not keyboard_sent:
            text += subprocess.check_output(['tesseract',str(frame),'stdout','--psm','6'],
                text=True,stderr=subprocess.DEVNULL,timeout=8)
        if not keyboard_sent and re.search(r'Host\s+keyboard',text,re.I):
            # This isolated display belongs to the test clone. Acquire its SDL
            # window afresh; no persistent window ID or desktop coordinates.
            windows=subprocess.check_output(['xdotool','search','--onlyvisible',
                '--name','^Previous [0-9]'],env=dict(os.environ,DISPLAY=display),
                text=True,timeout=5).splitlines()
            if len(windows) != 1:
                raise RuntimeError('Expected one owned Previous display window')
            env=dict(os.environ,DISPLAY=display)
            subprocess.run(['xdotool','windowfocus','--sync',windows[0]],env=env,check=True,timeout=5)
            subprocess.run(['xdotool','key','--clearmodifiers','super+l'],env=env,check=True,timeout=5)
            subprocess.run(['xdotool','type','--clearmodifiers','--delay','30','host-route'],
                           env=env,check=True,timeout=5)
            subprocess.run(['xdotool','key','--clearmodifiers','super+a','super+c'],
                           env=env,check=True,timeout=5)
            keyboard_sent=True
            print('Sent host SDL command-L and text',flush=True)
        for phase in ['deep','shrunk','restored','reference']:
            if (re.search(r'Paint\s+'+phase,text,re.I) or
                    (phase == 'deep' and re.search(r'Deep\s+scroll\s+rendering',text,re.I))):
                if phase in saved:
                    continue
                # Save a stable phase once. Overwriting its image while the
                # next resize begins can record a transition under the old title.
                with Image.open(frame) as pixels:
                    digest=hashlib.sha256(pixels.convert('RGB').tobytes()).digest()
                previous,count=pending.get(phase,(None,0))
                count=count+1 if digest == previous else 1
                pending[phase]=(digest,count)
                if count >= 2:
                    shutil.copy2(frame,guest/('paint-'+phase+'.png'))
                    (guest/('paint-'+phase+'.txt')).write_text(text)
                    print('Captured stable paint-'+phase,flush=True)
                    saved.add(phase)
    except (OSError,subprocess.SubprocessError):
        pass
    time.sleep(1)
print('Checkpoints: '+', '.join(sorted(saved)),flush=True)
