import ast
from pathlib import Path
from typing import Iterator

import refactor
from refactor import common
from refactor.context import Context
from refactor.internal.position_provider import infer_identifier_position

SOURCE_DIR = Path(refactor.__file__).parent


def iter_contexts() -> Iterator[Context]:
    for file in SOURCE_DIR.rglob("*.py"):
        source = file.read_text()
        tree = ast.parse(source)
        yield Context(source, tree)


def test_position_provider_for_definitions():
    for context in iter_contexts():
        nodes = [
            node
            for node in ast.walk(context.tree)
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            )
        ]
        for node in nodes:
            position = infer_identifier_position(node, node.name, context)
            assert position is not None
            known_location = common._get_known_location_from_source(
                context.source, position
            )
            assert known_location == node.name
