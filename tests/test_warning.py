from __future__ import annotations

import warnings
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from refactor import _check_asserts


@pytest.mark.parametrize("optimization_level, expected_warnings", [(1, 1), (2, 1)])
def test_import_warning(optimization_level, expected_warnings):
    with pytest.warns() as record:
        with patch("sys.flags", SimpleNamespace(optimize=optimization_level)):
            _check_asserts()

    assert len(record) == expected_warnings


@pytest.mark.parametrize("optimization_level", [0])
def test_import_no_warning(optimization_level):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with patch("sys.flags", SimpleNamespace(optimize=optimization_level)):
            _check_asserts()
