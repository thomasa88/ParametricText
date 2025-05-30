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

from __future__ import annotations

import queue
from typing import Iterable

import adsk
import adsk.core as ac
import adsk.fusion as af

# Must import lib as unique name, to avoid collision with other versions
# loaded by other add-ins
# globals should scream if thomasa88lib cannot be loaded
from . import globals
from .thomasa88lib import utils

from . import storage
from . import dialog
from . import textgenerator

DIALOG_CMD_ID = 'thomasa88_ParametricText_Map'
MIGRATE_CMD_ID = 'thomasa88_ParametricText_Migrate'
UPDATE_CMD_ID = 'thomasa88_ParametricText_Update'
ERROR_CMD_ID = 'thomasa88_ParametricText_ErrorNotification'
# Custom event that other add-ins can fire using app.fireCustomEvent() to trigger
# an update of the texts containing text parameters.
# Note to developers: If you are doing anything more complicated than updating a few
# user parameters in Fusion, you should likely write a script from scratch instead of
# trying to patch together two scripts/add-ins ;).
EXT_UPDATE_EVENT_ID = 'thomasa88_ParametricText_Ext_Update'
PANEL_IDS = [
            'SketchModifyPanel',
            'SolidModifyPanel',
            'SheetMetalModifyPanel',
            'AssembleUtilityPanel',
            'SurfaceModifyPanel',
            'SnapshotSolidModifyPanel',
            'CAMManagePanel',
            # TODO: Add Modify panel Flat Panel Solid and Flat Panel Surface,
            # if that is possible. https://forums.autodesk.com/t5/fusion-api-and-scripts-forum/add-in-not-shown-in-quot-flat-pattern-quot/m-p/7540174
        ]

# Flag to check if add-in has been started/initialized.
started_: bool = False

running_compute_all_: bool = False

def run(_context: str) -> None:
    with globals.error_catcher_:
        globals.app_ = ac.Application.get()
        globals.ui_ = globals.app_.userInterface

        # Instance check, in case the user has installed ParametricText both from
        # the app store and from github
        instance_string = f'{globals.NAME_VERSION} in {utils.get_file_dir()}'
        if hasattr(adsk, 'thomasa88_parametric_text_running'):
            globals.ui_.messageBox(f"Two copies of {globals.ADDIN_NAME} are enabled:\n\n"
                           f"{adsk.thomasa88_parametric_text_running}\n" # type: ignore
                           f"{instance_string}\n\n"
                           "Please disable (add-ins dialog) or uninstall one copy.",
                           globals.NAME_VERSION)
            return
        adsk.thomasa88_parametric_text_running = instance_string # type: ignore
        global started_
        started_ = True

        # Make sure an old version of this command is not running and blocking the "add"
        if globals.ui_.activeCommand == DIALOG_CMD_ID:
            globals.ui_.terminateActiveCommand()

        dialog_cmd_def = dialog.create_cmd(DIALOG_CMD_ID, update_texts)

        for panel_id in PANEL_IDS:
            panel = globals.ui_.allToolbarPanels.itemById(panel_id)
            old_control = panel.controls.itemById(DIALOG_CMD_ID)
            if old_control:
                old_control.deleteMe()
            panel.controls.addCommand(dialog_cmd_def, 'ChangeParameterCommand', False)

        globals.events_manager_.add_handler(globals.app_.documentSaving, callback=document_saving_handler)
        globals.events_manager_.add_handler(globals.ui_.commandTerminated, callback=command_terminated_handler)
        globals.events_manager_.add_handler(globals.ui_.commandStarting, callback=command_starting_handler)

        globals.events_manager_.add_handler(globals.app_.documentOpened, callback=document_opened_handler)

        # Command used to group all "Set attributes" to one item in Undo history
        update_cmd_def = globals.ui_.commandDefinitions.itemById(UPDATE_CMD_ID)
        if update_cmd_def:
            update_cmd_def.deleteMe()
        update_cmd_def = globals.ui_.commandDefinitions.addButtonDefinition(UPDATE_CMD_ID, 'Calculate Text Parameters', '')
        globals.events_manager_.add_handler(update_cmd_def.commandCreated,
                                    callback=update_cmd_created_handler)

        error_cmd_def = globals.ui_.commandDefinitions.itemById(ERROR_CMD_ID)
        if error_cmd_def:
            error_cmd_def.deleteMe()
        error_cmd_def = globals.ui_.commandDefinitions.addButtonDefinition(ERROR_CMD_ID, 'Show error', '')
        globals.events_manager_.add_handler(error_cmd_def.commandCreated,
                                    callback=error_cmd_created_handler)
        
        delayed_event = globals.events_manager_.register_event(EXT_UPDATE_EVENT_ID)
        globals.events_manager_.add_handler(delayed_event, callback=ext_call_update_handler)

        if globals.app_.isStartupComplete and is_usable_workspace():
            # Add-in was (re)loaded while Fusion 360 was running
            storage.check_storage_version()
            if globals.settings_[globals.TROUBLESHOOT_SETTING]:
                dump_sketches()

