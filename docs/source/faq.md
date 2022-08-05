## Frequently Asked Questions

### Isn't AST a wrong format for doing source to source transformations?

It is a common misconception that ASTs are not suitable for source code transformations, since they
don't preserve "syntactic clutter". Even though the last part is true, it actually doesn't really prevent
us to do the first. Unlike other AST-based solutions (like `ast.unparse()`), refactor itself has the chance of
leveraging the original AST as well as the original source code. With this information in our hands, we can
lower the target of a transformation into a very well scoped segment of source code (instead of the whole
file), then scan it for any details we can rescue (like comments, child nodes that haven't been touched)
and finally we can apply our transformations in a very conservative manner.

### What should I look next if refactor is not the right fit for me?

On use cases where refactor is not a right fit, we can highly recommend [parso](https://github.com/davidhalter/parso)
and [LibCST](https://github.com/Instagram/LibCST) as the other best tools in this space. They don't work on the AST level,
but rather provide their own syntax tree (a [CST]) to let you operate on (as well as a custom parser).

[cst]: https://eli.thegreenplace.net/2009/02/16/abstract-vs-concrete-syntax-trees/
