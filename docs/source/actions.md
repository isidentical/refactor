# Actions

Each rule can return an `Action` which is simply an order to refactor. The
main entrypoint for an `Action` is it's `apply()` method, where it takes the
source code and returns the refactored version of it.

## Action

The default `apply()` method implemented in `refactor.Action` calls the
`build()` method, and replaces the original node it got with the new node
returned by the `build()` method. Here is a simple action that will replace
`+` with `-` on a binary operation

```py
class CustomBuildAction(refactor.Action):

    def build(self):
        new_node = self.branch()
        new_node.op = ast.Sub()
        return new_node
```

The `branch()` method will return an exact copy of the current node, and
on top of that node we will change the `op` to point to `ast.Sub` (`-`) instead
of `ast.Add` (`+`).

Let's also write the rule that uses it:

```py
class ReplaceAdd(refactor.Rule):

    def match(self, node):
        assert isinstance(node, ast.BinOp)
        assert isinstance(node.op, ast.Add)

        return CustomBuildAction(node)
```

## ReplacementAction

If you want to build the new node in the rule rather than in a custom action's `build()`,
you can simply use the `ReplacementAction`. It will replace the `node` (first argument)
with the `target` (second argument). Also it's `build()` method will return the `target`.

```py
class ReplaceAdd(refactor.Rule):

    def match(self, node):
        assert isinstance(node, ast.BinOp)
        assert isinstance(node.op, ast.Add)

        new_node = copy.deepcopy(node)
        new_node.op = ast.Sub()
        return refactor.ReplacementAction(node, new_node)
```

## NewStatementAction

If you don't want to replace a node, but rather add a new statement after that (e.g adding
a new import if it already doesn't exist), it's where `NewStatementAction` comes to play. Let's
write a simple example which would add `exit()` calls to the end of every `main()` function:

```py
@dataclass
class AddExitAction(refactor.NewStatementAction):

    status_code: int

    def build(self):
        return ast.Call(
            ast.Name("exit", ast.Load()),
            args = [ast.Constant(self.status_code)],
            keywords = []
        )

class AddExitCalls(refactor.Rule):

    def match(self, node):
        # find all main() functions
        assert isinstance(node, ast.FunctionDef)
        assert node.name == 'main'

        # ensure the last statement *is not* exit()
        last_stmt = node.body[-1]
        if (
            isinstance(last_stmt, ast.Expr)
            and isinstance(call := last_stmt.value, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "exit"
        ):
            return None

        # add a new statement after the last statement of
        # the current function to call exit()
        return AddExitAction(last_stmt, 0)
```
