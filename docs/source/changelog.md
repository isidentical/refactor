# Changelog

## 0.4.1

- Preserve indented literal expressions (e.g the first argument of the following call):

```
call(
    "something"
    "foo"
    "bar,
    3
)
```

## 0.4.0

- Fixed recursion on dependency resolution.
- Implemented precise unparsing to leverage from existing structures in the given source.
- Implemented `refactor.core.Configuration` to configure the unparser.
- Renamed `refactor.ast.UnparserBase` to `refactor.ast.BaseUnparser`.
- Removed `token_map` attribute from `refactor.ast.BaseUnparser`.
- Removed `refactor.context.CustomUnparser`.
- Changed `refactor.core.Action`'s `build` method to raise a `NotImplementedError`. Users now have to override it.

## 0.3.0

- `refactor.NewStatementAction` now auto indents the new statement by looking at previous statement's start prefix.
- Refactors now preserve the trailing new line.
- `refactor.ast.split_lines` will now return a `refactor.ast.Lines` (list-like) object rather than a list.
- All command line programs now has `-a`, `--apply` option which writes the refactored version back to the file instead of dumping the diff.
- Some of non-deterministic refactors (generating variations of the same code) are now early exitted.
- `refactor.context.ScopeInfo` objects now can list definitions made in their context.
- `refactor.context.Context` objects now store the path for the module they are processing if it is available.
- Refactors now preserve the starting indentation for multiline statements.

# (0.4.0) Adding a new argument to the whole call

-print(call(.1), maybe+something_else.prop)
+print(call(.1), maybe+something_else.prop, 'Hello')
