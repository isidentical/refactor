"""
Without a custom unparser, the styling will default to what
ast.unparse is choosing;

Without the LiteralPreservingUnparser:
```
$ python examples/switch_places.py t.py
@@ -1,2 +1,2 @@

-print(1e400 + 1e100)
-print('''xxx''' + "x")
+print(1e+100 - 1e309)
+print('x' - 'xxx')
```

But if plug our custom unparser, then it will look like this;
```
$ python examples/switch_places.py t.py
@@ -1,2 +1,2 @@

-print(1e400 + 1e100)
-print('''xxx''' + "x")
+print(1e100 - 1e400)
+print("x" - '''xxx''')
```
"""


import ast
from contextlib import suppress

import refactor
from refactor import common
from refactor.ast import UnparserBase
from refactor.context import CustomUnparser


class LiteralPreservingUnparser(UnparserBase):
    def visit_Constant(self, node: ast.Constant) -> None:
        if token := self.token_map.get(common.position_for(node)):
            with suppress(ValueError):
                real_value = ast.literal_eval(token.string)
                if real_value == node.value:
                    return self.write(token.string)

        return super().visit_Constant(node)


class PreserveLiterals(CustomUnparser):

    unparser = LiteralPreservingUnparser


class SwitchPlacesAction(refactor.Action):
    def build(self):
        new_node = self.branch()
        new_node.op = ast.Sub()
        new_node.left, new_node.right = self.node.right, self.node.left
        return new_node


class SwitchPlaces(refactor.Rule):
    context_providers = (PreserveLiterals,)

    def match(self, node: ast.AST) -> refactor.Action:
        assert isinstance(node, ast.BinOp)
        assert isinstance(node.op, ast.Add)
        return SwitchPlacesAction(node)


if __name__ == "__main__":
    refactor.run(rules=[SwitchPlaces])
