# ENVIRONMENT (ubuntuovh) — OCR Gemini

## Kontekst
Na serwerze `tomaasz@ubuntuovh` działają obecnie DWA repozytoria:
- **Produkcja (działa):** `~/projects/ocr-gemini`
- **Nowe modularne (w budowie):** `~/projects/ocr-gemini-pipeline`

Zasada: produkcja nie jest ruszana podczas refaktorów. Nowe repo dojrzewa obok.

---

## Produkcja — stan obecny (ocr-gemini)
### Systemd
- Unit: `gemini-ocr.service`
- ExecStart: `/usr/local/bin/gemini-ocr-run.sh`
- WorkingDirectory: `/home/tomaasz/projects/ocr-gemini`
- EnvironmentFile: `/etc/default/gemini-ocr`
- Logi:
  - `/var/log/gemini-ocr/gemini-ocr.log`
  - `/var/log/gemini-ocr/gemini-ocr.err.log`

### Konfiguracja runtime
- Python venv: `/home/tomaasz/projects/ocr-gemini/.venv/bin/python`
- Skrypt: `/home/tomaasz/projects/ocr-gemini/gemini_ocr.py`
- Prompt file: `/home/tomaasz/gemini_prompts.json` (jeśli inna ścieżka — wpisać)
- Profile Playwright: `/home/tomaasz/.pw_gemini_profile`
- Input root (OCR_ROOT): `/home/tomaasz/mnt/nas_genealogy/...`
- Output root (OCR_OUT_ROOT): `/home/tomaasz/ocr_out`

### DB (PostgreSQL w Docker)
Źródło prawdy: `/etc/default/gemini-ocr`:
- PGHOST=127.0.0.1
- PGPORT=5432
- PGDATABASE=genealogy
- PGUSER=tomaasz
Autoryzacja: `~/.pgpass` (działa)

Schema: `genealogy`
Tabele kluczowe: `ocr_document`, `ocr_entry`, `ocr_step`, ...

---

## Nowe repo (ocr-gemini-pipeline)
Ścieżka: `~/projects/ocr-gemini-pipeline`
Zasada: **nie edytujemy `legacy/`** — to tylko referencja. Nowy kod idzie do `src/ocr_gemini/`.

MANIFEST: `MANIFEST.md`

---

## Procedura przełączenia produkcji na nowe repo (dopiero po stabilizacji)
1) Zaktualizować `/etc/default/gemini-ocr`:
   - PYTHON_EXEC -> venv w nowym repo
   - SCRIPT_FILE -> nowy entrypoint (np. `-m ocr_gemini` lub `ocr-gemini`)
2) Zmienić WorkingDirectory w unit na nowe repo (opcjonalnie)
3) `sudo systemctl daemon-reload && sudo systemctl restart gemini-ocr`
4) Weryfikacja logów w `/var/log/gemini-ocr/`

(Na razie NIE ROBIMY tego kroku.)
