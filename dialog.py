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

from __future__ import annotations
from collections import defaultdict
from typing import Callable

import adsk.core as ac
import adsk.fusion as af

from . import globals
from . import storage
from . import textgenerator

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

class DialogState:
    def __init__(self, next_id: int):
        self.cmd: ac.Command = None
        self.last_selected_row: int | None = None
        self.addin_updating_select: bool = False
        self.removed_texts: list[int] = []
        # Keep a list of unselects, to handle user unselecting multiple at once (window selection)
        self.pending_unselects: list[af.SketchText] = []
        self.insert_button_values: list[InsertButtonValue] = []
        
        # Contains selections for all rows of the currently active dialog
        # This dict must be reset every time the dialog is opened,
        # as the user might have cancelled it the last time.
        # The list for each row cannot be a set(), as SketchText is not hashable.
        self.selection_map: defaultdict[int, list[af.SketchText]] = defaultdict(list)

        # It seems that attributes are not saved until the command is executed,
        # so we must keep the ID in a buffer, to keep track correctly, as the ID in
        # storage will not be up to date.
        # We don't need to keep an ID per open document, as the command is
        # terminated (executed) and closed when the user switches document,
        # so just keep one global ID.
        self.next_id: int = next_id

class InsertButtonValue:
    def __init__(self, value: str, prepend: bool = False) -> None:
        self.value = value
        self.prepend = prepend

dialog_state_: DialogState
update_texts_: Callable

def create_cmd(cmd_id: str, update_fn: Callable) -> ac.CommandDefinition:
    global update_texts_
    update_texts_ = update_fn

    dialog_cmd_def = globals.ui_.commandDefinitions.itemById(cmd_id)
    if dialog_cmd_def:
        dialog_cmd_def.deleteMe()

    dialog_cmd_def = globals.ui_.commandDefinitions.addButtonDefinition(cmd_id,
                                                                'Change Text Parameters',            
                                                                'Displays the Text Parameters dialog box.\n\n'
                                                                'Assign and edit sketch text parameters.\n\n'
                                                                f'({globals.NAME_VERSION})',
                                                                './resources/text_parameter')
    globals.events_manager_.add_handler(dialog_cmd_def.commandCreated,
                                    callback=dialog_cmd_created_handler)
    return dialog_cmd_def

def dialog_cmd_created_handler(args: ac.CommandCreatedEventArgs) -> None:
    if not storage.is_valid():
        if not storage.check_storage_version():
            return

    # Reset dialog state
    global dialog_state_
    dialog_state_ = DialogState(storage.load_next_id())

    design = globals.get_design()
    cmd = args.command
    dialog_state_.cmd = cmd

    cmd.setDialogMinimumSize(450, 200)
    cmd.setDialogInitialSize(450, 300)

    # Set this explicitly. Better to save than lose everything when the user launches
    # another command (?)
    cmd.isExecutedWhenPreEmpted = True

    globals.events_manager_.add_handler(cmd.execute,
                                callback=dialog_cmd_execute_handler)

    globals.events_manager_.add_handler(cmd.inputChanged,
                                callback=dialog_cmd_input_changed_handler)

    globals.events_manager_.add_handler(cmd.preSelect,
                                callback=dialog_cmd_pre_select_handler)
    globals.events_manager_.add_handler(cmd.select,
                                callback=dialog_cmd_select_handler)
    globals.events_manager_.add_handler(cmd.unselect,
                                callback=dialog_cmd_unselect_handler)

    about = cmd.commandInputs.addTextBoxCommandInput('about', '', f'<font size="4"><b>{globals.NAME_VERSION}</b></font>', 2, True)
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
                      'This button allows insertion of curly braces when Fusion '
                      'prevents insertion when using a keyboard layout that requires AltGr to be pressed.',
                      override_label='{}+',
                      evaluate=False, resourceFolder='./resources/prepend_braces')
    add_insert_button(table_input, InsertButtonValue('{}'), 'Append curly braces',
                      'Inserts curly braces at the end of the text box of the currently selected row.\n\n'
                      'This button allows insertion of curly braces when Fusion '
                      'prevents insertion when using a keyboard layout that requires AltGr to be pressed.',
                      override_label='+{}',
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
                          override_label=label)
        label_0f = f'{{{short_name}:.0f}}'
        insert_text_0f = f'{{{param.name}:.0f}}'
        add_insert_button(table_input, InsertButtonValue(insert_text_0f),
                          f'Append the <i>{param.name}</i> parameter, with no decimals.',
                          override_label=label_0f)
    
    # The select events cannot work without having an active SelectionCommandInput
    select_input = cmd.commandInputs.addSelectionInput('select', 'Sketch Texts', '')
    select_input.addSelectionFilter(ac.SelectionCommandInput.Texts)
    select_input.setSelectionLimits(0, 0)
    select_input.isVisible = False

    quick_ref = table_input.commandInputs.addTextBoxCommandInput('quick_ref', '', QUICK_REF, QUICK_REF_LINES, True)
    quick_ref.isFullWidth = True

    quick_ref = table_input.commandInputs.addTextBoxCommandInput('settings_head', '', '<b>Settings</b>', 1, True)
    cmd.commandInputs.addBoolValueInput('autocompute', 'Run Compute All automatically', True,
                                                            './resources/auto_compute_all',
                                                            globals.settings_[globals.AUTOCOMPUTE_SETTING])
    cmd.commandInputs.addBoolValueInput('troubleshoot', 'Troubleshooting mode', True, '',
                                        globals.settings_[globals.TROUBLESHOOT_SETTING])

    dialog_state_.selection_map.clear()
    texts = storage.load_texts()
    for text_id, text_info in texts.items():
        dialog_state_.selection_map[text_id] = text_info.sketch_texts
        add_row(table_input, text_id, new_row=False,
                format_str=text_info.format_str)

    if table_input.rowCount == 0:
        add_row(table_input, create_id())

