from __future__ import annotations

import ast

from refactor import Representative, Rule, run
from refactor.actions import Replace
from refactor.context import Ancestry


class CheckFutureAnnotationsImport(Representative):
    def check(self) -> bool:
        body = self.context.tree.body
        if isinstance(body[0], ast.ImportFrom):
            import_stmt = body[0]
        elif isinstance(body[1], ast.ImportFrom):
            import_stmt = body[1]
        else:
            return False

        assert import_stmt.module == "__future__"
        assert any(alias.name == "annotations" for alias in import_stmt.names)
        return True


class RefactorFutureAnnotationUsedRule(Rule):
    context_providers = (CheckFutureAnnotationsImport, Ancestry)

    def match(self, node: ast.AST) -> Replace | None:
        assert isinstance(node, ast.Name)
        assert node.id in ("List", "Dict")

        for field, parent in self.context["ancestry"].traverse(node):
            if field == "annotation":
                break
        else:
            return None

        assert self.context["check_future_annotations_import"].check()

        future_annotation_mapping = {"List": "list", "Dict": "dict"}
        new_annotation_id = future_annotation_mapping[node.id]

        target = ast.Name(id=new_annotation_id, ctx=node.ctx)
        return Replace(node, target)


if __name__ == "__main__":
    run(rules=[RefactorFutureAnnotationUsedRule])
