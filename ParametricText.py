#Author-Thomas Axelsson
#Description-Allows using parameters for texts.

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

import adsk.core, adsk.fusion, adsk.cam, traceback
from collections import defaultdict
import datetime
import re

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

QUICK_REF = '''<b>Quick Reference</b><br>
{_.version}<br>
{param}|{param.value}, {param.expr}, {param.unit}, {param.comment}<br>
{_.version:03} = 024 (integer),<br>
{param.value:.3f} = 1.000, {param.value:03.0f} = 001 (float),<br>
{param.comment:.6} = My com
'''
QUICK_REF_LINES = QUICK_REF.count('<br>') + 1

class SelectAction:
    Select = 1
    Unselect = 2

class DialogState:
    def __init__(self):
        self.last_selected_row = None
        self.addin_updating_select = False
        self.removed_texts = []
        # Keep a list of unselects, to handle user unselecting multiple at once (window selection)
        self.pending_unselects = []

app_ = None
ui_ = None

manifest_ = thomasa88lib.manifest.read()
error_catcher_ = thomasa88lib.error.ErrorCatcher(msgbox_in_debug=False,
                                                 msg_prefix=f'{NAME} v {manifest_["version"]}')
events_manager_ = thomasa88lib.events.EventsManager(error_catcher_)

# Contains selections for all rows of the currently active dialog
# This dict must be reset every time the dialog is opened,
# as the user might have cancelled it the last time.
# The list for each row cannot be a set(), as SketchText is not hashable.
dialog_selection_map_ = defaultdict(list)

# It seems that attributes are not saved until the command is executed,
# so we must keep the ID in a buffer, to keep track correctly
# We don't need to keep an ID per open document, as the command is
# terminated (executed) and closed when the user switches document,
# so just keep one global ID.
dialog_next_id_ = None

dialog_state_ = None

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
                                                                 'Displays the Text Parameters dialog box.\n\n'
                                                                 'Assign and edit sketch text parameters.\n\n'
                                                                  f'({NAME} v {manifest_["version"]})',
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

    # Set this explicitly. Better to save than lose everything when the user launches
    # another command (?)
    cmd.isExecutedWhenPreEmpted = True

    events_manager_.add_handler(cmd.execute,
                                callback=map_cmd_execute_handler)

    events_manager_.add_handler(cmd.inputChanged,
                                callback=map_cmd_input_changed_handler)

    events_manager_.add_handler(cmd.preSelect,
                                callback=map_cmd_pre_select_handler)
    events_manager_.add_handler(cmd.select,
                                callback=map_cmd_select_handler)
    events_manager_.add_handler(cmd.unselect,
                                callback=map_cmd_unselect_handler)

    about = cmd.commandInputs.addTextBoxCommandInput('about', '', f'<font size="4"><b>{NAME} v{manifest_["version"]}</b></font>', 2, True)
    about.isFullWidth = True
    
    table_input = cmd.commandInputs.addTableCommandInput('table', '', 3, '4:1:8')
    table_input.isFullWidth = True
    table_input.maximumVisibleRows = 10
    table_input.minimumVisibleRows = 10

    table_add = table_input.commandInputs.addBoolValueInput('add_row_btn', '+', False, './resources/add', True)
    table_add.tooltip = 'Add a new row'
    table_remove = table_input.commandInputs.addBoolValueInput('remove_row_btn', '-', False, './resources/remove', True)
    table_remove.tooltip = 'Remove selected row'
    table_button_spacer = table_input.commandInputs.addBoolValueInput('spacer', '  ', False, '', True)
    table_button_spacer.isEnabled = False
    insert_braces = table_input.commandInputs.addBoolValueInput('insert_braces_btn', '{}', False, './resources/braces', True)
    insert_braces.tooltip = 'Insert curly braces'
    insert_braces.tooltipDescription = ('Inserts curly braces at the end of the text box of the currently selected row.\n\n'
                                        'This button allows insertion of curly braces when Fusion 360™ '
                                        'prevents insertion when using a keyboard layout that requires AltGr to be pressed.')
    
    table_input.addToolbarCommandInput(table_add)
    table_input.addToolbarCommandInput(table_remove)
    table_input.addToolbarCommandInput(table_button_spacer)
    table_input.addToolbarCommandInput(insert_braces)
    
    # The select events cannot work without having an active SelectionCommandInput
    select_input = cmd.commandInputs.addSelectionInput('select', 'Sketch Texts', '')
    select_input.addSelectionFilter(adsk.core.SelectionCommandInput.Texts)
    select_input.setSelectionLimits(0, 0)
    select_input.isVisible = False

    quick_ref = table_input.commandInputs.addTextBoxCommandInput('quick_ref', '', QUICK_REF, QUICK_REF_LINES, True)
    quick_ref.isFullWidth = True

    # Reset dialog state
    global dialog_state_
    dialog_state_ = DialogState()

    load(cmd)

    if table_input.rowCount == 0:
        add_row(table_input, get_next_id())

