from __future__ import annotations

import ast
import textwrap
import typing
from collections.abc import Iterator, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import pytest

from refactor import BaseAction, Rule, Session, common, context
from refactor.actions import (
    Erase,
    EraseOrReplace,
    InsertBefore,
    LazyInsertBefore,
    InsertAfter,
    LazyInsertAfter,
    LazyReplace,
    Replace,
)
from refactor.ast import DEFAULT_ENCODING
from refactor.context import Representative, Scope, ScopeType


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
        return Replace(node, replacement)


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

        return Replace(node, value)


class ImportFinder(Representative):
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
class AddNewImport(LazyInsertAfter):
    module: str
    names: list[str]

    def build(self):
        return ast.ImportFrom(
            level=0,
            module=self.module,
            names=[ast.alias(name) for name in self.names],
        )


@dataclass
class AddNewImportBefore(LazyInsertBefore):
    module: str
    names: list[str]

    def build(self):
        return ast.ImportFrom(
            level=0,
            module=self.module,
            names=[ast.alias(name) for name in self.names],
        )


@dataclass
class ModifyExistingImport(LazyReplace):
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
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
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
        typing_imports = self.context["import_finder"].collect("typing", scope=scope)

        if len(typing_imports) == 0:
            last_import = self.find_last_import(self.context.tree)
            return AddNewImport(last_import, "typing", [node.id])

        assert len(typing_imports) >= 1
        assert node.id not in typing_imports

        closest_import = common.find_closest(node, *typing_imports.values())
        return ModifyExistingImport(closest_import, node.id)


class TypingAutoImporterBefore(Rule):
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
    from typing import Dict, List, Iterable, Optional, Tuple
    from something import another

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
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
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
        typing_imports = self.context["import_finder"].collect("typing", scope=scope)

        if len(typing_imports) == 0:
            last_import = self.find_last_import(self.context.tree)
            return AddNewImportBefore(last_import, "typing", [node.id])

        assert len(typing_imports) >= 1
        assert node.id not in typing_imports

        closest_import = common.find_closest(node, *typing_imports.values())
        return ModifyExistingImport(closest_import, node.id)


class AsyncifierAction(LazyReplace):
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


class AwaitifierAction(LazyReplace):
    def build(self):
        if isinstance(self.node, ast.Expr):
            self.node.value = ast.Await(self.node.value)
            return self.node
        if isinstance(self.node, ast.Call):
            new_node = ast.Await(self.node)
            return new_node


class MakeCallAwait(Rule):
    INPUT_SOURCE = """
    def somefunc():
        call(
            arg0,
             arg1) # Intentional mis-alignment
    """

    EXPECTED_SOURCE = """
    def somefunc():
        await call(
            arg0,
             arg1) # Intentional mis-alignment
    """

    def match(self, node):
        assert isinstance(node, ast.Expr)
        assert isinstance(node.value, ast.Call)
        return AwaitifierAction(node)


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

    def match(self, node: ast.AST) -> BaseAction | None:
        assert isinstance(node, (ast.FunctionDef, ast.Lambda))
        assert any(kw_default is None for kw_default in node.args.kw_defaults)

        if isinstance(node, ast.Lambda) and not (
            isinstance(node.body, ast.Name) and isinstance(node.body.ctx, ast.Load)
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

    def _get_public_functions(self) -> Sequence[str] | None:
        # __all__ generally contains only a list/tuple of strings
        # so it should be easy to infer.

        global_scope = self.context.scope.global_scope

        try:
            [raw_definition] = global_scope.get_definitions("__all__")
        except ValueError:
            return None

        assert isinstance(raw_definition, ast.Assign)

        try:
            return ast.literal_eval(raw_definition.value)
        except ValueError:
            return None

    def match(self, node: ast.AST) -> Replace:
        assert isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))
        assert not node.name.startswith("_")

        node_scope = self.context.scope.resolve(node)
        assert node_scope.scope_type is ScopeType.GLOBAL

        public_functions = self._get_public_functions()
        assert public_functions is not None
        assert node.name not in public_functions

        new_node = common.clone(node)
        new_node.name = "_" + node.name
        return Replace(node, new_node)


