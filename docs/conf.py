# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import os
import sys
import datetime
sys.path.insert(0, os.path.abspath('../..'))


# automatic metadata access
import cmdkit  # noqa

# -- Project information -----------------------------------------------------

project = 'cmdkit'
copyright = f'2019-{datetime.datetime.now().year} Geoffrey Lentner'
author = 'Geoffrey Lentner <glentner@purdue.edu>'

# The full version, including alpha/beta/rc tags
release = cmdkit.__version__
version = cmdkit.__version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.viewcode',
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.extlinks',
    'sphinxext.opengraph',
    'sphinx_sitemap',
    'sphinx_copybutton',
    'sphinxcontrib.details.directive',
    'enum_tools.autoenum',
]

# do not include fully qualified names of objects with autodoc
add_module_names = False

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['build', 'Thumbs.db', '.DS_Store']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'pydata_sphinx_theme'
html_baseurl = 'https://cmdkit.readthedocs.io'
html_theme_options = {
    'external_links': [],
    'github_url': 'https://github.com/glentner/cmdkit',
    'logo': {
        'image_light': '_static/logo_light.png',
        'image_dark': '_static/logo_dark.png'
    },
    'pygment_light_style': 'tango',
    'pygment_dark_style': 'monokai',
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# export variables with epilogue
rst_epilog = f"""
.. |release| replace:: {release}
.. |copyright| replace:: {copyright}
"""
