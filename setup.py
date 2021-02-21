# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Build and installation script for CmdKit."""

# standard libs
import os
import re
from setuptools import setup, find_packages


# get long description from README.rst
with open('README.rst', mode='r') as readme:
    long_description = readme.read()


# get package metadata by parsing __meta__ module
with open('cmdkit/__meta__.py', mode='r') as source:
    content = source.read().strip()
    metadata = {key: re.search(key + r'\s*=\s*[\'"]([^\'"]*)[\'"]', content).group(1)
                for key in ['__pkgname__', '__version__', '__authors__', '__contact__',
                            '__description__', '__license__']}


# core dependencies
DEPENDENCIES = []


# add dependencies for readthedocs.io
if os.environ.get('READTHEDOCS') == 'True':
    DEPENDENCIES.extend(['pydata-sphinx-theme'])


setup(
    name             = metadata['__pkgname__'],
    version          = metadata['__version__'],
    author           = metadata['__authors__'],
    author_email     = metadata['__contact__'],
    description      = metadata['__description__'],
    license          = metadata['__license__'],
    keywords         = 'command-line utility toolkit',
    url              = 'https://cmdkit.readthedocs.io',
    packages         = find_packages(),
    include_package_data = True,
    long_description = long_description,
    long_description_content_type = 'text/x-rst',
    classifiers      = ['Development Status :: 5 - Production/Stable',
                        'Topic :: Software Development :: Libraries :: Application Frameworks',
                        'Programming Language :: Python :: 3',
                        'Programming Language :: Python :: 3.7',
                        'Programming Language :: Python :: 3.8',
                        'Programming Language :: Python :: 3.9',
                        'License :: OSI Approved :: Apache Software License', ],
    entry_points     = {'console_scripts': []},
    install_requires = DEPENDENCIES,
    extras_require   = {
        'toml': ['toml>=0.10.1', ],
        'yaml': ['pyyaml>=5.3.1', ],
    },
)