class RemoveDeadCode(Rule):
    INPUT_SOURCE = """
    CONSTANT_1 = True
    CONSTANT_2 = False
    CONSTANT_3 = 1
    CONSTANT_4 = 0
    CONSTANT_5 = uninferrable()
    CONSTANT_6 = False
    CONSTANT_6 += 0
    CONSTANT_7: bool = False
    if CONSTANT_1:
        pass
    if CONSTANT_2:
        pass
    if CONSTANT_3:
        pass
    if CONSTANT_4:
        pass
    if CONSTANT_5:
        pass
    def f():
        if CONSTANT_1:
            pass
    def f():
        if CONSTANT_1:
            if CONSTANT_2:
                if CONSTANT_3:
                    pass
    def f():
        if CONSTANT_1:
            pass
        if CONSTANT_2:
            pass
    def f3():
        if CONSTANT_2:
            pass
        return
    def f4():
        try:
            if CONSTANT_2:
                pass
        except Exception:
            z = 4
            if CONSTANT_2:
                pass
        finally:
            if CONSTANT_4:
                pass
    for function in f():
        if CONSTANT_5:
            pass
    else:
        if CONSTANT_2:
            pass
    for function in f():
        if CONSTANT_2:
            pass
        a = 1
    else:
        b = 2
        if CONSTANT_2:
            pass
    if CONSTANT_6:
        if CONSTANT_7:
            pass
    """

    EXPECTED_SOURCE = """
        CONSTANT_1 = True
        CONSTANT_2 = False
        CONSTANT_3 = 1
        CONSTANT_4 = 0
        CONSTANT_5 = uninferrable()
        CONSTANT_6 = False
        CONSTANT_6 += 0
        CONSTANT_7: bool = False
        if CONSTANT_1:
            pass
        if CONSTANT_3:
            pass
        if CONSTANT_5:
            pass
        def f():
            if CONSTANT_1:
                pass
        def f():
            if CONSTANT_1:
                pass
        def f():
            if CONSTANT_1:
                pass
        def f3():
            return
        def f4():
            try:
                pass
            except Exception:
                z = 4
            finally:
                pass
        for function in f():
            if CONSTANT_5:
                pass
        else:
            pass
        for function in f():
            a = 1
        else:
            b = 2
        if CONSTANT_6:
            pass
    """

    def match(self, node: ast.AST) -> EraseOrReplace | None:
        assert isinstance(node, ast.If)

        if isinstance(node.test, ast.Constant):
            static_condition = node.test.value
        elif isinstance(node.test, ast.Name):
            node_scope = self.context.scope.resolve(node)
            definitions = node_scope.get_definitions(node.test.id)
            assert len(definitions) == 1 and isinstance(
                definition := definitions[0], (ast.Assign, ast.AnnAssign)
            )
            assert isinstance(definition.value, ast.Constant)
            static_condition = definition.value
        else:
            return None

        assert not static_condition.value
        assert not node.orelse
        return EraseOrReplace(node)


class DownstreamAnalyzer(Representative):
    context_providers = (context.Scope,)

    def iter_dependents(
        self, name: str, source: ast.Import | ast.ImportFrom
    ) -> Iterator[ast.Name]:
        for node in ast.walk(self.context.tree):
            if (
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == name
            ):
                node_scope = self.context.scope.resolve(node)
                definitions = node_scope.get_definitions(name)
                if any(definition is source for definition in definitions):
                    yield node


class RenameImportAndDownstream(Rule):
    context_providers = (DownstreamAnalyzer,)

    INPUT_SOURCE = """
        import a

        a.do_something()

        for _ in a.iter():
            print(
                a
                        + 1
                           + 3
            )

        @a.series
        def f():
            import a

            class Z(a.Backport):
                meth = a.method

            return a.backport()

        a

        def multi():
            if A:
                if B:
                    import a
                else:
                    import a
            else:
                import a

            for _ in range(x):
                a.do_something()

            return a.dot()
        """

    EXPECTED_SOURCE = """
        import b

        b.do_something()

        for _ in b.iter():
            print(
                b
                        + 1
                           + 3
            )

        @b.series
        def f():
            import b

            class Z(b.Backport):
                meth = b.method

            return b.backport()

        b

        def multi():
            if A:
                if B:
                    import b
                else:
                    import b
            else:
                import b

            for _ in range(x):
                b.do_something()

            return b.dot()
        """

    def match(self, node: ast.AST) -> Iterator[Replace]:
        assert isinstance(node, (ast.Import, ast.ImportFrom))

        aliases = [alias for alias in node.names if alias.name == "a"]
        assert len(aliases) == 1

        [alias] = aliases
        for dependent in self.context.downstream_analyzer.iter_dependents(
            alias.asname or alias.name, node
        ):
            yield Replace(dependent, ast.Name("b", ast.Load()))

        replacement = common.clone(node)
        replacement.names[node.names.index(alias)].name = "b"
        yield Replace(node, replacement)


