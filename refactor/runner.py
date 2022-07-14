import os
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

_DEFAULT_WORKERS = object()


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


def _determine_workers(workers: Any, debug_mode: bool = False) -> int:
    if isinstance(workers, int):
        return workers
    elif workers is _DEFAULT_WORKERS:
        cpu_count = os.cpu_count()
        if debug_mode or not cpu_count:
            return 1
        else:
            return cpu_count
    else:
        raise ValueError(f"Invalid number of workers: {workers!r}")


def run_files(
    session: Session,
    files: Iterable[Path],
    apply: bool = False,
    workers: Any = _DEFAULT_WORKERS,
) -> int:
    workers = _determine_workers(workers, session.config.debug_mode)

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
    parser.add_argument("-w", "--workers", type=int, default=_DEFAULT_WORKERS)
    parser.add_argument(
        "-d", "--enable-debug-mode", action="store_true", default=False
    )

    options = parser.parse_args()
    session.config.debug_mode = options.enable_debug_mode
    files = chain.from_iterable(
        expand_paths(source_dest) for source_dest in options.src
    )
    return run_files(
        session,
        files,
        apply=options.apply,
        workers=options.workers,
    )


def run(*args, **kwargs) -> int:  # type: ignore
    session = Session(*args, **kwargs)
    main = partial(unbound_main, session=session)
    return main()
