# OCR (Gemini UI + Playwright)

Automatyzacja OCR skanów przez web UI Google Gemini (Playwright + Chrome profil) z użyciem Playwright (persistent Chrome profile).

## Wymagania
- Python 3.10+
- Playwright
- Zalogowany profil Chrome do Gemini (persistent context)

## Instalacja
```bash
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
playwright install chromium
```

## Konfiguracja promptów
Prompty są w `gemini_prompts.json` w formacie:
- `prompts: [ { "id": "...", "template": [ ... ] }, ... ]`

Placeholdery w template:
- `__FILE_NAME__`
- `__SOURCE_PATH__`

## Uruchomienie
```bash
python3 gemini_ocr.py \
  --root ~/mnt/nas_genealogy/metryki \
  --out-root ~/ocr_out \
  --prompts ./gemini_prompts.json \
  --prompt-id agad_generic \
  --profile-dir ~/.pw_gemini_profile \
  --limit 1 \
  --recursive \
  --headed \
  --debug-dir ~/ocr_debug
```

## Konfiguracja przez ENV
W repo jest `gemini_ocr.env.example`. Skopiuj do `gemini_ocr.env` i uzupełnij:

```bash
cp gemini_ocr.env.example gemini_ocr.env
```

Wczytanie env w bash:
```bash
set -a
source gemini_ocr.env
set +a
```

## Bezpieczeństwo
Nie commituj profilu Chrome (`--profile-dir`) ani danych wyjściowych (`ocr_out/`, `ocr_debug/`).
