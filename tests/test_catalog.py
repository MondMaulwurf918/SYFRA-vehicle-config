import copy
import json

import pytest

from vehicle_config import CatalogError, Code, parse_catalog, validate
from vehicle_config.catalog import DEFAULT_CATALOG_PATH


@pytest.fixture
def raw_catalog():
    return json.loads(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))


def test_shipped_catalog_is_consistent(raw_catalog):
    catalog = parse_catalog(raw_catalog)
    assert set(catalog.models) == {"aero", "terra", "volt"}
    assert len(catalog.rules) == len(raw_catalog["rules"])


def test_rule_with_typo_is_rejected(raw_catalog):
    raw_catalog["rules"][2]["then"]["any_of"] = ["r19_sprot"]
    with pytest.raises(CatalogError, match="r19_sprot"):
        parse_catalog(raw_catalog)


def test_model_offering_unknown_option_is_rejected(raw_catalog):
    raw_catalog["models"]["volt"]["available"]["color"].append("pink")
    with pytest.raises(CatalogError, match="pink"):
        parse_catalog(raw_catalog)


def test_model_without_engines_is_rejected(raw_catalog):
    raw_catalog["models"]["volt"]["available"]["engine"] = []
    with pytest.raises(CatalogError, match="keine Auswahl für engine"):
        parse_catalog(raw_catalog)


@pytest.mark.parametrize("change, expected", [
    (lambda r: r.update(type="forbids"), "type"),
    (lambda r: r.update(message=""), "message"),
    (lambda r: r["when"].update(field="seats"), "seats"),
    (lambda r: r.pop("then"), "any_of"),
])
def test_malformed_rule_is_rejected(raw_catalog, change, expected):
    change(raw_catalog["rules"][0])
    with pytest.raises(CatalogError, match=expected):
        parse_catalog(raw_catalog)


def test_duplicate_rule_id_is_rejected(raw_catalog):
    raw_catalog["rules"].append(copy.deepcopy(raw_catalog["rules"][0]))
    with pytest.raises(CatalogError, match="nicht eindeutig"):
        parse_catalog(raw_catalog)


def test_all_problems_are_listed_together(raw_catalog):
    raw_catalog["models"]["volt"]["available"]["color"].append("pink")
    raw_catalog["rules"][0]["type"] = "forbids"
    with pytest.raises(CatalogError) as exc_info:
        parse_catalog(raw_catalog)
    assert len(exc_info.value.problems) == 2


def test_new_rule_needs_no_code_change(raw_catalog, config):
    # Ein neuer Fachwunsch ("Signalrot nur mit Komfortpaket") ist nur eine Katalogänderung.
    raw_catalog["rules"].append({
        "id": "red-requires-comfort",
        "type": "requires",
        "when": {"field": "color", "any_of": ["red"]},
        "then": {"field": "packages", "any_of": ["comfort"]},
        "message": "Signalrot gibt es nur mit Komfortpaket.",
    })
    catalog = parse_catalog(raw_catalog)

    issues = validate(config, catalog)
    assert [i.code for i in issues] == [Code.RULE_VIOLATION]
    assert issues[0].rule == "red-requires-comfort"

    config["packages"].append("comfort")
    assert validate(config, catalog) == []


def test_rules_can_refer_to_the_model(raw_catalog, config):
    raw_catalog["rules"].append({
        "id": "aero-no-winter",
        "type": "excludes",
        "when": {"field": "model", "any_of": ["aero"]},
        "then": {"field": "packages", "any_of": ["winter"]},
        "message": "Winterpaket für den Aero ausverkauft.",
    })
    issues = validate(config, parse_catalog(raw_catalog))
    assert [i.rule for i in issues] == ["aero-no-winter"]
