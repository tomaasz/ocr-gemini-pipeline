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


class ImageUploadFailed(UIActionError):
    """Raised when image upload fails (no path found or no success signal)."""
    pass


MENU_DETECTION_TIMEOUT_MS = 2000


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
        n = min(candidates.count(), 200)
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
        n2 = min(candidates2.count(), 260)
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
    """
    stop_like = page.locator("text=/Stop|Zatrzymaj|Anuluj|Cancel|Stop generating/i")
    answer_area = page.locator(
        "[data-test-id*='response' i], [data-testid*='response' i], .response-container, .markdown, message-content"
    )

    stop_appeared = False
    try:
        stop_like.first.wait_for(state="visible", timeout=5000)
        stop_appeared = True
    except Exception:
        stop_appeared = False

    if stop_appeared:
        try:
            stop_like.first.wait_for(state="hidden", timeout=timeout_ms)

            if stability_ms > 0:
                page.wait_for_timeout(stability_ms)
                if stop_like.first.is_visible():
                    stop_like.first.wait_for(state="hidden", timeout=timeout_ms)

        except Exception:
            save_debug_artifacts(page, debug_dir, "wait_gen_stuck_visible")
            raise UIActionTimeoutError(
                f"Generation stuck: Stop button still visible after {timeout_ms}ms"
            )
    else:
        try:
            if answer_area.count() > 0 and answer_area.first.is_visible():
                return
        except Exception:
            pass

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
    """
    stop_like = page.locator("text=/Stop|Zatrzymaj|Anuluj|Cancel|Stop generating/i")
    answer_area = page.locator(
        "[data-test-id*='response' i], [data-testid*='response' i], .response-container, .markdown, message-content"
    )

    max_retries = 3
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
            wait_for_generation_complete(
                page, generation_timeout_ms, debug_dir=debug_dir
            )
            return

        save_debug_artifacts(page, debug_dir, f"send_no_confirmation_{attempt}")
        page.wait_for_timeout(500)

    save_debug_artifacts(page, debug_dir, "send_failed_final")
    raise UIActionTimeoutError("Failed to send message (no confirmation detected).")


def _assert_on_gemini_chat(page: Page) -> None:
    """
    Gemini potrafi przekierować na:
    - myactivity.google.com (ustawienia aktywności / zgody)
    - accounts.google.com (logowanie)
    - ogólne consent / interstitiale

    W takich stanach upload i tak nie ma sensu.
    """
    url = (page.url or "").lower()
    if "myactivity.google.com" in url or "accounts.google.com" in url:
        raise UIActionError(
            f"Nie jesteś na ekranie czatu Gemini (URL={page.url}). "
            "To wygląda na przekierowanie do aktywności / logowania. "
            "Otwórz Gemini w profilu Playwright i dokończ logowanie/zgody, potem uruchom skrypt ponownie."
        )


def _try_filechooser_upload(page: Page, file_path: str, trigger_budget_ms: int) -> bool:
    """
    Attempts to trigger upload via file chooser, handling both direct buttons and menu-based flows.
    """
    # Regex for the initial button ("Add", "Plus", "Attach")
    rx_btn = re.compile(
        r"(upload|attach|add|file|image|photo|picture|"
        r"prześlij|przeslij|załącz|zalacz|dodaj|plik|obraz|zdj[eę]cie|grafika)",
        re.I,
    )

    # Regex for the menu item if the button opens a menu
    rx_menu = re.compile(
        r"(upload|image|photo|picture|computer|device|"
        r"prześlij|obraz|zdj[eę]cie|komputer|urządzeni)",
        re.I,
    )

    root = _composer_root(page)
    candidates = root.locator("button, [role='button']")
    n = min(candidates.count(), 320)

    for i in range(n):
        el = candidates.nth(i)
        try:
            if not el.is_visible():
                continue

            # Check if button matches "Add/Attach" logic
            aria = (el.get_attribute("aria-label") or "").strip()
            title = (el.get_attribute("title") or "").strip()
            txt = ""
            try:
                txt = (el.inner_text() or "").strip()
            except Exception:
                pass

            blob = " ".join([aria, title, txt]).strip()

            if not blob or not rx_btn.search(blob):
                continue

            # Attempt 1: Direct click expecting file chooser
            # We use a short timeout because if it's a menu, it will timeout quickly.
            try:
                # Short timeout to detect if it's NOT a direct file chooser.
                # This constant is a probe timeout, not a hard limit for the user.
                with page.expect_file_chooser(timeout=MENU_DETECTION_TIMEOUT_MS) as fc_info:
                    el.click(timeout=1000)

                chooser = fc_info.value
                chooser.set_files(file_path)
                return True
            except Exception:
                # If direct upload failed (likely timeout), check if a menu opened
                try:
                    # Look for common menu containers
                    menu = page.locator(
                        "div[role='menu'], ul[role='menu'], .mat-mdc-menu-panel, [data-role='menu']"
                    ).first
                    if menu.is_visible():
                        # Search for upload item within the menu
                        items = menu.locator("[role='menuitem'], button, li")
                        target = items.filter(has_text=rx_menu).first
                        if target.is_visible():
                            with page.expect_file_chooser(
                                timeout=trigger_budget_ms
                            ) as fc_info_2:
                                target.click(timeout=1000)
                            chooser = fc_info_2.value
                            chooser.set_files(file_path)
                            return True
                except Exception:
                    pass

                # If neither worked, loop continues to next candidate
                pass

        except Exception:
            continue

    return False


