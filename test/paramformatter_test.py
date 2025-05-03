#!/usr/bin/python3

import os
import sys
import unittest

sys.path.append(os.path.realpath('.'))
from paramformatter import *

class ParamFormatterTest(unittest.TestCase):
    class FakeParam:
        def __init__(self, value=0.0):
            self.unit = ''
            self.value = value

    def test_mixed_frac_inch(self):
        values = [
            (1.25, '1 1/4"'),
            (2.75, '2 3/4"'),
            (1.1, '1 1/10"'),
            (5.0, '5"'),
            (0.2, '1/5"'),
            (0.0, '0"'),
            (-1.0, '-1"'),
            (-10.3, '-10 3/10"'),
            (0.203125, '13/64"')
            ]
        for v in values:
            print(f'{v[0]:<8} | {v[1]}')
            self.assertEqual(mixed_frac_inch(self.FakeParam(v[0]), None), v[1])

if __name__ == '__main__':
    unittest.main()
