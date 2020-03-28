# pylint: disable=undefined-variable,import-error,
import re
import pytest

import os
import sys

# make sure to import the version of PyOPM found in ./
# instead of importing a stable version from /.../site-packages/
cwd = os.path.realpath('.')
if cwd not in sys.path:
    sys.path.insert(0, cwd)

import pyopm
from pyopm.core import (ObjectPattern, ObjectPatternMatch, ObjectMultiPattern, matcher_pattern,
                        AmbiguityError, NoMatchingPatternError)


CONFIG_DEFAULT = {
    'changed existing': 'restore',  # restore (original value), keep (current value)
    # 'changed non-existing': 'delete',  # delete, keep (current value)
    'changed non-existing': 'keep',  # 'delete' would be better, but it does not work atm
    'deleted existing': 'restore',  # restore (original value), ignore
    'deleted non-existing': 'ignore',  # restore (bound value), ignore
    'unchanged existing': 'restore',  # restore (original value), keep (bound value)
    # 'unchanged non-existing': 'delete',  # delete, keep (bound value)
    'unchanged non-existing': 'keep',  # 'delete' would be better, but it does not work atm
}
CONFIG_INVERSE = {
    'changed existing': 'keep',  # restore (original value), keep (current value)
    'changed non-existing': 'delete',  # delete, keep (current value)
    'deleted existing': 'ignore',  # restore (original value), ignore
    'deleted non-existing': 'restore',  # restore (bound value), ignore
    'unchanged existing': 'keep',  # restore (original value), keep (bound value)
    'unchanged non-existing': 'delete',  # delete, keep (bound value)
}


class DummyContext:
    def __enter__(self):
        pass

    def __exit__(self, *a):
        pass


class Dummy6:
    # pylint: disable=too-few-public-methods,missing-class-docstring
    def __init__(self, a, b, c, d, e, f):
        self.a, self.b, self.c, self.d, self.e, self.f = a, b, c, d, e, f


PD6 = {'obj.a': {'bind': {'a': None}}, 'obj.b': {'bind': {'b': None}},
       'obj.c': {'bind': {'c': None}}, 'obj.d': {'bind': {'d': None}},
       'obj.e': {'bind': {'e': None}}, 'obj.f': {'bind': {'f': None}}}


def test_start_end_block_default_cfg():
    """Test _start_block and _end_block (default config)."""
    o = Dummy6(1, 2, 3, 4, 5, 6)
    p = ObjectPattern(PD6, config=CONFIG_DEFAULT)
    print(p.config)
    m = p.match(o)
    a = 5  # existing, modified
    b = 6  # existing, deleted
    c = 7  # existing, unchanged
    with m:
        # pylint: disable=used-before-assignment
        assert (a, b, c, d, e, f) == (1, 2, 3, 4, 5, 6)
        a = 6
        del b
        d = 1
        del e
    assert a == 5
    assert b == 6
    assert c == 7
    assert d == 1
    with pytest.raises(NameError):
        print(e)  # works (because e is a global variable)
    assert f == 6


def test_start_end_block_inverse_cfg():
    """Test _start_block and _end_block (inverse config)."""
    o = Dummy6(1, 2, 3, 4, 5, 6)
    p = ObjectPattern(PD6, config=CONFIG_INVERSE)
    print(p.config)
    m = p.match(o)
    a = 5  # existing, modified
    b = 6  # existing, deleted
    c = 7  # existing, unchanged
    with DummyContext() if sys.implementation.name == 'pypy' else pytest.warns(UserWarning):
        with m:
            # pylint: disable=used-before-assignment
            assert (a, b, c, d, e, f) == (1, 2, 3, 4, 5, 6)
            a = 6
            del b
            d = 1
            del e
    assert a == 6
    with pytest.raises(NameError):
        print(b)
    assert c == 3
    if sys.implementation.name == 'pypy':
        with pytest.raises(NameError):
            print(d)
    else:
        assert d == 1
    assert e == 5
    # with pytest.raises(NameError):
    #     print(f)  # existed in target f_globals?


