# OCR v1: Operational Runbook

## 1. Definition: OCR v1 DONE

**OCR v1** represents a stable, production-ready release of the Gemini OCR pipeline. It is characterized by:

*   **Streaming Discovery:** Uses `os.scandir` recursively to safely handle massive file trees on NAS/SSHFS without hanging or excessive memory usage.
*   **Robust Runtime:** Includes a **Watchdog** system to detect UI hangs (uploads, prompts, generation) and raise explicit exceptions.
*   **Retry Budget:** Automatically retries failed documents (default: 2 attempts) with cleanup steps (page reload/clear) before marking as skipped.
*   **Observability:** Centralized timeout configuration via Environment Variables and per-document performance metrics (duration, attempts, outcome).

**Scope:**
*   File discovery (local & NAS).
*   Browser automation (Playwright) for Gemini.
*   Basic error handling & retry logic.
*   Logging & Metrics.

**Out of Scope (for v1):**
*   Database schema changes.
*   Advanced post-processing (entity linking).
*   Complex multi-worker orchestration (beyond basic CLI usage).

---

## 2. Prerequisites

1.  **Python 3.10+**
2.  **Virtual Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Playwright Browsers:**
    ```bash
    playwright install chromium
    ```
4.  **Browser Profile:**
    A persistent browser profile (`--profile-dir`) is **required** for OCR runs to maintain login sessions.
    *   *Tip:* Run with `--headed --wait-login` once to create/login manually.

---

## 3. Supported Modes & Flags

### A. Import / Discovery Only (`--import-only`)
Scans the directory tree and lists files that *would* be processed. Does **not** launch a browser or require a profile.
*   **Safe for:** Verifying NAS connectivity and file counts.

```bash
python3 gemini_ocr.py --root /mnt/nas/docs --recursive --import-only
```

### B. Standard OCR Run
Processes images, sends them to Gemini, and captures responses.

```bash
python3 gemini_ocr.py \
  --root /mnt/nas/docs \
  --recursive \
  --profile-dir ./profiles/worker1 \
  --limit 100
```

### Common Flags
*   `--recursive`: Scan subdirectories.
*   `--limit N`: Stop after processing N files (early exit).
*   `--timeout-ms N`: Global timeout for the session (default: configurable via ENV).
*   `--headed`: Run visible browser (debugging).
*   `--wait-login`: Pause at startup to allow manual login.
*   `--debug-dir PATH`: Save screenshots/HTML dumps on errors.

---

## 4. Configuration (Environment Variables)

Timeouts are centralized in `gemini_config.py`. You can override defaults using environment variables (values in **milliseconds**).

| Variable | Default | Description |
| :--- | :--- | :--- |
| `GEMINI_TIMEOUT_PAGE_LOAD` | 180,000 | Initial page load timeout. |
| `GEMINI_TIMEOUT_FIND_COMPOSER` | 60,000 | Wait time for chat input box to appear. |
| `GEMINI_TIMEOUT_UPLOAD_OVERLAY`| 20,000 | Wait for "Upload files" overlay. |
| `GEMINI_TIMEOUT_ATTACH_CONFIRM`| 8,000 | Max wait for attachment verification (thumbnail). |
| `GEMINI_TIMEOUT_PROMPT_PASTE` | 10,000 | Max time to paste prompt text. |
| `GEMINI_TIMEOUT_SEND_CONFIRM` | 30,000 | Wait for message to enter "Analyzing" state. |
| `GEMINI_TIMEOUT_GEN_APPEAR` | 20,000 | Wait for response generation to start. |
| `GEMINI_TIMEOUT_GEN_DONE` | 240,000 | Max time for full response generation. |
| `GEMINI_TIMEOUT_CLEANUP_WAIT` | 5,000 | Wait time during cleanup attempts. |

**Example:**
```bash
export GEMINI_TIMEOUT_GEN_DONE=300000
python3 gemini_ocr.py ...
```

---

## 5. Output & Metrics

### Logs
The script logs progress to `stdout`.
*   **Per-File Metrics:**
    ```text
    METRICS: file=doc_001.jpg | status=success | attempts=1 | duration=15.4s
    ```
*   **Errors:**
    ```text
    WARN: Błąd przy doc_002.jpg (attempt 1): <Error Details>
    ERROR: Wyczerpano limit prób dla doc_002.jpg. Skipping.
    METRICS: file=doc_002.jpg | status=error | attempts=2 | duration=45.2s | reason=Timeout
    ```

---

## 6. Recipes (Copy/Paste)

**Recipe 1: Dry Run (Scan files on NAS)**
```bash
python3 gemini_ocr.py \
  --root /mnt/data/genealogy \
  --recursive \
  --import-only \
  --limit 50
```

**Recipe 2: Interactive Login (First Run)**
```bash
python3 gemini_ocr.py \
  --root ./dummy_folder \
  --profile-dir ./profiles/my_profile \
  --headed \
  --wait-login
# (Log in manually in the browser window, then press ENTER in terminal)
```

**Recipe 3: Production Batch Run (Robust)**
```bash
export GEMINI_TIMEOUT_PAGE_LOAD=300000  # 5 min for slow starts
export GEMINI_TIMEOUT_GEN_DONE=300000   # 5 min for long docs

python3 gemini_ocr.py \
  --root /mnt/data/genealogy/batch_2023 \
  --recursive \
  --profile-dir ./profiles/worker1 \
  --debug-dir ./logs/debug_snaps \
  --limit 1000
```

---

## 7. Troubleshooting

| Symptom | Probable Cause | Resolution |
| :--- | :--- | :--- |
| **Hang at startup** | Profile locked or browser zombie. | Kill orphaned chrome processes (`pkill -f chrome`). Ensure unique `--profile-dir` per worker. |
| **Timeout on "Upload"** | Network latency or NAS slow read. | Increase `GEMINI_TIMEOUT_UPLOAD_OVERLAY`. Check NAS connectivity. |
| **"Prompt paste failed"** | Clipboard/Input focus lost. | Retry budget usually handles this. If persistent, check if window manager interferes (headless mode is safer). |
| **High "Skipped" count** | Gemini rejecting requests or strict filters. | Check `debug_dir` screenshots. You may need to rotate IP or wait (rate limits). |
| **Script exits early** | `--limit` reached or empty folder. | Check if `--limit` is set. Verify `--root` path exists. |
