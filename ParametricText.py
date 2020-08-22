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

MAP_CMD_ID = 'thomasa88_ParametricText_Map'
PANEL_IDS = [
            'SketchModifyPanel',
            'SolidModifyPanel',
            'SheetMetalModifyPanel',
            'AssembleUtilityPanel',
            'SurfaceModifyPanel',
            'SnapshotSolidModifyPanel'
        ]

SELECTED_COLUMN = 0

app_ = None
ui_ = None

error_catcher_ = thomasa88lib.error.ErrorCatcher(msgbox_in_debug=False)
events_manager_ = thomasa88lib.events.EventsManager(error_catcher_)
manifest_ = thomasa88lib.manifest.read()

# Contains selections for the currently active dialog
# This dict must be reset every time the dialog is opened,
# as the user might have cancelled it the last time.
dialog_selection_map_ = defaultdict(list)

# It seems that attributes are not saved until the command is executed,
# so we must keep the ID in a buffer, to keep track correctly
dialog_next_id_ = None

last_selected_row_ = None
addin_updating_select_ = False
removed_texts_ = []

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
                                                                  f'Change Text Parameters',
                                                                  f'{NAME} (v {manifest_["version"]})',
                                                                  './resources/text_parameter')
        events_manager_.add_handler(map_cmd_def.commandCreated,
                                    callback=map_cmd_created_handler)

        for panel_id in PANEL_IDS:
            panel = ui_.allToolbarPanels.itemById(panel_id)
            old_control = panel.controls.itemById(MAP_CMD_ID)
            if old_control:
                old_control.deleteMe()
            panel.controls.addCommand(map_cmd_def, 'ChangeParameterCommand', False)

        #map_control = panel.controls.addCommand(map_cmd_def)
        #map_control.isPromotedByDefault = True
        #map_control.isPromoted = True

        events_manager_.add_handler(app_.documentSaving, callback=document_saving_handler)
        events_manager_.add_handler(ui_.commandTerminated, callback=command_terminated_handler)

def stop(context):
    with error_catcher_:
        events_manager_.clean_up()

        for panel_id in PANEL_IDS:
            panel = ui_.allToolbarPanels.itemById(panel_id)
            control = panel.controls.itemById(MAP_CMD_ID)
            if control:
                control.deleteMe()
        
        map_cmd_def = panel.controls.itemById(MAP_CMD_ID)
        if map_cmd_def:
            map_cmd_def.deleteMe()

def map_cmd_created_handler(args: adsk.core.CommandCreatedEventArgs):
    global command_
    cmd = args.command
    command_ = cmd
    design: adsk.fusion.Design = app_.activeProduct

    cmd.setDialogMinimumSize(450, 200)
    cmd.setDialogInitialSize(450, 300)

    events_manager_.add_handler(cmd.execute,
                                callback=map_cmd_execute_handler)

    events_manager_.add_handler(cmd.inputChanged,
                                callback=map_cmd_input_changed_handler)

    about = cmd.commandInputs.addTextBoxCommandInput('about', '', f'{NAME} v{manifest_["version"]}', 1, True)
    about.isFullWidth = True
    
    table_input = cmd.commandInputs.addTableCommandInput('table', '', 3, '')
    table_input.isFullWidth = True
    table_add = table_input.commandInputs.addBoolValueInput('add_row', '+', False,
                                                            thomasa88lib.utils.get_fusion_deploy_folder() +
                                                            '/Fusion/UI/FusionUI/Resources/Image/Add', True)
    table_remove = table_input.commandInputs.addBoolValueInput('remove_row', '-', False,
                                                               thomasa88lib.utils.get_fusion_deploy_folder() +
                                                               '/Fusion/UI/FusionUI/Resources/Image/Remove', True)
    table_input.addToolbarCommandInput(table_add)
    table_input.addToolbarCommandInput(table_remove)
    
    select_input = cmd.commandInputs.addSelectionInput('select', 'Sketch Texts', '')
    select_input.addSelectionFilter(adsk.core.SelectionCommandInput.Texts)
    select_input.setSelectionLimits(0, 0)

    global removed_texts_
    removed_texts_.clear()
    load(cmd)

    if table_input.rowCount == 0:
        add_row(table_input, get_next_id())

### preview: executePreview show text from param.

