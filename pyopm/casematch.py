import inspect
import functools
from warnings import warn
import typing as T

from .core import ObjectPattern, ObjectPatternMatch, NoMatchingPatternError, AmbiguityError

cproperty = (functools.cached_property if hasattr(functools, 'cached_property')
             else property)


class SwitchBlock:
    def __init__(self, *cases: T.Iterable[T.Tuple[ObjectPattern, T.Callable]]):
        self.cases = list(cases)

    def switch(self, obj: object):
        ...
