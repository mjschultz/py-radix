#!/usr/bin/env python

from distutils.core import setup, Extension
from os.path import dirname, realpath, join

from radix import __version__

BASE_DIR = dirname(realpath(__file__))

with open(join(BASE_DIR, 'README.rst')) as f:
    README = f.read()

if __name__ == '__main__':
    sources = ['radix/_radix/radix.c', 'radix/_radix/python.c']
    radix = Extension('_radix', sources=sources)
    setup(
        name="py-radix",
        version=__version__,
        maintainer="Michael J Schultz",
        maintainer_email="mjschultz@gmail.com",
        url="http://www.github.com/mjschultz/py-radix",
        description="Radix tree implementation",
        long_description=README,
        license="BSD",
        ext_modules=[radix]
    )
