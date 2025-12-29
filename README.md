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
