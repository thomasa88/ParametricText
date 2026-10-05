Issues/Bugs
===========

Known Limitations
-----------------

- Update of text parameters does not automatically occur when the user cancels dimensioning by selecting another tool.

   - The workaround is to run Compute All manually.

The following are known limitations that cannot be fixed, due to the Fusion add-in interface.

- :kbd:`{` and :kbd:`}` cannot be entered in string inputs in Fusion on keyboards where they require :kbd:`AltGr` to be pressed.

  - The workaround is to use the :guilabel:`{}` buttons in the dialog.

- The mouse pointer must be moved before clicking on the same sketch text again, to do a second select/unselect.

- ``_.file`` does not update on file rename/copy.

  - The workaround is to open the *Change Text Parameters* dialog and click :guilabel:`OK`, in the new document.

Reporting Issues |issues_badge|
-------------------------------

.. |issues_badge| image:: https://badgen.net/github/open-issues/thomasa88/ParametricText

Please use the `Issues <https://github.com/thomasa88/ParametricText/issues>`__ page to find existing issues and to report new issues.

For better support when reporting an issue, please include the steps you performed and the
result. Also include copies of any error messages.

Enabling :ref:`troubleshooting mode<settings>` and copying the output from the text commands terminal is also recommended.
