from argparse import Namespace
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Generator

import pytest

from refactor.validate_inputs import _DEFAULT_FILES, validate_main_inputs


@contextmanager
def add_to_default(p: Path) -> Generator:
    try:
        _DEFAULT_FILES.append(p)
        yield
    finally:
        _DEFAULT_FILES.pop()


def test_valid_inputs():
    with NamedTemporaryFile() as f:
        options = Namespace(refactor_file=Path(f.name))
        validate_main_inputs(options)
        assert options.refactor_file == Path(f.name)

    with NamedTemporaryFile() as f:
        tmp_file = Path(f.name)
        options = Namespace(refactor_file=Path(f.name))
        with add_to_default(tmp_file):
            validate_main_inputs(options)
        assert options.refactor_file == tmp_file


def test_invalid_inputs_refactor_file_none():
    import os

    with pytest.raises(ValueError):
        os.chdir("/")
        validate_main_inputs(Namespace(refactor_file=None))


def test_invalid_inputs():
    with pytest.raises(ValueError):
        validate_main_inputs(Namespace(refactor_file=Path("/some/bad/file/somewhere.py")))
