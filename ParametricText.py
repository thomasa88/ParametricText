#Author-Thomas Axelsson
#Description-Allows using parameters for texts.

# This file is part of DirectName, a Fusion 360 add-in for naming
# features directly after creation.
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

import adsk.core, adsk.fusion, adsk.cam, traceback
from collections import defaultdict

NAME = 'ParametricText'

# Must import lib as unique name, to avoid collision with other versions
# loaded by other add-ins
from .thomasa88lib import utils
from .thomasa88lib import events
#from .thomasa88lib import timeline
from .thomasa88lib import manifest
from .thomasa88lib import error

# Force modules to be fresh during development
import importlib
importlib.reload(thomasa88lib.utils)
importlib.reload(thomasa88lib.events)
#importlib.reload(thomasa88lib.timeline)
importlib.reload(thomasa88lib.manifest)
importlib.reload(thomasa88lib.error)

PANEL_ID = 'thomasa88_ParametricText_Panel'
MAP_CMD_ID = 'thomasa88_ParametricText_Map'

SELECTED_COLUMN = 0

app_ = None
ui_ = None

error_catcher_ = thomasa88lib.error.ErrorCatcher(msgbox_in_debug=False)
events_manager_ = thomasa88lib.events.EventsManager(error_catcher_)
manifest_ = thomasa88lib.manifest.read()

selection_map_ = defaultdict(list)

### design.attributes to save
### select to point out. a text prompt to ask for parameter name
### command dialog - use the same dialog for removing selections
### update when parameter changes? need refresh button???
### design.userParameters[0].name / .comment
### design.rootComponent.sketches

def run(context):
    global app_
    global ui_
    with error_catcher_:
        app_ = adsk.core.Application.get()
        ui_ = app_.userInterface

        # Make sure an old version of this command is not running and blocking the "add"
        if ui_.activeCommand == MAP_CMD_ID:
            ui_.terminateActiveCommand()

        map_cmd_def = ui_.commandDefinitions.itemById(MAP_CMD_ID)
        if map_cmd_def:
            map_cmd_def.deleteMe()

        # Use a Command to get a transaction when renaming
        map_cmd_def = ui_.commandDefinitions.addButtonDefinition(MAP_CMD_ID,
                                                                  f'Map parameter to text',
                                                                  f'{NAME} (v {manifest_["version"]})',
                                                                  '')
        events_manager_.add_handler(map_cmd_def.commandCreated,
                                    callback=map_cmd_created_handler)

        tab = ui_.allToolbarTabs.itemById('ToolsTab')
#### set panel to only be visible in design? OK by default?
        panel = tab.toolbarPanels.itemById(PANEL_ID)
        if panel:
            panel.deleteMe()
        panel = tab.toolbarPanels.add(PANEL_ID, f'{NAME}')

        map_control = panel.controls.addCommand(map_cmd_def)
        map_control.isPromotedByDefault = True
        #map_control.isPromoted = True


def stop(context):
    with error_catcher_:
        events_manager_.clean_up()

        map_cmd_def = ui_.commandDefinitions.itemById(MAP_CMD_ID)
        if map_cmd_def:
            map_cmd_def.deleteMe()

        tab = ui_.allToolbarTabs.itemById('ToolsTab')
        panel = tab.toolbarPanels.itemById(PANEL_ID)
        if panel:
            panel.deleteMe()

def map_cmd_created_handler(args: adsk.core.CommandCreatedEventArgs):
    cmd = args.command
    design: adsk.fusion.Design = app_.activeProduct

    cmd.setDialogMinimumSize(450, 200)

    events_manager_.add_handler(cmd.execute,
                                callback=map_cmd_execute_handler)

    events_manager_.add_handler(cmd.inputChanged,
                                callback=map_cmd_input_changed_handler)

    #param_input = cmd.commandInputs.addDropDownCommandInput('param', 'User parameter', adsk.core.DropDownStyles.TextListDropDownStyle)
    
    table_input = cmd.commandInputs.addTableCommandInput('table', '', 3, '')
    table_input.isFullWidth = True
    table_add = table_input.commandInputs.addBoolValueInput('add_row', '+', False, '', True)
    table_remove = table_input.commandInputs.addBoolValueInput('remove_row', '-', False, '', True)
    table_input.addToolbarCommandInput(table_add)
    table_input.addToolbarCommandInput(table_remove)
    
    select_input = cmd.commandInputs.addSelectionInput('select', 'Sketch Texts', '')
    select_input.addSelectionFilter(adsk.core.SelectionCommandInput.Texts)
    select_input.setSelectionLimits(1, 0)

    load(cmd)

    if table_input.rowCount == 0:
        add_row(table_input, get_next_id())

