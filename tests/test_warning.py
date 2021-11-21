from types import SimpleNamespace
from unittest.mock import patch

import pytest

from refactor import _check_asserts


@pytest.mark.parametrize(
    "optimization_level, expected_warnings", [(0, 0), (1, 1), (2, 1)]
)
def test_import_warnign(optimization_level, expected_warnings):
    with pytest.warns(None) as record:
        with patch("sys.flags", SimpleNamespace(optimize=optimization_level)):
            _check_asserts()

    assert len(record) == expected_warnings