def truncate_text(text: str, length: int) -> str:
    return text[0:length]

def add_insert_button(table_input: ac.TableCommandInput,
                      insert_value: InsertButtonValue,
                      tooltip: str,
                      tooltip_description: str = '',
                      evaluate: bool = True,
                      override_label: str | None = None,
                      resourceFolder: str = '') -> None:
    button_id = f'insert_btn_{len(dialog_state_.insert_button_values)}'
    dialog_state_.insert_button_values.append(insert_value)
    if override_label:
        label = override_label
    else:
        label = insert_value.value

    if evaluate:
        tooltip += '<br><br>Current value: ' + textgenerator.generate_text(insert_value.value, None)

    button = table_input.commandInputs.addBoolValueInput(button_id, label, False, resourceFolder, True)
    button.tooltip = tooltip
    button.tooltipDescription = tooltip_description
    table_input.addToolbarCommandInput(button)

### preview: executePreview show text from param.

def dialog_cmd_input_changed_handler(args: ac.InputChangedEventArgs) -> None:
    table_input: ac.TableCommandInput = args.inputs.itemById('table')
    need_update_select_input = False
    update_select_force = False
    if args.input.id == 'add_row_btn':
        add_row(table_input, create_id())
    elif args.input.id == 'remove_row_btn':
        row = table_input.selectedRow
        if row != -1:
            remove_row(table_input, row)
    elif args.input.id.startswith('insert_btn_'):
        row = table_input.selectedRow
        if row != -1:
            insert_id = int(args.input.id.split('_')[-1])
            insert_value = dialog_state_.insert_button_values[insert_id]
            text_id = globals.extract_text_id(table_input.getInputAtPosition(row, 0))
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
        text_id = globals.extract_text_id(args.input)
        sketch_texts_input = ac.StringValueCommandInput.cast(
            table_input.commandInputs.itemById(f'sketchtexts_{text_id}'))
        sketch_texts = dialog_state_.selection_map[text_id]
        sketch_texts.clear()
        set_row_sketch_texts_text(sketch_texts_input, sketch_texts)
        need_update_select_input = True
        update_select_force = True
    elif args.input.id == 'select':
        handle_select_input_change(table_input)

    if need_update_select_input:
        # Wait for the table row selection to update before updating select input
        globals.events_manager_.delay(lambda: update_select_input(table_input, update_select_force))

def dialog_cmd_pre_select_handler(args: ac.SelectionEventArgs) -> None:
    # Select all proxies pointing to the same SketchText
    selected_text_proxy = af.SketchText.cast(args.selection.entity)
    native_sketch_text = get_native_sketch_text(selected_text_proxy)
    sketch_text_proxies = get_sketch_text_proxies(native_sketch_text)
    additional = ac.ObjectCollection.create()
    for sketch_text_proxy in sketch_text_proxies:
        # Documentation says to not add the user-provided selection,
        # as it will make it unselected.
        # Does not seem to make a difference. Maybe it only applies
        # to the select event.
        if sketch_text_proxy != selected_text_proxy:
            additional.add(sketch_text_proxy)
    # Note: This triggers a select event for every added selection
    args.additionalEntities = additional

