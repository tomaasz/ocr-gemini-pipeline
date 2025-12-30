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
    page: Page,
    timeout_ms: int,
    stability_ms: int = 500,
    debug_dir: Optional[Path] = None,
) -> None:
    """
    Waits for the generation to complete by observing the Stop button or response.

    Logic:
    1. Wait for "Stop" button to appear (generation started) with short timeout (5s).
    2. If Stop appeared:
       - Wait for "Stop" to disappear (generation finished).
       - Perform stability check (ensure it stays hidden).
    3. If Stop NEVER appeared:
       - Check if Response container is visible.
       - If yes: assume fast generation -> Success.
       - If no: Failure (neither Stop nor Response found).

    Args:
        page: Playwright Page object.
        timeout_ms: Max time to wait for completion.
        stability_ms: Time to wait after Stop disappears to ensure no flicker.
        debug_dir: Directory to save debug artifacts on failure.
    """
    stop_like = page.locator("text=/Stop|Zatrzymaj|Anuluj|Cancel|Stop generating/i")
    answer_area = page.locator(
        "[data-test-id*='response' i], [data-testid*='response' i], .response-container, .markdown, message-content"
    )

    stop_appeared = False
    try:
        # 1. Wait for Start (Stop button visible)
        stop_like.first.wait_for(state="visible", timeout=5000)
        stop_appeared = True
    except Exception:
        stop_appeared = False

    if stop_appeared:
        # 2. Wait for Finish (Stop button hidden)
        try:
            stop_like.first.wait_for(state="hidden", timeout=timeout_ms)

            # Stability check
            if stability_ms > 0:
                page.wait_for_timeout(stability_ms)
                if stop_like.first.is_visible():
                    # Stop button flickered back! Wait again.
                    stop_like.first.wait_for(state="hidden", timeout=timeout_ms)

        except Exception:
            save_debug_artifacts(page, debug_dir, "wait_gen_stuck_visible")
            raise UIActionTimeoutError(
                f"Generation stuck: Stop button still visible after {timeout_ms}ms"
            )
    else:
        # 3. Stop never appeared - check for fast generation
        try:
            if answer_area.count() > 0 and answer_area.first.is_visible():
                return  # Success: Fast generation
        except Exception:
            pass

        # Failure: No signal found
        save_debug_artifacts(page, debug_dir, "wait_gen_no_signal")
        raise UIActionTimeoutError(
            "Generation verification failed: Stop button never appeared and no response container found."
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
            wait_for_generation_complete(
                page, generation_timeout_ms, debug_dir=debug_dir
            )
            return

        # If we are here, confirmation timed out for this attempt.
        save_debug_artifacts(page, debug_dir, f"send_no_confirmation_{attempt}")
        page.wait_for_timeout(500)  # Wait a bit before retry

    # If all retries failed
    save_debug_artifacts(page, debug_dir, "send_failed_final")
    raise UIActionTimeoutError("Failed to send message (no confirmation detected).")


def upload_image(
    page: Page,
    image_path: Path,
    timeout_ms: int = 10000,
    debug_dir: Optional[Path] = None,
) -> None:
    """
    Uploads an image to the chat interface.

    Strategy:
    1. Find file input element and set files.
    2. Wait for thumbnail/attachment indicator to appear.
       Contract: UI signal (thumbnail visible) determines upload success.

    Args:
        page: Playwright Page object.
        image_path: Path to the image file.
        timeout_ms: Max time for upload process.
        debug_dir: Debug directory.
    """
    try:
        # Heuristic: Find hidden file input.
        # Use first file input found (usually correct for single chat interface).
        file_input = page.locator('input[type="file"]').first

        # Ensure image path is absolute/resolved
        resolved_path = image_path.resolve()

        # Set files
        file_input.set_input_files(str(resolved_path), timeout=timeout_ms // 2)

        # Wait for confirmation (thumbnail)
        # Search for an image preview inside the composer area or broadly.
        # Often previews have blob: src or are inside a specific container.
        # We'll search for an 'img' that is NOT a button icon/avatar.
        # Using a broad check for now: img[src^='blob:'], or specific classes if known.
        # Fallback: just wait a moment if no specific selector is reliable without inspection.
        # However, to meet the requirement "Wait for deterministic UI signal", we try to find a blob image.

        # Try to find the preview.
        # This selector targets images with blob sources (common for previews)
        # or images inside known preview containers.
        preview = page.locator(
            "img[src^='blob:'], .file-preview img, [data-testid='attachment-thumbnail']"
        ).first

        preview.wait_for(state="visible", timeout=timeout_ms // 2)

    except Exception as e:
        save_debug_artifacts(page, debug_dir, "upload_failed")
        raise UIActionError(f"Failed to upload image {image_path.name}: {e}")


def get_last_response(page: Page) -> str:
    """
    Extracts text from the last response container.

    Warning: This relies on DOM order (taking the last container).
    It assumes the last response container corresponds to the last sent message.

    Args:
        page: Playwright Page object.

    Returns:
        Extracted text or empty string if no response found.
    """
    answer_area = page.locator(
        "[data-test-id*='response' i], [data-testid*='response' i], .response-container, .markdown, message-content"
    )

    try:
        count = answer_area.count()
        if count == 0:
            return ""

        # Get the last element
        last_response = answer_area.nth(count - 1)
        return last_response.inner_text()
    except Exception:
        return ""
