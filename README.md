# Object Pattern Matching for Python 3

Object pattern matching (opm) is similar to regular expressions. Instead of matching a string against a pattern, we match objects. Some programming languages have this feature built-in, like Rust:

```rust
let result = my_function();
match result {
    Some(value) => do_this(value),
    _ => do_that(),
}
```

This is just a very simple example, but this a very powerful technique.

However, this feature is not available in python by default. This repository contains the fruits of my work to implement this feature in python.

# Installation

Simply install this package with pip:

```shell
pip install --user pyopm
```

# Usage

**Note:** Until now, only very basic features have been implemented.

```python
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
m = p.match({0: 0, 'one': 1})  # 0: 0 does not match the rules -> m is None
m = p.match({0: 0.2, 'one': 1})  # match!

with m:  # magic: use the objects bound to the names specified above
    print(keys)
    print(values)
    print(list(zip(keys, values)))  # should be the same as...
    print(items)  # ...this!
    # Result:
    # dict_keys([0, 'one'])
	# dict_values([0.2, 1])
	# [(0, 0.2), ('one', 1)]
	# [(0, 0.2), ('one', 1)]
```

