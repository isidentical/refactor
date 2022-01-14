import importlib
import importlib.util
from argparse import ArgumentParser
from pathlib import Path
from typing import Iterable, Type

from refactor.core import Rule, Session
from refactor.runner import run_files

_POSSIBLE_FILES = [Path("refactors.py"), Path(".refactors/__init__.py")]


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
    if options.refactor_file:
        refactor_file = options.refactor_dir
        if refactor_file.exists():
            raise ValueError(
                f"Given --refactor-file '{refactor_file!s}' doesn't exist"
            )
    else:
        for refactor_file in _POSSIBLE_FILES:
            if refactor_file.exists():
                break
        else:
            raise ValueError(
                "Either provide a file using --refactor-file or ensure one of "
                "these directories exist: "
                + ", ".join(map(str, _POSSIBLE_FILES))
            )

    session = Session(list(get_refactors(refactor_file)))
    return run_files(session, options.src, apply=options.dont_apply, workers=1)


if __name__ == "__main__":
    exit(main())
