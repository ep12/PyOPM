"""Implement basic Object Pattern Matching functionality."""
import re
import functools
from warnings import warn
import inspect

from pprint import pformat
from textwrap import indent


def break_attr_path(path: str):
    """Stupid approach to split an expression into parts."""
    parts, tmp = [], ''
    for x in re.split(r'([\.\[])', path):  # TODO: match parens?
        if x in {'.', '[', '('}:
            tmp = x
            continue
        parts.append(tmp + x)
    return tuple(parts)


class NoMatchingPatternError(ValueError):
    """Exception that is raised, when an object didn't match any case."""


class AmbiguityError(ValueError):
    """Exception that is raised, when an object matched more than one case."""


class ObjectPattern:  # pylint: disable=missing-class-docstring,too-few-public-methods
    ...


class ObjectPatternMatch:
    """A match corresponding to a (pattern, object) pair."""

    def __init__(self, obj: object, pattern: ObjectPattern, bound: dict):
        self.obj, self.pattern = obj, pattern
        self.bound = bound

    def __bool__(self):
        return True

    def __repr__(self):
        return f'ObjectPatternMatch({self.obj!r}, {self.pattern!r}, {self.bound!r})'

    def __str__(self):
        return f'<ObjectPatternMatch bindings={self.bound!r}/>'

    def __enter__(self):
        # W0201: attribute-defined-outside-init
        self.__f = inspect.currentframe()  # pylint: disable=W0201
        self.__existing_globals = dict(  # pylint: disable=W0201
            filter(lambda t: t[0] in self.bound,
                   self.__f.f_globals))
        self.__f.f_globals.update(self.bound)
        return self

    def __exit__(self, exc_type, exc_value, trb):
        for k in self.bound:
            self.__f.f_globals.pop(k, None)
        self.__f.f_globals.update(self.__existing_globals)
        del(self.__f, self.__existing_globals)
        # Do we need to handle exc_type, exc_value, traceback?


class ObjectPattern:
    """A pattern that can be applied to any object."""

    def __init__(self, pattern: dict, verbose: bool = False):
        assert isinstance(pattern, dict)
        self.pattern, self.verbose = pattern, verbose

    def __str__(self):
        return ('<ObjectPattern \n'
                + indent(pformat(self.pattern, width=76), ' ' * 4)
                + '\n/>')

    def __repr__(self):
        return f'<ObjectPattern({pformat(self.pattern)})'

    @functools.cached_property
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

        return ObjectPatternMatch(obj, self, bound)
