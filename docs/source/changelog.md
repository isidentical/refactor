# Changelog

## 0.5.0

### Major

This release includes the overhaul of our action system, and with the next releases we will start removing the old ones. A list
of changes regarding actions can be seen here:

- `refactor.core` no longer contains any actions (the deprecated aliases are still imported and exposed but all the new actions go into `refactor.actions`)
- `Action` is now split into two, a `refactor.actions.BaseAction` which is the base of all actions (useful for type hinting) and a `refactor.actions.LazyReplace` (a replace action that builds the node lazily in its `build()`).
- `ReplacementAction` is now `refactor.actions.Replace`
- `NewStatementAction` is now `refactor.actions.LazyInsertAfter`
- `TargetedNewStatementAction` is now `refactor.actions.InsertAfter`

For migrating your code base to the new style actions, we wrote a small tool (that we also used internally), [examples/deprecated_aliases.py](https://github.com/isidentical/refactor/blob/master/examples/deprecated_aliases.py). Feel free to try it, and let us know if the transition was seamless.

### Other Changes

- Added experimental Windows support, contributed by [Hakan Celik](https://github.com/hakancelikdev)
- `common.find_closest` now takes `end_lineno` and `end_col_offset` into account. It also ensures there is at least one target node.
- Added `debug_mode` setting to `refactor.context.Configuration`
- Added a command-line flag (`-d`/`--enable-debug-mode`) to the default CLI runner to change session's configuration.
- When unparsable source code is generated, the contents can be now seen if the debug mode is enabled.
- \[Experimental\] Added ability to *partially* recover floating comments (from preceding or succeeding lines) bound to statements.
- The context providers now can be accessed with attribute notation, e.g. `self.context.scope` instead of `self.context.metadata["scope]`.
- If you access a built-in context provider (scope/ancestry) and it is not already imported, we auto-import it. So most common context providers are now ready to be used.

## 0.4.4

- Fixed crash of scope processing code due to keyword-only argument marker. Reported by [Felix Uellendall](https://github.com/feluelle) and contributed by [Hakan Celik](https://github.com/hakancelikdev)

## 0.4.3

- Fixed internal guards from failing due to a name error. Reported and contributed by [Nikita Sobolev](https://github.com/sobolevn).

## 0.4.2

- Fixed handling of `--refactor-file`. Reported and contributed by [gerrymanoim](https://github.com/gerrymanoim).

## 0.4.1

- Added support for preserving indented literal expressions (e.g the first argument of the following call):

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
