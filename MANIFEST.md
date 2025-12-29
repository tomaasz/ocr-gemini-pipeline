# MANIFEST – OCR Gemini Pipeline

Ten plik jest **kontraktem zmian** (dla ludzi i AI).
Ma zapobiegać „rozlewaniu się” refaktorów, mieszaniu etapów
oraz przypadkowemu naruszeniu działającej produkcji.

---

## RULES (dla AI / PR)

1) **Nie edytuj plików w `legacy/`**  
   `legacy/` to zamrożona referencja działającej wersji produkcyjnej.
   Zmiany tam są zabronione.

2) **Nowy kod trafia wyłącznie do `src/ocr_gemini/`**  
   Wszystkie nowe moduły, refaktory i testy muszą żyć w `src/ocr_gemini/`.

3) **Każde zadanie ma wskazać dokładnie 1–3 pliki do zmiany**  
   Wyjątki (nadal max 3 pliki):
   - zmiana kodu + test + aktualizacja docs,
   - dodanie nowego pliku (liczy się jako jeden z 1–3).

4) **PR nie może mieszać refaktoru i zmian logiki**  
   - refaktor → bez zmiany zachowania,
   - zmiana logiki → bez kosmetyki kodu „przy okazji”.

5) **Źródło prawdy produkcji jest POZA tym repo**  
   Produkcja działa z osobnego repo (`ocr-gemini`) + systemd.
   To repo jest rozwijane równolegle i bezpiecznie.

---

## Aktualny stan modularizacji (fakty)

- **Stage 1 – DONE**
  - `config.py` (timeouts, stałe)
  - `db.py` (PostgreSQL, upsert document/entry)
  - `metrics.py` (DocumentMetrics)
  - pakiet zainstalowany jako `pip install -e .`

- **Stage 1.2 – DONE**
  - `files.py` (discovery + sha256, streaming, deterministic)
  - `output.py` (zapisy txt/json/meta do out-root)

- **Stage 1.3 – NEXT**
  - `pipeline.py` (orkiestracja bez UI: discovery → DB → output)

- **Stage 2 – LATER**
  - `ui/actions.py`
  - `ui/extract.py`
  - integracja Playwright / Gemini UI

---

## Struktura i odpowiedzialności modułów (source of truth)

- `src/ocr_gemini/cli.py`
  - tylko argparse + wejście do programu
  - brak logiki biznesowej

- `src/ocr_gemini/pipeline.py`
  - orkiestracja:
    - iteracja plików
    - statusy w DB
    - retry
    - integracja modułów
  - **bez kodu UI**

- `src/ocr_gemini/config.py`
  - konfiguracja runtime (timeouts, stałe)

- `src/ocr_gemini/db.py`
  - zapis do PostgreSQL (`ocr_document`, `ocr_entry`)
  - transakcje, mapping pól

- `src/ocr_gemini/files.py`
  - discovery plików
  - sha256
  - stabilny porządek przetwarzania

- `src/ocr_gemini/output.py`
  - zapis artefaktów OCR (txt/json/meta)

- `src/ocr_gemini/ui/actions.py`
  - JEDYNE miejsce na zmiany UI (Playwright)

- `src/ocr_gemini/ui/extract.py`
  - parsowanie odpowiedzi z DOM

---

## Zasada zmian (routing)

- Zmiany UI → **tylko** `ui/*.py`
- Zmiany DB → **tylko** `db.py`
- Zmiany discovery/output → `files.py`, `output.py`
- Zmiany sterujące → `pipeline.py`
- Zmiany CLI → `cli.py`

Nie edytuj `pipeline.py` i `cli.py`, jeśli nie jest to konieczne.

---

## Checklist PR (minimalna)

- [ ] Dotykam maks. 1–3 plików
- [ ] Nie edytuję `legacy/`
- [ ] Zmiany mają jeden cel (refaktor albo logika)
- [ ] Zmiana trafia do właściwego modułu
- [ ] Etap (Stage X) jest jasno wskazany w opisie PR
