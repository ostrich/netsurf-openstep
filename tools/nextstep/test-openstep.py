#!/usr/bin/env python3
"""GUI probe for the external tools/ports/openstep.py disposable-clone runner.

Required host-test arguments: project=PATH, desktop-helper=PATH.
Optional: temporary-login=me (disposable clone only).
"""
import ctypes
import ctypes.util
import os
from pathlib import Path
import re
import sys
import subprocess
import time


def run(agent, directory, output, arguments):
    options = {}
    for argument in arguments:
        key, separator, value = argument.partition('=')
        if not separator or not value or key in options or key not in {
                'project', 'desktop-helper', 'temporary-login'}:
            raise RuntimeError('Invalid GUI test argument: ' + key)
        options[key] = value
    if not {'project', 'desktop-helper'} <= set(options):
        raise RuntimeError('GUI test requires project and desktop-helper paths')
    if options.get('temporary-login', 'me') != 'me':
        raise RuntimeError('Only the disposable me-account login mode is supported')
    project = Path(options['project']).resolve(strict=True)
    helper = Path(options['desktop-helper']).resolve(strict=True)
    result = agent.execute('/bin/sh', ['-c', 'cd ' + directory +
                           ' && /bin/sh run.sh > results.txt 2>&1'], execution_timeout=120)
    if result.get('exitcode') != 0:
        return result
    # Agent readiness precedes loginwindow/Workspace readiness. A GUI client
    # needs both the desktop bootstrap namespace and its account. Bound this
    # check independently of application startup.
    if options.get('temporary-login') == 'me':
        # This option is only for the disposable clone owned by the VM runner.
        # Generate a one-use password in memory; do not save it in artifacts.
        password = os.urandom(4).hex()
        crypt = ctypes.CDLL(ctypes.util.find_library('crypt'))
        crypt.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        crypt.crypt.restype = ctypes.c_char_p
        hashed = crypt.crypt(password.encode(), b'nt').decode()
        changed = agent.execute('/usr/bin/niutil', ['-createprop', '.', '/users/me', 'passwd', hashed], execution_timeout=15)
        if changed.get('exitcode') != 0:
            return changed
        sys.path.insert(0, str(project / 'installer'))
        from openstep import QMP
        q = QMP(output / 'work/qmp.sock')
        ready = False
        try:
            end = time.monotonic() + 70
            while time.monotonic() < end:
                screenshot = output / 'login-ready.ppm'
                q.call('screendump', {'filename': str(screenshot)})
                text = subprocess.check_output(['tesseract', str(screenshot), 'stdout', '--psm', '11'],
                                               text=True, stderr=subprocess.DEVNULL, timeout=8)
                if re.search('OPENSTEP', text, re.I) and re.search('Password', text, re.I):
                    ready = True
                    break
                time.sleep(.5)
            if ready:
                # Fresh login panels focus Name. No other actor has sent input.
                for key in list('me') + ['tab'] + list(password) + ['ret']:
                    q.call('human-monitor-command', {'command-line': 'sendkey ' + key})
                    time.sleep(.08)
        finally:
            q.close()
        if not ready:
            return {'exited': True, 'exitcode': 1}
    owner = None
    desktop_deadline = time.monotonic() + 100
    while time.monotonic() < desktop_deadline:
        processes = agent.execute('/bin/ps', ['-auxw'], execution_timeout=10)
        for line in processes.get('stdout', b'').decode(errors='replace').splitlines():
            if re.search(r'(?:^|\s|/)Workspace(?:\s|$)', line):
                candidate = line.split()[0]
                if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]*', candidate):
                    owner = candidate
                    desktop_pid = line.split()[1]
                    break
        if owner:
            break
        time.sleep(1)
    if not owner:
        agent.execute('/bin/sh', ['-c', 'echo "GUI-DESKTOP not ready" >> ' + directory + '/results.txt'], execution_timeout=10)
        return {'exited': True, 'exitcode': 1}
    fixture = '''<html><head><title>NetSurf test</title>
<style>body { font: 18px sans-serif; background: white; color: black }
h1 { color: #204080 } .sample { background: #80c080; padding: 12px }</style>
</head><body><h1>Native browser check</h1><p class="sample">HTML and CSS rendering</p>
<p id="js">JavaScript pending</p><script>
document.getElementById('js').textContent = 'JavaScript works';
document.title = 'NetSurf JS OK';</script>
<p><a href="about:welcome">A normal browser link</a></p></body></html>'''
    local = output / 'fixture.html'
    local.write_text(fixture)
    agent.upload(local, directory + '/fixture.html', mode=0o644)
    # Supply the desktop namespace to open(1), then let Workspace launch the
    # app with its real -MachLaunch arguments. Direct exec bypasses this
    # launch protocol and cannot qualify a double-clickable installation.
    agent.execute('/bin/chmod', ['755', directory], execution_timeout=10)
    agent.upload(local, directory + '/NetSurf.app/welcome.html', mode=0o644)
    sys.path.insert(0, str(project / 'installer'))
    from openstep import QMP
    qmp = QMP(output / 'work/qmp.sock')
    agent.upload(helper, directory + '/desktop-exec', mode=0o755)
    command = (directory + '/desktop-exec ' + desktop_pid + ' ' + owner + ' ' +
               '/usr/bin/open ' + directory + '/NetSurf.app > ' + directory +
               '/gui-launch.txt 2>&1 < /dev/null &')
    agent.execute('/bin/sh', ['-c', command], execution_timeout=10)
    passed = False
    quit_cleanly = False
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline:
            ppm = output / 'browser.ppm'
            qmp.call('screendump', {'filename': str(ppm)})
            from PIL import Image
            Image.open(ppm).save(output / 'browser.png')
            text = subprocess.check_output(['tesseract', str(ppm), 'stdout', '--psm', '11'],
                                           text=True, stderr=subprocess.DEVNULL, timeout=8)
            (output / 'browser-ocr.txt').write_text(text)
            if re.search(r'Native\s+browser', text, re.I) and re.search(r'JavaScript\s+works', text, re.I):
                passed = True
                break
            time.sleep(.5)
        if passed:
            qmp.call('human-monitor-command', {'command-line': 'sendkey alt-q'})
            end = time.monotonic() + 10
            while time.monotonic() < end:
                processes = agent.execute('/bin/ps', ['-ax'], execution_timeout=10)
                if not re.search(r'(?:^|\s|/)NetSurf(?:\s|$)', processes.get('stdout', b'').decode(errors='replace')):
                    quit_cleanly = True
                    break
                time.sleep(.3)
    finally:
        qmp.close()
    try:
        agent.download(directory + '/gui-launch.txt', output / 'gui-launch.txt')
    except RuntimeError:
        pass
    if not passed:
        try:
            agent.download('/usr/adm/messages', output / 'system-messages.txt')
        except RuntimeError:
            pass
    line = 'GUI-PROBE ' + ('PASS' if passed and quit_cleanly else 'FAIL')
    agent.execute('/bin/sh', ['-c', 'echo "' + line + '" >> ' + directory + '/results.txt'], execution_timeout=10)
    return {'exited': True, 'exitcode': 0 if passed and quit_cleanly else 1}
