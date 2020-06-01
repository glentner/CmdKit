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
from setuptools import setup, find_packages

# internal libs
from cmdkit.__meta__ import (__pkgname__,
                             __version__,
                             __authors__,
                             __contact__,
                             __license__,
                             __description__)


with open('README.md', mode='r') as readme:
    long_description = readme.read()


setup(
    name             = __pkgname__,
    version          = __version__,
    author           = __authors__,
    author_email     = __contact__,
    description      = __description__,
    license          = __license__,
    keywords         = 'command-line utility toolkit',
    url              = 'https://cmdkit.readthedocs.io',
    packages         = find_packages(),
    long_description = long_description,
    long_description_content_type='text/markdown',
    classifiers      = ['Development Status :: 5 - Production/Stable',
                        'Topic :: Software Development :: Libraries :: Application Frameworks',
                        'Programming Language :: Python :: 3',
                        'Programming Language :: Python :: 3.7',
                        'Programming Language :: Python :: 3.8',
                        'License :: OSI Approved :: Apache Software License', ],
    entry_points     = {'console_scripts': []},
    install_requires = ['logalpha>=2.0.2', ],
    extras_require  = {
        'toml': ['toml', ],
        'yaml': ['pyyaml', ],
    },
)
