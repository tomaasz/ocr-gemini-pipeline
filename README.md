# OCR Gemini Pipeline (Stage 1.5)

Modular OCR pipeline using Gemini, designed for genealogy documents.
Currently in **Stage 1.5** (DB Write-back, Idempotency, and Resume).

## Documentation

- [**Run & Verification Guide**](docs/run.md) – **Start Here.** How to configure, run, and verify the pipeline.
- [**MANIFEST.md**](docs/MANIFEST.md) – Project contract, architecture, and design rules.
- [**TESTING.md**](docs/TESTING.md) – Testing strategy and instructions.
- [**Deployment Reference**](docs/reference/ENVIRONMENT_UBUNTUOVH.md) – Example deployment (Ubuntu OVH).

## Project Structure

```
ocr-gemini-pipeline/
├── src/ocr_gemini/     # Source code
│   ├── engine/         # Core engine logic & Playwright adapter
│   ├── ui/             # UI actions & helpers
│   ├── db/             # Database repository & config
│   ├── cli.py          # CLI entry point
│   └── ...
├── tests/              # Unit & smoke tests
├── docs/               # Documentation & Snapshots
├── sql/                # SQL Migrations
├── legacy/             # Reference to old codebase (read-only)
└── pyproject.toml      # Build configuration
```

## Quick Start (Stage 1.5)

Run the pipeline using the CLI:

```bash
# Basic usage with DB write-back (requires OCR_DB_DSN)
export OCR_DB_DSN="postgresql://user:pass@host:5432/dbname"
python -m ocr_gemini.cli \
  --input-dir ./images \
  --out-dir ./output \
  --profile-dir ./chrome-profile \
  --limit 2

# Resume failed/interrupted run
python -m ocr_gemini.cli \
  --input-dir ./images \
  --out-dir ./output \
  --profile-dir ./chrome-profile \
  --resume

# Force re-processing of already done files
python -m ocr_gemini.cli \
  --input-dir ./images \
  --out-dir ./output \
  --profile-dir ./chrome-profile \
  --force
```

**Note:** You must sign in to Gemini manually in the browser window during the first run (or launch browser separately with same profile). The pipeline assumes a signed-in state.

### DB Write-back & Idempotency
- **Success Definition**: A run is considered successful only if `ocr_run.status == 'done'`.
- **Idempotency**: By default, documents with a successful run are skipped (status recorded as `skipped`).
- **Resume**: `--resume` processes only documents that do not have a successful run (i.e. failed or never processed).
- **Force**: `--force` processes documents regardless of previous status, creating a new run.

## Debugging

*   **Debug Artifacts**: Screenshots and HTML are saved to `--out-dir/debug` (or specified `--debug-dir`) upon failure.
*   **Sequential Execution**: The pipeline processes images one by one, ensuring the previous generation is complete before starting the next.

## Reliability Helpers

Reusable, pure-logic helpers are available in `src/ocr_gemini/utils.py` to improve stability without coupling to Playwright:

*   **`retry_call`**: Retries a function with backoff on specific exceptions.
*   **`wait_for_generation_complete`**: Generic polling for process completion (e.g. generation).

These helpers abstract the retry/wait logic found in the legacy codebase.

## Stage 2: Playwright Engine (In Progress)

The `PlaywrightEngine` (Stage 1.5) now drives a real browser instance sequentially with DB persistence.
Future improvements will focus on:
- Robustness (auto-recovery).
- Advanced error handling.
