# MANIFEST — OCR Gemini Pipeline

Ten dokument jest **kontraktem projektu**.
Zmiany niezgodne z MANIFEST są traktowane jako błąd projektowy.

---

## Założenia ogólne

- Pipeline OCR sterowany przez **Gemini Web UI (Playwright)** — nie przez API
- Refaktor prowadzony **bez naruszania produkcji**
- Repo `ocr-gemini`:
  - działa w produkcji
  - jest nietykalne
- Repo `ocr-gemini-pipeline`:
  - nowa, modularna architektura
  - rozwijana etapami (Stage 1 → Stage 3)

---

## Struktura projektu

```
ocr-gemini-pipeline/
├── src/ocr_gemini/
│   ├── cli.py
│   ├── pipeline.py
│   ├── config.py
│   ├── db.py
│   ├── files.py
│   ├── output.py
│   ├── metrics.py
│   └── ui/            # Stage 2+
├── tests/
├── docs/
├── legacy/            # tylko referencja
└── pyproject.toml
```

---

## Zasady pracy

- Maksymalnie **1–3 pliki** na commit
- Brak mieszania:
  - refaktoru
  - zmiany logiki
  - zmian architektonicznych
- `legacy/`:
  - tylko do czytania
  - brak testów
  - brak modyfikacji

---

## Stage 1 — Modularny core (DONE)

- wydzielenie logiki do modułów
- src-layout (`src/ocr_gemini`)
- editable install (`pip install -e .`)
- pipeline bez UI (placeholder OCR)

---

## Stage 1.3 — Orkiestracja + stabilizacja (DONE)

### Zakres
- `Pipeline`:
  - discovery plików
  - metryki
  - zapis output
  - zapis DB
  - commit / rollback
- placeholder OCR (bez UI)
- pełny zestaw testów:
  - unit tests
  - smoke test (success)
  - smoke test (error)

### Testy
- `tests/test_files.py`
- `tests/test_output.py`
- `tests/test_metrics.py`
- `tests/test_pipeline_smoke.py`
- `tests/test_pipeline_error_path.py`

### Uruchamianie testów
```bash
/home/tomaasz/projects/ocr-gemini/.venv/bin/python -m pytest -q
```

Stage 1.3 uznaje się za zakończony **tylko przy zielonych testach**.

---

## Stage 2 — UI (Playwright + Gemini) (PLANOWANY)

- `ui/actions.py`
- `ui/extract.py`
- wstrzyknięcie OCR engine do pipeline
- brak testów UI (manual / smoke)

---

## Stage 3 — Stabilizacja produkcyjna (PLANOWANY)

- retry / backoff
- heurystyki jakości OCR
- monitoring
- testy integracyjne (opcjonalnie)

---

## Zasada nadrzędna

> Jeśli coś nie jest opisane w MANIFEST — **nie zakładaj, nie zgaduj, dopisz albo zapytaj**.
