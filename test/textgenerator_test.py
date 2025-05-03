#!/usr/bin/python3

import os
import sys
from types import SimpleNamespace as NS
import unittest
from datetime import datetime

sys.path.append(os.path.realpath("."))

import textgenerator


class TextGeneratorTest(unittest.TestCase):
    def setUp(self):
        def get_param(name: str):
            self.assertEqual(name, "param")
            return NS(unit="mm", value=223, expression="223 mm", comment="My comment")

        design = NS(
            allParameters=NS(
                itemByName=get_param,
            ),
            fusionUnitsManager=NS(convert=lambda value, from_unit, to_unit: 22.3),
            configurationTopTable=NS(activeRow=NS(name="Configuration 2")),
        )
        app = NS(
            activeProduct=design,
            activeDocument=NS(
                name="My File",
                isSaved=True,
                dataFile=NS(
                    versionNumber=24,
                    dateCreated=int(datetime(2020, 10, 24).timestamp()),
                ),
            ),
        )
        textgenerator.globals = NS(app_=app)

        self.sketch_text = NS(
            parentSketch=NS(
                name="Sketch1",
                parentComponent=NS(
                    name="Component1",
                    description="Complex Description in the Component",
                    partNumber="123-AB",
                ),
            )
        )

    
    def g(self, text: str):
        return textgenerator.generate_text(text, self.sketch_text)

    def test_parse_single(self):
        self.assertEqual(self.g("Hello, world!"), "Hello, world!")
        self.assertEqual(self.g("{param:.3f}"), "22.300")
        self.assertEqual(self.g("{param.value:.3f}"), "22.300")
        self.assertEqual(self.g("{param.value:03.0f}"), "022")
        self.assertEqual(self.g("{param.comment:.6}"), "My com")
        self.assertEqual(self.g("{param.unit}"), "mm")
        self.assertEqual(self.g("{param.expr}"), "223 mm")

        self.assertEqual(self.g("{_.version:03}"), "024")
        self.assertEqual(self.g("{_.component}"), "Component1")
        self.assertEqual(self.g("{_.compdesc}"), "Complex Description in the Component")
        self.assertEqual(self.g("{_.partnum}"), "123-AB")
        self.assertEqual(self.g("{_.configuration}"), "Configuration 2")
        self.assertEqual(self.g("{_.date}"), "2020-10-24")
        self.assertEqual(self.g("{_.date:%Y-%m-%d}"), "2020-10-24")
        self.assertEqual(self.g("{_.date:%m/%d/%Y}"), "10/24/2020")
        self.assertEqual(self.g("{_.file}"), "My File")
        self.assertEqual(self.g("{_.newline}"), "\n")
        self.assertEqual(self.g("{_.sketch}"), "Sketch1")

    def test_no_sketch_text(self):
        def gen(text: str):
            return textgenerator.generate_text(text, None)

        self.assertEqual(gen("Hello, world!"), "Hello, world!")
        self.assertEqual(gen("{_.sketch}"), "<?>")
        self.assertEqual(gen("{_.component}"), "<?>")

    def test_parse_multiple(self):
        self.assertEqual(
            self.g("A{param:.3f}B {param.value:.3f} {param.comment:.6}"),
            "A22.300B 22.300 My com",
        )


if __name__ == "__main__":
    unittest.main()
