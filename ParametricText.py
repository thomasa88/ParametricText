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
import enum
import datetime
import queue
import re
import math

NAME = 'ParametricText'

try:
    # Must import lib as unique name, to avoid collision with other versions
    # loaded by other add-ins
    from .thomasa88lib import utils
    from .thomasa88lib import events
    from .thomasa88lib import manifest
    from .thomasa88lib import error
    from .thomasa88lib import settings
except ImportError as e:
    ui = adsk.core.Application.get().userInterface
    ui.messageBox(f'{NAME} cannot load since thomasa88lib seems to be missing.\n\n'
                  f'Please make sure you have installed {NAME} according to the '
                  'installation instructions.\n\n'
                  f'Error: {e}', f'{NAME}')
    raise

# Force modules to be fresh during development
import importlib
importlib.reload(thomasa88lib.utils)
importlib.reload(thomasa88lib.events)
importlib.reload(thomasa88lib.manifest)
importlib.reload(thomasa88lib.error)
importlib.reload(thomasa88lib.settings)

from . import paramparser
from . import paramformatter

MAP_CMD_ID = 'thomasa88_ParametricText_Map'
MIGRATE_CMD_ID = 'thomasa88_ParametricText_Migrate'
UPDATE_CMD_ID = 'thomasa88_ParametricText_Update'
ERROR_CMD_ID = 'thomasa88_ParametricText_ErrorNotification'
EXT_UPDATE_EVENT_ID = 'thomasa88_ParametricText_Ext_Update'
PANEL_IDS = [
            'SketchModifyPanel',
            'SolidModifyPanel',
            'SheetMetalModifyPanel',
            'AssembleUtilityPanel',
            'SurfaceModifyPanel',
            'SnapshotSolidModifyPanel'
        ]

QUICK_REF = '''<b>Quick Reference</b><br>
{_.component}, {_.sketch}, {_.date}, {_.file}, {_.version}, {_.compdesc}<br>
{param}|{param.value}, {param.expr}, {param.unit}, {param.comment}<br>
<br>
{_.version:03} = 024 (integer)<br>
{param.value:.3f} = 1.000, {param.value:03.0f} = 001 (float)<br>
{param.comment:.6} = My com<br>
{_.date:%Y-%m-%d} = 2020-10-24<br>
<a href="https://parametrictext.readthedocs.io/en/stable/parameters.html">Full reference</a>
'''
QUICK_REF_LINES = QUICK_REF.count('<br>')

# The attribute "database" version. Used to check compatibility with
# parameters stored in the document.
STORAGE_VERSION = 2
ATTRIBUTE_GROUP = 'thomasa88_ParametricText'

AUTOCOMPUTE_SETTING = 'autocompute'

class DialogState:
    def __init__(self):
        self.last_selected_row = None
        self.addin_updating_select = False
        self.removed_texts = []
        # Keep a list of unselects, to handle user unselecting multiple at once (window selection)
        self.pending_unselects = []
        self.insert_button_values = []

class InsertButtonValue:
    def __init__(self, value, prepend=False):
        self.value = value
        self.prepend = prepend

app_ = None
ui_ = None

manifest_ = thomasa88lib.manifest.read()

NAME_VERSION = f'{NAME} v {manifest_["version"]}'

error_catcher_ = thomasa88lib.error.ErrorCatcher(msgbox_in_debug=False,
                                                 msg_prefix=NAME_VERSION)
events_manager_ = thomasa88lib.events.EventsManager(error_catcher_)
settings_ = thomasa88lib.settings.SettingsManager({
    AUTOCOMPUTE_SETTING: True
})

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

# Flag to disable add-in if there are storage mismatches.
enabled_ = True

# Flag to check if add-in has been started/initialized.
started_ = False

class WorkaroundState(enum.Enum):
    Check = 0
    Enabled = 1
    Disabled = 2

text_height_workaround_state_ = WorkaroundState.Disabled

