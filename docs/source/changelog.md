# Changelog

## Unreleased

- Fixed crash of scope processing code due to keyword-only argument marker. Reported by [Felix Uellendall](https://github.com/feluelle) and contributed by [Hakan Çelik](https://github.com/hakancelikdev)

## 0.4.3

- Fix internal guards from failing due to a name error. Reported and contributed by [Nikita Sobolev](https://github.com/sobolevn).

## 0.4.2

- Fix handling of `--refactor-file`. Reported and contributed by [gerrymanoim](https://github.com/gerrymanoim).

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
