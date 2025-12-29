#!/bin/bash
# Wrapper for Gemini OCR to handle optional arguments cleanly.
# This script should be placed at /usr/local/bin/gemini-ocr-run.sh (or similar)
# and referenced by the systemd service.

# Defaults (can be overridden by environment variables)
PYTHON_EXEC="${PYTHON_EXEC:-./venv/bin/python3}"
SCRIPT_FILE="${SCRIPT_FILE:-gemini_ocr.py}"

# Start building the command array
CMD=("$PYTHON_EXEC" "$SCRIPT_FILE")

# Helper function to check boolean values
# Returns 0 (true) for 1, true, yes, y (case insensitive)
# Returns 1 (false) otherwise
is_true() {
    local val="${1,,}" # convert to lowercase
    case "$val" in
        1|true|yes|y) return 0 ;;
        *) return 1 ;;
    esac
}

# --- Argument Construction ---

# 1. Root Directory (Required)
if [ -n "$OCR_ROOT" ]; then
    CMD+=("--root" "$OCR_ROOT")
else
    # We warn, but allow execution to proceed (script might handle defaults or fail)
    echo "WARNING: OCR_ROOT is not set." >&2
fi

# 2. Output Root Directory
if [ -n "$OCR_OUT_ROOT" ]; then
    CMD+=("--out-root" "$OCR_OUT_ROOT")
fi

# 3. Prompt ID
if [ -n "$OCR_PROMPT_ID" ]; then
    CMD+=("--prompt-id" "$OCR_PROMPT_ID")
fi

# 4. Profile Directory (Required unless import-only)
if [ -n "$OCR_PROFILE_DIR" ]; then
    CMD+=("--profile-dir" "$OCR_PROFILE_DIR")
fi

# 5. Recursive Scan
# Default to true (1) to match previous wrapper behavior, but allow overriding.
OCR_RECURSIVE="${OCR_RECURSIVE:-1}"
if is_true "$OCR_RECURSIVE"; then
    CMD+=("--recursive")
fi

# 6. Import Only Mode
if is_true "$OCR_IMPORT_ONLY"; then
    CMD+=("--import-only")
fi

# 7. Headed Mode
if is_true "$OCR_HEADED"; then
    CMD+=("--headed")
fi

# 8. Limit
if [ -n "$OCR_LIMIT" ] && [ "$OCR_LIMIT" != "0" ]; then
    CMD+=("--limit" "$OCR_LIMIT")
fi

# --- Execution / Debug ---

# If PRINT_ARGS is set to 1, print the command in shell-escaped format and exit.
if [ -n "$PRINT_ARGS" ] && [ "$PRINT_ARGS" == "1" ]; then
    printf "Starting Gemini OCR with command: "
    printf "%q " "${CMD[@]}"
    printf "\n"
    exit 0
fi

# Standard execution logging (simplified view)
echo "Starting Gemini OCR with command: ${CMD[*]}"

# Execute the constructed command
exec "${CMD[@]}"
