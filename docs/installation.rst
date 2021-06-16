Installation
============

ParametricText is available both on the Autodesk® App Store and Github.

The app store version comes as an easy to use installer, while the Github version comes as a zip file. The app store version usually lags 1-2 weeks on each new release, due to the approval process.

If in doubt, download the add-in from the app store. It also gives me download statistics.

Supported Platforms
-------------------

-  Windows
-  Mac OS

From Autodesk® App Store |app_store_version|
--------------------------------------------


Go to the `ParametricText page <https://apps.autodesk.com/All/en/List/Search?isAppSearch=True&searchboxstore=All&facet=&collection=&sort=&query=parametrictext>`__ on the Autodesk® App Store. Select your Operating System and follow the installation instructions on the page.

.. |app_store_version| image:: https://badgen.net/runkit/thomasa88/autodesk-appversion-badge/branches/master/2114937992453312456

From Github |github_version|
----------------------------

Download the add-in from the
`Releases <https://github.com/thomasa88/ParametricText/releases>`__
page. Find the version you want and download the ``ParametricText-vx.x.x.zip`` from under *Assets*.

Unpack the add-in into ``API\AddIns`` (see `How to install an add-in or script
in Fusion
360 <https://knowledge.autodesk.com/support/fusion-360/troubleshooting/caas/sfdcarticles/sfdcarticles/How-to-install-an-ADD-IN-and-Script-in-Fusion-360.html>`__).

Make sure the directory is named ``ParametricText``, with no suffix.

.. |github_version| image:: https://badgen.net/github/release/thomasa88/ParametricText/stable

Changing between App Store and Github variants
----------------------------------------------

The App Store installer and the Github files are installed in different places. Therefore, make sure to uninstall/remove the variant you are switching from, when changing installation method.

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