def run(context):
    global app_
    global ui_
    with error_catcher_:
        app_ = adsk.core.Application.get()
        ui_ = app_.userInterface

        # Instance check, in case the user has installed ParametricText both from
        # the app store and from github
        instance_string = f'{NAME_VERSION} in {thomasa88lib.utils.get_file_dir()}'
        if hasattr(adsk, 'thomasa88_parametric_text_running'):
            ui_.messageBox(f"Two copies of {NAME} are enabled:\n\n"
                           f"{adsk.thomasa88_parametric_text_running}\n"
                           f"{instance_string}\n\n"
                           "Please disable (add-ins dialog) or uninstall one copy.",
                           NAME_VERSION)
            return
        adsk.thomasa88_parametric_text_running = instance_string
        global started_
        started_ = True

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
                                                                  f'({NAME_VERSION})',
                                                                  './resources/text_parameter')
        events_manager_.add_handler(map_cmd_def.commandCreated,
                                    callback=map_cmd_created_handler)

        for panel_id in PANEL_IDS:
            panel = ui_.allToolbarPanels.itemById(panel_id)
            old_control = panel.controls.itemById(MAP_CMD_ID)
            if old_control:
                old_control.deleteMe()
            panel.controls.addCommand(map_cmd_def, 'ChangeParameterCommand', False)

        events_manager_.add_handler(app_.documentSaving, callback=document_saving_handler)
        events_manager_.add_handler(ui_.commandTerminated, callback=command_terminated_handler)

        events_manager_.add_handler(app_.documentOpened, callback=document_opened_handler)

        # Command used to group all "Set attributes" to one item in Undo history
        update_cmd_def = ui_.commandDefinitions.itemById(UPDATE_CMD_ID)
        if update_cmd_def:
            update_cmd_def.deleteMe()
        update_cmd_def = ui_.commandDefinitions.addButtonDefinition(UPDATE_CMD_ID, 'Calculate Text Parameters', '')
        events_manager_.add_handler(update_cmd_def.commandCreated,
                                    callback=update_cmd_created_handler)

        error_cmd_def = ui_.commandDefinitions.itemById(ERROR_CMD_ID)
        if error_cmd_def:
            error_cmd_def.deleteMe()
        error_cmd_def = ui_.commandDefinitions.addButtonDefinition(ERROR_CMD_ID, 'Show error', '')
        events_manager_.add_handler(error_cmd_def.commandCreated,
                                    callback=error_cmd_created_handler)
        
        delayed_event = events_manager_.register_event(EXT_UPDATE_EVENT_ID)
        events_manager_.add_handler(delayed_event, callback=ext_call_update_handler)

        if app_.isStartupComplete and is_design_workspace():
            # Add-in was (re)loaded while Fusion 360 was running
            check_storage_version()

def stop(context):
    if not started_:
        return

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

        del adsk.thomasa88_parametric_text_running

def map_cmd_created_handler(args: adsk.core.CommandCreatedEventArgs):
    global command_
    cmd = args.command
    command_ = cmd
    design: adsk.fusion.Design = app_.activeProduct

    if not enabled_:
        if not check_storage_version():
            return

    # Reset dialog state
    global dialog_state_
    dialog_state_ = DialogState()

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
    # Fusion 2.0.15291 breaks isFullWidth. Exception: RuntimeError: 2 : InternalValidationError : control
    # Bug: https://forums.autodesk.com/t5/fusion-360-api-and-scripts/bug-update-now-throws-exception-setting-isfullwidth-on/m-p/11725404
    try:
        table_input.isFullWidth = True
    except RuntimeError:
        pass
    table_input.maximumVisibleRows = 10
    table_input.minimumVisibleRows = 10

    # Table toolbar buttons are displayed in the order that they are added to the TableCommandInput, not the toolbar.
    table_add = table_input.commandInputs.addBoolValueInput('add_row_btn', '+', False, './resources/add', True)
    table_add.tooltip = 'Add a new row'
    table_input.addToolbarCommandInput(table_add)

    table_remove = table_input.commandInputs.addBoolValueInput('remove_row_btn', '-', False, './resources/remove', True)
    table_remove.tooltip = 'Remove selected row'
    table_input.addToolbarCommandInput(table_remove)

    table_button_spacer = table_input.commandInputs.addBoolValueInput('spacer', '  ', False, '', True)
    table_button_spacer.isEnabled = False
    table_input.addToolbarCommandInput(table_button_spacer)

    add_insert_button(table_input, InsertButtonValue('{}', prepend=True), 'Prepend curly braces',
                      'Inserts curly braces at the beginning of the text box of the currently selected row.\n\n'
                      'This button allows insertion of curly braces when Fusion 360™ '
                      'prevents insertion when using a keyboard layout that requires AltGr to be pressed.',
                      different_label='{}+',
                      evaluate=False, resourceFolder='./resources/prepend_braces')
    add_insert_button(table_input, InsertButtonValue('{}'), 'Append curly braces',
                      'Inserts curly braces at the end of the text box of the currently selected row.\n\n'
                      'This button allows insertion of curly braces when Fusion 360™ '
                      'prevents insertion when using a keyboard layout that requires AltGr to be pressed.',
                      different_label='+{}',
                      evaluate=False, resourceFolder='./resources/append_braces')
    
    table_button_spacer2 = table_input.commandInputs.addBoolValueInput('spacer2', '  ', False, '', True)
    table_button_spacer2.isEnabled = False
    table_input.addToolbarCommandInput(table_button_spacer2)

    add_insert_button(table_input, InsertButtonValue('{_.version}'), 'Append the document version parameter.')
    # Suggest som user parameters
    for i, param in enumerate(reversed(design.userParameters)):
        if i == 2:
            break
        short_name = truncate_text(param.name, 6)
        label = f'{{{short_name}}}'
        insert_text = f'{{{param.name}}}'
        add_insert_button(table_input, InsertButtonValue(insert_text),
                          f'Append the <i>{param.name}</i> parameter, with default formatting.',
                          different_label=label)
        label_0f = f'{{{short_name}:.0f}}'
        insert_text_0f = f'{{{param.name}:.0f}}'
        add_insert_button(table_input, InsertButtonValue(insert_text_0f),
                          f'Append the <i>{param.name}</i> parameter, with no decimals.',
                          different_label=label_0f)
    
    # The select events cannot work without having an active SelectionCommandInput
    select_input = cmd.commandInputs.addSelectionInput('select', 'Sketch Texts', '')
    select_input.addSelectionFilter(adsk.core.SelectionCommandInput.Texts)
    select_input.setSelectionLimits(0, 0)
    select_input.isVisible = False

    quick_ref = table_input.commandInputs.addTextBoxCommandInput('quick_ref', '', QUICK_REF, QUICK_REF_LINES, True)
    quick_ref.isFullWidth = True

    quick_ref = table_input.commandInputs.addTextBoxCommandInput('settings_head', '', '<b>Settings</b>', 1, True)
    autocompute_input = cmd.commandInputs.addBoolValueInput('autocompute', 'Run Compute All automatically', True,
                                                            './resources/auto_compute_all', settings_[AUTOCOMPUTE_SETTING])

    load(cmd)

    if table_input.rowCount == 0:
        add_row(table_input, get_next_id())

