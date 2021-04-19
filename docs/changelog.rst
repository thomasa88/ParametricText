What's New
----------

-  v 2.2.0

   -  Workaround for Fusion 360™ giving error when inspecting some selections, which broke the name tracking for ``_.component``, ``_.file`` and ``_.sketch``.  
   -  Do not show an add-in error when *Compute All* fails. Instead, show an error notification. (#9)
   -  Workaround for missing document metadata (dataFile error). Force Fusion 360™ to download metadata. (#22)
   -  Workaround for Fusion 360™ resetting text height on text content change. (#21)
   -  Check if multiple copies av ParametricText has been installed (will only work for this version or newer).
   -  Show error dialog for unhandled error when updating sketch text.
   -  New documentation

-  v 2.1.0

   -  Fix Fusion 360 crash in non-parametric mode, by not calling
      *Compute All* in non-parametric mode.
   -  Only run automatic *Compute All* if there are any text parameters
      that have been updated.
   -  Text substrings using Python slice operator.
   -  Add ``_.sketch``

-  v 2.0.0

   -  Rewritten selection engine.

      -  Handle selection of texts in multi-occurrence components
         better.
      -  “Inherit” sketch parameters when pasting using *Paste New*.

   -  New parameter values: ``_.component``, ``_.file``
   -  Storage format version 2, to handle the new selection engine.
   -  Only one Undo item for text updates (not applicable to document
      save).
   -  Show count of texts selected in each sketch.
   -  Option to run *Compute All* automatically, to force features to
      update.
   -  Detect missing *thomasa88lib* helper library.
   -  Quick buttons for prepending braces and appending common
      parameters.

-  v 1.1.0

   -  ``_.date`` for retrieving document save date.
   -  Workaround for `Fusion 360™
      bug <https://forums.autodesk.com/t5/fusion-360-api-and-scripts/cannot-select-shx-fonts-on-sketchtext-object/m-p/9606551>`__
      when using Autodesk® SHX fonts.
   -  Informative error when a text has a negative angle.
   -  Don’t re-evaluate texts when the Change Parameters dialog is
      closed without any changes.
   -  Handle unit-less parameter values.

-  v 1.0.1

   -  Fix error when using ``_.version`` in documents that have never
      been saved.
   -  Redesign logo to comply with app store.

-  v 1.0.0

   -  Out of beta!

-  v 0.2.1

   -  Set table height to 10 rows.
   -  Fix #1. Handle unsaved documents.

-  v 0.2.0

   -  Basic support for Python format specifiers.
   -  *Insert braces* button.
   -  Selection tooltip, to show all selections when the text is
      truncated.
   -  Hide “select control”. Integrate clear button into table.
   -  Use correct unit/scaling when showing parameter value.
   -  Quick reference in dialog.

-  v 0.1.1

   -  Enable *Run on Startup* by default.

-  v 0.1.0

   -  First beta release
