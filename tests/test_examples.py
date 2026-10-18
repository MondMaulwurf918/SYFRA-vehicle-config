"""The example files double as test data, so they can never drift out of date."""

import pytest

from conftest import EXAMPLES, codes
from vehicle_config import Code, load_configurations, validate

VALID = load_configurations(EXAMPLES / "valid_configs.json")
INVALID = load_configurations(EXAMPLES / "invalid_configs.json")

# Which errors each invalid example is supposed to produce.
EXPECTED = {
    "fehlende-angaben": [Code.MISSING_FIELD, Code.MISSING_FIELD],
    "tippfehler-farbe": [Code.UNKNOWN_OPTION],
    "tippfehler-feldname": [Code.UNKNOWN_FIELD, Code.MISSING_FIELD],
    "motor-nicht-fuer-modell": [Code.NOT_AVAILABLE_FOR_MODEL],
    "sportpaket-mit-150ps": [Code.RULE_VIOLATION],
    "elektro-mit-anhaengerpaket": [Code.RULE_VIOLATION],
    "offroad-ohne-allrad": [Code.RULE_VIOLATION],
    "falscher-datentyp": [Code.WRONG_TYPE, Code.WRONG_TYPE],
    "mehrere-fehler": [Code.DUPLICATE_OPTION, Code.NOT_AVAILABLE_FOR_MODEL, Code.RULE_VIOLATION],
}


@pytest.mark.parametrize("config", VALID, ids=[c["id"] for c in VALID])
def test_valid_examples(config, catalog):
    assert validate(config, catalog) == []


@pytest.mark.parametrize("config", INVALID, ids=[c["id"] for c in INVALID])
def test_invalid_examples(config, catalog):
    assert sorted(codes(validate(config, catalog))) == sorted(EXPECTED[config["id"]])


def test_every_invalid_example_has_an_expectation():
    assert {c["id"] for c in INVALID} == set(EXPECTED)
