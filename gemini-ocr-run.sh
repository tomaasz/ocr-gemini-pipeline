#!/bin/bash
set -euo pipefail

START_TS="$(date '+%Y-%m-%d %H:%M:%S')"

echo "[gemini-ocr] START ${START_TS}"
echo "[gemini-ocr] Host: $(hostname)"
echo "[gemini-ocr] User: $(whoami)"

# Defaults (overridable via env)
: "${PYTHON_EXEC:?PYTHON_EXEC not set}"
: "${SCRIPT_FILE:?SCRIPT_FILE not set}"

CMD=("$PYTHON_EXEC" "$SCRIPT_FILE")

# Required OCR params
: "${OCR_ROOT:?OCR_ROOT not set}"
: "${OCR_OUT_ROOT:?OCR_OUT_ROOT not set}"
: "${OCR_PROMPT_ID:?OCR_PROMPT_ID not set}"

CMD+=("--root" "$OCR_ROOT")
CMD+=("--out-root" "$OCR_OUT_ROOT")
CMD+=("--prompt-id" "$OCR_PROMPT_ID")

# Optional flags
[[ "${OCR_RECURSIVE:-0}" == "1" ]] && CMD+=("--recursive")
[[ "${OCR_LIMIT:-0}" != "0" ]] && CMD+=("--limit" "$OCR_LIMIT")
[[ -n "${OCR_PROFILE_DIR:-}" ]] && CMD+=("--profile-dir" "$OCR_PROFILE_DIR")
[[ -n "${OCR_PROMPTS_FILE:-}" ]] && CMD+=("--prompts-file" "$OCR_PROMPTS_FILE")
[[ "${OCR_IMPORT_ONLY:-0}" == "1" ]] && CMD+=("--import-only")
[[ "${OCR_HEADED:-0}" == "1" ]] && CMD+=("--headed")
[[ -n "${OCR_DEBUG_DIR:-}" ]] && CMD+=("--debug-dir" "$OCR_DEBUG_DIR")

# Debug / dry-run
if [[ "${PRINT_ARGS:-0}" == "1" ]]; then
  echo "[gemini-ocr] DRY-RUN (PRINT_ARGS=1)"
  printf '[gemini-ocr] CMD: %q ' "${CMD[@]}"
  echo
  exit 0
fi

echo "[gemini-ocr] Executing OCR pipeline..."
exec "${CMD[@]}"
