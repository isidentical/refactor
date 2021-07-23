import ast


def negate(node: ast.expr) -> ast.UnaryOp:
    """Negate the given `node`."""
    return ast.UnaryOp(op=ast.Not(), operand=node)


def apply_condition(condition: bool, node: ast.expr) -> ast.expr:
    """Negate the node if `condition` is a falsy value."""
    if condition:
        return node
    else:
        return negate(node)


def is_truthy(op: ast.cmpop) -> bool:
    """Return `True` for comparison operators that
    depend on truthness (`==`, `is`, `in`), `False`
    for others."""
    return isinstance(op, (ast.Eq, ast.In, ast.Is))
