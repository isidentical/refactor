import ast

from refactor import Rule, common, run
from refactor.actions import BaseAction, InsertAfter, Replace
from refactor.context import ScopeInfo, ScopeType

ACTION_ALIAS_MAPPING = {
    "Action": "LazyReplace",
    "ReplacementAction": "Replace",
    "NewStatementAction": "LazyInsertAfter",
    "TargetedNewStatementAction": "InsertAfter",
}


class RenameDeprecatedAliases(Rule):
    def match(self, node: ast.AST) -> BaseAction:
        assert isinstance(node, (ast.Name, ast.Attribute))
        assert isinstance(node.ctx, ast.Load)

        if isinstance(node, ast.Name):
            return self._rename_name(node)
        else:
            return self._rename_attr(node)

    def _alias_for(self, node: ast.AST, name: str) -> str:
        # For return types, we'll use "BaseAction" instead
        # "Replace" when we are renaming "Action". It is
        # much more likely that the user meant that.

        if name == "Action":
            for (
                parent_field,
                parent_node,
            ) in self.context.ancestry.traverse(node):
                if (
                    common.is_function(parent_node)
                    and parent_field == "returns"
                ):
                    return "BaseAction"

        return ACTION_ALIAS_MAPPING[name]

    def _rename_name(self, node: ast.Name) -> Replace:
        assert node.id in ACTION_ALIAS_MAPPING

        replacement_node = common.clone(node)
        replacement_node.id = self._alias_for(node, node.id)
        return Replace(node, replacement_node)

    def _rename_attr(self, node: ast.Attribute) -> Replace:
        assert node.attr in ACTION_ALIAS_MAPPING

        replacement_node = common.clone(node)
        replacement_node.attr = self._alias_for(node, node.attr)

        # Action imports from refactor.core now becomes refactor.actions
        if (
            isinstance(inner_attr := replacement_node.value, ast.Attribute)
            and isinstance(module := inner_attr.value, ast.Name)
            and module.id == "refactor"
            and inner_attr.attr == "core"
        ):
            replacement_node.value.attr = "actions"

        return Replace(node, replacement_node)


class AdjustImports(Rule):
    def match(self, node: ast.AST) -> BaseAction:
        node_scope = self.context.scope.resolve(node)
        assert node_scope.scope_type is ScopeType.GLOBAL

        if isinstance(node, ast.Import):
            return self._adjust_import(node, node_scope)
        else:
            assert isinstance(node, ast.ImportFrom)
            return self._adjust_from(node, node_scope)

    def _adjust_import(self, node: ast.Import, scope: ScopeInfo) -> BaseAction:
        assert any(alias.name == "refactor.core" for alias in node.names)
        assert not scope.get_definitions("refactor.actions")
        return InsertAfter(
            node,
            ast.Import(
                names=[
                    ast.alias(
                        name="refactor.actions",
                    )
                ],
            ),
        )

    def _adjust_from(
        self, node: ast.ImportFrom, scope: ScopeInfo
    ) -> BaseAction:
        assert node.module in ("refactor", "refactor.core")

        aliases_to_fill = [
            ACTION_ALIAS_MAPPING[alias.name]
            for alias in node.names
            if alias.name in ACTION_ALIAS_MAPPING
            if not scope.get_definitions(ACTION_ALIAS_MAPPING[alias.name])
        ]
        if "LazyReplace" in aliases_to_fill and not scope.get_definitions(
            "BaseAction"
        ):
            aliases_to_fill += ["BaseAction"]

        assert aliases_to_fill
        return InsertAfter(
            node,
            ast.ImportFrom(
                module="refactor.actions",
                names=[
                    ast.alias(
                        name=alias,
                    )
                    for alias in aliases_to_fill
                ],
                level=0,
            ),
        )


if __name__ == "__main__":
    run([RenameDeprecatedAliases, AdjustImports])
