"""Implement basic Object Pattern Matching functionality."""
import re
import sys
import functools
import typing as T
from warnings import warn
import inspect

from pprint import pformat
from textwrap import indent

if sys.implementation.name == 'cpython':
    from ctypes import pythonapi, py_object, c_int

    def locals_to_fast(frame, clear: int = 0, **_):  # pylint: disable=missing-function-docstring
        pythonapi.PyFrame_LocalsToFast(py_object(frame), c_int(clear))
elif sys.implementation.name == 'pypy':
    import __pypy__  # pylint: disable=import-error

    def locals_to_fast(frame, *_, **__):  # pylint: disable=missing-function-docstring
        __pypy__.locals_to_fast(frame)
else:

    def locals_to_fast(*_, **__):  # pylint: disable=missing-function-docstring
        warn('LocalsToFast not defined (unhandled python implementation)')

cproperty = getattr(functools, 'cached_property', property)
FrameType = inspect.types.FrameType


CONFIG = {
    'changed existing': 'restore',  # restore (original value), keep (current value)
    # 'changed non-existing': 'delete',  # delete, keep (current value)
    'changed non-existing': 'keep',  # 'delete' would be better, but it does not work atm
    'deleted existing': 'restore',  # restore (original value), ignore
    'deleted non-existing': 'ignore',  # restore (bound value), ignore
    'unchanged existing': 'restore',  # restore (original value), keep (bound value)
    # 'unchanged non-existing': 'delete',  # delete, keep (bound value)
    'unchanged non-existing': 'keep',  # 'delete' would be better, but it does not work atm
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


def _start_block(frame: FrameType, bind: dict,
                 warn_unused: bool = False) -> T.Tuple[FrameType, dict]:
    """Bind values to the frame scope."""
    # pylint: disable=too-many-locals
    spec = {k: {'bound_value': v} for k, v in bind.items()}
    f_locals, f_globals = frame.f_locals, frame.f_globals
    code = frame.f_code
    cv_fast = set(code.co_varnames)  # arguments, locals
    cv_global = set(code.co_names)  # globals
    cv_closure = set(code.co_cellvars)  # this scope and children <-|
    cv_deref = set(code.co_freevars)  # this scope and parents <----|
    cv_local = cv_fast | cv_closure | cv_deref
    vars_all = cv_local | cv_global   # | set(f_locals.keys()) | set(f_globals.keys())
    for varname, value in bind.items():
        f_locals, f_globals = frame.f_locals, frame.f_globals  # always update
        exists = spec[varname]['exists'] = varname in vars_all
        if not exists:
            if warn_unused:
                warn(f'Unused variable: {varname!r}')
            continue  # not used, no need to bind it
        if varname in cv_fast:  # f_local
            spec[varname]['access'] = 'FAST'
            spec[varname]['target'] = 'f_locals'
            spec[varname]['exists_in_target'] = varname in f_locals
            spec[varname]['value_in_target'] = f_locals.get(varname)
            # BUG: broken?
            f_locals[varname] = value
            locals_to_fast(frame)
            assert varname in frame.f_locals
            assert id(frame.f_locals[varname]) == id(value)
        elif varname in cv_global:
            spec[varname]['access'] = 'GLOBAL'
            spec[varname]['target'] = 'f_globals'
            spec[varname]['exists_in_target'] = varname in f_globals
            spec[varname]['value_in_target'] = f_globals.get(varname)
            f_globals[varname] = value
        elif varname in cv_closure:
            raise NotImplementedError('CLOSURE not yet implemented')
        elif varname in cv_deref:
            raise NotImplementedError('DEREF not yet implemented')
        else:
            raise NotImplementedError('unknown access not yet implemented')
    return frame, spec


def _calculate_actions(spec: dict, config: dict, f_locals: dict, f_globals: dict) -> dict:
    """Calculate what to do based on spec and config."""
    # pylint: disable=too-many-branches
    to_do = {k: {} for k in spec}
    for varname, vspec in spec.items():
        if not vspec['exists']:
            continue
        target = f_locals if vspec['target'] == 'f_locals' else f_globals
        existed_in_target = vspec['exists_in_target']
        value_1, value_2 = vspec['value_in_target'], vspec['bound_value']
        deleted = varname not in target
        modified = target.get(varname) != value_2 and not deleted
        if deleted:
            if existed_in_target:
                if config.get('deleted existing', 'restore') == 'restore':
                    to_do[varname]['action'] = 'set'
                    to_do[varname]['value'] = value_1
                else:
                    pass  # ignore: user does not want the value
            else:
                if config.get('deleted non-existing', 'ignore') == 'restore':
                    to_do[varname]['action'] = 'set'
                    to_do[varname]['value'] = value_2
                else:
                    pass  # ignore
        elif modified:
            if existed_in_target:
                if config.get('changed existing', 'restore') == 'restore':
                    to_do[varname]['action'] = 'set'
                    to_do[varname]['value'] = value_1
                else:
                    pass  # ignore: user wants to keep the changed value
            else:
                if config.get('changed non-existing', 'delete') == 'delete':
                    to_do[varname]['action'] = 'delete'
                else:
                    pass  # ignore: keep
        else:  # unmodified, not deleted
            if existed_in_target:
                if config.get('unchanged existing', 'restore') == 'restore':
                    to_do[varname]['action'] = 'set'
                    to_do[varname]['value'] = value_1
                else:
                    pass  # ignore: user wants to keep the changed value
            else:
                if config.get('unchanged non-existing', 'delete') == 'delete':
                    to_do[varname]['action'] = 'delete'
                else:
                    pass  # ignore: keep
    return to_do


def _end_block(frame: FrameType, spec: dict, config: dict):
    code = frame.f_code
    f_locals, f_globals = frame.f_locals, frame.f_globals
    to_do = _calculate_actions(spec, config, f_locals, f_globals)
    for varname, action_spec in to_do.items():
        f_locals, f_globals = frame.f_locals, frame.f_globals  # always update
        action = action_spec.get('action')
        if action == 'set':
            value = action_spec['value']
            if spec[varname]['target'] == 'f_globals':
                f_globals[varname] = value
            else:
                f_locals.update({**f_locals, varname: value})
                locals_to_fast(frame)
                assert varname in frame.f_locals
                assert id(frame.f_locals[varname]) == id(value)
        elif action == 'delete':
            if spec[varname]['target'] == 'f_globals':
                del f_globals[varname]
            else:
                del f_locals[varname]
                locals_to_fast(frame)
                if varname in frame.f_locals:
                    warn(f'Could not delete {varname!r} ({code.co_filename!r}, '
                         f'in {code.co_name!r} near line {frame.f_lineno})', stacklevel=2)


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
        self.__f, self.__espec = _start_block(inspect.currentframe().f_back, self.bound,
                                              self.config.get('warn: unused', False))
        return self

    def __exit__(self, exc_type, exc_value, trb):
        _end_block(self.__f, self.__espec, self.config)
        del self.__f, self.__espec
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
                    warn(f'Overwriting binding for {var_name!r}')
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
        # pylint: disable=attribute-defined-outside-init
        if len(self) > 1:
            if self.allow_ambiguities:
                warn(f'Ambiguity: {len(self)} patterns matched!')
            else:
                raise AmbiguityError(f'{self.obj!r} matched {len(self)} patterns!')
        elif not self:
            raise NoMatchingPatternError(f'{self.obj!r} did not match any pattern!')
        self.match = min(self.successful_matches.items())[1]
        self.__f, self.__espec = _start_block(inspect.currentframe().f_back,
                                              self.match.bound,
                                              self.config.get('warn: unused', False))
        return self

    def __exit__(self, exc_type, exc_value, trb):
        _end_block(self.__f, self.__espec, self.config)
        del self.__f, self.__espec
        # Do we need to handle exc_type, exc_value, traceback?


matcher_pattern = ObjectPattern({'obj.match': {'eval': [callable]}})
# matches re.Pattern, ObjectPattern, ...