### preview: executePreview show text from param.

def map_cmd_input_changed_handler(args: adsk.core.InputChangedEventArgs):
    global selection_map_
    design: adsk.fusion.Design = app_.activeProduct
    table_input: adsk.core.TableCommandInput = args.inputs.itemById('table')
    if args.input.id == 'add_row':
        add_row(table_input, get_next_id())
    elif args.input.id == 'remove_row':
        pass
    elif args.input.id == 'select':
        row = table_input.selectedRow
        if row != -1:
            select_input = args.inputs.itemById('select')
            text_id = get_text_id(table_input.getInputAtPosition(row, 0))
            selected_input = table_input.commandInputs.itemById(f'selected_{text_id}')
            
            selections = selection_map_[text_id]
            selections.clear()
            for i in range(select_input.selectionCount):
                sketch_text = select_input.selection(i).entity
                sketch = sketch_text.parentSketch
                selections.append(sketch_text)
            selected_input = table_input.commandInputs.itemById(f'selected_{text_id}')
            set_selected_text(selected_input, selections)
    elif args.input.id.startswith('parameter_'):
        parameter_input: adsk.core.DropDownCommandInput = args.input
        text_id = get_text_id(parameter_input)
        custom_input = table_input.commandInputs.itemById(f'custom_{text_id}')
        # Using isReadOnly instead of isEnabled, to allow the user to still select the row
        custom_input.isReadOnly = (parameter_input.selectedItem.index != 0)
    elif args.input.id.startswith('custom_'):
        print("custom")

def set_selected_text(selected_input, selections):
    if selections:
        selected_input.value = ', '.join(sorted(set([s.parentSketch.name for s in selections])))
    else:
        selected_input.value = '<No selections>'

def get_text_id(input_or_str):
    if isinstance(input_or_str, adsk.core.CommandInput):
        input_or_str = input_or_str.id
    return input_or_str.split('_')[-1]

def add_row(table_input, text_id, new_row=True, text_type=None, custom_text=None):
    global selection_map_
    design: adsk.fusion.Design = app_.activeProduct

    selections = selection_map_[text_id]

    row_index = table_input.rowCount

    # Using StringValueInput + isReadOnly to allow the user to still select the row
    selected_input = table_input.commandInputs.addStringValueInput(f'selected_{text_id}', '', '')
    #addTextBoxCommandInput(f'selected_{text_id}', '', '', 1, True)
    selected_input.isReadOnly = True
    set_selected_text(selected_input, selections)

    parameter_input = table_input.commandInputs.addDropDownCommandInput(f'parameter_{text_id}', '',
                                                                        adsk.core.DropDownStyles.LabeledIconDropDownStyle)

    custom_item = parameter_input.listItems.add('Custom value', True, './resources/custom_text')
    if text_type == 'custom':
        custom_item.isSelected = True

    parameter_input.listItems.addSeparator(-1)

    for param in design.userParameters:
        param_item = parameter_input.listItems.add(param.name, False, thomasa88lib.utils.get_fusion_deploy_folder() +
                '/Fusion/UI/FusionUI/Resources/Parameters/ParametersCommand')
        if text_type == 'parameter' and param.name == custom_text:
            param_item.isSelected = True
    
    if not new_row and not parameter_input.selectedItem and custom_text is not None:
        # Parameter has disappeared.. Roll with it..
        # Cross icon?
        param_item = parameter_input.listItems.add(param.name, False, thomasa88lib.utils.get_fusion_deploy_folder() +
            '/Fusion/UI/FusionUI/Resources/Parameters/ParametersCommand')
        param_item.isSelected = True
    
    if text_type == 'custom':
        custom_input_text = custom_text
    else:
        custom_input_text = ''
    custom_input = table_input.commandInputs.addStringValueInput(f'custom_{text_id}', '', custom_input_text)

    table_input.addCommandInput(selected_input, row_index, SELECTED_COLUMN)
    table_input.addCommandInput(parameter_input, row_index, 1)
    table_input.addCommandInput(custom_input, row_index, 2)
    
    if new_row:
        table_input.selectedRow = row_index
        select_input = table_input.parentCommand.commandInputs.itemById('select')
        select_input.clearSelection()

