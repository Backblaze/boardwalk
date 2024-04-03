import pytest
from boardwalk.utils import strtobool


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("y", True),
        ("Y", True),
        ("yes", True),
        ("True", True),
        ("t", True),
        ("true", True),
        ("True", True),
        ("On", True),
        ("on", True),
        ("1", True),
        ("n", False),
        ("no", False),
        ("f", False),
        ("false", False),
        ("off", False),
        ("0", False),
        ("Off", False),
        ("No", False),
        ("N", False),
    ],
)
def test_strtobool(test_input, expected):
    assert strtobool(test_input) == expected
