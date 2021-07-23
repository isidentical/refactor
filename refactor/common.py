import ast


def negate(node: ast.expr) -> ast.UnaryOp:
    """Negate the given `node`.

    Example:
        input => `foo`
        output => `not foo`
    """

    return ast.UnaryOp(op=ast.Not(), operand=node)
