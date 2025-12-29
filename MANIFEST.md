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

5) **Produkcja jest poza tym repo**  
   Produkcja działa z osobnego repo (`ocr-gemini`) + systemd (`gemini-ocr.service`).
   To repo jest rozwijane równolegle i bezpiecznie.

---

## Aktualny stan modularizacji (fakty)

### Stage 1 — DONE
- `config.py` (timeouts/stałe)
- `db.py` (PostgreSQL: upsert `ocr_document`, `ocr_entry`)
- `metrics.py` (`DocumentMetrics`)
- pakiet w venv zainstalowany jako `pip install -e .`

### Stage 1.2 — DONE
- `files.py` (discovery + sha256, streaming `os.scandir`, deterministic order)
- `output.py` (zapis `result.txt`, `result.json`, `meta.json` do `OCR_OUT_ROOT`)

### Stage 1.3 — DONE (bez UI)
- `pipeline.py` (orkiestracja bez UI: discovery → DB → output → DB)
- Smoke test potwierdzony:
  - uruchomienie: `OCR_LIMIT=1 python -m ocr_gemini.pipeline`
  - wynik: `processed: 1` + wpis w DB + zapis out-root

### Stage 2 — NEXT
- `ui/actions.py` (Playwright: upload/paste/send/wait/cleanup)
- `ui/extract.py` (wyciąganie tekstu z DOM)
- podpięcie UI do `pipeline.py` w miejscu placeholdera OCR

---

## Struktura i odpowiedzialności modułów (source of truth)

- `src/ocr_gemini/cli.py`
  - tylko argparse + wejście do programu
  - brak logiki biznesowej

- `src/ocr_gemini/pipeline.py`
  - orkiestracja:
    - iteracja plików
    - statusy w DB
    - retry (docelowo)
    - integracja modułów
  - **bez kodu UI** (Stage 1.3)
  - miejsce na wpięcie UI (Stage 2)

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

---

## Checklist PR (minimalna)

- [ ] Dotykam maks. 1–3 plików
- [ ] Nie edytuję `legacy/`
- [ ] Zmiany mają jeden cel (refaktor albo logika)
- [ ] Zmiana trafia do właściwego modułu
- [ ] Etap (Stage X) jest jasno wskazany w opisie PR
