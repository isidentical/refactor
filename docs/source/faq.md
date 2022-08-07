## Frequently Asked Questions

### Refactor-related Questions

#### How can I test my rules?

Refactor offers a [programmable API](tutorials/programmatic-api.md) which you
can use for your tests. Here are some examples for common test frameworks

::::{tab-set}
:::{tab-item} pytest

```{code-block} python
---
emphasize-lines: 2, 19, 20
---
import pytest
from refactor import Session
from fold_my_constants import FoldMyConstants, PropagateMyConstants

@pytest.mark.parametrize(
    "input, expected",
    [
        # True Positives
        ("1 + 2", "3"),
        ("a = 3 + 4", "a = 7"),
        ("a = 3 + 4; print(a - 1)", "a = 7; print(6)"),

        # False Negatives
        ("4 * 4", "4 * 4"),
        ("a = 3 + math.pi", "a = 3 + math.pi"),
    ]
)
def test_tutorial(input, expected):
    session = Session(rules=[FoldMyConstants, PropagateMyConstants])
    assert session.run(input) == expected
```

:::

:::{tab-item} unittest

```{code-block} python
---
emphasize-lines: 2, 18, 19
---
from unittest import TestCase
from refactor import Session
from fold_my_constants import FoldMyConstants, PropagateMyConstants

class TestRules(TestCase):
    def test_tutorial(self):
        for input, expected in [
            # True Positives
            ("1 + 2", "3"),
            ("a = 3 + 4", "a = 7"),
            ("a = 3 + 4; print(a - 1)", "a = 7; print(6)"),

            # False Negatives
            ("4 * 4", "4 * 4"),
            ("a = 3 + math.pi", "a = 3 + math.pi"),
        ]:
            with self.subTest(input=input, expected=expected):
                session = Session(rules=[FoldMyConstants, PropagateMyConstants])
                self.assertEqual(session.run(input), expected)
```

:::
::::

### Meta Questions

#### Isn't AST a wrong format for doing source to source transformations?

It is a common misconception that ASTs are not suitable for source code transformations, since they
don't preserve "syntactic clutter". Even though the last part is true, it actually doesn't really prevent
us to do the first. Unlike other AST-based solutions (like `ast.unparse()`), Refactor itself has the chance of
leveraging the original AST as well as the original source code. With this information in our hands, we can
lower the target of a transformation into a very well scoped segment of source code (instead of the whole
file), then scan it for any details we can rescue (like comments, child nodes that haven't been touched)
and finally we can apply our transformations in a very conservative manner.

#### What should I look next if Refactor is not the right fit for me?

On use cases where refactor is not a right fit, we can highly recommend [parso](https://github.com/davidhalter/parso)
and [LibCST](https://github.com/Instagram/LibCST) as the other best tools in this space. They don't work on the AST level,
but rather provide their own syntax tree (a [CST]) to let you operate on (as well as a custom parser).

[cst]: https://eli.thegreenplace.net/2009/02/16/abstract-vs-concrete-syntax-trees/
