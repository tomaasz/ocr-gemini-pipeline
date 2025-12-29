# ENVIRONMENT (ubuntuovh) — OCR Gemini

Ten dokument opisuje **twarde fakty** o środowisku na `tomaasz@ubuntuovh`.
Jest źródłem prawdy dla debugowania, onboardingu i przyszłego przełączenia produkcji.

---

## 1) Kontekst (2 repozytoria)

Na serwerze działają równolegle:

- **Produkcja (działa):** `~/projects/ocr-gemini` (Legacy)
- **Nowe modularne (w budowie):** `~/projects/ocr-gemini-pipeline` (Stage 1.3)

Zasada nadrzędna: **produkcji nie ruszamy**, dopóki nowe repo
nie przejdzie pełnej stabilizacji.

---

## 2) Produkcja — stan obecny (`ocr-gemini`)

### 2.1 systemd
- Unit: `gemini-ocr.service`
- ExecStart: `/usr/local/bin/gemini-ocr-run.sh`
- WorkingDirectory: `/home/tomaasz/projects/ocr-gemini`
- EnvironmentFile: `/etc/default/gemini-ocr`

Logi:
- `/var/log/gemini-ocr/gemini-ocr.log`
- `/var/log/gemini-ocr/gemini-ocr.err.log`

Weryfikacja:
```bash
systemctl status gemini-ocr --no-pager
systemctl cat gemini-ocr --no-pager
journalctl -u gemini-ocr -n 200 --no-pager
```

### 2.2 Wrapper Script
Plik `/usr/local/bin/gemini-ocr-run.sh` w root repozytorium jest wrapperem dla **legacy code**.
Nie jest używany do uruchamiania nowego pipeline'u (`ocr-gemini-pipeline`), chyba że zostanie zaktualizowany w przyszłości.

---

## 3) Nowy Pipeline (Stage 1.3)

Uruchamiany ręcznie (nie podpięty do systemd).

**Uruchomienie:**
```bash
set -a; source /etc/default/gemini-ocr; set +a
OCR_LIMIT=1 OCR_ALLOW_PLACEHOLDER=1 \
/home/tomaasz/projects/ocr-gemini/.venv/bin/python -m ocr_gemini.pipeline
```

**Baza Danych (PostgreSQL):**
Pipeline korzysta ze zmiennych:
- `PGHOST` (def: 127.0.0.1)
- `PGPORT` (def: 5432)
- `PGDATABASE` (def: genealogy)
- `PGUSER` (def: tomaasz)
- `PGPASSWORD` (opcjonalnie)

Nie korzysta ze zmiennej `DATABASE_URL`.
