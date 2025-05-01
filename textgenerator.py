import datetime
import re
from typing import cast

import adsk.core as ac
import adsk.fusion as af

from . import globals
from . import paramparser
from . import paramformatter

SUBST_PATTERN = re.compile(r'{([^}]+)}')
DOCUMENT_NAME_VERSION_PATTERN = re.compile(r' (?:v\d+|\(v\d+.*?\))$')
def evaluate_text(format_str: str, sketch_text: af.SketchText, next_version: bool | None= False) -> str:
    design: af.Design = globals.app_.activeProduct
    def sub_func(subst_match: re.Match[str]) -> str:
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

        # Indicates that it is "reasonable" to slice the formatted string.
        is_sliceable = False

        if var_name == '_':
            if member == 'version':
                # No version information available if the document is not saved
                if globals.app_.activeDocument.isSaved:
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
                elif globals.app_.activeDocument.isSaved:
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
                is_sliceable = True
            elif member == 'compdesc':
                value = sketch_text.parentSketch.parentComponent.description
                is_sliceable = True
            elif member == 'partnum':
                value = sketch_text.parentSketch.parentComponent.partNumber
                is_sliceable = True
            elif member == 'file':
                ### Can we handle "Save as" or document copying?
                # activeDocument.name and activeDocument.dataFile.name gives us the same
                # value, except that the former exists and gives the value "Untitled" for
                # unsaved documents.
                document_name = globals.app_.activeDocument.name
                # Name string looks like this:
                # <name> v3
                # <name> (v3~recovered)
                # Strip the suffix
                document_name = DOCUMENT_NAME_VERSION_PATTERN.sub('', document_name)
                value = document_name
                is_sliceable = True
            elif member == 'sketch':
                value = sketch_text.parentSketch.name
                is_sliceable = True
            elif member == 'newline':
                value = '\n'
            elif member == 'configuration':
                top_table = design.configurationTopTable
                if top_table:
                    value = top_table.activeRow.name
                else:
                    value = '<No configuration>'
                is_sliceable = True
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
                is_sliceable = True
            elif member == 'expr':
                value = param.expression
            elif member == 'unit':
                value = param.unit
            elif member == 'inchfrac':
                value = paramformatter.mixed_frac_inch(param, design)
            else:
                return f'<Unknown member of {var_name}: {member}>'

        if param_spec.slice:
            if is_sliceable:
                value = cast(str, value)[param_spec.slice]
            else:
                return f'<Cannot substring parameter: {var_name}{member_sep}{member}>'

        try:
            formatted_str = ('{' + options_sep + options + '}').format(value)
        except ValueError as e:
            formatted_str = f'<{e.args[0]}>'
        return formatted_str

    shown_text = SUBST_PATTERN.sub(sub_func, format_str)
    return shown_text

def get_data_file() -> ac.DataFile:
    '''Wrapper for ActiveDocument.DataFile that tries to download the
    data from the cloud if it is not already cached.
    '''
    try:
        return probe_data_file()
    except NoDataFileError:
        pass

    # It looks like Fusion 360 has not downloaded the cloud data for this file,
    # either because it was opened through "Editable Documents" or as a sub-assembly
    # through another file, without opening t the file's folder.
    # Bug: https://forums.autodesk.com/t5/fusion-360-api-and-scripts/error-retrieving-datafile-in-unopened-folder/m-p/8384143#M6854
    
    # Trigger download of Editable Documents data
    if globals.app_.data.personalUseLimits:
        globals.app_.data.personalUseLimits.editableFiles
    
    try:
        return probe_data_file()
    except NoDataFileError:
        pass

    # Trigger download data for all documents
    progress = globals.ui_.createProgressDialog()
    progress.isCancelButtonShown = True
    projects = globals.app_.data.dataProjects
    base_msg = ("Cannot determine document's project (The folder has likely not been opened).\n"
                "Scanning for missing metadata.\n\n")
    try:
        progress.show(globals.NAME_VERSION, base_msg, 0, projects.count, 0)
        for i, p in enumerate(projects):
            progress.message = f"{base_msg}Scanning project \"{p.name}\""
            if progress.wasCancelled:
                break

            cache_data_folder(p.rootFolder)
            
            progress.progressValue = i + 1

            try:
                return probe_data_file()
            except NoDataFileError:
                pass
    finally:
        progress.hide()

    raise NoDataFileError

def cache_data_folder(folder: ac.DataFolder) -> None:
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

class NoDataFileError(Exception):
    pass

def probe_data_file() -> ac.DataFile:
    try:
        return globals.app_.activeDocument.dataFile
    except RuntimeError as e:
        if e.args and e.args[0].startswith('2 : InternalValidationError : dataFile'):
            # DataFile is currently not cached
            raise NoDataFileError from e
        else:
            raise
