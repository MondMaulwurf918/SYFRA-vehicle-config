# Syfra Fahrzeugkonfigurator – Konfigurationsprüfung

Kleines Python-Programm, das Fahrzeugkonfigurationen aus JSON-Dateien einliest und gegen einen Optionskatalog prüft:

- **Vollständigkeit:** Modell, Motor, Farbe und Felgen müssen angegeben sein (Ausstattungspakete sind optional).
- **Existenz:** Jede gewählte Option muss im Katalog existieren – bei Tippfehlern mit Vorschlag („Meinten Sie 'black'?“).
- **Verfügbarkeit:** Die Option muss für das gewählte Modell angeboten werden.
- **Kombinationen:** Regeln wie „Sportpaket nicht mit dem 150-PS-Benziner“ oder „Offroad-Paket nur mit Allrad“.

Jeder Fehler wird mit Feld, verständlicher Meldung und einem festen Fehlercode ausgegeben.

## Starten

Voraussetzung: Python 3.10 oder neuer. Das Programm selbst braucht nur die Standardbibliothek, für die Tests wird `pytest` benötigt.

```bash
git clone https://github.com/MondMaulwurf918/SYFRA-vehicle-config.git
cd SYFRA-vehicle-config


# Beispiele prüfen
python -m vehicle_config examples/valid_configs.json
python -m vehicle_config examples/invalid_configs.json

# Ausgabe als JSON (z. B. für ein Frontend)
python -m vehicle_config examples/invalid_configs.json --json

# Tests
pip install -r requirements-dev.txt
python -m pytest
```

Beispielausgabe:

```text
examples/invalid_configs.json
  [FEHLER] tippfehler-farbe
           - color: Farbe 'blak' gibt es nicht. Meinten Sie 'black'?  [UNKNOWN_OPTION]
  [FEHLER] sportpaket-mit-150ps
           - engine, packages: Das Sportpaket ist mit dem 150-PS-Benziner nicht kombinierbar.  [RULE_VIOLATION]
  ...
Ergebnis: 9 geprüft, 0 gültig, 9 ungültig.
```

**Exit-Codes:** `0` alles gültig · `1` mindestens eine Konfiguration ungültig · `2` Datei oder Katalog nicht lesbar.
So lässt sich das Programm auch in Skripten oder einer CI-Pipeline verwenden.

## Eingabeformat

Eine Datei enthält entweder **eine** Konfiguration (Objekt) oder **mehrere** (Liste):

```json
{
  "id": "kunde-4711",
  "model": "terra",
  "engine": "h250",
  "color": "blue",
  "rims": "r19_sport",
  "packages": ["sport", "winter"]
}
```

`id` ist optional und dient nur zur Anzeige. Alle gültigen Werte stehen in [`data/catalog.json`](data/catalog.json).

## Aufbau

```text
data/catalog.json           Modelle, Optionen und Kombinationsregeln (Daten, kein Code)
vehicle_config/
  loader.py                 JSON einlesen, verständliche Fehler bei kaputten Dateien
  catalog.py                Katalog laden und auf Widerspruchsfreiheit prüfen, Regel-Logik
  validator.py              Prüfung einer Konfiguration in vier Stufen
  cli.py                    Kommandozeile, Textausgabe, JSON-Ausgabe, Exit-Codes
examples/                   gültige und ungültige Beispielkonfigurationen
tests/                      73 pytest-Tests
```

## Entscheidungen

**1. Katalog und Regeln sind Daten, kein Code.**
Ein Konfigurator ändert sich ständig: neue Modelle, neue Farben, neue Einschränkungen. Wenn diese Dinge in JSON stehen, ist eine neue Regel eine Datenänderung und kein Code-Deployment, und auch jemand ohne Python-Kenntnisse kann sie lesen. Der Test `test_new_rule_needs_no_code_change` zeigt das: eine neue Regel wird nur im Katalog ergänzt und sofort durchgesetzt.