def test_object_pattern_basic():
    """Test ObjectPattern (basic use cases)."""
    pattern = ObjectPattern({
        'obj': {
            'eval': [lambda o: callable(o) or o is None]
        },
        'obj.__class__': {
            'eval': [lambda o: isinstance(o, type)],
            'bind': {'obj_type': None, 'obj_type_str': str}
        },
        'obj.__doc__': {
            'bind': {'docstring': None}
        }
    })
    m1 = pattern.match(None)
    m2 = pattern.match(ObjectPattern)
    m3 = pattern.match(set())
    assert isinstance(m1, ObjectPatternMatch)
    assert isinstance(m2, ObjectPatternMatch)
    assert m3 is None
    assert bool(m1)
    assert bool(m2)
    with m1:
        assert 'obj_type' in globals()
        assert obj_type == type(None)
        assert isinstance(obj_type_str, str)
        assert docstring == None.__doc__
    with m2:
        assert obj_type == type
        assert isinstance(obj_type_str, str)
        assert docstring == ObjectPattern.__doc__


def test_object_pattern_special_cases():
    """Test ObjectPattern (errors and warnings)"""
    p2 = ObjectPattern({'obj.keys': {'bind': {'keys': lambda o: list(o())}}})
    assert p2.match(None) is None

    p2.verbose = True
    with pytest.warns(UserWarning) as e:
        assert p2.match(None) is None
    assert e[0].message.args[0] == ("Missing attribute? 'obj.keys', "
                                    "'NoneType' object has no attribute 'keys'")

    def tf(o):
        return isinstance(o(), list)
    p3 = ObjectPattern({'obj.keys': {'eval': [tf]}}, verbose=True)
    d = {0: 1}
    with pytest.warns(UserWarning) as e:
        assert p3.match(d) is None
    assert e[0].message.args[0] == f"Test failed: {tf!r} (('obj', '.keys'): {d.keys!r})"

    def tf(o):
        raise ValueError('DEAD')
    p4 = ObjectPattern({'obj.keys': {'eval': [tf]}}, verbose=True)
    with pytest.warns(UserWarning) as e:
        assert p4.match(d) is None
    assert e[0].message.args[0] == (f"Error running {tf!r} (('obj', '.keys'):"
                                    f" {d.keys!r}): {ValueError('DEAD')}")

    p5 = ObjectPattern({'obj.keys': {'bind': {'keys': lambda o: list(o())}},
                        'obj.values': {'bind': {'keys': lambda o: list(o())}}},
                       verbose=True)
    with pytest.warns(UserWarning) as e:
        assert p5.match(d) is not None
    assert e[0].message.args[0] == f"Overwriting binding for 'keys'"


def test_object_pattern_context_handler():
    class Dummy:
        # pylint: disable=too-few-public-methods,missing-class-docstring
        def __init__(self, a, b, c, d, e):
            self.a, self.b, self.c, self.d, self.e = a, b, c, d, e

    p = ObjectPattern({
        'obj': {'eval': [lambda x: isinstance(x, Dummy)]},
        'obj.a': {'bind': {'a': None}},
        'obj.b': {'bind': {'b': None}},
        'obj.c': {'bind': {'c': None}},
        'obj.d': {'bind': {'d': None}},
        'obj.e': {'bind': {'e': None}}
    })
    o = Dummy('This', 'is', 1, 'stupid', 'test')
    m = p.match(o)
    a = 'That'
    d = 'smart'
    with m:
        c = m.bound['c']
        print(a, b, c, d, e)  # pylint: disable=used-before-assignment
        c = 'a'
        a = 'Dis'
        print(a, b, c, d, e)
        print('__exit__')
    # NOTE: this works with pypy, but insane defaults have been chosen to
    #   guarantee consistency across implementations
    # if sys.implementation.name == 'pypy':
    #     with pytest.raises(NameError):  # BUG: `del b` does not work
    #         print(b)
    #     with pytest.raises(NameError):  # BUG: broken #assignlocal/deletelocal
    #         print(c)
    #     with pytest.raises(NameError):
    #         print(e)
    assert a == 'That'
    assert d == 'smart'
    # TODO: more checks


