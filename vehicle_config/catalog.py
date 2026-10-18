"""The option catalog: models, options and compatibility rules.

The catalog is data (data/catalog.json), not code. A new model, color or rule
is a JSON change. Because a typo in data would otherwise fail silently (a rule
pointing at "r19_sprot" would simply never match), the catalog is checked for
consistency when it is loaded and refused if anything does not add up.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .loader import read_json

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"

# Configuration fields whose values are catalog options.
OPTION_FIELDS = ("engine", "color", "rims", "packages")
# Fields every model must offer at least one choice for.
MANDATORY_OPTION_FIELDS = ("engine", "color", "rims")
# Rules may refer to the model as well as to options.
RULE_FIELDS = ("model",) + OPTION_FIELDS
RULE_TYPES = ("requires", "excludes")

# A configuration reduced to: field -> selected option ids.
# Single-choice fields hold one id, "packages" holds any number.
Selection = dict[str, tuple[str, ...]]


class CatalogError(Exception):
    """The catalog is malformed or internally inconsistent."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Katalog ist fehlerhaft:\n" + "\n".join(f"  - {p}" for p in problems))


@dataclass(frozen=True)
class Model:
    id: str
    name: str
    available: dict[str, frozenset[str]]  # option field -> allowed option ids


@dataclass(frozen=True)
class Condition:
    field: str
    any_of: frozenset[str]

    def matches(self, selection: Selection) -> bool:
        """True if at least one selected value of `field` is in `any_of`."""
        return any(value in self.any_of for value in selection.get(self.field, ()))


@dataclass(frozen=True)
class Rule:
    """`requires`: if `when` matches, `then` must match.
    `excludes`: if `when` matches, `then` must not match."""

    id: str
    type: str
    when: Condition
    then: Condition
    message: str

    def is_violated(self, selection: Selection) -> bool:
        if not self.when.matches(selection):
            return False
        if self.type == "requires":
            return not self.then.matches(selection)
        return self.then.matches(selection)


@dataclass(frozen=True)
class Catalog:
    models: dict[str, Model]
    options: dict[str, dict[str, str]]  # field -> option id -> display name
    rules: tuple[Rule, ...]

    def ids(self, field: str) -> Iterable[str]:
        """All valid ids for a field ("model" or an option field)."""
        return self.models.keys() if field == "model" else self.options[field].keys()

    def name(self, field: str, option_id: str) -> str:
        if field == "model":
            return self.models[option_id].name
        return self.options[field][option_id]


def load_catalog(path: Path = DEFAULT_CATALOG_PATH) -> Catalog:
    return parse_catalog(read_json(path))


def parse_catalog(data: Any) -> Catalog:
    """Build a Catalog from parsed JSON. Collects every problem, then raises once."""
    if not isinstance(data, dict):
        raise CatalogError(["Der Katalog muss ein JSON-Objekt sein."])

    problems: list[str] = []
    options = _parse_options(data.get("options"), problems)
    models = _parse_models(data.get("models"), options, problems)
    known_ids = {"model": set(models), **{f: set(options[f]) for f in OPTION_FIELDS}}
    rules = _parse_rules(data.get("rules", []), known_ids, problems)

    if problems:
        raise CatalogError(problems)
    return Catalog(models=models, options=options, rules=tuple(rules))


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _display_name(entry: Any, fallback: str) -> str:
    if isinstance(entry, dict) and isinstance(entry.get("name"), str):
        return entry["name"]
    return fallback


def _parse_options(raw: Any, problems: list[str]) -> dict[str, dict[str, str]]:
    raw = raw if isinstance(raw, dict) else {}
    options: dict[str, dict[str, str]] = {}
    for field in OPTION_FIELDS:
        entries = raw.get(field)
        if not isinstance(entries, dict) or not entries:
            problems.append(f"options.{field} fehlt oder ist leer.")
            entries = {}
        options[field] = {oid: _display_name(entry, oid) for oid, entry in entries.items()}
    return options


def _parse_models(
    raw: Any, options: dict[str, dict[str, str]], problems: list[str]
) -> dict[str, Model]:
    if not isinstance(raw, dict) or not raw:
        problems.append("models fehlt oder ist leer.")
        return {}

    models: dict[str, Model] = {}
    for model_id, entry in raw.items():
        where = f"Modell '{model_id}'"
        available_raw = entry.get("available") if isinstance(entry, dict) else None
        if not isinstance(available_raw, dict):
            problems.append(f"{where}: 'available' fehlt.")
            available_raw = {}

        available: dict[str, frozenset[str]] = {}
        for field in OPTION_FIELDS:
            ids = available_raw.get(field, [])
            if not _is_str_list(ids):
                problems.append(f"{where}: available.{field} muss eine Liste von Texten sein.")
                ids = []
            for option_id in ids:
                if option_id not in options[field]:
                    problems.append(f"{where}: {field} '{option_id}' gibt es nicht in options.{field}.")
            if field in MANDATORY_OPTION_FIELDS and not ids:
                problems.append(f"{where}: bietet keine Auswahl für {field} an.")
            available[field] = frozenset(ids)

        models[model_id] = Model(model_id, _display_name(entry, model_id), available)
    return models


def _parse_condition(
    raw: Any, where: str, known_ids: dict[str, set[str]], problems: list[str]
) -> Condition | None:
    if not (
        isinstance(raw, dict)
        and isinstance(raw.get("field"), str)
        and _is_str_list(raw.get("any_of"))
        and raw["any_of"]
    ):
        problems.append(f"{where}: braucht 'field' (Text) und 'any_of' (nicht-leere Liste von Texten).")
        return None

    field = raw["field"]
    if field not in known_ids:
        problems.append(f"{where}: unbekanntes Feld '{field}' (erlaubt: {', '.join(RULE_FIELDS)}).")
        return None
    for value in raw["any_of"]:
        if value not in known_ids[field]:
            problems.append(f"{where}: '{value}' gibt es nicht als {field}.")
    return Condition(field, frozenset(raw["any_of"]))


def _parse_rules(raw: Any, known_ids: dict[str, set[str]], problems: list[str]) -> list[Rule]:
    if not isinstance(raw, list):
        problems.append("rules muss eine Liste sein.")
        return []

    rules: list[Rule] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            problems.append(f"rules[{index}] muss ein Objekt sein.")
            continue

        rule_id = entry.get("id")
        where = f"Regel '{rule_id}'" if isinstance(rule_id, str) else f"rules[{index}]"
        ok = True

        if not isinstance(rule_id, str) or not rule_id:
            problems.append(f"{where}: 'id' fehlt.")
            ok = False
        elif rule_id in seen_ids:
            problems.append(f"{where}: id ist nicht eindeutig.")
            ok = False
        else:
            seen_ids.add(rule_id)

        if entry.get("type") not in RULE_TYPES:
            problems.append(f"{where}: 'type' muss einer von {', '.join(RULE_TYPES)} sein.")
            ok = False
        if not isinstance(entry.get("message"), str) or not entry["message"].strip():
            problems.append(f"{where}: 'message' fehlt.")
            ok = False

        when = _parse_condition(entry.get("when"), f"{where}.when", known_ids, problems)
        then = _parse_condition(entry.get("then"), f"{where}.then", known_ids, problems)
        if ok and when and then:
            rules.append(Rule(rule_id, entry["type"], when, then, entry["message"]))
    return rules
