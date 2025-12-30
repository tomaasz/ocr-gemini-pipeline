
## Added Features

### Two Browser Workers Capability
- **Added**: `WorkerPool` logic in `src/ocr_gemini/ui/worker_pool.py`.
- **Added**: `workers` parameter in `PlaywrightEngine` constructor.
- **Legacy Evidence**: `legacy/gemini_ocr.py` (lines 902, 946) showed support for external parallelization via `OCR_WORKER_ID`. The new implementation internalizes this via a pool.
- **Next**: Wiring `WorkerPool` to actual Playwright context creation and job submission in `PlaywrightEngine.ocr`.

### Resilient Send Logic
- **Added**: `send_message` in `src/ocr_gemini/ui/actions.py` with reliability logic.
- **Legacy Evidence**: Ported from `legacy/gemini_ocr.py` (lines 543-644).
- **Features**:
    - Separate `send_timeout_ms` and `confirm_timeout_ms`.
    - Heuristic "Send" button detection.
    - Fallback to "Enter" key in composer.
    - Deterministic confirmation via "Stop" button or response visibility.
    - Debug artifact generation on failure.
