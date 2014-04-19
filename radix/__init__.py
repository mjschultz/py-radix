try:
    from radix._radix import Radix
except Exception as e:
    print 'C extension not found'
    print e

__version__ = '0.6.0'

__all__ = ['Radix']
