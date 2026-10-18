"""Reading JSON files with error messages a user can act on."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class InputError(Exception):
    """A file could not be read or is not valid JSON."""


class _DuplicateKeyError(Exception):
    def __init__(self, key: str) -> None:
        self.key = key


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    # Python's json module silently keeps the last value of a duplicated key.
    # In a configuration that hides a real mistake ("color" given twice), so we
    # refuse it instead.
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(key)
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    path = Path(path)
    try:
        # utf-8-sig also accepts files saved with a BOM (e.g. by Windows Notepad).
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise InputError(f"Datei nicht gefunden: {path}") from None
    except UnicodeDecodeError:
        raise InputError(f"{path} ist keine UTF-8-Textdatei.") from None
    except OSError as exc:
        raise InputError(f"{path} kann nicht gelesen werden: {exc.strerror}") from None

    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise InputError(
            f"Ungültiges JSON in {path} (Zeile {exc.lineno}, Spalte {exc.colno}): {exc.msg}"
        ) from None
    except _DuplicateKeyError as exc:
        raise InputError(f"{path}: Schlüssel '{exc.key}' kommt in einem Objekt doppelt vor.") from None


def load_configurations(path: Path) -> list[Any]:
    """A file may hold one configuration (object) or several (list)."""
    data = read_json(path)
    return data if isinstance(data, list) else [data]
