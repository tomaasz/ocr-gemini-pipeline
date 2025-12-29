#!/bin/bash
# Regression test for ops/systemd/gemini-ocr-run.sh wrapper
# Ensures arguments are constructed correctly, specifically handling spaces and preventing duplicates.

WRAPPER_SCRIPT="ops/systemd/gemini-ocr-run.sh"

# Ensure the wrapper is executable
chmod +x "$WRAPPER_SCRIPT"

# Define test environment variables
export PYTHON_EXEC="/bin/python3"
export SCRIPT_FILE="/app/gemini_ocr.py"
export OCR_ROOT="/home/user/My Documents/Scans"  # Path with spaces
export OCR_OUT_ROOT="/home/user/ocr_out"
export OCR_PROMPT_ID="test_prompt"
export OCR_PROFILE_DIR="/home/user/.profile"
export OCR_RECURSIVE="1"
export OCR_LIMIT="5"
export OCR_HEADED="0"
export OCR_IMPORT_ONLY="false"
export PRINT_ARGS="1"

echo "Running wrapper with PRINT_ARGS=1..."
OUTPUT=$($WRAPPER_SCRIPT)
EXIT_CODE=$?

echo "Output: $OUTPUT"

if [ $EXIT_CODE -ne 0 ]; then
    echo "FAIL: Wrapper exited with code $EXIT_CODE"
    exit 1
fi

# 1. Check for duplicate --out-root
OUT_ROOT_COUNT=$(echo "$OUTPUT" | grep -o "\-\-out-root" | wc -l)
if [ "$OUT_ROOT_COUNT" -ne 1 ]; then
    echo "FAIL: --out-root appears $OUT_ROOT_COUNT times (expected 1)"
    exit 1
fi

# 2. Check for presence of --prompt-id
if ! echo "$OUTPUT" | grep -q "\-\-prompt-id test_prompt"; then
    echo "FAIL: --prompt-id argument missing or incorrect"
    exit 1
fi

# 3. Check for correct handling of path with spaces
# We expect the shell-escaped output to match the input path.
# printf %q will output /home/user/My\ Documents/Scans
EXPECTED_PART="/home/user/My\ Documents/Scans"

# We use grep -F (fixed string) to avoid regex interpretation of backslashes
if ! echo "$OUTPUT" | grep -F -q "$EXPECTED_PART"; then
    echo "FAIL: OCR_ROOT path with spaces not found correctly in output."
    echo "Expected part: $EXPECTED_PART"
    exit 1
fi

echo "SUCCESS: All regression checks passed."
exit 0