class AssertEncoder(Rule):
    INPUT_SOURCE = """
        print(hello)
        assert "aaaaaBBBBcccc", "len=1"
        print('''
        test🥰🥰🥰
        © ®© ®
        ''')
        assert "©© ®®copyrighted®® ©©©", "len=2"
        print(hello)
        if something:
            assert (
                "🥰 😎 😇 print\
                    🥰 😎 😇"
            ), "some emojisss"

            def ensure():
                assert "€urre€y of eu™", "len=3"

        print("refactor  🚀 🚀")
    """

    EXPECTED_SOURCE = """
        print(hello)
        assert decrypt('<aaaaaBBBBcccc>'), "len=1"
        print('''
        test🥰🥰🥰
        © ®© ®
        ''')
        assert decrypt('<©© ®®copyrighted®® ©©©>'), "len=2"
        print(hello)
        if something:
            assert (
                decrypt('<🥰 😎 😇 print                    🥰 😎 😇>')
            ), "some emojisss"

            def ensure():
                assert decrypt('<€urre€y of eu™>'), "len=3"

        print("refactor  🚀 🚀")
    """

    def match(self, node: ast.AST) -> Replace:
        assert isinstance(node, ast.Assert)
        assert isinstance(test := node.test, ast.Constant)
        assert isinstance(inner_text := test.value, str)

        encrypt_call = ast.Call(
            func=ast.Name("decrypt"),
            args=[ast.Constant(f"<{inner_text}>")],
            keywords=[],
        )
        return Replace(test, encrypt_call)


class Usages(Representative):
    context_providers = (Scope,)

    def find(self, name: str, needle: ast.AST) -> Iterator[ast.AST]:
        """Iterate all possible usage sites of ``name``."""
        for node in ast.walk(self.context.tree):
            if isinstance(node, ast.Name) and node.id == name:
                scope = self.context.scope.resolve(node)
                if needle in scope.get_definitions(name):
                    yield node


class PropagateAndDelete(Rule):
    context_providers = (Usages,)

    INPUT_SOURCE = """
        import ast
        import foo
        def traverse():
            import bar
            for node in ast.walk(ast.parse("1 + 2")):
                dump(node, bar.loads())

        def dump(node, loaded):
            import zoo
            zoo.check(loaded)
            print(ast.dump(node))

        def no():
            ast = 1
            print(ast)

        class T(ast.NodeTransformer):
            traverse()
    """

    EXPECTED_SOURCE = """
    def traverse():
        for node in __import__('ast').walk(__import__('ast').parse("1 + 2")):
            dump(node, __import__('bar').loads())

    def dump(node, loaded):
        __import__('zoo').check(loaded)
        print(__import__('ast').dump(node))

    def no():
        ast = 1
        print(ast)

    class T(__import__('ast').NodeTransformer):
        traverse()
    """

    def match(self, node: ast.AST) -> Iterator[BaseAction]:
        # Check if this is a single import with no alias.
        assert isinstance(node, ast.Import)
        assert len(node.names) == 1

        [name] = node.names
        assert name.asname is None

        # Replace each usage of this module with its own __import__() call.
        import_call = ast.Call(
            func=ast.Name("__import__"),
            args=[ast.Constant(name.name)],
            keywords=[],
        )
        for usage in self.context.usages.find(name.name, node):
            yield Replace(usage, import_call)

        # And finally remove the import itself
        yield Erase(node)


class FoldMyConstants(Rule):
    INPUT_SOURCE = """
    result = (
        1 * 2 + (5 + 3) # A very complex math equation
    ) + 8 # Don't forget the 8 here
    """

    EXPECTED_SOURCE = """
    result = 18 # Don't forget the 8 here
    """

    def match(self, node: ast.AST) -> Replace:
        # Look for an arithmetic addition or subtraction
        assert isinstance(node, ast.BinOp)
        assert isinstance(op := node.op, (ast.Add, ast.Sub, ast.Mult))

        # Where both left and right are constants
        assert isinstance(left := node.left, ast.Constant)
        assert isinstance(right := node.right, ast.Constant)

        # And then replace it with the result of the computation
        if isinstance(op, ast.Add):
            result = ast.Constant(left.value + right.value)
        elif isinstance(op, ast.Mult):
            result = ast.Constant(left.value * right.value)
        else:
            result = ast.Constant(left.value - right.value)
        return Replace(node, result)


