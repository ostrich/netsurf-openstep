#!/usr/bin/env python3
"""Capture bounded visual evidence from owned, already launched test clones."""
import argparse
import concurrent.futures
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--project', type=Path, required=True)
p.add_argument('--suite', type=Path, required=True)
p.add_argument('--arch', action='append', required=True, choices=['i386','m68k','hppa','sparc'])
p.add_argument('--timeout', type=int, default=420)
a = p.parse_args()
if not 1 <= a.timeout <= 900:
    p.error('Timeout must be 1..900 seconds')
sys.path.insert(0, str(a.project.resolve() / 'host/qemu/tests/risc'))
from risc_control import Guest


def capture(arch):
    directory = a.suite.resolve() / arch / 'guest'
    guest = Guest(directory)
    end = time.monotonic() + a.timeout
    saved = set()
    video = None
    video_log = None
    while time.monotonic() < end:
        if (directory / 'collection.json').exists():
            break
        if not (directory / 'runtime.pid').exists():
            time.sleep(.5)
            continue
        try:
            if arch == 'm68k':
                display = (a.suite / arch / 'display.txt').read_text().strip()
                path = directory / 'gui-check.png'
                subprocess.run(['import', '-display', display, '-window', 'root', str(path)],
                               check=True, capture_output=True, timeout=8)
            else:
                path = guest.screen('gui-check')
            if arch == 'm68k' and video is None:
                from PIL import Image
                with Image.open(path) as frame:
                    size = '%dx%d' % frame.size
                video_log = (directory / 'video.log').open('wb')
                video = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'x11grab',
                    '-framerate', '10', '-video_size', size, '-i', display,
                    '-t', str(a.timeout), '-c:v', 'ffv1', '-level', '3',
                    str(directory / 'gui-video.mkv')], stdout=video_log, stderr=video_log)
            text = subprocess.check_output(['tesseract', str(path), 'stdout', '--psm', '11'],
                                           text=True, stderr=subprocess.DEVNULL, timeout=8)
            (directory / 'gui-check.txt').write_text(text)
            for name, pattern in [('local-page', r'Native\s+browser\s+check'),
                                  ('http-page', r'Network\s+browser\s+check'),
                                  ('https-page', r'Secure\s+browser\s+check')]:
                if (name not in saved and re.search(pattern, text, re.I)
                        and re.search(r'Java\s*Script\s+works|Scrollable\s+document|HTML\s+and\s+CSS\s+rendering', text, re.I)):
                    shutil.copyfile(path, directory / (name + '.png'))
                    (directory / (name + '.txt')).write_text(text)
                    saved.add(name)
                    print(arch + ': captured ' + name, flush=True)
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
            pass
        time.sleep(2)
    if video is not None:
        if video.poll() is None:
            video.send_signal(signal.SIGINT)
            try:
                video.wait(timeout=10)
            except subprocess.TimeoutExpired:
                video.kill(); video.wait()
        video_log.close()
        if 'local-page' not in saved and (directory / 'gui-video.mkv').stat().st_size:
            frames = directory / 'video-frames'
            frames.mkdir(exist_ok=True)
            extraction = subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i',
                str(directory / 'gui-video.mkv'), '-vf', 'fps=1/2',
                '-frames:v', '450', str(frames / '%04d.png')],
                capture_output=True, timeout=60)
            scan_end = time.monotonic() + 60
            for frame in sorted(frames.glob('*.png'), reverse=True):
                if time.monotonic() >= scan_end:
                    break
                text = subprocess.check_output(['tesseract', str(frame), 'stdout', '--psm', '11'],
                    text=True, stderr=subprocess.DEVNULL, timeout=8)
                if (re.search(r'Native\s+browser\s+check', text, re.I)
                        and re.search(r'Java\s*Script\s+works|Scrollable\s+document|HTML\s+and\s+CSS\s+rendering', text, re.I)):
                    shutil.copyfile(frame, directory / 'local-page.png')
                    (directory / 'local-page.txt').write_text(text)
                    saved.add('local-page')
                    print(arch + ': captured local-page from video', flush=True)
                    break
    print(arch + ': visual checkpoints ' + ', '.join(sorted(saved)), flush=True)


with concurrent.futures.ThreadPoolExecutor(max_workers=len(a.arch)) as pool:
    list(pool.map(capture, a.arch))