def get_next_id():
    next_id_attr = design.attributes.itemByName('thomasa88_ParametricText', 'nextId')
    if not next_id_attr:
        next_id_attr = design.attributes.add('thomasa88_ParametricText', 'nextId', str(0))
    text_id = int(next_id_attr.value)
    next_id_attr.value = str(text_id + 1)
    return text_id

def map_cmd_execute_handler(args: adsk.core.CommandEventArgs):
    global selection_map_
    cmd = args.command
    save(cmd)

def save(cmd):
    table_input: adsk.core.TableCommandInput = cmd.commandInputs.itemById('table')
    design: adsk.fusion.Design = app_.activeProduct

    for row_index in range(table_input.rowCount):
        text_id = get_text_id(table_input.getInputAtPosition(row_index, 0))
        selections = selection_map_[text_id]
        parameter_input = table_input.commandInputs.itemById(f'parameter_{text_id}')
        selected_parameter = parameter_input.selectedItem
        if selected_parameter.index == 0:
            text = table_input.commandInputs.itemById(f'custom_{text_id}').value
            parameter_name = None
        else:
            parameter_name = selected_parameter.name
            parameter = design.userParameters.itemByName(parameter_name)
            if parameter:
                text = parameter.comment
            else:
                text = None
        if text is None:
            text = ''

        old_attrs = design.findAttributes('thomasa88_ParametricText', f'hasParametricText_{text_id}')
        for old_attr in old_attrs:
            old_attr.deleteMe()
        
        custom_text_attr = design.attributes.itemByName('thomasa88_ParametricText', f'customText_{text_id}')
        if custom_text_attr:
            custom_text_attr.deleteMe()

        for sketch_text in selections:
            if parameter_name:
                sketch_text.attributes.add('thomasa88_ParametricText', f'hasParametricText_{text_id}', 'parameter')
                design.attributes.add('thomasa88_ParametricText', f'customText_{text_id}', parameter_name)
            else:
                sketch_text.attributes.add('thomasa88_ParametricText', f'hasParametricText_{text_id}', 'custom')
                design.attributes.add('thomasa88_ParametricText', f'customText_{text_id}', text)
            sketch_text.text = text

    # Save some memory
    selection_map_.clear()

def load(cmd):
    global selection_map_
    table_input: adsk.core.TableCommandInput = cmd.commandInputs.itemById('table')
    design: adsk.fusion.Design = app_.activeProduct

    selection_map_.clear()

    text_types = {}

    attrs = design.findAttributes('thomasa88_ParametricText', 're:hasParametricText_[0-9]+')
    for attr in attrs:
        # Features might be consumed and return on rollback! Don't delete attribute (?)
        #if not attr.parent:
        #    attr.deleteMe()

        text_id = get_text_id(attr.name)
        selections = selection_map_[text_id]
        if attr.parent:
            selections.append(attr.parent)
        
        if attr.otherParents:
            for other_parent in attr.otherParents:
                selections.append(other_parent)
        
        text_types[text_id] = attr.value

    for text_id in selection_map_.keys():
        text_type = text_types[text_id]
        custom_text_attr = design.attributes.itemByName('thomasa88_ParametricText', f'customText_{text_id}')
        if custom_text_attr:
            custom_text = custom_text_attr.value
        else:
            custom_text = None

        add_row(table_input, text_id, new_row=False,
                text_type=text_type,
                custom_text=custom_text)
    