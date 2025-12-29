#!/usr/bin/env python3
import sys
from pathlib import Path

# Add project root to sys.path to allow importing modules
sys.path.append(str(Path(__file__).parent.parent))

try:
    import gemini_config
    print("--- Effective Gemini OCR Configuration ---")
    print(f"{'TIMEOUT':<35} | {'VALUE (ms)':<10}")
    print("-" * 50)
    for key, val in gemini_config.UI_TIMEOUTS.items():
        print(f"{key:<35} | {val:<10}")
    print("-" * 50)
    print("To override, set env vars like: export GEMINI_TIMEOUT_PAGE_LOAD=300000")
except ImportError:
    print("Error: Could not import gemini_config. Run this script from the project root or scripts/ folder.")
    sys.exit(1)
