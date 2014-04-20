try:
    from ._radix import Radix
except Exception as e:
    from .radix import Radix

__version__ = '0.6.0'
__all__ = ['Radix']