### preview: executePreview show text from param.

def map_cmd_input_changed_handler(args: adsk.core.InputChangedEventArgs):
    global dialog_selection_map_
    design: adsk.fusion.Design = app_.activeProduct
    table_input: adsk.core.TableCommandInput = args.inputs.itemById('table')
    select_input = args.inputs.itemById('select')
    need_update_select_input = False
    update_select_force = False
    text_id = get_text_id(args.input)
    if args.input.id == 'add_row_btn':
        add_row(table_input, get_next_id())
    elif args.input.id == 'remove_row_btn':
        row = table_input.selectedRow
        if row != -1:
            remove_row(table_input, row)
    elif args.input.id == 'insert_braces_btn':
        row = table_input.selectedRow
        if row != -1:
            text_id = get_text_id(table_input.getInputAtPosition(row, 0))
            value_input = table_input.commandInputs.itemById(f'value_{text_id}')
            value_input.value += '{}'
    elif args.input.id.startswith('value_'):
        need_update_select_input = True
    elif args.input.id.startswith('sketchtexts_'):
        need_update_select_input = True
    elif args.input.id.startswith('clear_btn_'):
        sketch_texts_input = table_input.commandInputs.itemById(f'sketchtexts_{text_id}')
        sketch_texts = dialog_selection_map_[text_id]
        sketch_texts.clear()
        set_row_sketch_texts_text(sketch_texts_input, sketch_texts)
        need_update_select_input = True
        update_select_force = True
    elif args.input.id == 'select':
        handle_select_input_change(table_input)

    if need_update_select_input:
        # Wait for the table row selection to update before updating select input
        events_manager_.delay(lambda: update_select_input(table_input, update_select_force))

def map_cmd_pre_select_handler(args: adsk.core.SelectionEventArgs):
    # Select all proxies pointing to the same SketchText
    selected_text_proxy = args.selection.entity
    native_sketch_text = get_native_sketch_text(selected_text_proxy)
    sketch_text_proxies = get_sketch_text_proxies(native_sketch_text)
    additional = adsk.core.ObjectCollection.create()
    for sketch_text_proxy in sketch_text_proxies:
        # Documentation says to not add the user-provided selection,
        # as it will make it unselected.
        # Does not seem to make a difference. Maybe it only applies
        # to the select event.
        if sketch_text_proxy != selected_text_proxy:
            additional.add(sketch_text_proxy)
    # Note: This triggers a select event for every added selection
    args.additionalEntities = additional

def map_cmd_select_handler(args: adsk.core.SelectionEventArgs):
    #print("SELECT", args.selection.entity, args.selection.entity.parentSketch.name)
    dialog_state_.pending_unselects.clear()

def map_cmd_unselect_handler(args: adsk.core.SelectionEventArgs):
    #print("UNSELECT", args.selection.entity, args.selection.entity.parentSketch.name)
    # args.additionalEntities does not seem to work for unselect and activeInput seems
    # to not be set. Just store what happened and sort it out in the input_changed
    # handler.
    dialog_state_.pending_unselects.append(args.selection.entity)

