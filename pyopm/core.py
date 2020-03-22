"""Implement basic Object Pattern Matching functionality."""
import re
import functools
import typing as T
from warnings import warn
import inspect

from pprint import pformat
from textwrap import indent

cproperty = (functools.cached_property if hasattr(functools, 'cached_property')
             else property)
FrameType = inspect.types.FrameType


CONFIG = {
    'with block/changed existing': 'restore',  # restore, keep
    'with block/changed non-existing': 'delete',  # delete, keep
}


def break_attr_path(path: str):
    """Stupid approach to split an expression into parts."""
    parts, tmp = [], ''
    for x in re.split(r'([\.\[])', path):  # TODO: match parens?
        if x in {'.', '[', '('}:
            tmp = x
            continue
        parts.append(tmp + x)
    return tuple(parts)


def _start_block(frame: FrameType, bind: dict) -> T.Tuple[FrameType, dict]:
    existing = {k: v for k, v in frame.f_globals.items() if k in bind}
    frame.f_globals.update(bind)
    return frame, existing


def _end_block(frame: FrameType, bind: dict, original_values: dict, config: dict):
    unchanged_non_existing = {k for k, v in frame.f_globals.items()
                              if k in bind and v == bind[k] and k not in original_values}
    unchanged_existing = {k for k, v in frame.f_globals.items()
                          if k in bind and v == bind[k] and k in original_values}
    changed_non_existing = {k for k, v in frame.f_globals.items()
                            if k in bind and v != bind[k] and k not in original_values}
    changed_existing = {k for k, v in frame.f_globals.items()
                        if k in bind and v != bind[k] and k in original_values}
    for k in unchanged_non_existing:
        frame.f_globals.pop(k, None)
    for k in unchanged_existing:
        frame.f_globals[k] = original_values[k]
    if config.get('with block/changed non-existing', 'delete') == 'delete':
        for k in changed_non_existing:
            frame.f_globals.pop(k, None)
    if config.get('with block/changed existing', 'restore') == 'restore':
        for k in changed_existing:
            frame.f_globals[k] = original_values[k]


class NoMatchingPatternError(ValueError):
    """Exception that is raised, when an object didn't match any case."""


class AmbiguityError(ValueError):
    """Exception that is raised, when an object matched more than one case."""


class ObjectPattern:  # pylint: disable=missing-class-docstring,too-few-public-methods
    ...


class ObjectPatternMatch:
    """A match corresponding to a (pattern, object) pair."""

    def __init__(self, obj: object, pattern: ObjectPattern, bound: dict,
                 config: T.Optional[dict] = None):
        self.obj, self.pattern = obj, pattern
        self.bound = bound
        self.config = config if isinstance(config, dict) else CONFIG

    def __bool__(self):
        return True

    def __repr__(self):
        return f'ObjectPatternMatch({self.obj!r}, {self.pattern!r}, {self.bound!r})'

    def __str__(self):
        return f'<ObjectPatternMatch bindings={self.bound!r}/>'

    def __enter__(self):
        # pylint: disable=attribute-defined-outside-init
        self.__f, self.__existing = _start_block(inspect.currentframe().f_back, self.bound)
        return self

    def __exit__(self, exc_type, exc_value, trb):
        _end_block(self.__f, self.bound, self.__existing, self.config)
        del(self.__f, self.__existing)
        # Do we need to handle exc_type, exc_value, traceback?


class ObjectPattern:
    """A pattern that can be applied to any object."""

    def __init__(self, pattern: dict, verbose: bool = False,
                 config: T.Optional[dict] = None):
        assert isinstance(pattern, dict)
        self.pattern, self.verbose = pattern, verbose
        self.config = config if isinstance(config, dict) else CONFIG

    def __str__(self):
        return ('<ObjectPattern \n'
                + indent(pformat(self.pattern, width=76), ' ' * 4)
                + '\n/>')

    def __repr__(self):
        return f'<ObjectPattern({pformat(self.pattern)}) />'

    @cproperty
    def compiled_pattern(self):
        """Split the keys into attribute path bits."""
        return {break_attr_path(k): v for k, v in self.pattern.items()}

    def match(self, obj: object,
              eval_globals: dict = None, eval_locals: dict = None):
        # pylint: disable=too-many-locals
        """Apply the pattern to obj."""
        verbose = self.verbose
        eval_locals = ({'obj': obj, **eval_locals} if isinstance(eval_locals, dict)
                       else {'obj': obj})
        object_cache, bound = {}, {}

        def evalp(s):
            nonlocal eval_globals, eval_locals
            # Ugly, I know...
            # But now we don't have to deal with __getitem__ etc...
            return eval(s, eval_globals, eval_locals)

        for kt, v in self.compiled_pattern.items():
            for i in range(len(kt)):
                skt = kt[:i + 1]
                sk = ''.join(skt)
                if skt not in object_cache:
                    try:
                        object_cache[skt] = evalp(sk)
                    except Exception as e:
                        if verbose:
                            warn(f'Missing attribute? {sk!r}, {e}')
                        return None
            o = object_cache[kt]
            for test_func in v.get('eval', []):
                try:
                    if not bool(test_func(o)):
                        if verbose:
                            warn(f'Test failed: {test_func!r} ({kt!r}: {o!r})')
                        return None
                except Exception as e:
                    warn(f'Error running {test_func!r} ({kt!r}: {o!r}): {e}')
                    return None
            for var_name, var_eval in v.get('bind', {}).items():
                if verbose and var_name in bound:
                    warn(f'Overriding binding for {var_name!r}')
                bound[var_name] = (var_eval(o) if callable(var_eval) else
                                   (eval(var_eval, eval_globals, {**eval_locals, 'o': o})
                                    if isinstance(var_eval, str) else o))

        return ObjectPatternMatch(obj, self, bound, self.config)


class ObjectMultiPattern:
    """Implement matching against multiple patterns functionality."""
    # TODO: match method?

    def __init__(self, obj: object, *patterns: ObjectPattern,
                 allow_ambiguities: bool = False, config: T.Optional[dict] = None,
                 **match_args):
        self.obj = obj
        self.patterns = list(patterns)
        self.matches = [p.match(obj, **match_args) for p in self.patterns]
        self.match = None
        self.allow_ambiguities = allow_ambiguities
        self.config = config if isinstance(config, dict) else CONFIG

    @cproperty
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
        self.__f, self.__existing = _start_block(inspect.currentframe().f_back, self.match.bound)
        return self

    def __exit__(self, exc_type, exc_value, trb):
        _end_block(self.__f, self.match.bound, self.__existing, self.config)
        del(self.__f, self.__existing)
        # Do we need to handle exc_type, exc_value, traceback?


matcher_pattern = ObjectPattern({'obj.match': {'eval': [callable]}})
# matches re.Pattern, ObjectPattern, ...
