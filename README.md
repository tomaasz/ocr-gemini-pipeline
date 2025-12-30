# OCR Gemini Pipeline (Stage 1.3)

Modular OCR pipeline using Gemini, designed for genealogy documents.
Currently in **Stage 1.3** (orchestration core, fake engine, no real UI automation yet).

## Documentation

- [**Run & Verification Guide**](docs/run.md) – **Start Here.** How to configure, run, and verify the pipeline.
- [**MANIFEST.md**](docs/MANIFEST.md) – Project contract, architecture, and design rules.
- [**TESTING.md**](docs/TESTING.md) – Testing strategy and instructions.
- [**Deployment Reference**](docs/reference/ENVIRONMENT_UBUNTUOVH.md) – Example deployment (Ubuntu OVH).

## Project Structure

```
ocr-gemini-pipeline/
├── src/ocr_gemini/     # Source code (Stage 1.3+)
├── tests/              # Unit & smoke tests
├── docs/               # Documentation & Snapshots
├── legacy/             # Reference to old codebase (read-only)
└── pyproject.toml      # Build configuration
```

## Quick Start (Stage 1.3)

See [**Run & Verification Guide**](docs/run.md) for full instructions.

1.  **Install**:
    ```bash
    pip install -e .
    ```

2.  **Run (Minimal)**:
    ```bash
    export OCR_ROOT="/path/to/images"
    export OCR_OUT_ROOT="/path/to/output"
    export OCR_PROMPT_ID="test_prompt"
    export OCR_ALLOW_PLACEHOLDER="1"

    python -m ocr_gemini.pipeline
    ```

## Debugging

Configuration options for debugging failures:

*   **`OCR_DEBUG_DIR`**: Path to directory where debug artifacts (screenshots, HTML, metadata) will be saved upon failure.
    *   If unset, no debug artifacts are saved.
    *   Example: `export OCR_DEBUG_DIR="./debug_artifacts"`
*   **`OCR_UI_TIMEOUT_MS`**: Global timeout for UI operations (default: 180,000 ms).
    *   *Note: Currently plumbing only. Will be wired to Playwright engine in future stages.*

### Legacy Evidence (Reference)

*   Legacy `gemini_ocr.py` used `--debug-dir` to dump screenshots on `cleanup_failed`, `extract_response_failed`, etc.
*   Legacy timeouts were hardcoded or passed via CLI args (e.g. `--timeout-ms`).

## Reliability Helpers

Reusable, pure-logic helpers are available in `src/ocr_gemini/utils.py` to improve stability without coupling to Playwright:

*   **`retry_call`**: Retries a function with backoff on specific exceptions.
*   **`wait_for_generation_complete`**: Generic polling for process completion (e.g. generation).

These helpers abstract the retry/wait logic found in the legacy codebase (e.g., `send_message_with_retry`, `wait_generation_cycle`).