def handle_select_input_change(table_input):
    row = table_input.selectedRow
    if dialog_state_.addin_updating_select or row == -1:
        return

    select_input = command_.commandInputs.itemById('select')
    text_id = get_text_id(table_input.getInputAtPosition(row, 0))
    sketch_texts_input = table_input.commandInputs.itemById(f'sketchtexts_{text_id}')
    
    sketch_texts = dialog_selection_map_[text_id]
    sketch_texts.clear()
    pending_unselect_sketch_texts = [get_native_sketch_text(u)
                                     for u in dialog_state_.pending_unselects]
    for i in range(select_input.selectionCount):
        # The selection will give us a proxy to the instance that the user selected
        sketch_text_proxy = select_input.selection(i).entity
        native_sketch_text = get_native_sketch_text(sketch_text_proxy)
        if not native_sketch_text:
            # This should not happen, but handle it gracefully
            print(f"{NAME} could not get native skech text for {sketch_text_proxy.parentSketch.name}")
            continue
        if (native_sketch_text not in sketch_texts and
            native_sketch_text not in pending_unselect_sketch_texts):
            sketch_texts.append(native_sketch_text)
    set_row_sketch_texts_text(sketch_texts_input, sketch_texts)

    if dialog_state_.pending_unselects:
        dialog_state_.pending_unselects.clear()
        # User unselected a sketch text proxy. We need to unselect all proxies pointing
        # to the same sketch text.
        # There seems to be no way of removing selections from SelectionCommandInput,
        # so we rebuild the selection list instead.
        update_select_input(table_input, force=True)

def update_select_input(table_input, force=False):
    if not table_input.isValid:
        # Dialog is likely closed. This is an effect of the delay() call.
        return
    
    row = table_input.selectedRow
    if row != dialog_state_.last_selected_row or force:
        # addSelection trigger inputChanged events. They are triggered directly at the function call.
        dialog_state_.addin_updating_select = True
        select_input = command_.commandInputs.itemById('select')
        select_input.clearSelection()
        if row != -1:
            text_id = get_text_id(table_input.getInputAtPosition(row, 0))
            for sketch_text in dialog_selection_map_[text_id]:
                # "This method is not valid within the commandCreated event but must be used later
                # in the command lifetime. If you want to pre-populate the selection when the
                # command is starting, you can use this method in the activate method of the Command."
                for sketch_text_proxy in get_sketch_text_proxies(sketch_text):
                    select_input.addSelection(sketch_text_proxy)
        dialog_state_.last_selected_row = row
        dialog_state_.addin_updating_select = False

def get_native_sketch_text(sketch_text_proxy):
    if sketch_text_proxy is None:
        return None
    sketch_proxy = sketch_text_proxy.parentSketch
    native_sketch = sketch_proxy.nativeObject
    if native_sketch is None:
        # This is already a native object (likely a root component sketch)
        return sketch_text_proxy
    return find_equal_sketch_text(native_sketch, sketch_text_proxy)

def get_sketch_text_proxies(native_sketch_text):
    design: adsk.fusion.Design = app_.activeProduct
    native_sketch = native_sketch_text.parentSketch
    in_occurrences = design.rootComponent.allOccurrencesByComponent(native_sketch.parentComponent)

    if in_occurrences.count == 0:
        # Root level sketch. There are no occurences and there will be no proxies.
        return [native_sketch_text]

    sketch_text_proxies = []
    for occurrence in in_occurrences:
        sketch_proxy = native_sketch.createForAssemblyContext(occurrence)
        sketch_text_proxy = find_equal_sketch_text(sketch_proxy, native_sketch_text)
        sketch_text_proxies.append(sketch_text_proxy)
    return sketch_text_proxies

def find_equal_sketch_text(sketch, sketch_text):
    '''Used when mapping proxy <--> native'''
    for st in sketch.sketchTexts:
        if is_sketch_text_equal(st, sketch_text):
            return st

def is_sketch_text_equal(a, b):
    '''Tries to determine if two SketchText objects belonging to the same Sketch are equal.
    SketchTexts might be proxies.'''
    return a.position.isEqualTo(b.position)

