#!/usr/bin/env python3
"""Reject incomplete acceptance evidence even when the outer guest exits zero."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('everyday', ROOT / 'tools/nextstep/check-everyday.py')
everyday = importlib.util.module_from_spec(spec)
spec.loader.exec_module(everyday)


class Evidence(unittest.TestCase):
    def setUp(self):
        self.record = {'native_halt': True, 'result_read_exitcode': 0, 'fsck': {'disk': 0}}
        self.text = '\n'.join('EVERYDAY PASS ' + name for name in sorted(everyday.CHECKS))
        self.text += '\nEVERYDAY-SUITE 0\nEVERYDAY-EXIT 0\nPORTS-BATCH-STATUS 0\n'
    def test_complete(self):
        self.assertEqual(everyday.validate(self.record, self.text, everyday.PHASES), [])
    def test_missing_check(self):
        self.assertTrue(everyday.validate(self.record, self.text.replace('EVERYDAY PASS arrow-scroll\n', ''), everyday.PHASES))
    def test_duplicate(self):
        self.assertTrue(everyday.validate(self.record, self.text + 'EVERYDAY-SUITE 0\n', everyday.PHASES))
    def test_failure(self):
        self.assertTrue(everyday.validate(self.record, self.text + 'EVERYDAY FAIL deadline\n', everyday.PHASES))
    def test_unclean_disk(self):
        self.record['fsck']['disk'] = 8
        self.assertTrue(everyday.validate(self.record, self.text, everyday.PHASES))
    def test_no_pixels(self):
        self.assertTrue(everyday.validate(self.record, self.text, set()))


if __name__ == '__main__':
    unittest.main()
