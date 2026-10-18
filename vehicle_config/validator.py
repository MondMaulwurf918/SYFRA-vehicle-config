"""Validate one vehicle configuration against the catalog.

Checks run in four stages:

  1. structure     required fields present, values have the right JSON type
  2. existence     every selected option exists in the catalog
  3. availability  every option is offered for the chosen model
  4. rules         compatibility rules from the catalog

All problems are collected (no fail-fast), so the user sees everything at once.
A field that fails an earlier stage is left out of the later ones: one mistake
gives one message, not a cascade of follow-up errors.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from .catalog import OPTION_FIELDS, Catalog, Selection

REQUIRED_FIELDS = ("model", "engine", "color", "rims")
OPTIONAL_FIELDS = ("id", "packages")
KNOWN_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

LABELS = {
    "model": "Modell",
    "engine": "Motor",
    "color": "Farbe",
    "rims": "Felgen",
    "packages": "Ausstattungspaket",
    "id": "ID",
}


class Code(str, Enum):
    """Stable, machine-readable error kinds. Tests and other programs check
    these instead of the German message text."""

    NOT_AN_OBJECT = "NOT_AN_OBJECT"
    MISSING_FIELD = "MISSING_FIELD"
    WRONG_TYPE = "WRONG_TYPE"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    UNKNOWN_OPTION = "UNKNOWN_OPTION"
    DUPLICATE_OPTION = "DUPLICATE_OPTION"
    NOT_AVAILABLE_FOR_MODEL = "NOT_AVAILABLE_FOR_MODEL"
    RULE_VIOLATION = "RULE_VIOLATION"


@dataclass(frozen=True)
class Issue:
    code: Code
    message: str
    field: str | None = None
    rule: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "field": self.field, "rule": self.rule, "message": self.message}


def validate(config: Any, catalog: Catalog) -> list[Issue]:
    """Return every problem in `config`. An empty list means the configuration is valid."""
    if not isinstance(config, dict):
        return [Issue(Code.NOT_AN_OBJECT, f"Eine Konfiguration muss ein JSON-Objekt sein, gefunden: {_json_type(config)}.")]

    issues: list[Issue] = []
    selection = _check_structure(config, issues)
    _check_options_exist(selection, catalog, issues)
    _check_model_availability(selection, catalog, issues)
    _check_rules(selection, catalog, issues)
    return issues


# --- stage 1 -----------------------------------------------------------------

def _check_structure(config: dict[str, Any], issues: list[Issue]) -> Selection:
    """Check fields and types; return the well-formed fields as a Selection."""
    selection: Selection = {}

    for key in config:
        if key not in KNOWN_FIELDS:
            issues.append(Issue(Code.UNKNOWN_FIELD, f"Unbekanntes Feld '{key}'.{_hint(key, KNOWN_FIELDS)}", field=key))

    for field in REQUIRED_FIELDS:
        value = config.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            issues.append(Issue(Code.MISSING_FIELD, f"Pflichtangabe fehlt: {LABELS[field]} ('{field}').", field=field))
        elif not isinstance(value, str):
            issues.append(_wrong_type(field, "ein Text", value))
        else:
            selection[field] = (value,)

    config_id = config.get("id")
    if "id" in config and (isinstance(config_id, bool) or not isinstance(config_id, (str, int))):
        issues.append(_wrong_type("id", "ein Text oder eine Zahl", config_id))

    packages = config.get("packages", [])  # optional, no packages is fine
    if not isinstance(packages, list):
        issues.append(_wrong_type("packages", "eine Liste", packages))
    elif any(not isinstance(p, str) for p in packages):
        issues.append(Issue(Code.WRONG_TYPE, "Jedes Ausstattungspaket in 'packages' muss ein Text sein.", field="packages"))
    else:
        for duplicate in sorted({p for p in packages if packages.count(p) > 1}):
            issues.append(Issue(Code.DUPLICATE_OPTION, f"Ausstattungspaket '{duplicate}' ist mehrfach angegeben.", field="packages"))
        selection["packages"] = tuple(dict.fromkeys(packages))  # de-duplicated, order kept

    return selection


# --- stage 2 -----------------------------------------------------------------

def _check_options_exist(selection: Selection, catalog: Catalog, issues: list[Issue]) -> None:
    for field in list(selection):
        known = list(catalog.ids(field))
        unknown = [value for value in selection[field] if value not in known]
        for value in unknown:
            issues.append(Issue(Code.UNKNOWN_OPTION, f"{LABELS[field]} '{value}' gibt es nicht.{_hint(value, known)}", field=field))
        if unknown:
            del selection[field]


# --- stage 3 -----------------------------------------------------------------

def _check_model_availability(selection: Selection, catalog: Catalog, issues: list[Issue]) -> None:
    if "model" not in selection:
        return  # without a valid model there is nothing to check against
    model = catalog.models[selection["model"][0]]

    for field in OPTION_FIELDS:
        allowed = model.available[field]
        not_offered = [value for value in selection.get(field, ()) if value not in allowed]
        for value in not_offered:
            offered = ", ".join(sorted(allowed)) or "keine"
            issues.append(Issue(
                Code.NOT_AVAILABLE_FOR_MODEL,
                f"{LABELS[field]} '{catalog.name(field, value)}' ({value}) gibt es nicht für den {model.name}. "
                f"Verfügbar: {offered}.",
                field=field,
            ))
        if not_offered:
            del selection[field]


# --- stage 4 -----------------------------------------------------------------

def _check_rules(selection: Selection, catalog: Catalog, issues: list[Issue]) -> None:
    for rule in catalog.rules:
        if rule.when.field not in selection or rule.then.field not in selection:
            continue  # a field involved already has an error, skip to avoid follow-up errors
        if rule.is_violated(selection):
            fields = list(dict.fromkeys([rule.when.field, rule.then.field]))
            issues.append(Issue(Code.RULE_VIOLATION, rule.message, field=", ".join(fields), rule=rule.id))


# --- helpers -----------------------------------------------------------------

def _hint(value: str, candidates: Iterable[str]) -> str:
    """A 'did you mean' suggestion for typos, otherwise the list of valid values."""
    candidates = sorted(candidates)
    close = difflib.get_close_matches(value, candidates, n=1, cutoff=0.6)
    if close:
        return f" Meinten Sie '{close[0]}'?"
    return f" Gültig sind: {', '.join(candidates)}."


def _wrong_type(field: str, expected: str, value: Any) -> Issue:
    return Issue(
        Code.WRONG_TYPE,
        f"{LABELS[field]} ('{field}') muss {expected} sein, gefunden: {_json_type(value)}.",
        field=field,
    )


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):  # before int: bool is a subclass of int in Python
        return "Wahrheitswert"
    if isinstance(value, (int, float)):
        return "Zahl"
    if isinstance(value, str):
        return "Text"
    if isinstance(value, list):
        return "Liste"
    return "Objekt"
