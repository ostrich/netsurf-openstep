#!/usr/bin/env python3
"""Host-driven GUI probe for tools/ports/openstep.py in the external VM project."""
import base64
from pathlib import Path
import re
import sys
import subprocess
import time


def run(agent, directory, output, arguments):
    options = dict(value.split('=', 1) for value in arguments)
    project = Path(options['project']).resolve(strict=True)
    result = agent.execute('/bin/sh', ['-c', 'cd ' + directory +
                           ' && /bin/sh run.sh > results.txt 2>&1'], execution_timeout=120)
    if result.get('exitcode') != 0:
        return result
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
    child = agent.request('guest-exec', {'path': '/bin/sh',
                          'arg': ['-c', 'exec ' + directory + '/NetSurf.app/NetSurf file://' +
                                  directory + '/fixture.html > ' + directory + '/browser.log 2>&1'],
                          'capture-output': True, 'env': ['NETSURF_STARTUP_TRACE=1']})
    pid = child['pid']
    sys.path.insert(0, str(project / 'installer'))
    from openstep import QMP
    qmp = QMP(output / 'work/qmp.sock')
    passed = False
    status = None
    deadline = time.monotonic() + 25
    try:
        while time.monotonic() < deadline:
            status = agent.request('guest-exec-status', {'pid': pid})
            if status['exited']:
                break
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
    finally:
        qmp.close()
        if status is None or not status['exited']:
            status = agent.request('guest-exec-status', {'pid': pid})
        if not status['exited']:
            agent.execute('/bin/kill', ['-TERM', str(pid)], execution_timeout=10)
            for _ in range(30):
                status = agent.request('guest-exec-status', {'pid': pid})
                if status['exited']:
                    break
                time.sleep(.1)
        (output / 'browser-output.txt').write_bytes(
            base64.b64decode(status.get('out-data', '')) + base64.b64decode(status.get('err-data', '')))
    agent.download(directory + '/browser.log', output / 'browser.log')
    import json
    (output / 'browser-status.json').write_text(json.dumps(status, indent=2) + '\n')
    line = 'GUI-PROBE ' + ('PASS' if passed else 'FAIL')
    agent.execute('/bin/sh', ['-c', 'echo "' + line + '" >> ' + directory + '/results.txt'], execution_timeout=10)
    return {'exited': True, 'exitcode': 0 if passed else 1}
