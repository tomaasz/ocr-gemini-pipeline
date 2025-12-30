"""
UI Actions for Gemini OCR.

This module contains resilient UI interaction logic ported from the legacy runner.
It focuses on stability and error recovery (retries, fallbacks).

Legacy evidence:
- legacy/gemini_ocr.py lines 543-644 (send_message_with_retry, _find_send_button)
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page, Locator

from ..debug import save_debug_artifacts


class UIActionError(RuntimeError):
    """Base class for UI action errors."""
    pass


class UIActionTimeoutError(UIActionError):
    """Raised when an action times out."""
    pass


def _find_composer(page: Page, timeout_ms: int = 2000) -> Locator:
    """
    Locates the contenteditable composer div.
    Legacy evidence: legacy/gemini_ocr.py lines 177-189
    """
    t0 = time.time()
    last_err = None
    while (time.time() - t0) * 1000 < timeout_ms:
        try:
            loc = page.locator("div[contenteditable='true']").first
            if loc.count() and loc.is_visible():
                return loc
        except Exception as e:
            last_err = e
        page.wait_for_timeout(200)
    raise UIActionTimeoutError(f"Composer not found. last_err={last_err!r}")


def _composer_root(page: Page) -> Locator:
    """
    Finds the root container of the composer to scope searches.
    Legacy evidence: legacy/gemini_ocr.py lines 192-206
    """
    try:
        comp = _find_composer(page, timeout_ms=1000)
    except UIActionTimeoutError:
        return page.locator("body")

    roots = [
        comp.locator("xpath=ancestor::div[contains(@class,'input-area')]").first,
        comp.locator("xpath=ancestor::div[contains(@class,'input')]").first,
        comp.locator("xpath=ancestor::form").first,
        comp.locator("xpath=ancestor::main").first,
    ]
    for r in roots:
        try:
            if r.count() and r.is_visible():
                return r
        except Exception:
            pass
    return page.locator("body")


def _tooltip_visible(page: Page, text_regex: str) -> bool:
    """
    Checks if a tooltip with matching text is visible.
    Legacy evidence: legacy/gemini_ocr.py lines 209-216
    """
    loc = page.locator(
        "div[role='tooltip'], .mat-mdc-tooltip, .mdc-tooltip__surface, .cdk-overlay-container"
    ).filter(has_text=re.compile(text_regex, re.I))
    try:
        return loc.first.is_visible()
    except Exception:
        return False


def _find_send_button(page: Page) -> Optional[Locator]:
    """
    Heuristic search for the Send button using aria-labels and tooltips.
    Legacy evidence: legacy/gemini_ocr.py lines 543-581
    """
    root = _composer_root(page)
    rx = re.compile(r"(wyślij|wyslij|prześlij|przeslij|send)", re.I)

    # 1. ARIA labels (fastest)
    candidates = root.locator("button[aria-label], [role='button'][aria-label]")
    try:
        n = min(candidates.count(), 160)
        for i in range(n):
            el = candidates.nth(i)
            if not el.is_visible():
                continue
            aria = (el.get_attribute("aria-label") or "").strip()
            if aria and rx.search(aria):
                return el
    except Exception:
        pass

    # 2. Tooltips (slower, requires hover)
    candidates2 = root.locator("button, [role='button']")
    try:
        n2 = min(candidates2.count(), 220)
        for i in range(n2):
            el = candidates2.nth(i)
            if not el.is_visible():
                continue
            try:
                el.hover(timeout=200)
                page.wait_for_timeout(100)
                if _tooltip_visible(page, r"\bPrze[śs]lij\b"):
                    return el
            except Exception:
                continue
    except Exception:
        pass

    return None


def wait_for_generation_complete(
    page: Page, timeout_ms: int, debug_dir: Optional[Path] = None
) -> None:
    """
    Waits for the generation to complete by observing the Stop button.

    Logic:
    1. Wait for "Stop" button to appear (generation started).
       - Uses a short timeout (5000ms).
       - If it doesn't appear, we assume generation finished very quickly or never
         showed the button (per user req: "Stop never appeared -> treat as already finished").
    2. Wait for "Stop" button to disappear (generation finished).

    Args:
        page: Playwright Page object.
        timeout_ms: Max time to wait for completion.
        debug_dir: Directory to save debug artifacts on failure.
    """
    stop_like = page.locator("text=/Stop|Zatrzymaj|Anuluj|Cancel|Stop generating/i")

    # 1. Wait for Start (Stop button visible)
    try:
        # We use a short timeout because send_message likely already confirmed start.
        # But if we are called late, it might already be gone.
        stop_like.first.wait_for(state="visible", timeout=5000)
    except Exception:
        # "Stop never appeared -> treat as already finished"
        # We log nothing or maybe debug log if we had a logger.
        pass

    # 2. Wait for Finish (Stop button hidden)
    try:
        stop_like.first.wait_for(state="hidden", timeout=timeout_ms)
    except Exception:
        save_debug_artifacts(page, debug_dir, "wait_gen_complete_timeout")
        raise UIActionTimeoutError(
            f"Generation did not complete (Stop button still visible) within {timeout_ms}ms"
        )


def send_message(
    page: Page,
    send_timeout_ms: int = 5000,
    confirm_timeout_ms: int = 10000,
    generation_timeout_ms: int = 120000,
    debug_dir: Optional[Path] = None,
) -> None:
    """
    Resiliently sends the message in the composer.

    Ported from legacy/gemini_ocr.py lines 584-644 (send_message_with_retry).

    Strategy:
    1. Try clicking the "Send" button (if found).
    2. Fallback: Focus composer and press Enter.
    3. Confirm generation started (Stop button or response container).
    4. Wait for generation to complete (Stop button disappears).

    Args:
        page: Playwright Page object.
        send_timeout_ms: Max time to attempt triggering the send action.
        confirm_timeout_ms: Max time to wait for confirmation (generation start).
        generation_timeout_ms: Max time to wait for generation to complete.
        debug_dir: Directory to save debug artifacts on failure.

    Raises:
        UIActionTimeoutError: If sending fails or confirmation is not received.
    """
    stop_like = page.locator("text=/Stop|Zatrzymaj|Anuluj|Cancel|Stop generating/i")
    answer_area = page.locator(
        "[data-test-id*='response' i], [data-testid*='response' i], .response-container, .markdown, message-content"
    )

    max_retries = 3
    # Distribute send_timeout_ms across retries roughly
    per_try_timeout = max(1000, send_timeout_ms // max_retries)

    for attempt in range(1, max_retries + 1):
        sent = False

        # 1) Try clicking "Send"
        try:
            btn = _find_send_button(page)
            if btn:
                btn.click(force=True, timeout=per_try_timeout)
                sent = True
        except Exception:
            # save debug but don't fail yet, try fallback
            save_debug_artifacts(page, debug_dir, f"send_click_failed_{attempt}")

        # 2) Fallback: Enter in composer
        if not sent:
            try:
                comp = _find_composer(page, timeout_ms=per_try_timeout)
                comp.click(force=True, timeout=per_try_timeout)
                page.keyboard.press("Enter")
                sent = True
            except Exception:
                save_debug_artifacts(page, debug_dir, f"send_enter_failed_{attempt}")

        # 3) Confirmation check
        t0 = time.time()
        confirmed = False
        while (time.time() - t0) * 1000 < confirm_timeout_ms:
            try:
                if stop_like.count() > 0 and stop_like.first.is_visible():
                    confirmed = True
                    break
            except Exception:
                pass

            try:
                if answer_area.count() > 0:
                    confirmed = True
                    break
            except Exception:
                pass

            page.wait_for_timeout(200)

        if confirmed:
            # 4) Wait for generation complete
            wait_for_generation_complete(page, generation_timeout_ms, debug_dir)
            return

        # If we are here, confirmation timed out for this attempt.
        save_debug_artifacts(page, debug_dir, f"send_no_confirmation_{attempt}")
        page.wait_for_timeout(500)  # Wait a bit before retry

    # If all retries failed
    save_debug_artifacts(page, debug_dir, "send_failed_final")
    raise UIActionTimeoutError("Failed to send message (no confirmation detected).")