def truncate_text(text, length):
    return text[0:length]

def add_insert_button(table_input, insert_value, tooltip,
                      tooltip_description='', evaluate=True, different_label=None,
                      prepend=False, resourceFolder=''):
    button_id = f'insert_btn_{len(dialog_state_.insert_button_values)}'
    dialog_state_.insert_button_values.append(insert_value)
    if different_label:
        label = different_label
    else:
        label = insert_value.value

    if evaluate:
        ## TODO: evaluate_text should handle sketch_text=None gracefully
        tooltip += '<br><br>Current value: ' + evaluate_text(insert_value.value, None)

    button = table_input.commandInputs.addBoolValueInput(button_id, label, False, resourceFolder, True)
    button.tooltip = tooltip
    button.tooltipDescription = tooltip_description
    table_input.addToolbarCommandInput(button)

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
    elif args.input.id.startswith('insert_btn_'):
        row = table_input.selectedRow
        if row != -1:
            insert_id = int(args.input.id.split('_')[-1])
            insert_value = dialog_state_.insert_button_values[insert_id]
            text_id = get_text_id(table_input.getInputAtPosition(row, 0))
            value_input = table_input.commandInputs.itemById(f'value_{text_id}')
            if insert_value.prepend:
                value_input.value = insert_value.value + value_input.value
            else:
                value_input.value += insert_value.value
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

def find_equal_sketch_text(in_sketch, sketch_text):
    '''Used when mapping proxy <--> native'''
    # Workaround for missing SketchText.nativeObject
    # Bug: https://forums.autodesk.com/t5/fusion-360-api-and-scripts/getting-nativeobject-for-sketchtext/td-p/9782524

    # Assuming the texts will be returned in the same order
    # from both proxy and native sketch.
    text_index = 0
    for i, st in enumerate(sketch_text.parentSketch.sketchTexts):
        if st == sketch_text:
            text_index = i
            break
    else:
        ui_.messageBox(f'Failed to translate sketch text proxy (component instance) to native text object.\n\n'
                        'Please inform the developer of what steps you performed to trigger this error.',
                        NAME_VERSION)
    return in_sketch.sketchTexts.item(text_index)

def set_row_sketch_texts_text(sketch_texts_input, sketch_texts):
    if sketch_texts:
        total_count = 0
        count_per_sketch = defaultdict(int)
        for sketch_text in sketch_texts:
            # Name is unique
            count_per_sketch[sketch_text.parentSketch.name] += 1
            total_count += 1
        display_names = []
        for sketch_name, count in count_per_sketch.items():
            display_name = sketch_name
            if count > 1:
                display_name += f' ({count})'
            display_names.append(display_name)
        value = ', '.join(sorted(display_names))
        # Indicate if not all selections are visible. Show all in tooltip.
        if total_count > 2:
            sketch_texts_input.value = f'[{total_count}] {value}'
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

    save_storage_version()

    if not save_next_id():
        return

    # TODO: Use this text map the whole time - instead of dialog_selection_map_
    texts = defaultdict(TextInfo)
    for row_index in range(table_input.rowCount):
        text_id = get_text_id(table_input.getInputAtPosition(row_index, 0))
        sketch_texts = dialog_selection_map_[text_id]
        text = table_input.commandInputs.itemById(f'value_{text_id}').value

        text_info = texts[text_id]
        text_info.text_value = text
        text_info.sketch_texts = sketch_texts

        remove_attributes(text_id)

        design.attributes.add(ATTRIBUTE_GROUP, f'textValue_{text_id}', text)
    
        for sketch_text in sketch_texts:
            sketch_text.attributes.add(ATTRIBUTE_GROUP, f'hasText_{text_id}', '')

    for text_id in dialog_state_.removed_texts:
        remove_attributes(text_id)

    # Save some memory
    dialog_selection_map_.clear()

    settings_[AUTOCOMPUTE_SETTING] = cmd.commandInputs.itemById('autocompute').value

    update_texts(texts=texts)

def save_storage_version():
    design: adsk.fusion.Design = app_.activeProduct

    design.attributes.add(ATTRIBUTE_GROUP, 'storageVersion', str(STORAGE_VERSION))

    # Add a warning to v1.x.x users
    design.attributes.add(ATTRIBUTE_GROUP, 'customTextValue_0', f'Parameters were created using version {manifest_["version"]} of {NAME}')
    design.attributes.add(ATTRIBUTE_GROUP, 'customTextType_0', 'custom')
    design.attributes.add(ATTRIBUTE_GROUP, 'customTextValue_1', f'Please update {NAME}')
    design.attributes.add(ATTRIBUTE_GROUP, 'customTextType_1', 'custom')

