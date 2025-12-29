# Testing

Celem testów w tym repozytorium jest utrzymanie stabilnego **core pipeline’u OCR**
podczas refaktoru oraz wdrażania UI (Stage 2 / Stage 3).

Testy **nie automatyzują Playwright / Gemini UI** — pilnują:
- kontraktów modułów,
- poprawnej orkiestracji,
- obsługi błędów i rollbacków.

Dzięki temu UI może być rozwijane i naprawiane bez ryzyka rozjechania logiki backendowej.

---

## Jak uruchomić testy (ubuntuovh)

Testy uruchamiamy **z venv produkcyjnego repo `ocr-gemini`**:

```bash
cd ~/projects/ocr-gemini-pipeline
/home/tomaasz/projects/ocr-gemini/.venv/bin/python -m pytest -q
```

---

## Co testujemy

### Unit tests (szybkie, deterministyczne)

- `tests/test_files.py`
  - discovery plików (`iter_files`)
  - rekurencja, sortowanie, limit
  - hash plików (`sha256_file`)

- `tests/test_output.py`
  - zapis artefaktów przez `write_outputs`
  - test oparty o kontrakt zwracany przez `OutputPaths`
  - brak zgadywania ścieżek wyjściowych

- `tests/test_metrics.py`
  - `DocumentMetrics`
  - `finish()`, duration, error_reason
  - serializacja JSON
  - format string (`__str__`)

---

### Smoke tests (orkiestracja bez DB / UI)

- `tests/test_pipeline_smoke.py`
  - przepływ **success** dla Stage 1.3
  - monkeypatch: pliki, DB, output
  - brak Postgresa i brak filesystemu

- `tests/test_pipeline_error_path.py`
  - przepływ **error**
  - rollback transakcji
  - best-effort zapis meta błędu
  - test zakłada propagację wyjątku (zgodnie z obecną implementacją)

---

## Czego nie testujemy (świadomie)

- UI automation (Playwright + Gemini Web UI)
  - testy UI będą flaky
  - dodane dopiero po ustabilizowaniu interfejsu `ui/*`

- Integracji z prawdziwym PostgreSQL
  - ewentualnie w przyszłości jako testy integracyjne
  - uruchamiane osobno, nie w standardowym `pytest`

---

## Zasady

- Testy muszą być:
  - szybkie
  - deterministyczne
  - bez sieci, bez DB, bez UI

- Zmiana kontraktu (argumenty, format output):
  - **wymaga aktualizacji testów w tym samym commicie**

- Katalog `legacy/`:
  - jest tylko referencją
  - testy nie powinny go dotykać
  - pytest ograniczony do katalogu `tests/`
