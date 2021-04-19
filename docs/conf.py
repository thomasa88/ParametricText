# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import sphinx_rtd_theme

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = 'ParametricText'
copyright = '2021, Thomas Axelsson'
author = 'Thomas Axelsson'

# The full version, including alpha/beta/rc tags
release = ''


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx_rtd_theme',
    'sphinx.ext.autosectionlabel'
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', 'venv']

# Do not generate warnings for duplicate labels created by autosectionlabel
suppress_warnings = ['autosectionlabel.*']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
# Read-the-docs theme
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# sphinx_rtd_theme ignores html_sidebars
# Overriding parts of the layout using HTML
# files in the _templates directory instead.
# html_sidebars = {
#     '**': [
#         'globaltoc.html',
#         'relations.html',
#         'searchbox.html',
#         # located at _templates/
#         'sidebar_bottom.html',
#     ]
# }

html_theme_options = {
    'navigation_depth': 2,
#    'logo_only': True
}

#html_logo = '../resources/logo/32x32.png'

def setup(app):
    # Make table cell content wrap
    app.add_css_file("wrapping-tables.css")
    app.add_css_file("home-logo.css")
    app.add_css_file("style.css")