def save_next_id():
    global dialog_next_id_
    design: adsk.fusion.Design = app_.activeProduct
    next_id = dialog_next_id_
    print(f"{NAME} SAVE NEXT ID {next_id}")
    if next_id is None:
        ui_.messageBox(f'Failed to save text ID counter. Save failed.\n\n'
                       'Please inform the developer of the steps you performed to trigger this error.',
                       NAME_VERSION)
        return False
    design.attributes.add(ATTRIBUTE_GROUP, 'nextId', str(next_id))
    dialog_next_id_ = None
    return True

def remove_attributes(text_id):
    design = app_.activeProduct

    old_attrs = design.findAttributes(ATTRIBUTE_GROUP, f'hasText_{text_id}')
    for old_attr in old_attrs:
        old_attr.deleteMe()

    value_attr = design.attributes.itemByName(ATTRIBUTE_GROUP, f'textValue_{text_id}')
    if value_attr:
        value_attr.deleteMe()

# Tries to update the given SketchText, if the text value has changed.
# Returns True if the supplied text value differed from the old value.
def set_sketch_text(sketch_text, text):
    try:
        # Avoid triggering computations and undo history for unchanged texts
        if sketch_text.text == text:
            return False
        
        # Changing any SketchText property resets the text height
        # Bug: https://forums.autodesk.com/t5/fusion-360-api-and-scripts/bug-setting-sketchtext-properties-resets-text-height-since-v-2-0/m-p/10357593
        # The only way to restore the height of a text is by setting its ModelParameter
        # However, there is no accessible mapping between SketchText and the parameter,
        # so we save the component's model parameters and restore the one that has been changed,
        # in case it has been changed.

        check_text_height_bug(sketch_text)

        global text_height_workaround_state_
        if text_height_workaround_state_ == WorkaroundState.Enabled:
            # Expecting parameter order to be stable inside our function scope
            param_exprs = [p.expression for p in sketch_text.parentSketch.parentComponent.modelParameters]

        sketch_text.text = text

        if text_height_workaround_state_ == WorkaroundState.Enabled:
            for orig_expr, param in zip(param_exprs, sketch_text.parentSketch.parentComponent.modelParameters):
                # Doubles! We should be able to check equality since we don't change the values
                if param.expression != orig_expr:
                    param.expression = orig_expr
                    break
    except RuntimeError as e:
        msg = None
        if len(e.args) > 0:
            msg = e.args[0]
        # Must be able to handle both errors. Angle error seems to come first,
        # so we will not reach the font error in that case.
        if msg == '3 : invalid input font name':
            # SHX font bug. Cannot set text when a SHX font is used. Switch to a TrueType font temporarily.
            # Bug: https://forums.autodesk.com/t5/fusion-360-api-and-scripts/cannot-select-shx-fonts-on-sketchtext-object/m-p/9606551

            # More broken in Fusion 360™ version 2.0.9142. Let's try the TrueType
            # workaround, if it starts working again...
            try:
                old_font = sketch_text.fontName + '.shx'
                # Let's hope the user has Arial
                sketch_text.fontName = 'Arial'
                sketch_text.text = text
                sketch_text.fontName = old_font
            except RuntimeError:
                ui_.messageBox(f'Cannot set text parameter in the sketch "{sketch_text.parentSketch.name}" '
                                'due to the text having an SHX font. This bug was introduced by Fusion 360™ version 2.0.9142.\n\n'
                                'Please change the text to not have an SHX font or remove it from the paremeter list.\n\n'
                                'See add-in help document/README for more information.',
                                NAME_VERSION)
                # Unhook the text from the text parameter?
        elif msg == '3 : invalid input angle':
            # Negative angle bug. Cannot set text when the angle is negative.
            # Bug: https://forums.autodesk.com/t5/fusion-360-api-and-scripts/bug-unable-to-modify-text-of-a-sketchtext-created-manually-with/m-p/9502107
            # This seems to have been fixed in Fusion 360 v 2.0.9142, but keeping this branch in case they
            # break it again.
            ui_.messageBox(f'Cannot set text parameter in the sketch "{sketch_text.parentSketch.name}" '
                            'due to the text having a negative angle.\n\n'
                            'Please edit the text to have a positive angle (add 360 degrees to the current angle).\n\n'
                            'See add-in help document/README for more information.',
                            NAME_VERSION)
            # Unhook the text from the text parameter?
        else:
            raise
    return True

