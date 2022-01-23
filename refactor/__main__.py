import importlib
import importlib.util
from argparse import ArgumentParser
from itertools import chain
from pathlib import Path
from typing import Iterable, Type

from refactor.core import Rule, Session
from refactor.runner import expand_paths, run_files
from refactor.validate_inputs import validate_main_inputs


def get_refactors(path: Path) -> Iterable[Type[Rule]]:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore

    for name, item in vars(module).items():
        if name.startswith("_") or name.endswith("_"):
            continue

        if not isinstance(item, type):
            continue

        if issubclass(item, Rule):
            if module_name := getattr(item, "__module__", None):
                components = module_name.split(".")
                if components[0] == "refactor":
                    continue
            yield item


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("src", nargs="+", type=Path)
    parser.add_argument("-d", "--refactor-file", type=Path)
    parser.add_argument(
        "-n", "--dont-apply", action="store_false", default=True
    )

    options = parser.parse_args()
    validate_main_inputs(options)

    session = Session(list(get_refactors(options.refactor_file)))
    files = chain.from_iterable(
        expand_paths(source_dest) for source_dest in options.src
    )
    return run_files(session, files, apply=options.dont_apply, workers=1)


if __name__ == "__main__":
    exit(main())
