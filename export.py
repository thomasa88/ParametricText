# This file is part of Parametric Text, a Fusion 360 add-in for creating text
# parameters.
#
# Copyright (c) 2025 Thomas Axelsson
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import csv
from dataclasses import dataclass
import os

import adsk.core as ac
import adsk.fusion as af

from . import globals

@dataclass
class ParamData:
    text_id: int
    format_str: str
    sketch_names: list[str]

last_dir: str | None = None

def export_csv(suggested_filename: str, data: list[ParamData]):
    dialog = globals.ui_.createFileDialog()
    dialog.title = 'Export with names'
    dialog.initialFilename = suggested_filename
    dialog.filter = 'CSV files (*.csv)'
    global last_dir
    if last_dir:
        dialog.initialDirectory = last_dir
    result = dialog.showSave()
    if result == ac.DialogResults.DialogOK:
        last_dir = os.path.dirname(dialog.filename)
        with open(dialog.filename, 'w', newline='') as f:
            writer = csv.writer(f, dialect='excel')
            writer.writerow(['Add-in version', f'{globals.NAME_VERSION}'])
            writer.writerow(['File format version', '1'])
            writer.writerow([])
            writer.writerow(['ID', 'Text', 'Sketches'])
            for param in data:
                writer.writerow([param.text_id, param.format_str, *param.sketch_names])

def import_csv(title: str) -> list[ParamData]:
    dialog = globals.ui_.createFileDialog()
    dialog.title = title
    dialog.filter = 'CSV files (*.csv)'
    dialog.initialFilename = ''
    global last_dir
    if last_dir:
        dialog.initialDirectory = last_dir
    result = dialog.showOpen()
    if result == ac.DialogResults.DialogOK:
        last_dir = os.path.dirname(dialog.filename)
        with open(dialog.filename, 'r', newline='') as f:
            reader = csv.reader(f, dialect='excel')
            
            metadata = {}
            for i, row in enumerate(reader):
                if globals.settings_[globals.TROUBLESHOOT_SETTING]:
                    globals.log(f"Read metadata row: {row}")
                # Libreoffice adds more columns if any of the rows in the CSV
                # has more columns, so always be prepared for empty trailing columns.
                if all(col == '' for col in row):
                    # Metadata end
                    break
                if len(row) < 2:
                    globals.ui_.messageBox(f'Bad metadata row: {row}', globals.NAME_VERSION)
                metadata[row[0]] = row[1]

            # No need to check add-in version, as it is only info.

            version = metadata.get('File format version')
            if version != '1':
                globals.ui_.messageBox(f'Unsupported file format version: {version}', globals.NAME_VERSION)
                return []

            try:
                header_row = next(reader)
                if globals.settings_[globals.TROUBLESHOOT_SETTING]:
                    globals.log(f"Read header row: {header_row}")
                if header_row[0:3] != ['ID', 'Text', 'Sketches']:
                    globals.ui_.messageBox(f'Bad header row: {header_row}', globals.NAME_VERSION)
                    return []
            except StopIteration:
                globals.ui_.messageBox('Did not find header row. Is the file data correct?', globals.NAME_VERSION)
                return []

            params = []
            for i, row in enumerate(reader):
                if globals.settings_[globals.TROUBLESHOOT_SETTING]:
                    globals.log(f"Read parameter row: {row}")
                
                row_num = i + 1
                try:
                    text_id = int(row[0])
                except ValueError:
                    globals.ui_.messageBox(f'Invalid ID at row {row_num}: {row[0]}', globals.NAME_VERSION)
                    return []
                params.append(ParamData(text_id=text_id, format_str=row[1], sketch_names=row[1:]))
            if not params:
                globals.ui_.messageBox('No parameters found in the file! Is the file data correct?', globals.NAME_VERSION)
            return params
    return []
