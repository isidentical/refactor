# Changelog

## in development

- `NewStatementAction` now auto indents the new statement by looking at previous statement's start prefix.
- Refactors now preserve the trailing new line
- `refactor.ast.split_lines` will now return a `refactor.ast.Lines` (list-like) object rather than a list
