#!/usr/bin/env python

import codecs
import re
import sys
import os

from setuptools import setup, find_packages, Extension
from os.path import abspath, dirname, join

here = abspath(dirname(__file__))

# determine the python version
IS_PYPY = hasattr(sys, 'pypy_version_info')
RADIX_NO_EXT = os.environ.get('RADIX_NO_EXT', False)


# Read the version number from a source file.
def find_version(*file_paths):
    # Open in Latin-1 so that we avoid encoding errors.
    # Use codecs.open for Python 2 compatibility
    with codecs.open(join(here, *file_paths), 'r', 'latin1') as f:
        version_file = f.read()

    # The version line must have the form
    # __version__ = 'ver'
    version_re = re.compile(r"^__version__ = ['\"]([^'\"]*)['\"]", re.M)
    version_match = version_re.search(version_file)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


with codecs.open(join(here, 'README.rst'), encoding='utf-8') as f:
    README = f.read()

# introduce some extra setup_args if Python 2.x
extra_kwargs = {}
if not IS_PYPY and not RADIX_NO_EXT:
    sources = ['radix/_radix.c', 'radix/_radix/radix.c']
    radix = Extension('radix._radix', sources=sources)
    extra_kwargs['ext_modules'] = [radix]


setup(
    name='py-radix',
    version=find_version('radix', '__init__.py'),
    maintainer='Michael J. Schultz',
    maintainer_email='mjschultz@gmail.com',
    url='https://github.com/mjschultz/py-radix',
    description='Radix tree implementation',
    long_description=README,
    license='BSD',
    keywords='radix tree trie python routing networking',
    classifiers=[
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Networking',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
    ],
    setup_requires=['nose', 'coverage'],
    packages=find_packages(exclude=['tests', 'tests.*']),
    test_suite='nose.collector',
    **extra_kwargs
)
