import ast
import textwrap
import typing
from dataclasses import dataclass
from typing import List

import pytest

import refactor
from refactor import ReplacementAction, Session, common, context
from refactor.context import Scope


class ReplaceNexts(refactor.Rule):
    INPUT_SOURCE = """
    def solution(Nexter: inputs):
        # blahblah some code here and there
        n = inputs.next_int()
        sub_process(inputs)
        st = inputs.next_str()
        sub_process(st)
    """

    EXPECTED_SOURCE = """
    def solution(Nexter: inputs):
        # blahblah some code here and there
        n = int(input())
        sub_process(inputs)
        st = str(input())
        sub_process(st)
    """

    def match(self, node):
        # We need a call
        assert isinstance(node, ast.Call)

        # on an attribute (inputs.xxx)
        assert isinstance(node.func, ast.Attribute)

        # where the name for attribute is `inputs`
        assert isinstance(node.func.value, ast.Name)
        assert node.func.value.id == "inputs"

        target_func_name = node.func.attr.removeprefix("next_")

        # make a call to target_func_name (e.g int) with input()
        target_func = ast.Call(
            ast.Name(target_func_name),
            args=[
                ast.Call(ast.Name("input"), args=[], keywords=[]),
            ],
            keywords=[],
        )
        return ReplacementAction(node, target_func)


class ReplacePlaceholders(refactor.Rule):
    INPUT_SOURCE = """
    def test():
        print(placeholder)
        print( # complicated
            placeholder
        )
        if placeholder is placeholder or placeholder > 32:
            print(3  + placeholder)
    """

    EXPECTED_SOURCE = """
    def test():
        print(42)
        print( # complicated
            42
        )
        if 42 is 42 or 42 > 32:
            print(3  + 42)
    """

    def match(self, node):
        assert isinstance(node, ast.Name)
        assert node.id == "placeholder"

        replacement = ast.Constant(42)
        return refactor.ReplacementAction(node, replacement)


class PropagateConstants(refactor.Rule):
    INPUT_SOURCE = """
    a = 1

    def main(d = 5):
        b = 4
        c = a + b
        e = 3
        e = 4
        return c + (b * 3) + d + e

    class T:
        b = 2
        print(a + b + c)

        def foo():
            c = 3
            print(a + b + c + d)
    """

    EXPECTED_SOURCE = """
    a = 1

    def main(d = 5):
        b = 4
        c = a + 4
        e = 3
        e = 4
        return c + (4 * 3) + d + e

    class T:
        b = 2
        print(a + 2 + c)

        def foo():
            c = 3
            print(a + b + 3 + d)
    """

    context_providers = (Scope,)

    def match(self, node):
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)

        current_scope = self.context["scope"].resolve(node)
        assert current_scope.defines(node.id)

        definitions = current_scope.definitions[node.id]

        assert len(definitions) == 1
        assert isinstance(definition := definitions[0], ast.Assign)
        assert isinstance(value := definition.value, ast.Constant)

        return refactor.ReplacementAction(node, value)


class ImportFinder(refactor.Representative):
    def collect(self, name, scope):
        import_statents = [
            node
            for node in ast.walk(self.context.tree)
            if isinstance(node, ast.ImportFrom)
            if node.module == name
            if scope.can_reach(self.context["scope"].resolve(node))
        ]

        names = {}
        for import_statement in import_statents:
            for alias in import_statement.names:
                names[alias.name] = import_statement

        return names


@dataclass
class AddNewImport(refactor.NewStatementAction):
    module: str
    names: List[str]

    def build(self):
        return ast.ImportFrom(
            level=0,
            module=self.module,
            names=[ast.alias(name) for name in self.names],
        )


@dataclass
class ModifyExistingImport(refactor.Action):
    name: str

    def build(self):
        new_node = self.branch()
        new_node.names.append(ast.alias(self.name))
        return new_node


class TypingAutoImporter(refactor.Rule):

    INPUT_SOURCE = """
    import lol
    from something import another

    def foo(items: List[Optional[str]]) -> Dict[str, List[Tuple[int, ...]]]:
        class Something:
            no: Iterable[int]

            def bar(self, context: Dict[str, int]) -> List[int]:
                print(1)
    """

    EXPECTED_SOURCE = """
    import lol
    from something import another
    from typing import Dict, List, Iterable, Optional, Tuple

    def foo(items: List[Optional[str]]) -> Dict[str, List[Tuple[int, ...]]]:
        class Something:
            no: Iterable[int]

            def bar(self, context: Dict[str, int]) -> List[int]:
                print(1)
    """

    context_providers = (ImportFinder, context.Scope)

    def find_last_import(self, tree):
        assert isinstance(tree, ast.Module)
        for index, node in enumerate(tree.body, -1):
            if isinstance(node, ast.Expr) and isinstance(
                node.value, ast.Constant
            ):
                continue
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            else:
                break

        return tree.body[index]

    def match(self, node):
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)
        assert node.id in typing.__all__
        assert not node.id.startswith("__")

        scope = self.context["scope"].resolve(node)
        typing_imports = self.context["import_finder"].collect(
            "typing", scope=scope
        )

        if len(typing_imports) == 0:
            last_import = self.find_last_import(self.context.tree)
            return AddNewImport(last_import, "typing", [node.id])

        assert len(typing_imports) >= 1
        assert node.id not in typing_imports

        closest_import = common.find_closest(node, *typing_imports.values())
        return ModifyExistingImport(closest_import, node.id)


@pytest.mark.parametrize(
    "rule",
    [
        ReplaceNexts,
        ReplacePlaceholders,
        PropagateConstants,
        TypingAutoImporter,
    ],
)
def test_complete_rules(rule):
    session = Session([rule])

    assert session.run(textwrap.dedent(rule.INPUT_SOURCE)) == textwrap.dedent(
        rule.EXPECTED_SOURCE
    )