def check_text_height_bug(sketch_text):
    global text_height_workaround_state_

    if text_height_workaround_state_ != WorkaroundState.Check:
        # Already checked
        return

    # We cannot trust the SketchText.height != 1.0 changing to 1.0, as it does not always match the
    # real value and the model parameter! (Real value of 2.0 gives a height value of 0.9999999999999996
    # and sometimes 2.0!)
    # The expression field will be different dependending on the units set in the document.
    # This means that we have no way of telling if any selected parameter is going to be affected, and
    # we therefore cannot detect on-the-fly if an "affected" parameter was left untouched.
    # Instead, we use the given text for testing if the bug is present, by observing if any parameters
    # change.

    # Note: We must restore the expression when we are done!

    orig_param_exprs = [p.expression for p in sketch_text.parentSketch.parentComponent.modelParameters]

    # We don't know which parameter is connected to the SketchText, so we must fiddle with the SketcText
    # and observe
    # The bug sets the value *close to* 1.0, but not always exactly 1.0. So try another value.
    test_height = 2.0
    sketch_text.height = test_height
    
    height_is_set = math.isclose(sketch_text.height, test_height, rel_tol=0.1)
    text_height_workaround_state_ = WorkaroundState.Disabled if height_is_set else WorkaroundState.Enabled
    print(f"{NAME} TEXT HEIGHT WORKAROUND:", text_height_workaround_state_)

    # Alternative method: Scan the parameters and find the changed value. We might need two tries, as
    # we might be setting the value the user set initially.

    # Restore the parameter's expression (which might be more than a simple value)
    for orig_expr, param in zip(orig_param_exprs, sketch_text.parentSketch.parentComponent.modelParameters):
        if param.expression != orig_expr:
            param.expression = orig_expr
            break

SUBST_PATTERN = re.compile(r'{([^}]+)}')
DOCUMENT_NAME_VERSION_PATTERN = re.compile(r' (?:v\d+|\(v\d+.*?\))$')
def evaluate_text(text, sketch_text, next_version=False):
    design: adsk.fusion.Design = app_.activeProduct
    def sub_func(subst_match):
        # https://www.python.org/dev/peps/pep-3101/
        # https://docs.python.org/3/library/string.html#formatspec

        param_string = subst_match.group(1)
        param_spec = paramparser.ParamSpec.from_string(param_string)

        if not param_spec:
            return f'<Cannot parse: {param_string}>'
        
        var_name = param_spec.var
        options = param_spec.format

        if options:
            options_sep = ':'
        else:
            options_sep = ''
            options = ''

        member = param_spec.member
        if member:
            member_sep = '.'
        else:
            member_sep = ''
            member = ''

        # Strings can be sliced
        string_value = False

        if var_name == '_':
            if member == 'version':
                # No version information available if the document is not saved
                if app_.activeDocument.isSaved:
                    version = get_data_file().versionNumber
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
                    unix_time_utc = get_data_file().dateCreated
                    save_time = datetime.datetime.fromtimestamp(unix_time_utc,
                                                                tz=datetime.timezone.utc)
                else:
                    # Set a fake time until the document is saved for the first time
                    # Doing this in the user's timezone, to get midnight time correct.
                    now = datetime.datetime.now(tz=None)
                    save_time = now.replace(hour=0, minute=0, second=0, microsecond=0)

                save_time_local = save_time.astimezone()
                value = save_time_local
            elif member == 'component':
                # RootComponent turns into the name of the document including version number
                # Strip it, as with _.file
                component_name = sketch_text.parentSketch.parentComponent.name
                component_name = DOCUMENT_NAME_VERSION_PATTERN.sub('', component_name)
                value = component_name
                string_value = True
            elif member == 'compdesc':
                value = sketch_text.parentSketch.parentComponent.description
                string_value = True
            elif member == 'file':
                ### Can we handle "Save as" or document copying?
                # activeDocument.name and activeDocument.dataFile.name gives us the same
                # value, except that the former exists and gives the value "Untitled" for
                # unsaved documents.
                document_name = app_.activeDocument.name
                # Name string looks like this:
                # <name> v3
                # <name> (v3~recovered)
                # Strip the suffix
                document_name = DOCUMENT_NAME_VERSION_PATTERN.sub('', document_name)
                value = document_name
                string_value = True
            elif member == 'sketch':
                ### Is this useful? Let's users edit the texts directly in the Browser or Timeline, I guess.
                value = sketch_text.parentSketch.name
                string_value = True
            elif member == 'newline':
                value = '\n'
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
                    # Has unit.
                    # Rounding is done to get rid of small floating point value noise,
                    # that result in "almost-correct" numbers. (42.99999999999 -> 43)
                    value = round(design.fusionUnitsManager.convert(param.value, "internalUnits", param.unit), 10)
            elif member == 'comment':
                value = param.comment
                string_value = True
            elif member == 'expr':
                value = param.expression
            elif member == 'unit':
                value = param.unit
            elif member == 'inchfrac':
                value = paramformatter.mixed_frac_inch(param, design)
            else:
                return f'<Unknown member of {var_name}: {member}>'

        if param_spec.slice:
            if string_value:
                value = value[param_spec.slice]
            else:
                return f'<Cannot substring number: {var_name}{member_sep}{member}>'

        try:
            formatted_str = ('{' + options_sep + options + '}').format(value)
        except ValueError as e:
            formatted_str = f'<{e.args[0]}>'
        return formatted_str

    shown_text = SUBST_PATTERN.sub(sub_func, text)
    return shown_text

