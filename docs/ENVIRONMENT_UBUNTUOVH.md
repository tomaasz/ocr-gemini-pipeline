# ENVIRONMENT (ubuntuovh) — OCR Gemini

Ten dokument opisuje **twarde fakty** o środowisku na `tomaasz@ubuntuovh`.
Jest źródłem prawdy dla debugowania, onboardingu i przyszłego przełączenia produkcji.

---

## 1) Kontekst (2 repozytoria)

Na serwerze działają równolegle:

- **Produkcja (działa):** `~/projects/ocr-gemini`
- **Nowe modularne (w budowie):** `~/projects/ocr-gemini-pipeline`

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