**2. Der Katalog wird beim Laden selbst geprüft.**
Der Nachteil von Regeln als Daten: Ein Tippfehler in einer Regel (`"r19_sprot"`) würde still nie greifen. Deshalb prüft `catalog.py` beim Laden, ob jede Regel und jedes Modell nur auf existierende Optionen verweist, ob Regel-IDs eindeutig sind usw. Ein fehlerhafter Katalog wird mit allen Problemen auf einmal abgelehnt, statt falsche Ergebnisse zu liefern.

**3. Zwei Regeltypen reichen: `requires` und `excludes`.**
„Wenn A gewählt ist, muss B / darf B nicht gewählt sein.“ Damit lassen sich alle Beispiele aus der Aufgabe ausdrücken. Intern wird jedes Feld als Menge von gewählten Werten behandelt (`engine` → `{"p150"}`, `packages` → `{"sport", "winter"}`). Dadurch funktioniert dieselbe Regel-Logik für Einzel- und Mehrfachauswahl, ohne Sonderfälle. Bewusst *kein* eigener Ausdrucks-Parser – das wäre für die Aufgabe übertrieben und schwerer zu prüfen.

**4. Vier Stufen, alle Fehler auf einmal, keine Folgefehler.**
Struktur → Existenz → Verfügbarkeit fürs Modell → Regeln. Der Nutzer bekommt alle Probleme in einem Durchlauf statt eines nach dem anderen. Ein Feld, das schon in einer früheren Stufe fehlerhaft ist, wird aus den späteren herausgenommen. Beispiel: Bei `"rims": "r19_sprot"` mit Sportpaket kommt nur der Tippfehler, nicht zusätzlich „Sportpaket erfordert Sportfelgen“. Ein Fehler, eine Meldung.

**5. Fehlercodes für Programme, deutsche Meldungen für Menschen.**
Jeder Fehler hat einen festen Code (`UNKNOWN_OPTION`, `RULE_VIOLATION`, …), das Feld und bei Regelverstößen die Regel-ID. Die Tests prüfen die Codes, nicht den Text – so kann man Meldungen umformulieren oder übersetzen, ohne Tests anzupassen. Die `--json`-Ausgabe macht das Ergebnis direkt für ein Frontend nutzbar.

**6. Strenge Eingabeprüfung.**
Unbekannte Felder (`"colour"`), falsche Typen (`"engine": 250`), doppelte Pakete und doppelte JSON-Schlüssel werden gemeldet statt ignoriert. Pythons `json`-Modul würde bei `{"color": "red", "color": "blue"}` still den letzten Wert nehmen – bei einer Bestellung ist das ein echter Fehler, den man sehen will.

**7. Nur Standardbibliothek.**
Mit Pydantic oder JSON Schema wäre die Strukturprüfung kürzer, aber die interessanten Teile (Verfügbarkeit, Kombinationsregeln, gute Meldungen) müsste man trotzdem selbst schreiben. Ohne Abhängigkeiten läuft das Programm überall sofort, und jede Zeile ist nachvollziehbar.

**8. Tests.**
Die meisten Validator-Tests starten von einer gültigen Basiskonfiguration und ändern genau *eine* Sache – so sieht man sofort, was einen Fehler auslöst. Die Beispieldateien sind gleichzeitig Testdaten, damit sie nie veralten. Dazu kommen Tests für den Katalog-Check und die Kommandozeile (Exit-Codes, kaputtes JSON, BOM, doppelte Schlüssel).

## Grenzen und mögliche Erweiterungen

- Regeln können sich nur auf konkrete Options-IDs beziehen, nicht auf Eigenschaften („alle Elektromotoren“). Bei vielen Motoren wären Attribute im Katalog (`"drive": "awd"`) und Bedingungen darauf der nächste Schritt.
- Bedingungen mit mehreren Teilen („wenn Terra *und* Diesel, dann …“) gibt es noch nicht; `when` könnte dafür eine Liste von Bedingungen werden.
- Preise, Lieferzeiten oder Länderspezifika sind nicht abgebildet.

### Neue Regel hinzufügen

In `data/catalog.json` unter `rules` ergänzen – fertig:

```json
{
  "id": "red-requires-comfort",
  "type": "requires",
  "when": { "field": "color", "any_of": ["red"] },
  "then": { "field": "packages", "any_of": ["comfort"] },
  "message": "Signalrot gibt es nur mit Komfortpaket."
}
```
