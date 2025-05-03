#!/usr/bin/python3

import os
import sys
import unittest

sys.path.append(os.path.realpath('.'))
from paramparser import *

class ParamParseTest(unittest.TestCase):
    def test_split_param(self):
        self.assertEqual(ParamSpec.from_string('_'), ParamSpec(var='_'))
        self.assertEqual(ParamSpec.from_string('_.version'), ParamSpec(var='_', member='version'))
        self.assertEqual(ParamSpec.from_string('_.version:02d'), ParamSpec(var='_', member='version', format='02d'))
        self.assertEqual(ParamSpec.from_string('_.file[1:5]'), ParamSpec(var='_', member='file', string_slice=slice(1, 5)))
        self.assertEqual(ParamSpec.from_string('_.file[1:5]:01'), ParamSpec(var='_', member='file', string_slice=slice(1, 5), format='01'))
        self.assertEqual(ParamSpec.from_string('param'), ParamSpec(var='param'))
        self.assertEqual(ParamSpec.from_string('param:-<2'), ParamSpec(var='param', format='-<2'))
        self.assertEqual(ParamSpec.from_string('param[1]:-<2'), ParamSpec(var='param', string_slice=slice(1, 2), format='-<2'))
        self.assertEqual(ParamSpec.from_string('param[-1:]'), ParamSpec(var='param', string_slice=slice(-1, None)))
        self.assertEqual(ParamSpec.from_string('param[:-3]'), ParamSpec(var='param', string_slice=slice(None, -3)))

    def test_slice_parsing(self):
        # Good
        self.assertEqual(ParamSpec.from_string('p[0]'), ParamSpec(var='p', string_slice=slice(0, 1)))
        self.assertEqual(ParamSpec.from_string('p[:5]'), ParamSpec(var='p', string_slice=slice(None, 5)))
        self.assertEqual(ParamSpec.from_string('p[6:]'), ParamSpec(var='p', string_slice=slice(6, None)))
        self.assertEqual(ParamSpec.from_string('p[5:6]'), ParamSpec(var='p', string_slice=slice(5, 6)))
        self.assertEqual(ParamSpec.from_string('p[:-1]'), ParamSpec(var='p', string_slice=slice(None, -1)))
        self.assertEqual(ParamSpec.from_string('p[1:-2]'), ParamSpec(var='p', string_slice=slice(1, -2)))

        # Meaningless, but valid
        self.assertEqual(ParamSpec.from_string('p[:]'), ParamSpec(var='p', string_slice=slice(None, None)))
        self.assertEqual(ParamSpec.from_string('p[-5:5]'), ParamSpec(var='p', string_slice=slice(-5, 5)))
        self.assertEqual(ParamSpec.from_string('p[11:5]'), ParamSpec(var='p', string_slice=slice(11, 5)))

        # Bad
        self.assertEqual(ParamSpec.from_string('p[]'), None)
        self.assertEqual(ParamSpec.from_string('p[a]'), None)
        self.assertEqual(ParamSpec.from_string('p[a:b]'), None)
        self.assertEqual(ParamSpec.from_string('p[:b]'), None)
        # No handling of step (at least for now)
        self.assertEqual(ParamSpec.from_string('p[1:3:2]'), None)
        self.assertEqual(ParamSpec.from_string('p[::]'), None)

    def test_split_example_strings(self):
        self.assertEqual(ParamSpec.from_string('d1:.3f'), ParamSpec(var='d1', format='.3f'))
        self.assertEqual(ParamSpec.from_string('d1.unit'), ParamSpec(var='d1', member='unit'))
        self.assertEqual(ParamSpec.from_string('d1:03.0f'), ParamSpec(var='d1', format='03.0f'))
        self.assertEqual(ParamSpec.from_string('width:.0f'), ParamSpec(var='width', format='.0f'))
        self.assertEqual(ParamSpec.from_string('width.expr'), ParamSpec(var='width', member='expr'))
        self.assertEqual(ParamSpec.from_string('height.expr'), ParamSpec(var='height', member='expr'))
        self.assertEqual(ParamSpec.from_string('_.version'), ParamSpec(var='_', member='version'))
        self.assertEqual(ParamSpec.from_string('_.version:03'), ParamSpec(var='_', member='version', format='03'))
        self.assertEqual(ParamSpec.from_string('_.file'), ParamSpec(var='_', member='file'))
        self.assertEqual(ParamSpec.from_string('_.component'), ParamSpec(var='_', member='component'))
        self.assertEqual(ParamSpec.from_string('_.date'), ParamSpec(var='_', member='date'))
        self.assertEqual(ParamSpec.from_string('_.date:%m/%d/%Y'), ParamSpec(var='_', member='date', format='%m/%d/%Y'))
        self.assertEqual(ParamSpec.from_string('_.date:%U'), ParamSpec(var='_', member='date', format='%U'))
        self.assertEqual(ParamSpec.from_string('_.date:%W'), ParamSpec(var='_', member='date', format='%W'))
        self.assertEqual(ParamSpec.from_string('_.date:%H:%M'), ParamSpec(var='_', member='date', format='%H:%M'))

    def test_bad_param_string(self):
        bad_strings = [
            '',
            '.',
            '.a',
            'a.',
            '.a[10]',
            '.a:5',
            '.[]',
            'a[]',
            '[]',
            ':',
            'a[',
            'a]',
            '[1]',
            'a[1',
            ':5',
            'a[10:10][]',
        ]
        for bad in bad_strings:
            self.assertIsNone(ParamSpec.from_string(bad), msg=f'Input: {repr(bad)}')

if __name__ == '__main__':
    unittest.main()
