# This file is part of Parametric Text, a Fusion 360 add-in for creating text
# parameters.
#
# Copyright (c) 2020 Thomas Axelsson
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

import importlib
from typing import cast

import adsk.core as ac
import adsk.fusion as af

ADDIN_NAME = 'ParametricText'

try:
    # Must import lib as unique name, to avoid collision with other versions
    # loaded by other add-ins
    from .thomasa88lib import utils
    from .thomasa88lib import events
    from .thomasa88lib import manifest
    from .thomasa88lib import error
    from .thomasa88lib import settings
except ImportError as e:
    ui = ac.Application.get().userInterface
    ui.messageBox(f'{ADDIN_NAME} cannot load since thomasa88lib seems to be missing.\n\n'
                  f'Please make sure you have installed {ADDIN_NAME} according to the '
                  'installation instructions.\n\n'
                  f'Error: {e}', f'{ADDIN_NAME}')
    raise

# Force modules to be fresh during development
importlib.reload(utils)
importlib.reload(events)
importlib.reload(manifest)
importlib.reload(error)
importlib.reload(settings)


manifest_ = manifest.read()

NAME_VERSION = f'{ADDIN_NAME} v {manifest_["version"]}'
AUTOCOMPUTE_SETTING = 'autocompute'


error_catcher_ = error.ErrorCatcher(msgbox_in_debug=False,
                                                 msg_prefix=NAME_VERSION)
events_manager_ = events.EventsManager(error_catcher_)
settings_ = settings.SettingsManager({
    AUTOCOMPUTE_SETTING: True
})

app_: ac.Application
ui_: ac.UserInterface


def extract_text_id(input_or_str: ac.CommandInput | str) -> int:
    if isinstance(input_or_str, ac.CommandInput):
        input_or_str = cast(ac.CommandInput, input_or_str).id
    return int(input_or_str.split('_')[-1])

def get_design() -> af.Design:
    design = af.FusionDocument.cast(app_.activeDocument).design
    return design
