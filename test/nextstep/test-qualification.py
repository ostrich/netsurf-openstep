#!/usr/bin/env python3
"""Regression for false-success paths found in native fixture shell scripts."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('qualification', ROOT/'tools/nextstep/check-qualification.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Results(unittest.TestCase):
    def setUp(self):
        self.record = {'native_halt': True, 'fsck': {'disk': 0}, 'result_read_exitcode': 0}
        self.text = '\n'.join(['GUI PASS case']*16 + ['NETWORK PASS case']*11 + ['IDENTITY PASS case']*16 +
            ['GUI-SUITE 0','NETWORK-SUITE 0 cases=11','IDENTITY-SUITE 0','GUI-EXIT 0','PORTS-BATCH-STATUS 0']) + '\n'
    def test_title_is_not_rendering(self):
        self.assertFalse(module.rendered_local_text('Native browser check'))
    def test_rendered_body(self):
        self.assertTrue(module.rendered_local_text('Native browser check\nJavaScript works'))
    def test_dithered_body(self):
        self.assertTrue(module.rendered_local_text('Native browser check\nayaScrintwarks\nScrollable document'))
    def test_unrelated_body(self):
        self.assertFalse(module.rendered_local_text('File Viewer\nScrollable document'))
    def test_complete(self):
        self.assertEqual(module.validate(self.record,self.text,True), [])
    def test_old_shell_false_success(self):
        # The outer shell once returned 0 after a failed GUI subtest.
        self.assertTrue(module.validate(self.record,self.text.replace('GUI-SUITE 0','GUI-SUITE 1'),True))
    def test_missing_gui(self):
        self.assertTrue(module.validate(self.record,self.text.replace('GUI-SUITE 0',''),True))
    def test_duplicate_success(self):
        self.assertTrue(module.validate(self.record,self.text+'GUI-SUITE 0\n',True))
    def test_failed_assertion(self):
        self.assertTrue(module.validate(self.record,self.text+'GUI FAIL late\n',True))
    def test_no_screenshot(self):
        self.assertTrue(module.validate(self.record,self.text,False))
    def test_unclean_guest(self):
        self.record['native_halt'] = False
        self.assertTrue(module.validate(self.record,self.text,True))


unittest.main()
