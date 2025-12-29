# Run & Verification Guide (Stage 1.3)

This guide covers how to **configure, run, and verify** the OCR Gemini Pipeline in its current state (Stage 1.3).

> **Note:** Stage 1.3 uses a `FakeEngine` (placeholder OCR) to test the orchestration, database, and output logic. Real OCR via Playwright will be enabled in Stage 2.

---

## 1. Installation

The pipeline is a Python package. Install it in editable mode:

```bash
# From the repository root (ocr-gemini-pipeline)
pip install -e .
```

---

## 2. Configuration (Environment Variables)

The pipeline is configured **exclusively** via environment variables.

### Required Variables
| Variable | Description | Example |
| :--- | :--- | :--- |
| `OCR_ROOT` | Input directory containing images to process. | `/home/user/scans/` |
| `OCR_OUT_ROOT` | Output directory for results. | `/home/user/ocr_out/` |
| `OCR_PROMPT_ID` | Identifier for the prompt to use (for meta). | `agad_generic` |
| `OCR_ALLOW_PLACEHOLDER` | **Must be set to `1`** to allow the FakeEngine. | `1` |

### Optional Variables
| Variable | Default | Description |
| :--- | :--- | :--- |
| `OCR_RECURSIVE` | `0` | Set to `1` to scan subdirectories. |
| `OCR_LIMIT` | `0` | Stop after N files (0 = no limit). |
| `OCR_RUN_TAG` | `None` | Custom string tag for the run (saved in DB/Meta). |
| `OCR_PIPELINE` | `stage1-no-ui` | Pipeline version identifier. |

### Database Configuration (PostgreSQL)
The pipeline connects to PostgreSQL using standard `PG*` variables.
Defaults are usually sufficient for local dev (localhost:5432).

| Variable | Default |
| :--- | :--- |
| `PGHOST` | `127.0.0.1` |
| `PGPORT` | `5432` |
| `PGDATABASE` | `genealogy` |
| `PGUSER` | `tomaasz` |
| `PGPASSWORD` | *(Empty)* |

---

## 3. Running the Pipeline

Execute the pipeline as a Python module:

```bash
# Example Run
export OCR_ROOT="/home/tomaasz/mnt/nas_genealogy/Sources/Nurskie dokumenty/"
export OCR_OUT_ROOT="/home/tomaasz/ocr_out"
export OCR_PROMPT_ID="agad_generic"
export OCR_ALLOW_PLACEHOLDER="1"
export OCR_LIMIT="1"

python -m ocr_gemini.pipeline
```

**Expected Console Output:**
```
OK: <filename> -> doc_id=123 entry_id=456 out=/path/to/output/...
{"processed": 1}
```

---

## 4. Verification

After running the pipeline, verify that the orchestration worked correctly.

### 4.1 Verify Outputs (Filesystem)
Check `OCR_OUT_ROOT`. For each processed file, you should see a directory structure mirroring the source, containing:
1.  **`result.txt`**: The OCR text (Stage 1.3: "FAKE OCR...").
2.  **`result.json`**: The structured data (Stage 1.3: `{"engine": "fake", ...}`).
3.  **`meta.json`**: Metadata about the run (metrics, paths, hashes).

```bash
ls -R $OCR_OUT_ROOT
# Should show result.txt, result.json, meta.json
```

### 4.2 Verify Database
Connect to the database and check the `genealogy` schema tables.

**Check `ocr_document`:**
```sql
SELECT doc_id, file_name, status, pipeline
FROM genealogy.ocr_document
ORDER BY updated_at DESC LIMIT 5;
```
*Expect: `status='done'`, `pipeline='stage1-no-ui'`.*

**Check `ocr_entry`:**
```sql
SELECT entry_id, doc_id, entry_text
FROM genealogy.ocr_entry
WHERE doc_id = <ID_FROM_ABOVE>;
```
*Expect: `entry_text` starting with "FAKE OCR...".*
