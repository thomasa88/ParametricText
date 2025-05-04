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

from collections import defaultdict

import adsk.fusion as af
import adsk.core as ac

from . import globals
from .thomasa88lib import utils

# The attribute "database" version. Used to check compatibility with
# parameters stored in the document.
STORAGE_VERSION: int = 2
ATTRIBUTE_GROUP = 'thomasa88_ParametricText'


class TextInfo:
    def __init__(self) -> None:
        self.sketch_texts: list[af.SketchText] = []
        self.format_str: str | None = None


# Flag to disable add-in if there are storage mismatches.
_is_valid_: bool = True

def _set_is_valid(valid: bool):
    global _is_valid_
    _is_valid_ = valid

def is_valid() -> bool:
    return _is_valid_

def load_texts() -> dict[int, TextInfo]:
    # TODO: Version 3 of ParametricText should store data in Document instead of Design,
    #       as there are sketches and user parameters in multiple product types.
    #       The hiearchy:
    #          * Document
    #            * Design
    #            * Sheet metal pattern (multiple)
    #            * more?
    design = globals.get_design()

    texts = defaultdict(TextInfo)

    value_attrs = [attr for attr in design.attributes.itemsByGroup(ATTRIBUTE_GROUP)
                  if attr.name.startswith('textValue_')]
    for value_attr in value_attrs:
        if not value_attr:
            continue
        text_id = globals.extract_text_id(value_attr.name)
        text_info = texts[text_id]
        text_info.format_str = value_attr.value

        # Get all sketch texts belonging to the attribute
        has_attrs = find_attributes_in_all_products(f'hasText_{text_id}')
        for has_attr in has_attrs:
            sketch_texts = text_info.sketch_texts
            if has_attr.parent:
                sketch_texts.append(af.SketchText.cast(has_attr.parent))
            if has_attr.otherParents:
                for other_parent in has_attr.otherParents:
                    sketch_texts.append(af.SketchText.cast(other_parent))
    
    return texts

def find_attributes_in_all_products(attr_name: str) -> list[ac.Attribute]:
    # Flat pattern sketches will be in the flat pattern product(s),
    # so need to loop all, not just Design.
    # Design is Design and FlatPatternProduct is inherited from Design.
    products = [p for p in globals.app_.activeDocument.products
                if isinstance(p, af.Design)]
    has_attrs = []
    for product in products:
        has_attrs += product.findAttributes(ATTRIBUTE_GROUP, attr_name)
    return has_attrs

def save_texts(texts: dict[int, TextInfo], removed_text_ids: list[int]) -> None:
    design = globals.get_design()

    save_storage_version()
    
    for text_id, text_info in texts.items():
        remove_attributes(text_id)

        assert text_info.format_str is not None, f'TextInfo for text_id {text_id} has no format string.'
        design.attributes.add(ATTRIBUTE_GROUP, f'textValue_{text_id}',
                              text_info.format_str)
    
        for sketch_text in text_info.sketch_texts:
            sketch_text.attributes.add(ATTRIBUTE_GROUP, f'hasText_{text_id}', '')

    for text_id in removed_text_ids:
        remove_attributes(text_id)

def save_storage_version() -> None:
    design = globals.get_design()

    design.attributes.add(ATTRIBUTE_GROUP, 'storageVersion', str(STORAGE_VERSION))

    # Add a warning to v1.x.x users
    design.attributes.add(ATTRIBUTE_GROUP, 'customTextValue_0', f'Parameters were created using version {globals.NAME_VERSION}')
    design.attributes.add(ATTRIBUTE_GROUP, 'customTextType_0', 'custom')
    design.attributes.add(ATTRIBUTE_GROUP, 'customTextValue_1', f'Please update {globals.ADDIN_NAME}')
    design.attributes.add(ATTRIBUTE_GROUP, 'customTextType_1', 'custom')

