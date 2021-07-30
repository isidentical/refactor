import ast
from collections import defaultdict
from typing import DefaultDict, List

import refactor
from refactor.context import Scope, ScopeInfo


class Assignments(refactor.Representative):
    context_providers = (Scope,)

    def collect(self, scope: ScopeInfo) -> DefaultDict[str, List[ast.Assign]]:
        assignments = defaultdict(list)
        for node in ast.walk(scope.node):
            # Check whether this is a simple assignment to a name
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(target := node.targets[0], ast.Name)
            ):
                # Check whether we can reach this assignment or not.
                # For example there might be child functions where the
                # definition is unreachable for us.
                assignment_scope = self.context["scope"].resolve(node)
                if scope.can_reach(assignment_scope):
                    assignments[target.id].append(node)

        return assignments


class PropagationRule(refactor.Rule):

    context_providers = (Assignments, Scope)

    def match(self, node: ast.AST) -> refactor.Action:
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)

        scope = self.context["scope"].resolve(node)
        definitions = self.context["assignments"].collect(scope)
        assignments = definitions[node.id]

        # The name should be defined in the current scope
        # and there shouldn't be any overrides
        assert len(assignments) == 1

        # The value should be a constant, so that we can safely propagate
        [assignment] = assignments
        assert isinstance(value := assignment.value, ast.Constant)

        return refactor.ReplacementAction(node, value)


if __name__ == "__main__":
    refactor.run(rules=[PropagationRule])
