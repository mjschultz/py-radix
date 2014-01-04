#!/usr/bin/env python

# Copyright (c) 2004 Damien Miller <djm@mindrot.org>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# $Id: setup.py,v 1.7 2007/12/18 00:53:53 djm Exp $

import sys
from distutils.core import setup, Extension

VERSION = "0.5"

if __name__ == '__main__':
	libs = []
	src = [ 'radix.c', 'radix_python.c' ]
	if sys.platform == 'win32':
		libs += [ 'ws2_32' ]
		src += [ 'inet_ntop.c', 'strlcpy.c' ]
	radix = Extension('radix', libraries = libs, sources = src)
	setup(	name = "py-radix",
		version = VERSION,
		author = "Damien Miller",
		author_email = "djm@mindrot.org",
        maintainer = "Michael J Schultz",
        maintainer_email = "mjschultz@gmail.com",
		url = "http://www.mindrot.org/py-radix.html",
		description = "Radix tree implementation",
		long_description = """\
py-radix is an implementation of a radix tree data structure for the storage 
and retrieval of IPv4 and IPv6 network prefixes.

The radix tree is the data structure most commonly used for routing table 
lookups. It efficiently stores network prefixes of varying lengths and 
allows fast lookups of containing networks.
""",
		license = "BSD",
		ext_modules = [radix]
	     )