def stop(_context: str) -> None:
    if not started_:
        return

    with globals.error_catcher_:
        globals.events_manager_.clean_up()

        panel = None
        for panel_id in PANEL_IDS:
            panel = globals.ui_.allToolbarPanels.itemById(panel_id)
            control = panel.controls.itemById(DIALOG_CMD_ID)
            if control:
                control.deleteMe()
        
        if panel:
            dialog_cmd_def = panel.controls.itemById(DIALOG_CMD_ID)
            if dialog_cmd_def:
                dialog_cmd_def.deleteMe()

        del adsk.thomasa88_parametric_text_running # type: ignore

# Tries to update the given SketchText, if the text value has changed.
# Returns True if the supplied text value differed from the old value.
def set_sketch_text(sketch_text: af.SketchText, text: str) -> bool:
    try:
        # Avoid triggering computations and undo history for unchanged texts
        if sketch_text.text == text:
            return False
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

            # More broken in Fusion 360™ version 2.0.9142. Let's try the TrueType
            # workaround, if it starts working again...
            try:
                old_font = sketch_text.fontName + '.shx'
                # Let's hope the user has Arial
                sketch_text.fontName = 'Arial'
                sketch_text.text = text
                sketch_text.fontName = old_font
            except RuntimeError:
                globals.ui_.messageBox(f'Cannot set text parameter in the sketch "{sketch_text.parentSketch.name}" '
                                'due to the text having an SHX font. This bug was introduced by Fusion 360™ version 2.0.9142.\n\n'
                                'Please change the text to not have an SHX font or remove it from the paremeter list.\n\n'
                                'See add-in help document/README for more information.',
                                globals.NAME_VERSION)
                # Unhook the text from the text parameter?
        elif msg == '3 : invalid input angle':
            # Negative angle bug. Cannot set text when the angle is negative.
            # Bug: https://forums.autodesk.com/t5/fusion-360-api-and-scripts/bug-unable-to-modify-text-of-a-sketchtext-created-manually-with/m-p/9502107
            # This seems to have been fixed in Fusion 360 v 2.0.9142, but keeping this branch in case they
            # break it again.
            globals.ui_.messageBox(f'Cannot set text parameter in the sketch "{sketch_text.parentSketch.name}" '
                            'due to the text having a negative angle.\n\n'
                            'Please edit the text to have a positive angle (add 360 degrees to the current angle).\n\n'
                            'See add-in help document/README for more information.',
                            globals.NAME_VERSION)
            # Unhook the text from the text parameter?
        elif (msg == '2 : InternalValidationError : res' and
              isinstance(globals.app_.activeProduct, af.FlatPatternProduct)):
            # For some reason, updating texts of sketches outside a flat pattern, while
            # being in the flat pattern environment, causes an InternalValidationError.
            # However, the sketch texts are updated correctly, so we just ignore this
            # error.
            # I have not been able to reproduce this in the Python console..
            globals.log('Ignore benign InternalValidationError when updating design '
                             'text from the flat pattern environment.')
        else:
            raise
    return True

def document_opened_handler(args: ac.DocumentEventArgs) -> None:
    if globals.settings_[globals.TROUBLESHOOT_SETTING]:
        globals.log(f"Document opened. Workspace: {globals.ui_.activeWorkspace.id}")
    if is_usable_workspace():
        storage.check_storage_version()

        if globals.settings_[globals.TROUBLESHOOT_SETTING]:
            dump_sketches()

