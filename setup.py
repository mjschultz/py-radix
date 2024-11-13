#!/usr/bin/env python

import codecs
import sys
import os

from setuptools import setup, find_packages, Extension
from os.path import abspath, dirname, join

here = abspath(dirname(__file__))

# determine the python version
IS_PYPY = hasattr(sys, 'pypy_version_info')
RADIX_NO_EXT = os.environ.get('RADIX_NO_EXT', '0')
RADIX_NO_EXT = True if RADIX_NO_EXT not in ('0', 'false', 'False') else False

with codecs.open(join(here, 'README.rst'), encoding='utf-8') as f:
    README = f.read()

# introduce some extra setup_args if Python 2.x
extra_kwargs = {}
if not IS_PYPY and not RADIX_NO_EXT:
    sources = ['radix/_radix.c', 'radix/_radix/radix.c']
    radix = Extension('radix._radix',
                      sources=sources,
                      include_dirs=[join(here, 'radix')])
    extra_kwargs['ext_modules'] = [radix]


tests_require = ['nose', 'coverage']


setup(
    name='py-radix',
    version='0.10.0',
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
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13'
    ],
    tests_require=tests_require,
    packages=find_packages(exclude=['tests', 'tests.*']),
    install_requires=[
        'win-inet-pton >= 1.0.1;platform_system=="Windows"',
    ],
    test_suite='nose.collector',
    **extra_kwargs
)
