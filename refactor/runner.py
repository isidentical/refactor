from argparse import ArgumentParser
from functools import partial
from itertools import chain
from pathlib import Path
from typing import Iterable, List, Optional

from refactor.core import Rule, Session


def expand_paths(path: Path) -> Iterable[Path]:
    return (path for path in path.glob("**/*.py") if path.is_file())


def unbound_main(session: Session, argv: Optional[List[str]] = None) -> int:
    parser = ArgumentParser()
    parser.add_argument("src", nargs="+", type=Path)

    options = parser.parse_args()
    files = chain.from_iterable(
        expand_paths(source_dest) for source_dest in options.src
    )

    for file in files:
        if change := session.run_file(file):
            print(change.compute_diff())

    return 0


def run(rules: List[Rule]) -> int:
    session = Session(rules)
    main = partial(unbound_main, session=session)
    return main()
