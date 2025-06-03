Installation
============

ParametricText is available both on the Autodesk® App Store and Github.

The app store version comes as an easy to use installer, while the Github version comes as a zip file. The app store version usually lags 1-2 weeks on each new release, due to the approval process.

If in doubt, download the add-in from the app store. It also gives me download statistics.

Supported Platforms
-------------------

-  Windows
-  Mac OS

From Autodesk® App Store
------------------------


Go to the `ParametricText page <https://apps.autodesk.com/All/en/List/Search?isAppSearch=True&searchboxstore=All&facet=&collection=&sort=&query=parametrictext>`__ on the Autodesk® App Store. Select your Operating System and follow the installation instructions on the page.

Note: There have been some reports of the Mac installer not installing the add-in correctly ("Change Text Parameters" not showing up in the *MODIFY* menu). In that case, try installing the add-in from Github instead, as described below.

From Github |github_version|
----------------------------

#. Download the add-in from the `Releases <https://github.com/thomasa88/ParametricText/releases>`__ page.
   Find the version you want and download the ``ParametricText-vx.x.x.zip`` from under *Assets*.

#. Unpack the zip file where you want to store ParametricText.

#. Open the Add-ins dialog in Fusion using :kbd:`Shift+S` or  :guilabel:`UTILITIES` -> :guilabel:`Add-ins` -> :guilabel:`Scripts and add-ins`.

#. Click :guilabel:`+` to add the add-in.

.. |github_version| image:: https://badgen.net/github/release/thomasa88/ParametricText/stable

Changing between App Store and Github variants
----------------------------------------------

The App Store installer and the Github files are installed in different places. Therefore, make sure to stop and disable or uninstall/remove the variant you are switching from, when changing installation method.

Migrating from v 1.x to v 2.x
-----------------------------

A new storage format was introduced in version 2, in November 2020, to
accommodate new features and more correctly track sketch instances. If
you load a document created with version 1, you will be prompted to
update the text parameters to the new version.

After updating the text parameters, they can no longer be edited with
version 1.

It is recommended to save the document before doing the update, to have
a backup version.
