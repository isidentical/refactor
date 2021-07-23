# Refactor

Simple, dependency-free, AST based source code refactoring interface.

> :warning: **This project is still work-in-progress**: Be very careful with depending on the APIs!

## How

`refactor` is nothing more than a tiny wrapper around your AST processing code. Each refactor
operation is a rule (`refactor.Rule`) where they return either an action (`refactor.Action`) to
translate or None from their `match` (`match(node: ast.AST) -> Optional[refactor.Action]`) method.