def is_usable_workspace() -> bool:
    '''Workspaces where ParametricText can be used/run.'''
    return globals.ui_.activeWorkspace.id == 'FusionSolidEnvironment'

def document_saving_handler(args: ac.DocumentEventArgs) -> None:
    if globals.settings_[globals.TROUBLESHOOT_SETTING]:
        globals.log(f"Document saving. Workspace: {globals.ui_.activeWorkspace.id}")
    if is_usable_workspace():
        # This cannot run async or delayed, as we must update the parameters before Fusion
        # saves the document.
        update_texts(text_filter=['_.version', '_.date'], next_version=True)

def command_terminated_handler(args: ac.ApplicationCommandEventArgs) -> None:
    if globals.settings_[globals.TROUBLESHOOT_SETTING]:
        globals.log(f"Command terminated: {args.commandId}, reason: {args.terminationReason}")
    if args.terminationReason != ac.CommandTerminationReason.CompletedTerminationReason:
        if args.terminationReason == ac.CommandTerminationReason.CancelledTerminationReason and args.commandId == 'DesignConfigurationUpdateNestedRowNameCmd':
            # User renamed a configuration
            update_texts_async(text_filter=['_.configuration'])
        return

    # Taking action directly disturbs the Paste New command, so update_texts()
    # must be delayed or called through update_texts_async().
    # Also, call the async function to only get one Undo item.

    match args.commandId:
        case ('ChangeParameterCommand' |
              'SketchEditDimensionCmdDef' |
              'DesignConfigurationActivateRowCmd'):
            # User (might have) changed a parameter
            update_texts_async()
        case 'FusionPasteNewCommand':
            # User pasted a component, that will have a new name
            update_texts_async(text_filter=['_.component'])
        case 'FusionPropertiesCommand':
            # User changed component properties
            update_texts_async(text_filter=['_.component', '_.compdesc', '_.partnum'])
        case 'RenameCommand' | 'FusionRenameTimelineEntryCommand':
            # User might have changed a component or sketch name
            text_filter = set()
            for selection in globals.ui_.activeSelections:
                # Getting "RuntimeError: 3 : object is invalid" if we try to get the entity
                # for selection of some features/objects.
                try:
                    entity = selection.entity
                except RuntimeError:
                    continue
                if isinstance(entity, af.Occurrence):
                    text_filter.add('_.component')
                elif isinstance(entity, af.Sketch):
                    text_filter.add('_.sketch')
            if text_filter:
                update_texts_async(text_filter=text_filter)

def command_starting_handler(args: ac.ApplicationCommandEventArgs) -> None:
    if globals.settings_[globals.TROUBLESHOOT_SETTING]:
        globals.log(f"Command starting: {args.commandId}")
    if args.commandId == 'FusionComputeAllCommand':
        # The user wants the whole design to be recomputed, so let's update the
        # sketch texts before that.
        # FusionComputeAllCommand does not seem to trigger when we call computeAll(),
        # but better be safe than sorry.
        if not running_compute_all_:
            update_texts_async()

# NOTE: This function might be called from inside a command
def update_texts(text_filter: Iterable[str] | None = None,
                 next_version: bool | None = False,
                 texts: dict[int, storage.TextInfo] | None = None) -> None:
    if not storage.is_valid():
        return

    if texts is None:
        # No cached map of texts was provided. Let's build it.
        texts = storage.load_texts()

    if not texts:
        # There are no texts in this document. Skip all processing.
        return

    update_count = 0
    for text_id, text_info in texts.items():
        format_str = text_info.format_str
        assert format_str is not None
        if not text_filter or [filter_value for filter_value in text_filter
                               if filter_value in format_str]:
            for sketch_text in text_info.sketch_texts:
                # Must evaluate for every sketch for every text, in case
                # the user has used the component name parameter.
                text_updated = set_sketch_text(sketch_text, textgenerator.generate_text(format_str, sketch_text, next_version))
                if text_updated:
                    update_count += 1

    design = globals.get_design()
    # It is illegal to do "Compute All" in a non-parametric design.
    if (update_count > 0 and
        design.designType == af.DesignTypes.ParametricDesignType and
        globals.settings_[globals.AUTOCOMPUTE_SETTING]):
        try:
            global running_compute_all_
            running_compute_all_ = True
            try:
                design.computeAll()
            except RuntimeError as e:
                msg = None
                if len(e.args) > 0:
                    msg = e.args[0]
                if (msg == '2 : InternalValidationError : res' and
                    isinstance(globals.app_.activeProduct, af.FlatPatternProduct)):
                    # See comment in set_sketch_text(). It triggers when doing compute all
                    # inside the flat pattern environment as well.
                    globals.log('Ignore benign InternalValidationError when updating design '
                                     'text from the flat pattern environment when doing Compute All.')
            finally:
                running_compute_all_ = False
        except RuntimeError as e:
            if e.args and 'Compute Failed' in e.args[0]:
                msg = f'Compute all, triggered by {globals.NAME_VERSION}, failed:<br>\n<br>\n'
                msg += e.args[0].replace('5 : ', '').replace('\n', '<br>\n')
                # Putting the call at the end of the event queue, to not abort
                # any command that called this function.
                globals.events_manager_.delay(lambda: show_error_notification(msg))
            else:
                raise
    
    if globals.settings_[globals.TROUBLESHOOT_SETTING]:
        globals.log(f"Updated {update_count} sketch texts.")
        dump_sketches()