def set_row_sketch_texts_text(sketch_texts_input, sketch_texts):
    if sketch_texts:
        value = ', '.join(sorted(set([s.parentSketch.name for s in sketch_texts])))
        # Indicate if not all selections are visible. Show all in tooltip.
        if len(sketch_texts) > 2:
            sketch_texts_input.value = f'({len(sketch_texts)}) {value}'
        else:
            sketch_texts_input.value = value
        sketch_texts_input.tooltip = value
    else:
        sketch_texts_input.value = '<No selections>'
        sketch_texts_input.tooltip = ''

def get_text_id(input_or_str):
    if isinstance(input_or_str, adsk.core.CommandInput):
        input_or_str = input_or_str.id
    return input_or_str.split('_')[-1]

def add_row(table_input, text_id, new_row=True, text=None):
    global dialog_selection_map_
    design: adsk.fusion.Design = app_.activeProduct

    sketch_texts = dialog_selection_map_[text_id]

    row_index = table_input.rowCount

    # Using StringValueInput + isReadOnly to allow the user to still select the row
    sketch_texts_input = table_input.commandInputs.addStringValueInput(f'sketchtexts_{text_id}', '', '')
    sketch_texts_input.isReadOnly = True
    set_row_sketch_texts_text(sketch_texts_input, sketch_texts)

    clear_selection_input = table_input.commandInputs.addBoolValueInput(f'clear_btn_{text_id}', 'X',
                                                                        False, './resources/clear_selection', True)
    clear_selection_input.tooltip = 'Clear selection'    
    
    if not text:
        text = ''
    value_input = table_input.commandInputs.addStringValueInput(f'value_{text_id}', '', text)

    table_input.addCommandInput(sketch_texts_input, row_index, 0)
    table_input.addCommandInput(clear_selection_input, row_index, 1)
    table_input.addCommandInput(value_input, row_index, 2)
    
    if new_row:
        table_input.selectedRow = row_index
        select_input = table_input.parentCommand.commandInputs.itemById('select')
        select_input.clearSelection()

def remove_row(table_input: adsk.core.TableCommandInput, row_index):
    text_id = get_text_id(table_input.getInputAtPosition(row_index, 0))
    table_input.deleteRow(row_index)
    dialog_state_.removed_texts.append(text_id)
    if table_input.rowCount > row_index:
        table_input.selectedRow = row_index
    else:
        table_input.selectedRow = table_input.rowCount - 1
    update_select_input(table_input, force=True)
    ### Restore original texts, if cached, if we have live update. Also on unselect.

def get_next_id():
    global dialog_next_id_
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

    if not save_next_id():
        return

    for row_index in range(table_input.rowCount):
        text_id = get_text_id(table_input.getInputAtPosition(row_index, 0))
        sketch_texts = dialog_selection_map_[text_id]
        text = table_input.commandInputs.itemById(f'value_{text_id}').value

        remove_attributes(text_id)

        design.attributes.add('thomasa88_ParametricText', f'textValue_{text_id}', text)
    
        for sketch_text in sketch_texts:
            sketch_text.attributes.add('thomasa88_ParametricText', f'hasText_{text_id}', '')
            set_sketch_text(sketch_text, evaluate_text(text))

    for text_id in dialog_state_.removed_texts:
        remove_attributes(text_id)

    # Save some memory
    dialog_selection_map_.clear()

def save_next_id():
    global dialog_next_id_
    design: adsk.fusion.Design = app_.activeProduct
    next_id = dialog_next_id_
    print(f"{NAME} SAVE NEXT ID {next_id}")
    if next_id is None:
        ui_.messageBox(f'{NAME}: Failed to save text ID counter. Save failed.\n\n'
                       'Please inform the developer of the steps you performed to trigger this error.')
        return False
    design.attributes.add('thomasa88_ParametricText', 'nextId', str(next_id))
    dialog_next_id_ = None
    return True