class AtomicTryBlock(Rule):
    INPUT_SOURCE = """
    def generate_index(base_path, active_path):
        module_index = defaultdict(dict)
        for base_file in base_path.glob("**/*.py"):
            file_name = str(base_file.relative_to(base_path))
            active_file = active_path / file_name
            module_name = file_name.replace('/', '.').removesuffix('.py')
            if 'test.' in module_name or '.tests' in module_name or 'encoding' in module_name or 'idle_test' in module_name:
                continue

            try:
                base_tree = get_tree(base_file, module_name)
                active_tree = get_tree(active_file, module_name)
                third_tree = get_tree(third_tree, module_name)
            except (SyntaxError, FileNotFoundError):
                continue

            print('processing ', module_name)
            try:
                base_tree = get_tree(base_file, module_name)
                active_tree = get_tree(active_file, module_name)
            except (SyntaxError, FileNotFoundError):
                continue"""

    EXPECTED_SOURCE = """
    def generate_index(base_path, active_path):
        module_index = defaultdict(dict)
        for base_file in base_path.glob("**/*.py"):
            file_name = str(base_file.relative_to(base_path))
            active_file = active_path / file_name
            module_name = file_name.replace('/', '.').removesuffix('.py')
            if 'test.' in module_name or '.tests' in module_name or 'encoding' in module_name or 'idle_test' in module_name:
                continue

            try:
                base_tree = get_tree(base_file, module_name)
            except (SyntaxError, FileNotFoundError):
                continue
            try:
                active_tree = get_tree(active_file, module_name)
            except (SyntaxError, FileNotFoundError):
                continue
            try:
                third_tree = get_tree(third_tree, module_name)
            except (SyntaxError, FileNotFoundError):
                continue

            print('processing ', module_name)
            try:
                base_tree = get_tree(base_file, module_name)
            except (SyntaxError, FileNotFoundError):
                continue
            try:
                active_tree = get_tree(active_file, module_name)
            except (SyntaxError, FileNotFoundError):
                continue"""

    def match(self, node: ast.AST) -> Iterator[Replace | InsertAfter]:
        assert isinstance(node, ast.Try)
        assert len(node.body) >= 2

        new_trys = []
        for stmt in node.body:
            new_try = common.clone(node)
            new_try.body = [stmt]
            new_trys.append(new_try)

        first_try, *remaining_trys = new_trys
        yield Replace(node, first_try)
        for remaining_try in reversed(remaining_trys):
            yield InsertAfter(node, remaining_try)


class WrapInMultilineFstring(Rule):
    INPUT_SOURCE = '''
def f():
    return """
a
"""
'''
    EXPECTED_SOURCE = '''
def f():
    return F("""
a
""")
'''

    def match(self, node):
        assert isinstance(node, ast.Constant)

        # Prevent wrapping F-strings that are already wrapped in F()
        # Otherwise you get infinite F(F(F(F(...))))
        parent = self.context.ancestry.get_parent(node)
        assert not (isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) and parent.func.id == 'F')

        return Replace(node, ast.Call(func=ast.Name(id="F"), args=[node], keywords=[]))


@pytest.mark.parametrize(
    "rule",
    [
        ReplaceNexts,
        ReplacePlaceholders,
        PropagateConstants,
        TypingAutoImporter,
        TypingAutoImporterBefore,
        MakeFunctionAsync,
        MakeCallAwait,
        OnlyKeywordArgumentDefaultNotSetCheckRule,
        InternalizeFunctions,
        RemoveDeadCode,
        RenameImportAndDownstream,
        AssertEncoder,
        PropagateAndDelete,
        FoldMyConstants,
        AtomicTryBlock,
        WrapInMultilineFstring,
    ],
)
def test_complete_rules(rule, tmp_path):
    session = Session([rule])

    source_code = textwrap.dedent(rule.INPUT_SOURCE)
    try:
        ast.parse(source_code)
    except SyntaxError:
        pytest.fail("Input source is not valid Python code")

    assert session.run(source_code) == textwrap.dedent(rule.EXPECTED_SOURCE)

    src_file_path = Path(tmp_path / rule.__name__.lower()).with_suffix(".py")
    src_file_path.write_text(source_code, encoding=DEFAULT_ENCODING)

    change = session.run_file(src_file_path)
    assert change is not None

    change.apply_diff()
    assert src_file_path.read_text(encoding=DEFAULT_ENCODING) == textwrap.dedent(
        rule.EXPECTED_SOURCE
    )
