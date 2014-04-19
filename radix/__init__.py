try:
    from _radix import *
except Exception as e:
    print 'C extension not found'
    print e

__version__ = '0.6.0'