def get_data_file():
    '''Wrapper for ActiveDocument.DataFile that tries to download the
    data from the cloud if it is not already cached.
    '''
    data_file, probe_error = probe_data_file()
    if data_file:
        return data_file

    # It looks like Fusion 360 has not downloaded the cloud data for this file,
    # either because it was opened through "Editable Documents" or as a sub-assembly
    # through another file, without opening t the file's folder.
    # Bug: https://forums.autodesk.com/t5/fusion-360-api-and-scripts/error-retrieving-datafile-in-unopened-folder/m-p/8384143#M6854
    
    # Trigger download of Editable Documents data
    if app_.data.personalUseLimits:
        app_.data.personalUseLimits.editableFiles
    
    data_file, probe_error = probe_data_file()
    if data_file:
        return data_file

    # Trigger download data for all documents
    progress = ui_.createProgressDialog()
    progress.isCancelButtonShown = True
    projects = app_.data.dataProjects
    base_msg = ("Cannot determine document's project (The folder has likely not been opened).\n"
                "Scanning for missing metadata.\n\n")
    progress.show(NAME_VERSION, base_msg, 0, projects.count, 0)
    for i, p in enumerate(projects):
        progress.message = f"{base_msg}Scanning project \"{p.name}\""
        if progress.wasCancelled:
            break

        cache_data_folder(p.rootFolder)
        
        progress.progressValue = i + 1

        data_file, probe_error = probe_data_file()
        if data_file:
            break

    progress.hide()
    
    if data_file:
        return data_file

    raise probe_error

def cache_data_folder(folder):
    '''Forces Fusion 360 to download metadata for all documents in
    the given folder.
    
    Note: Fusion 360 will always try to fetch new data, even though
          it has data cached.
    '''
    for child_df in folder.dataFiles:
        # This forces Fusion 360 to download and cache the DataFile
        child_df.id
    for child_folder in folder.dataFolders:
        cache_data_folder(child_folder)

def probe_data_file():
    try:
        return app_.activeDocument.dataFile, None
    except RuntimeError as e:
        if e.args and e.args[0].startswith('2 : InternalValidationError : dataFile'):
            # DataFile is currently not cached
            return None, e
        else:
            raise

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
    next_id_attr = design.attributes.itemByName(ATTRIBUTE_GROUP, 'nextId')
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

    value_attrs = [attr for attr in design.attributes.itemsByGroup(ATTRIBUTE_GROUP)
                  if attr.name.startswith('textValue_')]
    for value_attr in value_attrs:
        if not value_attr:
            continue
        text_id = get_text_id(value_attr.name)
        text_info = texts[text_id]
        text_info.text_value = value_attr.value

        # Get all sketch texts belonging to the attribute
        has_attrs = design.findAttributes(ATTRIBUTE_GROUP, f'hasText_{text_id}')
        for has_attr in has_attrs:
            sketch_texts = text_info.sketch_texts
            if has_attr.parent:
                sketch_texts.append(has_attr.parent)        
            if has_attr.otherParents:
                for other_parent in has_attr.otherParents:
                    sketch_texts.append(other_parent)
    
    return texts

def document_opened_handler(args: adsk.core.DocumentEventArgs):
    if is_design_workspace():
        check_storage_version()

def is_design_workspace():
    return ui_.activeWorkspace.id == 'FusionSolidEnvironment'

def check_storage_version():
    design: adsk.fusion.Design = app_.activeProduct
    storage_version_attr = design.attributes.itemByName(ATTRIBUTE_GROUP, 'storageVersion')
    if storage_version_attr:
        file_db_version = int(storage_version_attr.value)
    else:
        # Either no parametric text data is saved or v1.x.x was used.
        next_id_attr = design.attributes.itemByName(ATTRIBUTE_GROUP, 'nextId')
        if next_id_attr:
            # Add-in v1.x.x
            file_db_version = 1
        else:
            file_db_version = None

    if file_db_version is None:
        # No text parameters in this document
        return True
    if file_db_version == 1:
        ret = ui_.messageBox(f'This document has text parameters created with an older storage format version ({file_db_version}), '
                             f'which is not compatible with the current storage format version ({STORAGE_VERSION}).\n\n'
                             'The text parameters will be converted to the new storage format.\n\n'
                             f'If you proceed, the document will no longer work with the older version of {NAME}. '
                             f'If you cancel, you will not be able to update the text parameters using this version of {NAME}.',
                             NAME_VERSION,
                             adsk.core.MessageBoxButtonTypes.OKCancelButtonType)
        if ret == adsk.core.DialogResults.DialogOK:
            migrate_storage_async(file_db_version, STORAGE_VERSION)
        else:
            disable_addin()
    elif file_db_version == STORAGE_VERSION:
        # OK, this our version.
        enable_addin()
        return True
    elif file_db_version > STORAGE_VERSION:
        ui_.messageBox(f'This document has text parameters created with a newer storage format version ({file_db_version}), '
                       f'which is not compatible with this version of {NAME} ({STORAGE_VERSION}).\n\n'
                       f'You will need to update {NAME} to be able to update the text parameters.',
                       NAME_VERSION)
        disable_addin()
    else:
        ui_.messageBox(f'This document has text parameters created with unknown storage format version ({file_db_version}).\n\n'
                       f'You will not be able to update the text parameters.\n\n'
                       f'Please report this to the developer. It is recommended that you restore an old version '
                       f'of your document.',
                       NAME_VERSION)
        disable_addin()
    return False