def upload_image(
    page: Page,
    image_path: Path,
    timeout_ms: int = 10000,
    debug_dir: Optional[Path] = None,
) -> None:
    """
    Uploads an image to the chat interface.

    Robust strategy:
    0) Upewnij się, że jesteśmy na Gemini chat (nie myactivity/accounts).
    1) Prefer FileChooser (klik w ikonę/przycisk, expect_file_chooser, set_files).
    2) Fallback: input[type=file] (page + frames), set_input_files.
    3) Wait for deterministic UI signal (preview/attachment appears).
    """
    resolved_path = image_path.expanduser().resolve()
    file_path = str(resolved_path)

    trigger_budget = max(4000, timeout_ms // 2)
    preview_budget = max(4000, timeout_ms - trigger_budget)

    preview_selector = (
        "img[src^='blob:'], "
        "[data-testid*='attachment' i], "
        "[data-test-id*='attachment' i], "
        ".file-preview img"
    )

    def _wait_for_preview(deadline_ms: int) -> None:
        try:
            # Use wait_for(state="visible") for reliable state-based wait
            # rather than blind sleeps or polling loops.
            page.locator(preview_selector).first.wait_for(
                state="visible", timeout=deadline_ms
            )
        except Exception as e:
            raise ImageUploadFailed(
                f"Upload triggered but success signal (preview) did not appear within {deadline_ms}ms. "
                f"Last error: {e}"
            )

    try:
        _assert_on_gemini_chat(page)

        # 1) FileChooser approach
        if _try_filechooser_upload(page, file_path, trigger_budget):
            _wait_for_preview(preview_budget)
            return

        # 2) Fallback: input[type=file] in main page
        try:
            inp = page.locator('input[type="file"]').first
            inp.wait_for(state="attached", timeout=trigger_budget)
            inp.set_input_files(file_path, timeout=trigger_budget)
            _wait_for_preview(preview_budget)
            return
        except Exception:
            pass

        # 3) Fallback: frames
        for fr in page.frames:
            try:
                inp = fr.locator('input[type="file"]').first
                inp.wait_for(state="attached", timeout=3000)
                inp.set_input_files(file_path, timeout=trigger_budget)
                _wait_for_preview(preview_budget)
                return
            except Exception:
                continue

        raise ImageUploadFailed(
            f"Could not establish upload path. Attempted: Direct FileChooser (timeout {MENU_DETECTION_TIMEOUT_MS}ms), "
            "Menu 'Upload image' item, and input[type=file] fallback."
        )

    except ImageUploadFailed:
        save_debug_artifacts(page, debug_dir, "upload_failed_explicit")
        raise
    except Exception as e:
        save_debug_artifacts(page, debug_dir, "upload_failed_unexpected")
        raise ImageUploadFailed(f"Failed to upload image {image_path.name}: {e}") from e


def get_last_response(page: Page) -> str:
    """
    Extracts text from the last response container.
    """
    answer_area = page.locator(
        "[data-test-id*='response' i], [data-testid*='response' i], .response-container, .markdown, message-content"
    )

    try:
        count = answer_area.count()
        if count == 0:
            return ""
        last_response = answer_area.nth(count - 1)
        return last_response.inner_text()
    except Exception:
        return ""