async_update_queue_ = queue.Queue()
def update_texts_async(text_filter: Iterable[str] | None = None, next_version: bool = False) -> None:
    # Running this as a command to avoid a big list of "Set attribute" in the Undo history.
    # We cannot avoid having at least one item in the Undo list:
    # https://forums.autodesk.com/t5/fusion-360-api-and-scripts/stop-custom-graphics-from-being-added-to-undo/m-p/9438477
    async_update_queue_.put((text_filter, next_version))
    update_cmd_def = globals.ui_.commandDefinitions.itemById(UPDATE_CMD_ID)
    update_cmd_def.execute()

def update_cmd_created_handler(args: ac.CommandCreatedEventArgs) -> None:
    cmd = args.command
    globals.events_manager_.add_handler(cmd.execute, callback=update_cmd_execute_handler)
    cmd.isAutoExecute = True
    cmd.isRepeatable = False
    # The synchronous doExecute makes Fusion crash..
     #cmd.doExecute(True)
    # Check migration result

def update_cmd_execute_handler(args: ac.CommandEventArgs) -> None:
    update_texts(*async_update_queue_.get())

error_notification_msg_: str | None = None
def show_error_notification(msg: str) -> None:
    '''Show an error notification.

    Note: The notification and the "More info" dialog renders HTML newlines (<br>),
          while the tooltip, when doing mouse-over on the red sign at the lower
          right, uses the newline character (\n).
    '''
    # Passing the message in the tooltip did not work (the event queue
    # needs to spin?). Using a global variable instead.
    global error_notification_msg_
    error_notification_msg_ = msg

    error_cmd_def = globals.ui_.commandDefinitions.itemById(ERROR_CMD_ID)
    error_cmd_def.execute()

def error_cmd_created_handler(args: ac.CommandCreatedEventArgs) -> None:
    cmd = args.command
    cmd.isAutoExecute = True
    cmd.isRepeatable = False
    globals.events_manager_.add_handler(cmd.execute, callback=error_cmd_execute_handler)

def error_cmd_execute_handler(args: ac.CommandEventArgs) -> None:
    assert error_notification_msg_ is not None
    args.executeFailed = True
    args.executeFailedMessage = error_notification_msg_

def ext_call_update_handler(args: ac.CustomEventArgs) -> None:
    if globals.settings_[globals.TROUBLESHOOT_SETTING]:
        globals.log(f"External update event")
    update_texts()

def dump_sketches() -> None:
    globals.log(f"Sketch dump:")
    design = globals.get_design()
    for comp in design.allComponents:
        globals.log(f" C: {comp.name}")
        for sketch in comp.sketches:
            globals.log(f"  S: {sketch.name}")
            for sketch_text in sketch.sketchTexts:
                attr_text = ""
                attrs = sketch_text.attributes.itemsByGroup(storage.ATTRIBUTE_GROUP)
                has_attrs = [attr for attr in attrs if attr.name.startswith('hasText_')]
                if has_attrs:
                    attr = has_attrs[0]
                    attr_text = f" [id={globals.extract_text_id(attr.name)}]"
                try:
                    globals.log(f'   "{sketch_text.text}"{attr_text}')
                except Exception as e:
                    globals.log(str(e))