migrate_from_ = None
migrate_to_ = None
def migrate_storage_async(from_version, to_version):
    # Running this as a command to avoid a big list of "Set attribute" in the Undo history.
    global migrate_from_, migrate_to_
    migrate_from_ = from_version
    migrate_to_ = to_version
    migrate_cmd_def = ui_.commandDefinitions.itemById(MIGRATE_CMD_ID)
    if migrate_cmd_def:
        migrate_cmd_def.deleteMe()
    migrate_cmd_def = ui_.commandDefinitions.addButtonDefinition(MIGRATE_CMD_ID, 'Migrate Text Parameters', '')
    events_manager_.add_handler(migrate_cmd_def.commandCreated,
                                callback=migrate_cmd_created_handler)
    migrate_cmd_def.execute()

def migrate_cmd_created_handler(args: adsk.core.CommandCreatedEventArgs):
    cmd = args.command
    events_manager_.add_handler(cmd.execute, callback=migrate_cmd_execute_handler)
    cmd.isAutoExecute = True
    cmd.isRepeatable = False
    # The synchronous doExecute makes Fusion crash..
     #cmd.doExecute(True)
    # Check migration result

def migrate_cmd_execute_handler(args: adsk.core.CommandEventArgs):
    from_version = migrate_from_
    to_version = migrate_to_
    design: adsk.fusion.Design = app_.activeProduct
    print(f'{NAME} Migrating storage: {from_version} -> {to_version}')
    dump_storage()
    if from_version == 1 and to_version == 2:
        # Migrate global attributes
        design_attrs = design.attributes.itemsByGroup(ATTRIBUTE_GROUP)
        for attr in design_attrs:
            if attr.name.startswith('customTextType_'):
                print(f'{NAME} deleting attribute "{attr.name}"')
                attr.deleteMe()
            elif attr.name.startswith('customTextValue_'):
                text_id = get_text_id(attr.name)
                new_attr_name = f'textValue_{text_id}'
                print(f'{NAME} migrating "{attr.name}" -> "{new_attr_name}"')
                design.attributes.add(ATTRIBUTE_GROUP, new_attr_name, attr.value)
                attr.deleteMe()

        # The old version put the attributes on Sketch Text Proxies. The new format uses the
        # native Sketch Texts.
        migrate_proxy_to_native_sketch('hasParametricText_', 'hasText_')

        print(f'{NAME} writing version {to_version}')
        save_storage_version()
    else:
        ui_.messageBox('Cannot migrate from storage version {from_version} to {to_version}!',
                       NAME_VERSION)
        disable_addin()
        return

    dump_storage()
    print(f'{NAME} Migration done.')
    update_texts()
    ui_.messageBox('Migration complete!')

def migrate_proxy_to_native_sketch(old_attr_prefix, new_attr_prefix):
    design: adsk.fusion.Design = app_.activeProduct
    print(f'Migrating {old_attr_prefix} to {new_attr_prefix}')
    attrs = design.findAttributes(ATTRIBUTE_GROUP, r're:' + old_attr_prefix + r'\d+')
    for attr in attrs:
        if attr.value is None:
            print(f'Attribute {attr.name} has no value. Skipping...')
        text_id = get_text_id(attr.name)
        text = attr.value
        native_sketch_texts = []
        sketch_text_proxies = []
        if attr.parent:
            sketch_text_proxies.append(attr.parent)
        if attr.otherParents:
            for other_parent in attr.otherParents:
                sketch_text_proxies.append(other_parent)
        for proxy in sketch_text_proxies:
            native = get_native_sketch_text(proxy)
            if native and native not in native_sketch_texts:
                native_sketch_texts.append(native)
        for native in native_sketch_texts:
            native.attributes.add(ATTRIBUTE_GROUP, f'{new_attr_prefix}{text_id}', text)
        attr.deleteMe()

def dump_storage():
    design: adsk.fusion.Design = app_.activeProduct

    def print_attrs(attrs):
        for attr in attrs:
            print(f'"{attr.name}", "{attr.value}", '
                  f'"{parent_class_names(attr.parent)[0]}", ' +
                  '"' + '", "'.join(parent_class_names(attr.otherParents)) + '"')

    print('-' * 50)
    print('Design attributes')
    print_attrs(design.attributes.itemsByGroup(ATTRIBUTE_GROUP))
    print('Entity attributes')
    print_attrs(design.findAttributes(ATTRIBUTE_GROUP, ''))
    print('-' * 50)

def parent_class_names(parent_or_parents):
    if parent_or_parents is None:
        return ["None"]
    
    class_names = []
    if not isinstance(parent_or_parents, adsk.core.ObjectCollection):
        parent_or_parents = [parent_or_parents]

    for parent in parent_or_parents:
        class_names.append(thomasa88lib.utils.short_class(parent))
    
    return class_names

def enable_addin():
    global enabled_
    enabled_ = True

def disable_addin():
    global enabled_
    enabled_ = False

def document_saving_handler(args: adsk.core.DocumentEventArgs):
    if ui_.activeWorkspace.id == 'FusionSolidEnvironment':
        # This cannot run async or delayed, as we must update the parameters before Fusion
        # saves the document.
        update_texts(text_filter=['_.version', '_.date'], next_version=True)

