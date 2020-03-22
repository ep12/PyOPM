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