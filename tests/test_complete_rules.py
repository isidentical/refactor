import ast
import textwrap
import typing
from copy import deepcopy
from dataclasses import dataclass
from typing import List, Optional, Sequence

import pytest

import refactor
from refactor import BaseAction, Rule, Session, common, context
from refactor.actions import Replace
from refactor.context import Scope, ScopeType


class ReplaceNexts(Rule):
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
        return Replace(node, target_func)


class ReplacePlaceholders(Rule):
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
        return refactor.Replace(node, replacement)


class PropagateConstants(Rule):
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

        return refactor.Replace(node, value)


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
class AddNewImport(refactor.LazyInsertAfter):
    module: str
    names: List[str]

    def build(self):
        return ast.ImportFrom(
            level=0,
            module=self.module,
            names=[ast.alias(name) for name in self.names],
        )


@dataclass
class ModifyExistingImport(refactor.LazyReplace):
    name: str

    def build(self):
        new_node = self.branch()
        new_node.names.append(ast.alias(self.name))
        return new_node


class TypingAutoImporter(Rule):
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


class AsyncifierAction(refactor.LazyReplace):
    def build(self):
        new_node = self.branch()
        new_node.__class__ = ast.AsyncFunctionDef
        return new_node


class MakeFunctionAsync(Rule):
    INPUT_SOURCE = """
    def something():
        a += .1
        '''you know
            this is custom
                literal
        '''
        print(we,
            preserve,
                everything
        )
        return (
            right + "?")
    """

    EXPECTED_SOURCE = """
    async def something():
        a += .1
        '''you know
            this is custom
                literal
        '''
        print(we,
            preserve,
                everything
        )
        return (
            right + "?")
    """

    def match(self, node):
        assert isinstance(node, ast.FunctionDef)
        return AsyncifierAction(node)


class OnlyKeywordArgumentDefaultNotSetCheckRule(Rule):
    context_providers = (context.Scope,)

    INPUT_SOURCE = """
        class Klass:
            def method(self, *, a):
                print()

            lambda self, *, a: print

        """

    EXPECTED_SOURCE = """
        class Klass:
            def method(self, *, a=None):
                print()

            lambda self, *, a=None: print

        """

    def match(self, node: ast.AST) -> Optional[BaseAction]:
        assert isinstance(node, (ast.FunctionDef, ast.Lambda))
        assert any(kw_default is None for kw_default in node.args.kw_defaults)

        if isinstance(node, ast.Lambda) and not (
            isinstance(node.body, ast.Name)
            and isinstance(node.body.ctx, ast.Load)
        ):
            scope = self.context["scope"].resolve(node.body)
            scope.definitions.get(node.body.id, [])

        elif isinstance(node, ast.FunctionDef):
            for stmt in node.body:
                for identifier in ast.walk(stmt):
                    if not (
                        isinstance(identifier, ast.Name)
                        and isinstance(identifier.ctx, ast.Load)
                    ):
                        continue

                    scope = self.context["scope"].resolve(identifier)
                    while not scope.definitions.get(identifier.id, []):
                        scope = scope.parent
                        if scope is None:
                            break

        kw_defaults = []
        for kw_default in node.args.kw_defaults:
            if kw_default is None:
                kw_defaults.append(ast.Constant(value=None))
            else:
                kw_defaults.append(kw_default)

        target = deepcopy(node)
        target.args.kw_defaults = kw_defaults

        return Replace(node, target)


class InternalizeFunctions(Rule):
    INPUT_SOURCE = """
        __all__ = ["regular"]
        def regular():
            pass

        def foo():


            return easy_to_fool_me

        def               bar (                    ):
                return maybe_indented

        def        \
            maybe \
                (more):
                    return complicated

        if indented_1:
            if indented_2:
                def normal():
                    return normal

        @dataclass
        class Zebra:
            def does_not_matter():
                pass

        @deco
        async \
            def \
                async_function():
                    pass
        """

    EXPECTED_SOURCE = """
        __all__ = ["regular"]
        def regular():
            pass

        def _foo():


            return easy_to_fool_me

        def               _bar (                    ):
                return maybe_indented

        def        \
            _maybe \
                (more):
                    return complicated

        if indented_1:
            if indented_2:
                def _normal():
                    return normal

        @dataclass
        class _Zebra:
            def does_not_matter():
                pass

        @deco
        async \
            def \
                _async_function():
                    pass
        """

    def _get_public_functions(self) -> Optional[Sequence[str]]:
        # __all__ generally contains only a list/tuple of strings
        # so it should be easy to infer.

        global_scope = self.context.scope.global_scope

        try:
            [raw_definition] = global_scope.get_definitions("__all__") or []
        except ValueError:
            return None

        assert isinstance(raw_definition, ast.Assign)

        try:
            return ast.literal_eval(raw_definition.value)
        except ValueError:
            return None

    def match(self, node: ast.AST) -> Replace:
        assert isinstance(
            node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)
        )
        assert not node.name.startswith("_")

        node_scope = self.context.scope.resolve(node)
        assert node_scope.scope_type is ScopeType.GLOBAL

        public_functions = self._get_public_functions()
        assert public_functions is not None
        assert node.name not in public_functions

        new_node = common.clone(node)
        new_node.name = "_" + node.name
        return Replace(node, new_node)


@pytest.mark.parametrize(
    "rule",
    [
        ReplaceNexts,
        ReplacePlaceholders,
        PropagateConstants,
        TypingAutoImporter,
        MakeFunctionAsync,
        OnlyKeywordArgumentDefaultNotSetCheckRule,
        InternalizeFunctions,
    ],
)
def test_complete_rules(rule):
    session = Session([rule])

    assert session.run(textwrap.dedent(rule.INPUT_SOURCE)) == textwrap.dedent(
        rule.EXPECTED_SOURCE
    )
