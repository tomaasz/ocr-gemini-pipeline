from __future__ import annotations

import os


def _get_int(env_var: str, default: int) -> int:
    """Read int from env, fallback to default on missing/invalid."""
    try:
        val = os.getenv(env_var)
        if val:
            return int(val)
    except ValueError:
        pass
    return default


# Centralized timeouts (in milliseconds) used by UI automation (Playwright).
# NOTE: Stage 1 only переносит конфиг; UI code will use this later.
UI_TIMEOUTS: dict[str, int] = {
    # Page load / navigation
    "PAGE_LOAD": _get_int("GEMINI_TIMEOUT_PAGE_LOAD", 180_000),
    "FIND_COMPOSER": _get_int("GEMINI_TIMEOUT_FIND_COMPOSER", 60_000),
    # Upload & Attachment
    "UPLOAD_OVERLAY": _get_int("GEMINI_TIMEOUT_UPLOAD_OVERLAY", 20_000),
    "ATTACH_CONFIRM": _get_int("GEMINI_TIMEOUT_ATTACH_CONFIRM", 8_000),
    # Prompt & Send
    "PROMPT_PASTE": _get_int("GEMINI_TIMEOUT_PROMPT_PASTE", 10_000),
    "SEND_CONFIRM": _get_int("GEMINI_TIMEOUT_SEND_CONFIRM", 30_000),
    # Generation cycle
    "GEN_APPEAR": _get_int("GEMINI_TIMEOUT_GEN_APPEAR", 20_000),
    "GEN_DONE": _get_int("GEMINI_TIMEOUT_GEN_DONE", 240_000),
    # Cleanup / Recovery
    "CLEANUP_WAIT": _get_int("GEMINI_TIMEOUT_CLEANUP_WAIT", 5_000),
}
