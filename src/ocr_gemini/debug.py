from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional


def save_debug_artifacts(page: Any, debug_dir: Optional[Path], label: str) -> None:
    """
    Saves debug artifacts (screenshot, HTML, metadata) if debug_dir is set and page is available.

    Args:
        page: Playwright Page object (or mock with screenshot/content methods).
        debug_dir: Directory to save artifacts to. If None, does nothing.
        label: Label for the artifacts (e.g. 'error_cleanup').
    """
    if not debug_dir:
        return

    if not page:
        print("Warning: save_debug_artifacts called with page=None")
        return

    try:
        # Create directory if it doesn't exist
        debug_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize label
        # 1. Allow only alphanumeric, dot, underscore, hyphen
        safe_chars = "".join(c for c in label if c.isalnum() or c in "._-")
        # 2. Limit length (e.g., 50 chars)
        safe_label = safe_chars[:50]
        if not safe_label:
             safe_label = "unknown"

        # Generate safe filename timestamp + label
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        base_name = f"{timestamp}_{safe_label}"

        # Save screenshot
        try:
            screenshot_path = debug_dir / f"{base_name}.png"
            # Duck-typing: check if method exists
            if hasattr(page, "screenshot"):
                 page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception as e:
            print(f"Warning: Failed to save debug screenshot: {e}")

        # Save HTML
        try:
            html_path = debug_dir / f"{base_name}.html"
            if hasattr(page, "content"):
                content = page.content()
                html_path.write_text(content, encoding="utf-8")
        except Exception as e:
            print(f"Warning: Failed to save debug HTML: {e}")

        # Save Metadata
        try:
            meta_path = debug_dir / f"{base_name}_meta.txt"
            url = getattr(page, "url", "unknown")
            meta_content = f"Timestamp: {timestamp}\nLabel: {label}\nSafeLabel: {safe_label}\nURL: {url}\n"
            meta_path.write_text(meta_content, encoding="utf-8")
        except Exception as e:
            print(f"Warning: Failed to save debug metadata: {e}")

    except Exception as e:
        print(f"Error saving debug artifacts: {e}")