def dialog_cmd_select_handler(args: ac.SelectionEventArgs) -> None:
    #globals.log("SELECT {args.selection.entity} {args.selection.entity.parentSketch.name}")
    dialog_state_.pending_unselects.clear()

def dialog_cmd_unselect_handler(args: ac.SelectionEventArgs) -> None:
    #globals.log("UNSELECT {args.selection.entity} {args.selection.entity.parentSketch.name}")
    # args.additionalEntities does not seem to work for unselect and activeInput seems
    # to not be set. Just store what happened and sort it out in the input_changed
    # handler.
    dialog_state_.pending_unselects.append(af.SketchText.cast(args.selection.entity))

def handle_select_input_change(table_input: ac.TableCommandInput) -> None:
    row = table_input.selectedRow
    if dialog_state_.addin_updating_select or row == -1:
        return

    select_input = ac.SelectionCommandInput.cast(
        dialog_state_.cmd.commandInputs.itemById('select'))
    text_id = globals.extract_text_id(table_input.getInputAtPosition(row, 0))
    sketch_texts_input = ac.StringValueCommandInput.cast(
        table_input.commandInputs.itemById(f'sketchtexts_{text_id}'))
    
    sketch_texts = dialog_state_.selection_map[text_id]
    sketch_texts.clear()
    pending_unselect_sketch_texts = [get_native_sketch_text(u)
                                     for u in dialog_state_.pending_unselects]
    for i in range(select_input.selectionCount):
        # The selection will give us a proxy to the instance that the user selected
        sketch_text_proxy = af.SketchText.cast(select_input.selection(i).entity)
        native_sketch_text = get_native_sketch_text(sketch_text_proxy)
        if not native_sketch_text:
            # This should not happen, but handle it gracefully
            globals.log(f"could not get native sketch text for {get_sketch_sym_name(sketch_text_proxy)}")
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

    # Make sure a sketch text is not selected by another row as well.
    # Remove it from the other row in that case.
    for sel_text_id, sel_sketch_texts in dialog_state_.selection_map.items():
        if sel_text_id != text_id:
            colliding_selections = [s for s in sel_sketch_texts if s in sketch_texts]
            if colliding_selections:
                for coll_sel in colliding_selections:
                    globals.log(f"Clearing colliding selection from text {sel_text_id}: {get_sketch_sym_name(coll_sel)}")
                    sel_sketch_texts.remove(coll_sel)
                sel_texts_input = ac.StringValueCommandInput.cast(table_input.commandInputs.itemById(f'sketchtexts_{sel_text_id}'))
                set_row_sketch_texts_text(sel_texts_input, sel_sketch_texts)

def update_select_input(table_input: ac.TableCommandInput, force: bool = False) -> None:
    if not table_input.isValid:
        # Dialog is likely closed. This is an effect of the delay() call.
        return
    
    row = table_input.selectedRow
    if row != dialog_state_.last_selected_row or force:
        # addSelection trigger inputChanged events. They are triggered directly at the function call.
        dialog_state_.addin_updating_select = True
        select_input = dialog_state_.cmd.commandInputs.itemById('select')
        select_input.clearSelection()
        if row != -1:
            text_id = globals.extract_text_id(table_input.getInputAtPosition(row, 0))
            for sketch_text in dialog_state_.selection_map[text_id]:
                # "This method is not valid within the commandCreated event but must be used later
                # in the command lifetime. If you want to pre-populate the selection when the
                # command is starting, you can use this method in the activate method of the Command."
                for sketch_text_proxy in get_sketch_text_proxies(sketch_text):
                    select_input.addSelection(sketch_text_proxy)
        dialog_state_.last_selected_row = row
        dialog_state_.addin_updating_select = False

def get_native_sketch_text(sketch_text_proxy: af.SketchText | None) -> af.SketchText | None:
    if sketch_text_proxy is None:
        return None
    native = sketch_text_proxy.nativeObject
    if native is None:
        return sketch_text_proxy
    return native

def get_sketch_text_proxies(native_sketch_text: af.SketchText) -> list[af.SketchText]:
    design = globals.get_design()
    native_sketch = native_sketch_text.parentSketch
    in_occurrences = design.rootComponent.allOccurrencesByComponent(native_sketch.parentComponent)

    if in_occurrences.count == 0:
        # Root level sketch. There are no occurences and there will be no proxies.
        return [native_sketch_text]

    sketch_text_proxies: list[af.SketchText] = []
    for occurrence in in_occurrences:
        sketch_text_proxy = native_sketch_text.createForAssemblyContext(occurrence)
        sketch_text_proxies.append(sketch_text_proxy)
    return sketch_text_proxies

