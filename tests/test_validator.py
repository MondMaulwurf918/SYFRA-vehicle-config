import pytest

from conftest import codes
from vehicle_config import Code, validate


def test_base_config_is_valid(config, catalog):
    assert validate(config, catalog) == []


def test_packages_are_optional(config, catalog):
    del config["packages"]
    config["rims"] = "r18_comfort"
    assert validate(config, catalog) == []


# --- structure ---------------------------------------------------------------

@pytest.mark.parametrize("field", ["model", "engine", "color", "rims"])
def test_missing_required_field(config, catalog, field):
    del config[field]
    issues = validate(config, catalog)
    assert codes(issues) == [Code.MISSING_FIELD]
    assert issues[0].field == field


@pytest.mark.parametrize("value", ["", "   ", None])
def test_empty_value_counts_as_missing(config, catalog, value):
    config["color"] = value
    assert codes(validate(config, catalog)) == [Code.MISSING_FIELD]


def test_wrong_type_for_option(config, catalog):
    config["engine"] = 250
    issues = validate(config, catalog)
    assert codes(issues) == [Code.WRONG_TYPE]
    assert "Zahl" in issues[0].message


@pytest.mark.parametrize("packages", ["sport", {"sport": True}, ["sport", 1]])
def test_packages_must_be_list_of_strings(config, catalog, packages):
    config["packages"] = packages
    assert codes(validate(config, catalog)) == [Code.WRONG_TYPE]


def test_unknown_field_suggests_correct_name(config, catalog):
    config["colour"] = config.pop("color")
    issues = validate(config, catalog)
    assert sorted(codes(issues)) == sorted([Code.UNKNOWN_FIELD, Code.MISSING_FIELD])
    unknown = next(i for i in issues if i.code == Code.UNKNOWN_FIELD)
    assert "Meinten Sie 'color'?" in unknown.message


def test_duplicate_package(config, catalog):
    config["packages"] = ["sport", "winter", "sport"]
    issues = validate(config, catalog)
    assert codes(issues) == [Code.DUPLICATE_OPTION]
    assert "sport" in issues[0].message


@pytest.mark.parametrize("not_a_dict", [[], "aero", 42, None])
def test_config_must_be_object(catalog, not_a_dict):
    assert codes(validate(not_a_dict, catalog)) == [Code.NOT_AN_OBJECT]


# --- existence ---------------------------------------------------------------

def test_unknown_option_suggests_close_match(config, catalog):
    config["color"] = "blak"
    issues = validate(config, catalog)
    assert codes(issues) == [Code.UNKNOWN_OPTION]
    assert "Meinten Sie 'black'?" in issues[0].message


def test_unknown_option_without_close_match_lists_valid_values(config, catalog):
    config["engine"] = "v12"
    issues = validate(config, catalog)
    assert codes(issues) == [Code.UNKNOWN_OPTION]
    assert "Gültig sind:" in issues[0].message and "h250" in issues[0].message


def test_unknown_package(config, catalog):
    config["packages"] = ["sport", "massage"]
    assert codes(validate(config, catalog)) == [Code.UNKNOWN_OPTION]


def test_unknown_model_does_not_cause_availability_errors(config, catalog):
    config["model"] = "roadster"
    assert codes(validate(config, catalog)) == [Code.UNKNOWN_OPTION]


# --- availability per model --------------------------------------------------

def test_engine_not_offered_for_model(config, catalog):
    config.update(model="volt", engine="d200", rims="r17_aero", packages=[])
    issues = validate(config, catalog)
    assert codes(issues) == [Code.NOT_AVAILABLE_FOR_MODEL]
    assert issues[0].field == "engine"
    assert "Syfra Volt" in issues[0].message and "e220" in issues[0].message


def test_package_not_offered_for_model(config, catalog):
    config["packages"] = ["offroad"]  # Offroad gibt es nur für den Terra
    issues = validate(config, catalog)
    assert codes(issues) == [Code.NOT_AVAILABLE_FOR_MODEL]
    assert issues[0].field == "packages"


# --- compatibility rules -----------------------------------------------------

@pytest.mark.parametrize("changes, rule_id", [
    ({"engine": "p150"}, "sport-not-with-p150"),
    ({"engine": "e220", "packages": ["towing"], "rims": "r18_comfort"}, "towing-not-with-ev"),
    ({"rims": "r18_comfort"}, "sport-requires-sport-rims"),
    ({"model": "terra", "engine": "e220", "color": "white", "rims": "r20_offroad",
      "packages": ["offroad"]}, "offroad-requires-awd"),
    ({"model": "terra", "engine": "d200", "color": "white", "rims": "r19_sport",
      "packages": ["offroad"]}, "offroad-requires-offroad-rims"),
    ({"model": "terra", "engine": "d200", "color": "white", "rims": "r20_offroad",
      "packages": ["offroad", "sport"]}, "sport-requires-sport-rims"),
    ({"model": "terra", "engine": "d200", "color": "matte_green", "rims": "r19_sport",
      "packages": ["sport"]}, "matte-green-only-with-offroad"),
])
def test_rule_violation(config, catalog, changes, rule_id):
    config.update(changes)
    issues = validate(config, catalog)
    assert Code.RULE_VIOLATION in codes(issues)
    assert rule_id in [i.rule for i in issues]


def test_offroad_and_sport_exclude_each_other(config, catalog):
    config.update(model="terra", engine="d200", color="white", rims="r20_offroad",
                  packages=["offroad", "sport"])
    rules = [i.rule for i in validate(config, catalog)]
    assert "offroad-excludes-sport" in rules


def test_rule_message_comes_from_catalog(config, catalog):
    config["engine"] = "p150"
    issue = validate(config, catalog)[0]
    assert issue.message == "Das Sportpaket ist mit dem 150-PS-Benziner nicht kombinierbar."
    assert issue.field == "engine, packages"


# --- reporting behaviour -----------------------------------------------------

def test_all_problems_are_reported_at_once(config, catalog):
    config.update(engine="p150", color="matte_green", packages=["sport", "sport"])
    assert sorted(codes(validate(config, catalog))) == sorted([
        Code.DUPLICATE_OPTION,          # sport doppelt
        Code.NOT_AVAILABLE_FOR_MODEL,   # Mattgrün nicht für Aero
        Code.RULE_VIOLATION,            # Sportpaket + 150 PS
    ])


def test_broken_field_causes_no_follow_up_errors(config, catalog):
    # Felgen-Tippfehler: es soll nur der Tippfehler gemeldet werden,
    # nicht zusätzlich "Sportpaket erfordert Sportfelgen".
    config["rims"] = "r19_sprot"
    issues = validate(config, catalog)
    assert codes(issues) == [Code.UNKNOWN_OPTION]
    assert "Meinten Sie 'r19_sport'?" in issues[0].message