def map_cmd_input_changed_handler(args: adsk.core.InputChangedEventArgs):
    global dialog_selection_map_
    design: adsk.fusion.Design = app_.activeProduct
    table_input: adsk.core.TableCommandInput = args.inputs.itemById('table')
    select_input = args.inputs.itemById('select')
    need_update_select = False
    text_id = get_text_id(args.input)
    if args.input.id == 'add_row':
        add_row(table_input, get_next_id())
    elif args.input.id == 'remove_row':
        row = table_input.selectedRow
        if row != -1:
            remove_row(table_input, row)
    elif args.input.id.startswith('parameter_'):
        need_update_select = True
        parameter_input: adsk.core.DropDownCommandInput = args.input
        custom_input = table_input.commandInputs.itemById(f'custom_{text_id}')
        # Using isReadOnly instead of isEnabled, to allow the user to still select the row
        has_custom_text = (parameter_input.selectedItem.index == 0)
        custom_input.isReadOnly = not has_custom_text
    elif args.input.id.startswith('custom_'):
        need_update_select = True
    elif args.input.id.startswith('selected_'):
        need_update_select = True
    elif args.input.id == 'select':
        global addin_updating_select_
        row = table_input.selectedRow
        if not addin_updating_select_:
            if row != -1:
                text_id = get_text_id(table_input.getInputAtPosition(row, 0))
                selected_input = table_input.commandInputs.itemById(f'selected_{text_id}')
                
                selections = dialog_selection_map_[text_id]
                selections.clear()
                for i in range(select_input.selectionCount):
                    text_proxy = select_input.selection(i).entity
                    sketch = text_proxy.parentSketch
                    selections.append(text_proxy)

                set_selected_text(selected_input, selections)

    if need_update_select:
        events_manager_.delay(lambda: update_select_input(table_input))

def update_select_input(table_input, force=False):
    global last_selected_row_
    row = table_input.selectedRow
    if row != last_selected_row_ or force:
        global addin_updating_select_
        # addSelection trigger inputChanged events. They are triggered directly at the function call.
        addin_updating_select_ = True
        select_input = command_.commandInputs.itemById('select')
        select_input.clearSelection()
        if row != -1:
            text_id = get_text_id(table_input.getInputAtPosition(row, 0))
            for text_proxy in dialog_selection_map_[text_id]:
                # "This method is not valid within the commandCreated event but must be used later
                # in the command lifetime. If you want to pre-populate the selection when the
                # command is starting, you can use this method in the activate method of the Command."
                select_input.addSelection(text_proxy)
        last_selected_row_ = row
        addin_updating_select_ = False

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
    global dialog_selection_map_
    global last_selected_row_
    design: adsk.fusion.Design = app_.activeProduct

    selections = dialog_selection_map_[text_id]

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
        last_selected_row_ = row_index
    
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
        addin_updating_select_
        select_input.clearSelection()

def remove_row(table_input: adsk.core.TableCommandInput, row_index):
    text_id = get_text_id(table_input.getInputAtPosition(row_index, 0))
    table_input.deleteRow(row_index)
    removed_texts_.append(text_id)
    if table_input.rowCount > row_index:
        table_input.selectedRow = row_index
    else:
        table_input.selectedRow = table_input.rowCount - 1
    update_select_input(table_input, force=True)
    ### Restore original texts, if cached, if we have live update. Also on unselect.

def get_next_id():
    global dialog_next_id_
    design: adsk.fusion.Design = app_.activeProduct
    next_id_attr = design.attributes.itemByName('thomasa88_ParametricText', 'nextId')
    text_id = dialog_next_id_
    dialog_next_id_ += 1
    return text_id

def map_cmd_execute_handler(args: adsk.core.CommandEventArgs):
    global dialog_selection_map_
    cmd = args.command
    save(cmd)

def save(cmd):
    table_input: adsk.core.TableCommandInput = cmd.commandInputs.itemById('table')
    design: adsk.fusion.Design = app_.activeProduct

    global dialog_next_id_
    design.attributes.add('thomasa88_ParametricText', 'nextId', str(dialog_next_id_))
    dialog_next_id_ = None

    for row_index in range(table_input.rowCount):
        text_id = get_text_id(table_input.getInputAtPosition(row_index, 0))
        selections = dialog_selection_map_[text_id]
        parameter_input = table_input.commandInputs.itemById(f'parameter_{text_id}')
        selected_parameter = parameter_input.selectedItem
        if selected_parameter.index == 0:
            parameter_name = None
            text = table_input.commandInputs.itemById(f'custom_{text_id}').value
        else:
            parameter_name = selected_parameter.name
            text = get_parameter_comment(parameter_name)

        remove_attributes(text_id)

        if parameter_name:
            design.attributes.add('thomasa88_ParametricText', f'customTextType_{text_id}', 'parameter')
            design.attributes.add('thomasa88_ParametricText', f'customTextValue_{text_id}', parameter_name)
        else:
            design.attributes.add('thomasa88_ParametricText', f'customTextType_{text_id}', 'custom')
            design.attributes.add('thomasa88_ParametricText', f'customTextValue_{text_id}', text)
    
        for sketch_text in selections:
            sketch_text.attributes.add('thomasa88_ParametricText', f'hasParametricText_{text_id}', '')
            sketch_text.text = evaluate_text(text)

    for text_id in removed_texts_:
        remove_attributes(text_id)

    # Save some memory
    dialog_selection_map_.clear()