def remove_attributes(text_id):
    design = app_.activeProduct

    old_attrs = design.findAttributes('thomasa88_ParametricText', f'hasText_{text_id}')
    for old_attr in old_attrs:
        old_attr.deleteMe()

    value_attr = design.attributes.itemByName('thomasa88_ParametricText', f'textValue_{text_id}')
    if value_attr:
        value_attr.deleteMe()

def set_sketch_text(sketch_text, text):
    try:
        sketch_text.text = text
    except RuntimeError as e:
        msg = None
        if len(e.args) > 0:
            msg = e.args[0]
        # Must be able to handle both errors. Angle error seems to come first,
        # so we will not reach the font error in that case.
        if msg == '3 : invalid input font name':
            # SHX font bug. Cannot set text when a SHX font is used. Switch to a TrueType font temporarily.
            # Bug: https://forums.autodesk.com/t5/fusion-360-api-and-scripts/cannot-select-shx-fonts-on-sketchtext-object/m-p/9606551
            old_font = sketch_text.fontName + '.shx'
            # Let's hope the user has Arial
            sketch_text.fontName = 'Arial'
            sketch_text.text = evaluate_text(text)
            sketch_text.fontName = old_font
        elif msg == '3 : invalid input angle':
            # Negative angle bug. Cannot set text when the angle is negative.
            # Bug: https://forums.autodesk.com/t5/fusion-360-api-and-scripts/bug-unable-to-modify-text-of-a-sketchtext-created-manually-with/m-p/9502107
            ui_.messageBox(f'Cannot set text parameter in the sketch "{sketch_text.parentSketch.name}" '
                            'due to the text having a negative angle.\n\n'
                            'Please edit the text to have a positive angle (add 360 degrees to the current angle).\n\n'
                            'See add-in help document/README for more information.',
                            f'{NAME} v {manifest_["version"]}')
            # Unhook the text from the text parameter?

SUBST_PATTERN = re.compile(r'{([^}]+)}')
def evaluate_text(text, next_version=False):
    design: adsk.fusion.Design = app_.activeProduct
    def sub_func(subst_match):
        # https://www.python.org/dev/peps/pep-3101/
        # https://docs.python.org/3/library/string.html#formatspec
        var, options_sep, options = subst_match.group(1).partition(':')

        var_name, member_sep, member = var.partition('.')

        if var_name == '_':
            if member == 'version':
                # No version information available if the document is not saved
                if app_.activeDocument.isSaved:
                    version = app_.activeDocument.dataFile.versionNumber
                else:
                    version = 0
                if next_version:
                    version += 1
                value = version
            elif member == 'date':
                # This will provide the date and time using the local timezone
                # We don't have to delegate to strftime(), as .format() on datetime handles this!

                # Format as ISO 8601 date if no options are given
                if not options_sep:
                    options_sep = ':'
                    options = '%Y-%m-%d'

                if next_version:
                    # The user is saving, grab the current time. It will probably be a few
                    # seconds before the actual save time, but that should be good enough.
                    # Note: We must do this update before the save happens, to get a correct
                    # value in the save and to avoid making the document modified after the
                    # save.
                    save_time = datetime.datetime.now(tz=datetime.timezone.utc)
                elif app_.activeDocument.isSaved:
                    unix_time_utc = app_.activeDocument.dataFile.dateCreated
                    save_time = datetime.datetime.fromtimestamp(unix_time_utc,
                                                                tz=datetime.timezone.utc)
                else:
                    # Set a fake time until the document is saved for the first time
                    # Doing this in the user's timezone, to get midnight time correct.
                    now = datetime.datetime.now(tz=None)
                    save_time = now.replace(hour=0, minute=0, second=0, microsecond=0)

                save_time_local = save_time.astimezone()
                value = save_time_local
            else:
                return f'<Unknown member of {var_name}: {member}>'
        else:
            param = design.allParameters.itemByName(var_name)
            if param is None:
                return f'<Unknown parameter: {var_name}>'

            if member == 'value' or member == '':
                # Make sure that the value is in the unit that the user has given
                if param.unit == '':
                    # Unit-less
                    value = param.value
                else:
                    value = design.fusionUnitsManager.convert(param.value, "internalUnits", param.unit)
            elif member == 'comment':
                value = param.comment
            elif member == 'expr':
                value = param.expression
            elif member == 'unit':
                value = param.unit
            else:
                return f'<Unknown member of {var_name}: {member}>'
            
        try:
            formatted_str = ('{' + options_sep + options + '}').format(value)
        except ValueError as e:
            formatted_str = f'<{e.args[0]}>'
        return formatted_str

    shown_text = SUBST_PATTERN.sub(sub_func, text)
    return shown_text

