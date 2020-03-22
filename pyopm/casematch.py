import inspect
import functools
from warnings import warn

from core import ObjectPattern, ObjectPatternMatch, NoMatchingPatternError, AmbiguityError

class ObjectCaseMatch:
    """Implement some sort of case/match statement functionality."""

    def __init__(self, obj: object, *patterns: ObjectPattern,
                 allow_ambiguities: bool = False, **match_args):
        self.obj = obj
        self.patterns = list(patterns)
        self.matches = [p.match(obj, **match_args) for p in self.patterns]
        self.match = None
        self.allow_ambiguities = allow_ambiguities

    @functools.cached_property
    def successful_matches(self):
        """A dictionary containing all the successfull matches."""
        return dict(filter(lambda t: isinstance(t[1], ObjectPatternMatch),
                           enumerate(self.matches)))

    def __len__(self):
        return len(self.successful_matches)

    def __bool__(self):
        return len(self) == 1

    def __enter__(self):
        if len(self) > 1:
            if self.allow_ambiguities:
                warn(f'Ambiguity: {len(self)} patterns matched!')
            else:
                raise AmbiguityError(f'{self.obj!r} matched {len(self)} patterns!')
        elif not self:
            raise NoMatchingPatternError(f'{self.obj!r} did not match any pattern!')
        self.match = min(self.successful_matches.items())[1]
        # W0201: attribute-defined-outside-init
        self.__f = inspect.currentframe()  # pylint: disable=W0201
        self.__existing_globals = dict(  # pylint: disable=W0201
            filter(lambda t: t[0] in self.match.bound,
                   self.__f.f_globals))
        self.__f.f_globals.update(self.match.bound)
        return self

    def __exit__(self, exc_type, exc_value, trb):
        for k in self.match.bound:
            self.__f.f_globals.pop(k, None)
        self.__f.f_globals.update(self.__existing_globals)
        del(self.__f, self.__existing_globals)
        # Do we need to handle exc_type, exc_value, traceback?
