try:
    from ._radix import Radix as _Radix
except Exception as e:
    from .radix import Radix as _Radix

__version__ = '0.6.0'
__all__ = ['Radix']


# This acts as an entrypoint to the underlying object (be it a C
# extension or pure python representation, pickle files will work)
class Radix(object):
    def __init__(self):
        self._radix = _Radix()

    def add(self, *args, **kwargs):
        return self._radix.add(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._radix.delete(*args, **kwargs)

    def search_exact(self, *args, **kwargs):
        return self._radix.search_exact(*args, **kwargs)

    def search_best(self, *args, **kwargs):
        return self._radix.search_best(*args, **kwargs)

    def nodes(self):
        return self._radix.nodes()

    def prefixes(self):
        return self._radix.prefixes()

    def __iter__(self):
        for elt in self._radix:
            yield elt

    def __getstate__(self):
        return self._radix.__getstate__()

    def __setstate__(self, *args, **kwargs):
        self._radix.__setstate__(*args, **kwargs)

    def __reduce__(self):
        return (Radix, (), self.__getstate__())
