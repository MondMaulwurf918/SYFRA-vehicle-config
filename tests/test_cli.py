import json
import subprocess
import sys
from pathlib import Path

from conftest import EXAMPLES
from vehicle_config.cli import EXIT_ERROR, EXIT_INVALID, EXIT_OK, main


def run(capsys, *args):
    code = main([str(a) for a in args])
    out, err = capsys.readouterr()
    return code, out, err


def test_valid_file_exits_0(capsys):
    code, out, _ = run(capsys, EXAMPLES / "valid_configs.json")
    assert code == EXIT_OK
    assert "5 geprüft, 5 gültig, 0 ungültig" in out


def test_single_object_file(capsys):
    code, out, _ = run(capsys, EXAMPLES / "single_config.json")
    assert code == EXIT_OK
    assert "[OK]     kunde-4711" in out


def test_invalid_file_exits_1_and_explains(capsys):
    code, out, _ = run(capsys, EXAMPLES / "invalid_configs.json")
    assert code == EXIT_INVALID
    assert "[FEHLER] tippfehler-farbe" in out
    assert "Meinten Sie 'black'?" in out
    assert "[RULE_VIOLATION]" in out


def test_json_output(capsys):
    code, out, _ = run(capsys, EXAMPLES / "invalid_configs.json", "--json")
    assert code == EXIT_INVALID
    results = json.loads(out)["results"]
    first = results[0]
    assert first["id"] == "fehlende-angaben" and first["valid"] is False
    assert {i["code"] for i in first["issues"]} == {"MISSING_FIELD"}


def test_missing_file_exits_2(capsys, tmp_path):
    code, _, err = run(capsys, tmp_path / "gibts-nicht.json")
    assert code == EXIT_ERROR
    assert "Datei nicht gefunden" in err


def test_broken_json_reports_position(capsys, tmp_path):
    broken = tmp_path / "kaputt.json"
    broken.write_text('{\n  "model": "aero",\n  "engine": "h250"\n  "color": "red"\n}', encoding="utf-8")
    code, _, err = run(capsys, broken)
    assert code == EXIT_ERROR
    assert "Zeile 4" in err


def test_duplicate_key_is_rejected(capsys, tmp_path):
    path = tmp_path / "doppelt.json"
    path.write_text('{"model": "aero", "color": "red", "color": "blue"}', encoding="utf-8")
    code, _, err = run(capsys, path)
    assert code == EXIT_ERROR
    assert "'color' kommt in einem Objekt doppelt vor" in err


def test_file_with_bom_is_accepted(capsys, tmp_path):
    path = tmp_path / "bom.json"
    path.write_text((EXAMPLES / "single_config.json").read_text(encoding="utf-8"), encoding="utf-8-sig")
    code, _, _ = run(capsys, path)
    assert code == EXIT_OK


def test_broken_catalog_exits_2(capsys, tmp_path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text('{"options": {}, "models": {}}', encoding="utf-8")
    code, _, err = run(capsys, EXAMPLES / "valid_configs.json", "--catalog", catalog)
    assert code == EXIT_ERROR
    assert "Katalog ist fehlerhaft" in err


def test_runs_as_module():
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "vehicle_config", "examples/valid_configs.json"],
        cwd=root, capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