def load_next_id() -> int:
    next_id = 0
    design = globals.get_design()
    next_id_attr = design.attributes.itemByName(ATTRIBUTE_GROUP, 'nextId')
    if next_id_attr:
        if next_id_attr.value is None or next_id_attr.value == 'None':
            globals.ui_.messageBox(f'{globals.ADDIN_NAME}: Text id count value is corrupt: {next_id_attr.value}.\n\n'
                           'New texts might overwrite values of old texts. You should be able '
                           'to recover by loading an old version of this document.\n\n'
                           'Please inform the developer of what steps you performed to trigger this error.')
            next_id = 100 # Try to skip past used IDs..
        else:
            next_id = int(next_id_attr.value)
    globals.app_.log(f"{globals.ADDIN_NAME} LOAD NEXT ID {next_id}")
    return next_id

def save_next_id(next_id: int) -> bool:
    design = globals.get_design()
    globals.app_.log(f"{globals.ADDIN_NAME} SAVE NEXT ID {next_id}")
    if next_id is None:
        globals.ui_.messageBox(f'Failed to save text ID counter. Save failed.\n\n'
                       'Please inform the developer of the steps you performed to trigger this error.',
                       globals.NAME_VERSION)
        return False
    design.attributes.add(ATTRIBUTE_GROUP, 'nextId', str(next_id))
    return True

def remove_attributes(text_id: int) -> None:
    design = globals.get_design()

    old_attrs = find_attributes_in_all_products(f'hasText_{text_id}')
    for old_attr in old_attrs:
        old_attr.deleteMe()

    value_attr = design.attributes.itemByName(ATTRIBUTE_GROUP, f'textValue_{text_id}')
    if value_attr:
        value_attr.deleteMe()

##### update migration logic!
def check_storage_version() -> bool:
    '''Returns True if the storage format is compatible with the current version of the add-in.'''
    design = globals.get_design()
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
        ret = globals.ui_.messageBox(f'This document has text parameters created with an older storage format version ({file_db_version}), '
                             f'which is not compatible with the current storage format version ({STORAGE_VERSION}).\n\n'
                             'The text parameters will be converted to the new storage format.\n\n'
                             f'If you proceed, the document will no longer work with the older version of {globals.ADDIN_NAME}. '
                             f'If you cancel, you will not be able to update the text parameters using this version of {globals.ADDIN_NAME}.',
                             globals.NAME_VERSION,
                             ac.MessageBoxButtonTypes.OKCancelButtonType)
        if ret == ac.DialogResults.DialogOK:
            migrate_storage_async(file_db_version, STORAGE_VERSION)
        else:
            _set_is_valid(False)
    elif file_db_version == STORAGE_VERSION:
        # OK, this our version.
        _set_is_valid(True)
        return True
    elif file_db_version > STORAGE_VERSION:
        globals.ui_.messageBox(f'This document has text parameters created with a newer storage format version ({file_db_version}), '
                       f'which is not compatible with this version of {globals.ADDIN_NAME} ({STORAGE_VERSION}).\n\n'
                       f'You will need to update {globals.ADDIN_NAME} to be able to update the text parameters.',
                       globals.NAME_VERSION)
        _set_is_valid(False)
    else:
        globals.ui_.messageBox(f'This document has text parameters created with unknown storage format version ({file_db_version}).\n\n'
                       f'You will not be able to update the text parameters.\n\n'
                       f'Please report this to the developer. It is recommended that you restore an old version '
                       f'of your document.',
                       globals.NAME_VERSION)
        _set_is_valid(False)
    return False

migrate_from_ = None
migrate_to_ = None
def migrate_storage_async(from_version: int, to_version: int) -> None:
    # Running this as a command to avoid a big list of "Set attribute" in the Undo history.
    global migrate_from_, migrate_to_
    migrate_from_ = from_version
    migrate_to_ = to_version
    migrate_cmd_def = globals.ui_.commandDefinitions.itemById(MIGRATE_CMD_ID)
    if migrate_cmd_def:
        migrate_cmd_def.deleteMe()
    migrate_cmd_def = globals.ui_.commandDefinitions.addButtonDefinition(MIGRATE_CMD_ID, 'Migrate Text Parameters', '')
    events_manager_.add_handler(migrate_cmd_def.commandCreated,
                                callback=migrate_cmd_created_handler)
    migrate_cmd_def.execute()