def set_row_sketch_texts_text(sketch_texts_input: ac.StringValueCommandInput, sketch_texts: list[af.SketchText]) -> None:
    if sketch_texts:
        total_count = 0
        count_per_sketch = defaultdict(int)
        for sketch_text in sketch_texts:
            # Name is unique
            count_per_sketch[get_sketch_sym_name(sketch_text)] += 1
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

def get_sketch_sym_name(sketch_text: af.SketchText) -> str:
    '''Get a unique "symbolic" name for the sketch. The name is not
    guaranteed to be unique'''
    sketch = sketch_text.parentSketch
    name = sketch.name
    # Sketches in different products can have the same name, so
    # try to make it unique.
    if isinstance(sketch.parentComponent.parentDesign, af.FlatPatternProduct):
        name = f'F:{name}'
    return name

def add_row(table_input: ac.TableCommandInput, text_id: int, new_row: bool = True, format_str: str | None = None) -> None:
    sketch_texts = dialog_state_.selection_map[text_id]

    row_index = table_input.rowCount

    # Using StringValueInput + isReadOnly to allow the user to still select the row
    sketch_texts_input = table_input.commandInputs.addStringValueInput(f'sketchtexts_{text_id}', '', '')
    sketch_texts_input.isReadOnly = True
    set_row_sketch_texts_text(sketch_texts_input, sketch_texts)

    clear_selection_input = table_input.commandInputs.addBoolValueInput(f'clear_btn_{text_id}', 'X',
                                                                        False, './resources/clear_selection', True)
    clear_selection_input.tooltip = 'Clear selection'    
    
    if not format_str:
        format_str = ''
    value_input = table_input.commandInputs.addStringValueInput(f'value_{text_id}', '', format_str)

    table_input.addCommandInput(sketch_texts_input, row_index, 0)
    table_input.addCommandInput(clear_selection_input, row_index, 1)
    table_input.addCommandInput(value_input, row_index, 2)
    
    if new_row:
        table_input.selectedRow = row_index
        select_input = table_input.parentCommand.commandInputs.itemById('select')
        select_input.clearSelection()

def remove_row(table_input: ac.TableCommandInput, row_index: int) -> None:
    text_id = globals.extract_text_id(table_input.getInputAtPosition(row_index, 0))
    table_input.deleteRow(row_index)
    dialog_state_.removed_texts.append(text_id)
    if table_input.rowCount > row_index:
        table_input.selectedRow = row_index
    else:
        table_input.selectedRow = table_input.rowCount - 1
    update_select_input(table_input, force=True)
    ### Restore original texts, if cached, if we have live update. Also on unselect.

def create_id() -> int:
    text_id = dialog_state_.next_id
    dialog_state_.next_id += 1
    return text_id

def dialog_cmd_execute_handler(args: ac.CommandEventArgs) -> None:
    global dialog_state_

    cmd = args.command

    if not storage.save_next_id(dialog_state_.next_id):
        # TODO: Don't fail silently here
        return

    table_input = ac.TableCommandInput.cast(cmd.commandInputs.itemById('table'))
    texts = defaultdict(storage.TextInfo)
    for row_index in range(table_input.rowCount):
        text_id = globals.extract_text_id(table_input.getInputAtPosition(row_index, 0))
        sketch_texts = dialog_state_.selection_map[text_id]
        format_str = table_input.commandInputs.itemById(f'value_{text_id}').value

        text_info = texts[text_id]
        text_info.format_str = format_str
        text_info.sketch_texts = sketch_texts

    storage.save_texts(texts, dialog_state_.removed_texts)

    globals.settings_[globals.AUTOCOMPUTE_SETTING] = cmd.commandInputs.itemById('autocompute').value
    troubleshoot = cmd.commandInputs.itemById('troubleshoot').value
    globals.settings_[globals.TROUBLESHOOT_SETTING] = troubleshoot


    update_texts_(texts=texts)

    # Print this after update_texts() spam the log to make it visible to the user
    if troubleshoot:
        text_palette = globals.ui_.palettes.itemById('TextCommands')
        if text_palette:
            text_palette.isVisible = True
            globals.log(f"\n----------\n{globals.ADDIN_NAME} troubleshooting mode enabled. Press Ctrl+Alt+C to show and hide this console. Or go to File -> View -> Show/Hide Text Commands.\n----------\n")

    del dialog_state_
