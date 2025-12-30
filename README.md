# Stage 2.0: Retry & Recovery

This pipeline now supports resilient processing with automatic retries and error recovery.

## Features
* **Deterministic Retries**: Safely retry failed documents without duplication.
* **Error Classification**: Distinguishes between `transient` (retryable) and `permanent` (fatal) errors.
* **Recovery Actions**: Automatically attempts to recover from transient UI glitches (e.g., refreshing the page) within a single attempt.
* **Attempt Tracking**: Records each attempt as a distinct run in the database, linked to previous attempts.

## CLI Usage

### Basic Retry
Retry only documents that failed in previous runs (and are eligible for retry):
```bash
python -m src.ocr_gemini.cli \
  --input-dir ... --out-dir ... --profile-dir ... \
  --retry-failed
```
This will check the database for failed runs and retry them if they were transient or unknown errors.

### Advanced Configuration
Control the retry behavior:
```bash
python -m src.ocr_gemini.cli \
  ... \
  --retry-failed \
  --max-attempts 5 \
  --retry-backoff-seconds 10
```
* `--max-attempts N`: Stop retrying after N attempts (default: 3).
* `--retry-backoff-seconds S`: Wait S seconds before starting a new retry attempt (useful for rate limits, though not for UI sync).

## Error Handling Policy
| Error Kind | Examples | Action |
|------------|----------|--------|
| `transient` | Timeouts, Network glitches, Detached elements | Retry up to limit |
| `permanent` | File missing, Auth required, Invalid format | Fail immediately (do not retry) |
| `unknown` | Unclassified exceptions | Retry (treated as transient) |

## Database Schema Changes
`ocr_run` table now includes:
* `attempt_no`: The attempt number (1-based).
* `parent_run_id`: Link to the previous failed run.
* `error_kind`: Classification of the failure.
* `retry_after_seconds`: Optional delay (if recorded).
