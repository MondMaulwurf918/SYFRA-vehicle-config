"""Command line entry point: python -m vehicle_config FILE [FILE ...]

Exit codes:
  0  all configurations are valid
  1  at least one configuration is invalid
  2  a file or the catalog could not be read (input problem, not a config problem)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .catalog import DEFAULT_CATALOG_PATH, CatalogError, load_catalog
from .loader import InputError, load_configurations
from .validator import Issue, validate

EXIT_OK, EXIT_INVALID, EXIT_ERROR = 0, 1, 2


@dataclass
class Report:
    file: str
    label: str
    issues: list[Issue]

    @property
    def valid(self) -> bool:
        return not self.issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m vehicle_config",
        description="Prüft Fahrzeugkonfigurationen (JSON) gegen den Optionskatalog.",
    )
    parser.add_argument("files", nargs="+", type=Path,
                        help="JSON-Datei mit einer Konfiguration (Objekt) oder mehreren (Liste)")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_PATH,
                        help="anderer Katalog (Standard: data/catalog.json)")
    parser.add_argument("--json", action="store_true",
                        help="Ergebnis maschinenlesbar als JSON ausgeben")
    args = parser.parse_args(argv)

    try:
        catalog = load_catalog(args.catalog)
    except (InputError, CatalogError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return EXIT_ERROR

    reports: list[Report] = []
    file_errors: list[str] = []
    for path in args.files:
        try:
            configs = load_configurations(path)
        except InputError as exc:
            file_errors.append(str(exc))
            continue
        for index, config in enumerate(configs, start=1):
            reports.append(Report(str(path), _label(config, index), validate(config, catalog)))

    if args.json:
        _print_json(reports, file_errors)
    else:
        _print_text(reports, file_errors)

    if file_errors:
        return EXIT_ERROR
    return EXIT_OK if all(r.valid for r in reports) else EXIT_INVALID


def _label(config: Any, index: int) -> str:
    """Use the configuration's own id if it has one, else its position in the file."""
    if isinstance(config, dict):
        config_id = config.get("id")
        if isinstance(config_id, (str, int)) and not isinstance(config_id, bool):
            return str(config_id)
    return f"Konfiguration {index}"


def _print_text(reports: list[Report], file_errors: list[str]) -> None:
    current_file = None
    for report in reports:
        if report.file != current_file:
            current_file = report.file
            print(f"\n{current_file}")
        if report.valid:
            print(f"  [OK]     {report.label}")
            continue
        print(f"  [FEHLER] {report.label}")
        for issue in report.issues:
            where = f"{issue.field}: " if issue.field else ""
            print(f"           - {where}{issue.message}  [{issue.code.value}]")

    for error in file_errors:
        print(f"Fehler: {error}", file=sys.stderr)

    valid = sum(r.valid for r in reports)
    summary = f"\nErgebnis: {len(reports)} geprüft, {valid} gültig, {len(reports) - valid} ungültig"
    if file_errors:
        summary += f", {len(file_errors)} Datei(en) nicht lesbar"
    print(summary + ".")


def _print_json(reports: list[Report], file_errors: list[str]) -> None:
    payload = {
        "results": [
            {"file": r.file, "id": r.label, "valid": r.valid, "issues": [i.to_dict() for i in r.issues]}
            for r in reports
        ],
        "file_errors": file_errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
