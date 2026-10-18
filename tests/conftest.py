from pathlib import Path

import pytest

from vehicle_config import load_catalog

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture(scope="session")
def catalog():
    return load_catalog()


@pytest.fixture
def config():
    """A known-good configuration. Each test changes exactly one thing,
    so it is obvious which change makes it invalid."""
    return {
        "model": "aero",
        "engine": "h250",
        "color": "red",
        "rims": "r19_sport",
        "packages": ["sport", "winter"],
    }


def codes(issues):
    return [issue.code for issue in issues]
