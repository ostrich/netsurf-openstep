#!/usr/bin/env python3
"""Require explicit GUI, network, identity and shutdown evidence, not just exit 0."""
import argparse
import json
from pathlib import Path
import re


def validate(record, text, screenshot):
    problems = []
    if not record.get('native_halt'):
        problems.append('native halt was not established')
    checks = record.get('fsck', {})
    if not checks or any(value != 0 for value in checks.values()):
        problems.append('stopped filesystem checks did not all pass')
    if record.get('result_read_exitcode') != 0:
        problems.append('native result log was not collected')
    for expression, expected, label in [
        (r'^GUI-SUITE (\d+)\r?$', ['0'], 'GUI suite'),
        (r'^IDENTITY-SUITE (\d+)\r?$', ['0'], 'certificate identity suite'),
        (r'^NETWORK-SUITE (\d+) cases=11\r?$', ['0'], 'network suite'),
        (r'^GUI-EXIT (\d+)\r?$', ['0'], 'application exit'),
        (r'^PORTS-BATCH-STATUS (\d+)\r?$', ['0'], 'outer native batch')]:
        if re.findall(expression, text, re.M) != expected:
            problems.append(label + ' did not report exactly one success')
    if len(re.findall(r'^GUI PASS ', text, re.M)) != 16:
        problems.append('expected 16 native GUI checks')
    if len(re.findall(r'^NETWORK PASS ', text, re.M)) != 11:
        problems.append('expected 11 network checks')
    if len(re.findall(r'^IDENTITY PASS ', text, re.M)) != 16:
        problems.append('expected 16 certificate identity checks')
    if re.search(r'^(GUI|NETWORK|IDENTITY) FAIL\b', text, re.M):
        problems.append('an explicit test failure was logged')
    if not screenshot:
        problems.append('rendered local-page screenshot was not captured')
    return problems


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite', required=True, type=Path)
    p.add_argument('--arch', action='append', choices=['i386','m68k','hppa','sparc'])
    p.add_argument('--host-fixture', type=Path, help='Host endpoint evidence for Previous')
    p.add_argument('--host-token', help='Unique prepared payload name for Previous requests')
    a = p.parse_args()
    records = {}
    for arch in a.arch or ['i386','m68k','hppa','sparc']:
        directory = a.suite / arch / 'guest'
        try:
            record = json.loads((directory / 'collection.json').read_text())
            text = (directory / 'results.txt').read_text(errors='replace')
            problems = validate(record, text, ((directory / 'local-page.png').is_file() or (directory / 'native-page.png').is_file()))
            if arch != 'm68k':
                if len(re.findall(r'^REQUEST TLSv1\.3 /secure\r?$', text, re.M)) < 2:
                    problems.append('verified HTTPS fetch/reload requests were not observed')
            elif a.host_fixture and a.host_token:
                requests = [json.loads(line) for line in (a.host_fixture / 'requests.jsonl').read_text().splitlines()]
                if sum(row['path'] == '/secure?run=' + a.host_token and row['tls'] == 'TLSv1.3' for row in requests) < 2:
                    problems.append('host did not observe the HTTPS fetch and reload')
            else:
                problems.append('Previous requires host endpoint evidence')
        except (OSError, ValueError) as error:
            problems = ['missing or invalid evidence: ' + str(error)]
        records[arch] = {'passed': not problems, 'problems': problems}
        print(arch + ': ' + ('PASS' if not problems else '; '.join(problems)))
    (a.suite / 'qualification.json').write_text(json.dumps(records, indent=2) + '\n')
    raise SystemExit(any(not value['passed'] for value in records.values()))


if __name__ == '__main__':
    main()
