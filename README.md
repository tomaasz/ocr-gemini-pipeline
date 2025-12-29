# OCR Gemini Pipeline (Stage 1.3)

Modular OCR pipeline using Gemini, designed for genealogy documents.
Currently in **Stage 1.3** (orchestration core, fake engine, no real UI automation yet).

## Documentation

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

To run the pipeline with the **Fake Engine** (no Playwright/Browser required):

1.  **Install**:
    ```bash
    pip install -e .
    ```

2.  **Run**:
    The pipeline is configured via environment variables.

    ```bash
    export OCR_ROOT="/path/to/images"
    export OCR_OUT_ROOT="/path/to/output"
    export OCR_PROMPT_ID="test_prompt"
    export OCR_ALLOW_PLACEHOLDER="1"  # Required for FakeEngine

    # Optional DB config (defaults to localhost/genealogy/tomaasz)
    # export PGHOST=... PGPORT=... PGDATABASE=...

    python -m ocr_gemini.pipeline
    ```

    See [MANIFEST.md](docs/MANIFEST.md) for detailed configuration.

## Features (Stage 1.3)

- **Discovery**: Recursive file scanning with limits.
- **Database**: Upserts documents and entries to PostgreSQL (`genealogy` schema).
- **Artifacts**: Saves `result.txt`, `result.json`, and `meta.json` for each file.
- **Metrics**: Tracks processing time and status.
- **Engine**: Plugable OCR engine (currently `FakeEngine` defaults).

## Legacy Wrapper

The root script `gemini-ocr-run.sh` is a wrapper for the **legacy** system.
For the new pipeline, use `python -m ocr_gemini.pipeline`.
