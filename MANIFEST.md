# MANIFEST – OCR Gemini Pipeline

## Gdzie co jest
- src/ocr_gemini/cli.py
  - tylko argparse + wejście do programu
- src/ocr_gemini/pipeline.py
  - kontrola retry, kolejność kroków, zapis outputów i DB
- src/ocr_gemini/ui/actions.py
  - upload/paste/send/wait/cleanup — jedyne miejsce na zmiany UI
- src/ocr_gemini/ui/extract.py
  - wyciąganie tekstu odpowiedzi z DOM
- src/ocr_gemini/db.py
  - zapis do PostgreSQL (ocr_document + ocr_entry)
- src/ocr_gemini/files.py
  - skanowanie plików i sha256
- src/ocr_gemini/output.py
  - zapis plików txt/json do out-root

## Zasada zmian
Jeśli zadanie dotyczy UI → zmieniaj wyłącznie ui/*.py.
Jeśli dotyczy DB → zmieniaj wyłącznie db.py.
Nie edytuj pipeline/cli jeśli nie trzeba.
