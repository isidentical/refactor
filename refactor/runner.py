from argparse import ArgumentParser
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import nullcontext
from functools import partial
from itertools import chain
from pathlib import Path
from typing import Any, ContextManager, Iterable, List, Optional, Type

from refactor.core import Rule, Session


def expand_paths(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return None

    for path in path.glob("**/*.py"):
        if path.is_file():
            yield path


def unbound_main(session: Session, argv: Optional[List[str]] = None) -> int:
    parser = ArgumentParser()
    parser.add_argument("src", nargs="+", type=Path)
    parser.add_argument("-w", "--workers", type=int, default=4)

    options = parser.parse_args()
    files = chain.from_iterable(
        expand_paths(source_dest) for source_dest in options.src
    )

    executor: ContextManager[Any]
    if options.workers == 1:
        executor = nullcontext()
        changes = (session.run_file(file) for file in files)
    else:
        executor = ProcessPoolExecutor(max_workers=options.workers)
        futures = [executor.submit(session.run_file, file) for file in files]
        changes = (future.result() for future in as_completed(futures))

    with executor:
        for change in changes:
            if change is None:
                continue

            print(change.compute_diff())

    return 0


def run(rules: List[Type[Rule]]) -> int:
    session = Session(rules)
    main = partial(unbound_main, session=session)
    return main()
