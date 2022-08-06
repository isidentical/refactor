# Glossary

```{glossary}
constant
    An `ast.Constant` object that represents a hard-coded literal in the source code.

engine
    Engine is the core transformation loop that resides within a [session](refactor.core.Session). It
    is responsible for traversing the AST, managing rules and their context as well as running them
    on each node and continuously transform the source code until nothing more can be done with it.
```
