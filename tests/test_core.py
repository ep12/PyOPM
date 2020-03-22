# pylint: disable=undefined-variable,import-error,
import re
from pyopm.core import ObjectPattern, ObjectPatternMatch, ObjectMultiPattern, matcher_pattern


def test_basic_1():
    """Test ObjectPattern."""
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
        assert obj_type == type(None)
        assert isinstance(obj_type_str, str)
        assert docstring == None.__doc__
    with m2:
        assert obj_type == type
        assert isinstance(obj_type_str, str)
        assert docstring == ObjectPattern.__doc__


def test_basic_2():
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


def test_meta_match():
    """Test the matcher_pattern."""
    assert bool(matcher_pattern.match(ObjectPattern))
    # assert bool(matcher_pattern.match(ObjectMultiPattern))
    if hasattr(re, 'Pattern'):
        assert bool(matcher_pattern.match(re.Pattern))