def load(cmd):
    global dialog_selection_map_
    table_input: adsk.core.TableCommandInput = cmd.commandInputs.itemById('table')

    load_next_id()

    dialog_selection_map_.clear()
    texts = get_texts()

    for text_id, text_info in texts.items():
        dialog_selection_map_[text_id] = text_info.sketch_texts
        add_row(table_input, text_id, new_row=False,
                text=text_info.text_value)

def load_next_id():
    global dialog_next_id_
    design: adsk.fusion.Design = app_.activeProduct
    next_id_attr = design.attributes.itemByName('thomasa88_ParametricText', 'nextId')
    if next_id_attr:
        if next_id_attr.value is None or next_id_attr.value == 'None':
            ui_.messageBox(f'{NAME}: Text id count value is corrupt: {next_id_attr.value}.\n\n'
                           'New texts might overwrite values of old texts. You should be able '
                           'to recover by loading an old version of this document.\n\n'
                           'Please inform the developer of what steps you performed to trigger this error.')
            dialog_next_id_ = 100 # Try to skip past used IDs..
        else:
            dialog_next_id_ = int(next_id_attr.value)
    else:
        dialog_next_id_ = 0
    print(f"{NAME} LOAD NEXT ID {dialog_next_id_}")

class TextInfo:
    def __init__(self):
        self.sketch_texts = []
        self.text_value = None

def get_texts():
    design: adsk.fusion.Design = app_.activeProduct

    texts = defaultdict(TextInfo)

    value_attrs = [attr for attr in design.attributes.itemsByGroup('thomasa88_ParametricText')
                  if attr.name.startswith('textValue_')]
    for value_attr in value_attrs:
        if not value_attr:
            continue
        text_id = get_text_id(value_attr.name)
        text_info = texts[text_id]
        text_info.text_value = value_attr.value

        # Get all sketch texts belonging to the attribute
        has_attrs = design.findAttributes('thomasa88_ParametricText', f'hasText_{text_id}')
        for has_attr in has_attrs:
            sketch_texts = text_info.sketch_texts
            if has_attr.parent:
                sketch_texts.append(has_attr.parent)        
            if has_attr.otherParents:
                for other_parent in has_attr.otherParents:
                    sketch_texts.append(other_parent)
    
    return texts

def document_saving_handler(args: adsk.core.DocumentEventArgs):
    if ui_.activeWorkspace.id == 'FusionSolidEnvironment':
        texts = get_texts()
        for text_id, text_info in texts.items():
            text = text_info.text_value
            
            if '_.version' or '_.date' in text:
                for sketch_text in text_info.sketch_texts:
                    set_sketch_text(sketch_text, evaluate_text(text, next_version=True))

def command_terminated_handler(args: adsk.core.ApplicationCommandEventArgs):
    if (args.commandId == 'ChangeParameterCommand' and
        args.terminationReason == adsk.core.CommandTerminationReason.CompletedTerminationReason):
        # User (might have) changed a parameter
        texts = get_texts()
        for text_id, text_info in texts.items():
            evaluated_text = evaluate_text(text_info.text_value)
            
            if text_info.sketch_texts and text_info.sketch_texts[0].text != evaluated_text:
                for sketch_text in text_info.sketch_texts:
                    set_sketch_text(sketch_text, evaluated_text)
    ### TODO: Update when user selects "Compute All"
    #elif args.commandId == 'FusionComputeAllCommand':
    #    load()
    #    save()
