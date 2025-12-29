# MANIFEST — OCR Gemini Pipeline

Ten dokument jest **kontraktem projektu**.
Zmiany niezgodne z MANIFEST są traktowane jako błąd projektowy.

---

## Czego TU NIE MA (What does NOT belong here)

To repozytorium **ocr-gemini-pipeline** jest ściśle wydzielonym projektem. Nie należy tu wrzucać:
1.  **Profilu przeglądarki (User Data Dir):** Dane sesji Gemini/Chrome są trzymane poza repozytorium (np. `~/.pw_gemini_profile`).
2.  **Danych wejściowych/wyjściowych:** Katalogi ze skanami i wyniki OCR są zewnętrzne.
3.  **Logiki biznesowej innej niż gen-genealogy:** To narzędzie jest generyczne dla pipeline'u OCR, specyficzne parsery metryk kościelnych itp. powinny być w osobnych warstwach lub projektach, jeśli nie dotyczą bezpośrednio ekstrakcji tekstu/danych z obrazu.
4.  **Ad-hoc skryptów:** Wszystko co wchodzi do `src/` musi być częścią pipeline'u. Skrypty "brudnopisowe" trzymaj lokalnie.

---

## Założenia ogólne

- Pipeline OCR sterowany przez **Gemini Web UI (Playwright)** — nie przez API.
- Refaktor prowadzony **bez naruszania produkcji**.
- Repo `ocr-gemini` (Legacy):
  - działa w produkcji.
  - jest nietykalne.
- Repo `ocr-gemini-pipeline` (New):
  - nowa, modularna architektura.
  - rozwijana etapami (Stage 1 → Stage 3).

---

## Struktura projektu

```
ocr-gemini-pipeline/
├── src/ocr_gemini/
│   ├── cli.py             # (Planowane)
│   ├── pipeline.py        # Entry point: python -m ocr_gemini.pipeline
│   ├── config.py
│   ├── db.py              # Obsługa PostgreSQL
│   ├── files.py           # Discovery plików
│   ├── output.py          # Zapis artefaktów (json, txt, meta)
│   ├── metrics.py
│   └── ui/                # Engines (FakeEngine, RealEngine)
├── tests/
├── docs/
│   ├── snapshots/         # Zrzuty stanu środowiska
│   └── reference/         # Opisy deploymentów
├── legacy/                # Tylko referencja (stary kod)
└── pyproject.toml
```

---

## Zasady pracy

- Maksymalnie **1–3 pliki** na commit.
- Brak mieszania:
  - refaktoru,
  - zmiany logiki,
  - zmian architektonicznych.
- `legacy/`:
  - tylko do czytania,
  - brak testów,
  - brak modyfikacji.

---

## Stage 1 — Modularny core (DONE)

- wydzielenie logiki do modułów
- src-layout (`src/ocr_gemini`)
- editable install (`pip install -e .`)
- pipeline bez UI (placeholder OCR)

---

## Stage 1.3 — Orkiestracja + stabilizacja (DONE)

### Zakres
- `Pipeline` (`src/ocr_gemini/pipeline.py`):
  - discovery plików
  - metryki
  - zapis output
  - zapis DB (`genealogy.ocr_document`, `genealogy.ocr_entry`)
  - commit / rollback
- placeholder OCR:
  - `FakeEngine` w `src/ocr_gemini/ui/fake_engine.py`
  - Wymaga `OCR_ALLOW_PLACEHOLDER=1`
- pełny zestaw testów:
  - unit tests
  - smoke test (success)
  - smoke test (error)

### Konfiguracja (ENV)
Pipeline Stage 1.3 jest konfigurowany **wyłącznie** przez zmienne środowiskowe:

**Wymagane:**
- `OCR_ROOT`: Katalog wejściowy.
- `OCR_OUT_ROOT`: Katalog wyjściowy.
- `OCR_PROMPT_ID`: ID promptu (np. `agad_generic`).
- `OCR_ALLOW_PLACEHOLDER`: `1` (aby pozwolić na FakeEngine).

**Opcjonalne:**
- `OCR_RECURSIVE`: `1` (domyślnie `0`).
- `OCR_LIMIT`: Liczba plików (domyślnie `0` = bez limitu).
- `OCR_RUN_TAG`: Oznacznie runu.
- `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`: Konfiguracja DB.

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
