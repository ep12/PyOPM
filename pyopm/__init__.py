"""Implement object pattern matching for python."""

from .core import (ObjectPattern, ObjectPatternMatch, ObjectMultiPattern,
                   NoMatchingPatternError, AmbiguityError)
from .casematch import SwitchBlock