def command_terminated_handler(args: adsk.core.ApplicationCommandEventArgs):
    #print(f"{NAME} terminate: {args.commandId}, reason: {args.terminationReason}")
    if args.terminationReason != adsk.core.CommandTerminationReason.CompletedTerminationReason:
        return

    # Taking action directly disturbs the Paste New command, so update_texts()
    # must be delayed or called through update_texts_async().
    # Also, call the async function to only get one Undo item.

    if args.commandId in ['ChangeParameterCommand',
                          'SketchEditDimensionCmdDef',
                          'DesignConfigurationActivateRowCmd']:
        # User (might have) changed a parameter
        update_texts_async()
    elif args.commandId == 'FusionPasteNewCommand':
        # User pasted a component, that will have a new name
        update_texts_async(text_filter=['_.component'])
    elif (args.commandId in ['RenameCommand',
                             'FusionRenameTimelineEntryCommand']):
        # User might have changed a component or sketch name
        text_filter = set()
        for selection in ui_.activeSelections:
            # Getting "RuntimeError: 3 : object is invalid" if we try to get the entity
            # for selection of some features/objects.
            try:
                entity = selection.entity
            except RuntimeError:
                continue
            if isinstance(entity, adsk.fusion.Occurrence):
                text_filter.add('_.component')
            elif isinstance(entity, adsk.fusion.Sketch):
                text_filter.add('_.sketch')
        if text_filter:
            update_texts_async(text_filter=['_.component', '_.sketch'])


    ### TODO: Update when user selects "Compute All"
    #elif args.commandId == 'FusionComputeAllCommand':
    #    load()
    #    save()

# NOTE: This function might be called from inside a command
def update_texts(text_filter=None, next_version=False, texts=None):
    if not enabled_:
        return

    if not texts:
        # No cached map of texts was provided. Let's build it.
        texts = get_texts()

    if not texts:
        # There are no texts in this document. Skip all processing.
        return

    update_count = 0
    for text_id, text_info in texts.items():
        text = text_info.text_value
        if not text_filter or [filter_value for filter_value in text_filter if filter_value in text]:
            for sketch_text in text_info.sketch_texts:
                # Must evaluate for every sketch for every text, in case
                # the user has used the component name parameter.
                text_updated = set_sketch_text(sketch_text, evaluate_text(text, sketch_text, next_version))
                if text_updated:
                    update_count += 1

    design: adsk.fusion.Design = app_.activeProduct
    # It is illegal to do "Compute All" in a non-parametric design.
    if (update_count > 0 and
        design.designType == adsk.fusion.DesignTypes.ParametricDesignType and
        settings_[AUTOCOMPUTE_SETTING]):
        try:
            design.computeAll()
        except RuntimeError as e:
            if e.args and 'Compute Failed' in e.args[0]:
                msg = f'Compute all, triggered by {NAME_VERSION}, failed:<br>\n<br>\n'
                msg += e.args[0].replace('5 : ', '').replace('\n', '<br>\n')
                # Putting the call at the end of the event queue, to not abort
                # any command that called this function.
                events_manager_.delay(lambda: show_error_notification(msg))
            else:
                raise

async_update_queue_ = queue.Queue()
def update_texts_async(text_filter=None, next_version=False):
    # Running this as a command to avoid a big list of "Set attribute" in the Undo history.
    # We cannot avoid having at least one item in the Undo list:
    # https://forums.autodesk.com/t5/fusion-360-api-and-scripts/stop-custom-graphics-from-being-added-to-undo/m-p/9438477
    async_update_queue_.put((text_filter, next_version))
    update_cmd_def = ui_.commandDefinitions.itemById(UPDATE_CMD_ID)
    update_cmd_def.execute()

def update_cmd_created_handler(args: adsk.core.CommandCreatedEventArgs):
    cmd = args.command
    events_manager_.add_handler(cmd.execute, callback=update_cmd_execute_handler)
    cmd.isAutoExecute = True
    cmd.isRepeatable = False
    # The synchronous doExecute makes Fusion crash..
     #cmd.doExecute(True)
    # Check migration result

def update_cmd_execute_handler(args: adsk.core.CommandEventArgs):
    update_texts(*async_update_queue_.get())

error_notification_msg_ = None
def show_error_notification(msg):
    '''Show an error notification.

    Note: The notification and the "More info" dialog renders HTML newlines (<br>),
          while the tooltip, when doing mouse-over on the red sign at the lower
          right, uses the newline character (\n).
    '''
    # Passing the message in the tooltip did not work (the event queue
    # needs to spin?). Using a global variable instead.
    global error_notification_msg_
    error_notification_msg_ = msg

    error_cmd_def = ui_.commandDefinitions.itemById(ERROR_CMD_ID)
    error_cmd_def.execute()

def error_cmd_created_handler(args: adsk.core.CommandCreatedEventArgs):
    cmd = args.command
    cmd.isAutoExecute = True
    cmd.isRepeatable = False
    events_manager_.add_handler(cmd.execute, callback=error_cmd_execute_handler)

def error_cmd_execute_handler(args: adsk.core.CommandEventArgs):
    args.executeFailed = True
    args.executeFailedMessage = error_notification_msg_

def ext_call_update_handler(args: adsk.core.CustomEventArgs):
    update_texts()