def migrate_cmd_created_handler(args: ac.CommandCreatedEventArgs) -> None:
    cmd = args.command
    events_manager_.add_handler(cmd.execute, callback=migrate_cmd_execute_handler)
    cmd.isAutoExecute = True
    cmd.isRepeatable = False
    # The synchronous doExecute makes Fusion crash..
     #cmd.doExecute(True)
    # Check migration result

def migrate_cmd_execute_handler(args: ac.CommandEventArgs) -> None:
    from_version = migrate_from_
    to_version = migrate_to_
    design = globals.get_design()
    globals.app_.log(f'{globals.ADDIN_NAME} Migrating storage: {from_version} -> {to_version}')
    dump_storage()
    if from_version == 1 and to_version == 2:
        # Migrate global attributes
        design_attrs = design.attributes.itemsByGroup(ATTRIBUTE_GROUP)
        for attr in design_attrs:
            if attr.name.startswith('customTextType_'):
                globals.app_.log(f'{globals.ADDIN_NAME} deleting attribute "{attr.name}"')
                attr.deleteMe()
            elif attr.name.startswith('customTextValue_'):
                text_id = globals.extract_text_id(attr.name)
                new_attr_name = f'textValue_{text_id}'
                globals.app_.log(f'{globals.ADDIN_NAME} migrating "{attr.name}" -> "{new_attr_name}"')
                design.attributes.add(ATTRIBUTE_GROUP, new_attr_name, attr.value)
                attr.deleteMe()

        # The old version put the attributes on Sketch Text Proxies. The new format uses the
        # native Sketch Texts.
        migrate_proxy_to_native_sketch('hasParametricText_', 'hasText_')

        globals.app_.log(f'{globals.ADDIN_NAME} writing version {to_version}')
        save_storage_version()
    else:
        globals.ui_.messageBox('Cannot migrate from storage version {from_version} to {to_version}!',
                       globals.NAME_VERSION)
        _set_is_valid(False)
        return

    dump_storage()
    globals.app_.log(f'{globals.ADDIN_NAME} Migration done.')
    update_texts()
    globals.ui_.messageBox('Migration complete!')

def migrate_proxy_to_native_sketch(old_attr_prefix: str, new_attr_prefix: str) -> None:
    design = globals.get_design()
    globals.app_.log(f'Migrating {old_attr_prefix} to {new_attr_prefix}')
    attrs = design.findAttributes(ATTRIBUTE_GROUP, r're:' + old_attr_prefix + r'\d+')
    for attr in attrs:
        if attr.value is None:
            globals.app_.log(f'Attribute {attr.name} has no value. Skipping...')
        text_id = globals.extract_text_id(attr.name)
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

def dump_storage() -> None:
    '''Dumps all stored data to the console.'''
    design = globals.get_design()

    def print_attrs(attrs):
        for attr in attrs:
            globals.app_.log(f'"{attr.name}", "{attr.value}", '
                  f'"{parent_class_names(attr.parent)[0]}", ' +
                  '"' + '", "'.join(parent_class_names(attr.otherParents)) + '"')

    globals.app_.log('-' * 50)
    globals.app_.log('Design attributes')
    print_attrs(design.attributes.itemsByGroup(ATTRIBUTE_GROUP))
    globals.app_.log('Entity attributes')
    print_attrs(find_attributes_in_all_products(''))
    globals.app_.log('-' * 50)

def parent_class_names(parent_or_parents) -> list[str]:
    if parent_or_parents is None:
        return ["None"]
    
    class_names = []
    if not isinstance(parent_or_parents, ac.ObjectCollection):
        parent_or_parents = [parent_or_parents]

    for parent in parent_or_parents:
        class_names.append(utils.short_class(parent))
    
    return class_names
