from argparse import ArgumentParser
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import nullcontext
from functools import partial
from itertools import chain
from pathlib import Path
from typing import (
    Any,
    ContextManager,
    DefaultDict,
    Dict,
    Iterable,
    List,
    Optional,
)

from refactor.core import Session


def expand_paths(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return None

    for path in path.glob("**/*.py"):
        if path.is_file():
            yield path


def dump_stats(stats: Dict[str, int]) -> str:
    messages = []
    for status, n_files in stats.items():
        if n_files == 0:
            continue

        message = f"{n_files} file"
        if n_files > 1:
            message += "s"
        message += f" {status}"
        messages.append(message)

    return ", ".join(messages)


def run_files(
    session: Session,
    files: Iterable[Path],
    apply: bool = False,
    workers: int = 1,
) -> int:
    executor: ContextManager[Any]
    if workers == 1:
        executor = nullcontext()
        changes = (session.run_file(file) for file in files)
    else:
        executor = ProcessPoolExecutor(max_workers=workers)
        futures = [executor.submit(session.run_file, file) for file in files]
        changes = (future.result() for future in as_completed(futures))

    with executor:
        stats: DefaultDict[str, int] = defaultdict(int)
        for change in changes:
            if change is None:
                stats["left unchanged"] += 1
                continue

            stats["reformatted"] += 1
            if apply:
                print(f"reformatted {change.file!s}")
                change.apply_diff()
            else:
                print(change.compute_diff())

    print("All done!")
    if message := dump_stats(stats):
        print(message)

    return stats["reformatted"] > 0


def unbound_main(session: Session, argv: Optional[List[str]] = None) -> int:
    parser = ArgumentParser()
    parser.add_argument("src", nargs="+", type=Path)
    parser.add_argument("-a", "--apply", action="store_true", default=False)
    parser.add_argument("-w", "--workers", type=int, default=4)

    options = parser.parse_args()
    files = chain.from_iterable(
        expand_paths(source_dest) for source_dest in options.src
    )
    return run_files(
        session, files, apply=options.apply, workers=options.workers
    )


def run(*args, **kwargs) -> int:  # type: ignore
    session = Session(*args, **kwargs)
    main = partial(unbound_main, session=session)
    return main()
