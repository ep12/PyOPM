# pylint: disable=undefined-variable
from pyopm import ObjectPattern

p = ObjectPattern({
    'obj': {'eval': [lambda o: isinstance(o, dict)]},
    'obj.keys': {'eval': [lambda k: all(isinstance(x, (int, str)) for x in k())],
                 'bind': {'keys': lambda o: o()}},
    'obj.values': {'bind': {'values': lambda o: o()}},
    'obj.items': {'eval': [lambda i: all(isinstance(y, float if isinstance(x, int) else int)
                                         for x, y in i())],
                  'bind': {'items': lambda i: list(i())}},
})

m = p.match({0, 1, 2})  # not a dict -> m is None
print(type(m))
m = p.match({0: 0, 'one': 1})  # 0: 0 does not match the rules -> m is None
print(type(m))
m = p.match({0: 0.2, 'one': 1})  # match!
print(type(m))

with m:  # magic: use the objects bound to the names specified above
    print(keys)
    print(values)
    print(list(zip(keys, values)))  # should be the same as...
    print(items)  # ...this!

# Result:
# |> <class 'NoneType'>
# |> <class 'NoneType'>
# |> <class 'pyopm.core.ObjectPatternMatch'>
# |> dict_keys([0, 'one'])
# |> dict_values([0.2, 1])
# |> [(0, 0.2), ('one', 1)]
# |> [(0, 0.2), ('one', 1)]
