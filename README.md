# OCR Gemini Pipeline (Stage 1.4)

Modular OCR pipeline using Gemini, designed for genealogy documents.
Currently in **Stage 1.4** (Runnable Sequential Pipeline via CLI).

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
│   ├── cli.py          # CLI entry point
│   └── ...
├── tests/              # Unit & smoke tests
├── docs/               # Documentation & Snapshots
├── legacy/             # Reference to old codebase (read-only)
└── pyproject.toml      # Build configuration
```

## Quick Start (Stage 1.4)

Run the pipeline using the CLI:

```bash
# Basic usage (Headful mode recommended for first run to sign in)
python -m ocr_gemini.cli \
  --input-dir ./images \
  --out-dir ./output \
  --profile-dir ./chrome-profile \
  --limit 2

# Headless mode (after sign-in)
python -m ocr_gemini.cli \
  --input-dir ./images \
  --out-dir ./output \
  --profile-dir ./chrome-profile \
  --headless
```

**Note:** You must sign in to Gemini manually in the browser window during the first run (or launch browser separately with same profile). The pipeline assumes a signed-in state.

## Debugging

*   **Debug Artifacts**: Screenshots and HTML are saved to `--out-dir/debug` (or specified `--debug-dir`) upon failure.
*   **Sequential Execution**: The pipeline processes images one by one, ensuring the previous generation is complete before starting the next.

## Reliability Helpers

Reusable, pure-logic helpers are available in `src/ocr_gemini/utils.py` to improve stability without coupling to Playwright:

*   **`retry_call`**: Retries a function with backoff on specific exceptions.
*   **`wait_for_generation_complete`**: Generic polling for process completion (e.g. generation).

These helpers abstract the retry/wait logic found in the legacy codebase.

## Stage 2: Playwright Engine (In Progress)

The `PlaywrightEngine` (Stage 1.4) now drives a real browser instance sequentially.
Future improvements will focus on:
- Robustness (auto-recovery).
- Advanced error handling.
