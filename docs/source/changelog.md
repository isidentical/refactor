# Changelog

## 0.4.0

- Dependency resolution in context providers no longer cause recursions.
- `token_map` attributes got removed from `refactor.ast.BaseUnparser`.
- `refactor.ast.UnparserBase` got renamed to `refactor.ast.BaseUnparser`.
- Implemented the ability of precisely retrieving the existing child nodes from the source code through `refactor.ast.PreciseUnparser`.

## 0.3.0

- `refactor.NewStatementAction` now auto indents the new statement by looking at previous statement's start prefix.
- Refactors now preserve the trailing new line.
- `refactor.ast.split_lines` will now return a `refactor.ast.Lines` (list-like) object rather than a list.
- All command line programs now has `-a`, `--apply` option which writes the refactored version back to the file instead of dumping the diff.
- Some of non-deterministic refactors (generating variations of the same code) are now early exitted.
- `refactor.context.ScopeInfo` objects now can list definitions made in their context.
- `refactor.context.Context` objects now store the path for the module they are processing if it is available.
- Refactors now preserve the starting indentation for multiline statements.