def test_basic_object_multi_pattern():
    """Test ObjectMultiPattern."""
    p1 = ObjectPattern({
        'obj': {
            'eval': [
                lambda o: isinstance(o, dict),
                lambda o: (all(isinstance(x, int) for x in o.keys())
                           and all(isinstance(x, str) for x in o.values())),
            ],
            'bind': {
                'keys': lambda o: list(o.keys()),
                'values': lambda o: list(o.values())
            }
        }
    })
    p2 = ObjectPattern({
        'obj': {
            'eval': [
                lambda o: isinstance(o, (list, tuple)),
                lambda o: all(isinstance(x, tuple) and len(x) == 2 for x in o),
                lambda o: all(isinstance(x[0], int) for x in o),
                lambda o: all(isinstance(x[1], str) for x in o)
            ],
            'bind': {
                'keys': lambda o: [x[0] for x in o],
                'values': lambda o: [x[1] for x in o]
            }
        }
    })
    o1 = [(0, 'zero'), (1, 'one'), (2, 'two')]
    o2 = tuple(o1)
    o3 = dict(o1)
    for obj in (o1, o2, o3):
        with ObjectMultiPattern(obj, p1, p2):
            assert keys == [0, 1, 2]
            assert values == ['zero', 'one', 'two']

    p3 = ObjectPattern({'obj': {'eval': [lambda o: isinstance(o, list)]}})
    with pytest.warns(UserWarning) as e:
        with ObjectMultiPattern(o1, p1, p2, p3, allow_ambiguities=True):
            pass
    assert e[0].message.args[0] == 'Ambiguity: 2 patterns matched!'

    with pytest.raises(AmbiguityError) as e:
        with ObjectMultiPattern(o1, p1, p2, p3, allow_ambiguities=False):
            pass
    assert e.value.args[0] == f'{o1!r} matched 2 patterns!'

    with pytest.raises(NoMatchingPatternError) as e:
        with ObjectMultiPattern(None, p1, p2, p3):
            pass
    assert e.value.args[0] == f'{None!r} did not match any pattern!'


def test_str_repr():
    p = ObjectPattern({})
    p2 = ObjectPattern({'obj': {'eval': [callable]}})
    assert str(p) == '<ObjectPattern \n    {}\n/>'
    assert repr(p) == '<ObjectPattern({}) />'
    m = p.match(None)
    assert str(m) == '<ObjectPatternMatch bindings={}/>'
    assert repr(m) == 'ObjectPatternMatch(None, <ObjectPattern({}) />, {})'
    # mp = ObjectMultiPattern(str, p2, p, allow_ambiguities=True)
    # assert str(mp) == 


def test_context_handler():
    p = ObjectPattern({
        'obj.keys': {'eval': [lambda o: all(isinstance(x, int) for x in o())],
                     'bind': {'keys': lambda o: o()}},
        'obj.values': {'bind': {'values': lambda o: o()}},
        'obj.items': {'bind': {'items': lambda o: o()}},
    })
    m = p.match({0: 1, 1: 'two', 2: 3.0})
    values = []
    with m:
        assert list(keys) == [0, 1, 2]
        assert list(values) == [1, 'two', 3.0]
        with pytest.raises(NameError):
            # 'items' is in co_consts instead of co_varnames
            print(eval('items'))  # pylint: disable=eval-used


def test_meta_match():
    """Test the matcher_pattern."""
    assert bool(matcher_pattern.match(ObjectPattern))
    # assert bool(matcher_pattern.match(ObjectMultiPattern))
    if hasattr(re, 'Pattern'):
        assert bool(matcher_pattern.match(re.Pattern))


if __name__ == '__main__':
    print(pyopm)
    import dis
    # test_start_end_block()
    print('== test_object_pattern_basic')
    test_object_pattern_basic()
    print('== test_object_special_cases')
    test_object_pattern_special_cases()
    #
    d = dis.Bytecode(test_object_pattern_context_handler)
    print(d.dis())
    print('names    GLOBAL : ', d.codeobj.co_names)
    print('varnames FAST   : ', d.codeobj.co_varnames)
    print('cellvars CLOSURE: ', d.codeobj.co_cellvars)
    print('freevars DEREF  : ', d.codeobj.co_freevars)
    #
    print('== test_object_context_handler')
    test_object_pattern_context_handler()
    print('== test_object_multi_pattern')
    test_basic_object_multi_pattern()
    print('== test_str_repr')
    test_str_repr()
    print('== test_context_handler')
    test_context_handler()
    print('== test_meta_match')
    test_meta_match()