def remove_attributes(text_id):
    design = app_.activeProduct

    old_attrs = design.findAttributes('thomasa88_ParametricText', f'hasParametricText_{text_id}')
    for old_attr in old_attrs:
        old_attr.deleteMe()
    
    custom_type = design.attributes.itemByName('thomasa88_ParametricText', f'customTextType_{text_id}')
    if custom_type:
        custom_type.deleteMe()

    custom_value = design.attributes.itemByName('thomasa88_ParametricText', f'customTextValue_{text_id}')
    if custom_value:
        custom_value.deleteMe()

def evaluate_text(text, next_version=False):
    version = app_.activeDocument.dataFile.latestVersionNumber
    if next_version:
        version += 1
    shown_text = text.replace('<version>', str(version))
    return shown_text

def load(cmd):
    global dialog_selection_map_
    design: adsk.fusion.Design = app_.activeProduct
    table_input: adsk.core.TableCommandInput = cmd.commandInputs.itemById('table')

    global dialog_next_id_
    next_id_attr = design.attributes.itemByName('thomasa88_ParametricText', 'nextId')
    if next_id_attr:
        dialog_next_id_ = int(next_id_attr.value)
    else:
        dialog_next_id_ = 0

    dialog_selection_map_.clear()
    texts = get_texts()

    for text_id, text_info in texts.items():
        dialog_selection_map_[text_id] = text_info.sketch_texts
        add_row(table_input, text_id, new_row=False,
                    text_type=text_info.text_type,
                    custom_text=text_info.text_value)

class TextInfo:
    def __init__(self):
        self.sketch_texts = []
        self.text_type = None
        self.text_value = None

def get_texts():
    design: adsk.fusion.Design = app_.activeProduct

    texts = defaultdict(TextInfo)

    type_attrs = [attr for attr in design.attributes.itemsByGroup('thomasa88_ParametricText')
                  if attr.name.startswith('customTextType_')]    
    for type_attr in type_attrs:
        if not type_attr:
            continue
        text_id = get_text_id(type_attr.name)
        value_attr = design.attributes.itemByName('thomasa88_ParametricText', f'customTextValue_{text_id}')
        if not value_attr:
            continue
        text_info = texts[text_id]
        text_info.text_type = type_attr.value
        text_info.text_value = value_attr.value

        # Get all sketch texts belonging to the attribute
        has_attrs = design.findAttributes('thomasa88_ParametricText', f're:hasParametricText_{text_id}')
        for has_attr in has_attrs:
            sketch_texts = text_info.sketch_texts
            if has_attr.parent:
                sketch_texts.append(has_attr.parent)        
            if has_attr.otherParents:
                for other_parent in has_attr.otherParents:
                    sketch_texts.append(other_parent)
    
    return texts

def document_saving_handler(args: adsk.core.DocumentEventArgs):
    texts = get_texts()
    for text_id, text_info in texts.items():
        text = ''
        if text_info.text_type == 'parameter':
            text = get_parameter_comment(text_info.text_value)
        else:
            text = text_info.text_value
        
        if '<version>' in text:
            for sketch_text in text_info.sketch_texts:
                sketch_text.text = evaluate_text(text, next_version=True)

def command_terminated_handler(args: adsk.core.ApplicationCommandEventArgs):
    if args.commandId == 'ChangeParameterCommand': # args.commandTerminationReason
        # User (might have) changed a parameter
        texts = get_texts()
        for text_id, text_info in texts.items():
            if text_info.text_type == 'parameter':
                text = get_parameter_comment(text_info.text_value)
                
                if text_info.sketch_texts and text_info.sketch_texts[0].text != text:
                    for sketch_text in text_info.sketch_texts:
                        sketch_text.text = evaluate_text(text)

def get_parameter_comment(parameter_name):
    design: adsk.fusion.Design = app_.activeProduct
    parameter = design.userParameters.itemByName(parameter_name)
    if parameter:
        text = parameter.comment
    else:
        text = '???'
    return text
