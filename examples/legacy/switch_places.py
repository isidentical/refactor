"""
A simple example that leverages the existing tokens to
regenerate the string back.

```
$ python examples/switch_places.py t.py
@@ -1,2 +1,2 @@

-print(1e400 + 1e100)
-print('''xxx''' + "x")
+print(1e100 - 1e400)
+print("x" - '''xxx''')
```
"""


from __future__ import annotations

import ast
from contextlib import suppress
from functools import cached_property

import refactor
from refactor import common
from refactor.ast import BaseUnparser


class LiteralPreservingUnparser(BaseUnparser):
    def visit_Constant(self, node: ast.Constant) -> None:
        if token := self.token_map.get(common.position_for(node)):
            with suppress(ValueError):
                real_value = ast.literal_eval(token.string)
                if real_value == node.value:
                    return self.write(token.string)

        return super().visit_Constant(node)

    @cached_property
    def token_map(self):
        return {(*token.start, *token.end): token for token in self.tokens}


class SwitchPlacesAction(refactor.LazyReplace):
    def build(self):
        new_node = self.branch()
        new_node.op = ast.Sub()
        new_node.left, new_node.right = self.node.right, self.node.left
        return new_node


class SwitchPlaces(refactor.Rule):
    def match(self, node: ast.AST) -> refactor.BaseAction:
        assert isinstance(node, ast.BinOp)
        assert isinstance(node.op, ast.Add)
        return SwitchPlacesAction(node)


if __name__ == "__main__":
    refactor.run(
        rules=[SwitchPlaces],
        config=refactor.Configuration(unparser=LiteralPreservingUnparser),
    )
