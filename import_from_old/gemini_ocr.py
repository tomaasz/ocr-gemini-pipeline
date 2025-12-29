#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Tuple, Dict, Any
from enum import Enum, auto

from playwright.sync_api import sync_playwright, Page, Locator, TimeoutError as PlaywrightTimeoutError

from gemini_config import UI_TIMEOUTS
from gemini_metrics import DocumentMetrics

# NEW: DB writer
try:
    from db_writer import MinimalDbWriter, db_config_from_env
    HAS_DB = True
except Exception:
    HAS_DB = False


class GeminiError(RuntimeError):
    """Base class for Gemini OCR errors."""
    pass


class GeminiTimeoutError(GeminiError):
    """Raised when an operation times out (upload, prompt, generation)."""
    pass


class GeminiRuntimeError(GeminiError):
    """Raised when a runtime error occurs (e.g. element not found)."""
    pass


class ComposerState(Enum):
    EMPTY = auto()
    ATTACHED = auto()
    ANALYZING = auto()
    READY = auto()


# ----------------------------
# Logging / Debug
# ----------------------------

def ts() -> str:
    return time.strftime("%H:%M:%S")


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def ensure_dir(p: Optional[Path]) -> None:
    if p:
        p.mkdir(parents=True, exist_ok=True)


def dump_debug(page: Page, debug_dir: Optional[Path], tag: str) -> None:
    if not debug_dir:
        return
    ensure_dir(debug_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", tag)[:120]
    try:
        page.screenshot(path=str(debug_dir / f"{stamp}_{safe}.png"), full_page=True)
    except Exception:
        pass
    try:
        (debug_dir / f"{stamp}_{safe}.html").write_text(page.content(), encoding="utf-8")
    except Exception:
        pass


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ----------------------------
# Prompts
# ----------------------------

def load_prompts(prompts_path: Path) -> dict:
    return json.loads(prompts_path.read_text(encoding="utf-8"))


def get_prompt_text(prompts_json: dict, prompt_id: Optional[str]) -> str:
    default_id = prompts_json.get("default_prompt_id")
    pid = prompt_id or default_id
    if not pid:
        raise RuntimeError("Brak prompt-id oraz default_prompt_id w pliku promptów.")

    for p in (prompts_json.get("prompts") or []):
        if p.get("id") == pid:
            template = p.get("template", "")
            if isinstance(template, list):
                template = "\n".join(template)
            if not isinstance(template, str):
                raise RuntimeError("Pole template w promptach ma nieoczekiwany typ.")
            template = template.strip("\n")
            if not template.strip():
                raise RuntimeError("Prompt template jest pusty.")
            return template

    raise RuntimeError(f"Nie znaleziono promptu o id={pid!r}.")


# ----------------------------
# Files discovery
# ----------------------------

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def iter_images(root: Path, recursive: bool) -> Iterable[Path]:
    if root.is_file():
        if root.suffix.lower() in IMG_EXT:
            yield root
        return

    if not root.exists():
        raise RuntimeError(f"Root nie istnieje: {root}")

    def _scan(p: Path):
        try:
            with os.scandir(p) as it:
                entries = sorted(list(it), key=lambda e: e.name)
                for entry in entries:
                    if entry.is_file():
                        if Path(entry.name).suffix.lower() in IMG_EXT:
                            yield Path(entry.path)
                    elif entry.is_dir() and recursive:
                        yield from _scan(Path(entry.path))
        except OSError as e:
            log(f"Error scanning {p}: {e}")

    yield from _scan(root)


# ----------------------------
# Gemini UI helpers
# ----------------------------

GEMINI_URL = "https://gemini.google.com/app"


def goto_gemini(page: Page, timeout_ms: int, debug_dir: Optional[Path]) -> None:
    log(f"Otwieram: {GEMINI_URL}")
    page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_timeout(600)
    try:
        _ = find_composer(page, timeout_ms=UI_TIMEOUTS["FIND_COMPOSER"])
    except Exception:
        dump_debug(page, debug_dir, "after_open_no_composer")


def find_composer(page: Page, timeout_ms: int = UI_TIMEOUTS["FIND_COMPOSER"]) -> Locator:
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
    raise RuntimeError(f"Nie znalazłem pola wpisywania (composer). last_err={last_err!r}")


def _composer_root(page: Page) -> Locator:
    comp = find_composer(page)
    roots = [
        comp.locator("xpath=ancestor::div[contains(@class,'input-area')]").first,
        comp.locator("xpath=ancestor::div[contains(@class,'input')]").first,
        comp.locator("xpath=ancestor::form").first,
        comp.locator("xpath=ancestor::main").first,
    ]
    for r in roots:
        try:
            if r and r.count() and r.is_visible():
                return r
        except Exception:
            pass
    return page.locator("body")


def _tooltip_visible(page: Page, text_regex: str) -> bool:
    loc = page.locator(
        "div[role='tooltip'], .mat-mdc-tooltip, .mdc-tooltip__surface, .cdk-overlay-container"
    ).filter(has_text=re.compile(text_regex, re.I))
    try:
        return loc.first.is_visible()
    except Exception:
        return False


# ----------------------------
# Attachment detection (FAST, multi-signal)
# ----------------------------

def _is_attachment_present(page: Page) -> bool:
    """
    Wykrywa załącznik po wielu sygnałach. Nie opiera się wyłącznie o 'visible',
    bo Gemini bywa kapryśne (overlay, animacje, lazy render).
    """
    # (1) miniatura blob/data
    for sel in [
        "img[src^='blob:']",
        "img[src^='data:']",
    ]:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            pass

    # (2) elementy “attachment” po data-testid/class
    for sel in [
        "[data-testid*='attach' i]",
        "[data-test-id*='attach' i]",
        "[data-testid*='upload' i]",
        "[data-test-id*='upload' i]",
        "[class*='attachment' i]",
        "[class*='upload' i]",
    ]:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            pass

    # (3) przycisk “Usuń/Remove”
    for sel in [
        "button:has-text('Usuń')",
        "button:has-text('Remove')",
        "[role='button']:has-text('Usuń')",
        "[role='button']:has-text('Remove')",
    ]:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            pass

    # (4) tekstowe sygnały (PL/EN)
    try:
        if page.locator("text=/plik|files|uploaded|załącz|zal[aą]cz/i").count() > 0:
            return True
    except Exception:
        pass

    return False


def wait_attachment_fast(page: Page, timeout_ms: int = 8000, poll_ms: int = 200) -> bool:
    """
    Krótki, reaktywny polling – jeśli UI pokaże załącznik szybko, idziemy dalej od razu.
    """
    t0 = time.time()
    while (time.time() - t0) * 1000 < timeout_ms:
        if _is_attachment_present(page):
            return True
        page.wait_for_timeout(poll_ms)
    return False


def _is_analyzing(page: Page) -> bool:
    stop_text = page.locator("text=/Stop|Zatrzymaj|Anuluj|Cancel|Stop generating/i")
    try:
        if stop_text.count() > 0 and stop_text.first.is_visible():
            return True
    except Exception:
        pass

    stop_aria = page.locator(
        "button[aria-label*='Stop' i], button[aria-label*='Zatrzymaj' i], "
        "button[aria-label*='Anuluj' i], button[aria-label*='Cancel' i]"
    )
    try:
        if stop_aria.count() > 0 and stop_aria.first.is_visible():
            return True
    except Exception:
        pass

    spinners = page.locator("mat-spinner, [role='progressbar'], .spinner, .loading-indicator")
    try:
        if spinners.count() > 0 and spinners.first.is_visible():
            return True
    except Exception:
        pass

    return False


def get_composer_state(page: Page) -> ComposerState:
    if _is_analyzing(page):
        return ComposerState.ANALYZING
    if _is_attachment_present(page):
        return ComposerState.ATTACHED

    try:
        comp = page.locator("div[contenteditable='true']").first
        if comp.count() > 0 and comp.is_visible():
            text = comp.inner_text().strip()
            if not text:
                return ComposerState.EMPTY
            return ComposerState.READY
    except Exception:
        pass

    return ComposerState.READY


# ----------------------------
# Upload helpers
# ----------------------------

def _find_plus_button(page: Page, timeout_ms: int, debug_dir: Optional[Path]) -> Optional[Locator]:
    root = _composer_root(page)
    candidates = root.locator("button, [role='button']")
    n = min(candidates.count(), 140)

    aria_good = [
        re.compile(r"menu\s+przesyłania\s+pliku", re.I),
        re.compile(r"menu\s+przesylania\s+pliku", re.I),
        re.compile(r"dodaj\s+pliki", re.I),
        re.compile(r"upload", re.I),
        re.compile(r"attach", re.I),
        re.compile(r"file", re.I),
        re.compile(r"zał[aą]cz", re.I),
    ]

    for i in range(n):
        el = candidates.nth(i)
        try:
            if not el.is_visible():
                continue
            aria = (el.get_attribute("aria-label") or "").strip()
            if aria and any(rx.search(aria) for rx in aria_good):
                return el
        except Exception:
            continue

    for i in range(n):
        el = candidates.nth(i)
        try:
            if not el.is_visible():
                continue
            aria = (el.get_attribute("aria-label") or "").strip().lower()
            if aria in ("mikrofon", "microphone", "wyślij wiadomość", "wyslij wiadomosc", "send", "send message"):
                continue
            el.hover(timeout=timeout_ms)
            page.wait_for_timeout(150)
            if _tooltip_visible(page, r"\bDodaj\s+pliki\b"):
                return el
        except Exception:
            continue

    dump_debug(page, debug_dir, "plus_not_found")
    return None


def _overlay_upload_button(page: Page) -> Locator:
    overlay = page.locator(".cdk-overlay-container")
    return overlay.locator(
        "button:has-text('Prześlij pliki'), button:has-text('Przeslij pliki'), "
        "button:has-text('Upload files'), button:has-text('Upload file')"
    ).first


def _try_input_type_file(page: Page, img_path: Path) -> bool:
    inputs = page.locator("input[type='file']")
    try:
        cnt = inputs.count()
    except Exception:
        cnt = 0
    if cnt <= 0:
        return False
    for i in range(cnt):
        inp = inputs.nth(i)
        try:
            inp.set_input_files(str(img_path))
            return True
        except Exception:
            continue
    return False


def _try_hidden_trigger_js(page: Page, img_path: Path, timeout_ms: int, debug_dir: Optional[Path]) -> bool:
    selectors = [
        "button[data-test-id='hidden-local-image-upload-button']",
        "button[data-test-id='hidden-local-file-upload-button']",
        "button.hidden-local-file-image-selector-button",
        "button[xapfileselectortrigger]",
    ]
    found = None
    for sel in selectors:
        try:
            if page.locator(sel).count() > 0:
                found = sel
                break
        except Exception:
            pass
    if not found:
        return False

    try:
        with page.expect_file_chooser(timeout=timeout_ms) as fc_info:
            page.evaluate(
                """(sel) => {
                    const el = document.querySelector(sel);
                    if (!el) return false;
                    try { el.removeAttribute('aria-hidden'); } catch(e) {}
                    try { el.scrollIntoView({block:'center', inline:'center'}); } catch(e) {}
                    el.click();
                    return true;
                }""",
                found,
            )
        fc_info.value.set_files(str(img_path))
        return True
    except Exception:
        dump_debug(page, debug_dir, "hidden_trigger_js_failed")
        return False


def upload_image(
    page: Page,
    img_path: Path,
    timeout_ms: int,
    attach_confirm_ms: int,
    attach_hard_fail: bool,
    debug_dir: Optional[Path],
) -> None:
    log(f"upload: start -> {img_path}")
    _ = find_composer(page, timeout_ms=timeout_ms)

    if _try_input_type_file(page, img_path):
        log("upload: OK przez input[type=file]")
        ok = wait_attachment_fast(page, timeout_ms=attach_confirm_ms)
        if ok:
            log("upload: potwierdzono załącznik ✅")
            return
        dump_debug(page, debug_dir, "attach_not_confirmed_input_file")
        msg = f"upload: nie potwierdziłem załącznika w {attach_confirm_ms}ms (input[type=file])"
        if attach_hard_fail:
            raise GeminiTimeoutError(msg)
        log(msg + " — idę dalej (soft).")
        return

    plus_btn = _find_plus_button(page, timeout_ms=timeout_ms, debug_dir=debug_dir)

    if not plus_btn:
        log("upload: nie znalazłem plusa tooltip/aria – próbuję click po współrzędnych (lewy dół composera)")
        try:
            comp = find_composer(page, timeout_ms=timeout_ms)
            box = comp.bounding_box()
            if not box:
                raise RuntimeError("Brak bounding_box composera.")
            x = box["x"] + 22
            y = box["y"] + box["height"] - 22
            page.mouse.click(x, y)
            page.wait_for_timeout(200)
            plus_btn = _find_plus_button(page, timeout_ms=timeout_ms, debug_dir=debug_dir)
        except Exception as e:
            log(f"upload: click po współrzędnych nie pomógł: {e}")

    if not plus_btn:
        log("upload: nadal brak plusa – próbuję hidden trigger JS")
        if _try_hidden_trigger_js(page, img_path, timeout_ms=timeout_ms, debug_dir=debug_dir):
            log("upload: OK przez hidden trigger (JS click)")
            ok = wait_attachment_fast(page, timeout_ms=attach_confirm_ms)
            if ok:
                log("upload: potwierdzono załącznik ✅")
                return
            dump_debug(page, debug_dir, "attach_not_confirmed_hidden_trigger")
            msg = f"upload: nie potwierdziłem załącznika w {attach_confirm_ms}ms (hidden trigger)"
            if attach_hard_fail:
                raise GeminiTimeoutError(msg)
            log(msg + " — idę dalej (soft).")
            return
        raise GeminiRuntimeError("Nie znalazłem '+' (tooltip/aria/koordynaty) ani nie zadziałał hidden trigger.")

    aria = plus_btn.get_attribute("aria-label")
    log(f"upload: klik PLUS aria-label={aria!r}")
    plus_btn.click(force=True, timeout=timeout_ms)

    try:
        log("upload: czekam na overlay z 'Prześlij pliki'")
        _overlay_upload_button(page).wait_for(state="visible", timeout=UI_TIMEOUTS["UPLOAD_OVERLAY"])
        btn = _overlay_upload_button(page)

        log("upload: klik 'Prześlij pliki' + expect_file_chooser")
        with page.expect_file_chooser(timeout=timeout_ms) as fc_info:
            btn.click(force=True, timeout=timeout_ms)
        fc_info.value.set_files(str(img_path))
        log("upload: OK (filechooser.set_files)")
    except Exception as e:
        log(f"upload: overlay/chooser nie zadziałał: {e}")
        dump_debug(page, debug_dir, "upload_overlay_failed")
        if _try_hidden_trigger_js(page, img_path, timeout_ms=timeout_ms, debug_dir=debug_dir):
            log("upload: OK przez hidden trigger (JS click) [fallback]")
        else:
            raise

    ok = wait_attachment_fast(page, timeout_ms=attach_confirm_ms)
    if ok:
        log("upload: potwierdzono załącznik ✅")
        return

    dump_debug(page, debug_dir, "attach_not_confirmed_after_set_files")
    msg = f"upload: nie potwierdziłem załącznika w {attach_confirm_ms}ms — UI bywa zmienne"
    if attach_hard_fail:
        raise GeminiTimeoutError(msg)
    log(msg + " — idę dalej (soft).")


# ----------------------------
# Prompt paste (fast)
# ----------------------------

def paste_prompt_fast(page: Page, text: str, timeout_ms: int, debug_dir: Optional[Path]) -> None:
    comp = find_composer(page, timeout_ms=timeout_ms)
    comp.wait_for(state="visible", timeout=timeout_ms)

    try:
        box = comp.bounding_box()
        if box:
            page.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
        else:
            comp.click(force=True, timeout=timeout_ms)
    except Exception:
        comp.click(force=True, timeout=timeout_ms)

    try:
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
    except Exception:
        pass

    try:
        page.evaluate("(t) => navigator.clipboard.writeText(t)", text)
        page.keyboard.press("Control+V")
    except Exception:
        try:
            page.keyboard.type(text, delay=3)
        except Exception as e:
            dump_debug(page, debug_dir, "prompt_paste_failed")
            raise GeminiRuntimeError(f"Nie udało się wkleić prompta: {e}")

    t0 = time.time()
    while (time.time() - t0) < 3.0:
        try:
            if comp.inner_text().strip():
                log("prompt: wklejony")
                return
        except Exception:
            pass
        page.wait_for_timeout(150)

    log("prompt: UWAGA — nie potwierdziłem tekstu w 3s, ale idziemy dalej (UI bywa opóźnione).")


# ----------------------------
# Send + generation cycle
# ----------------------------

def _find_send_button(page: Page) -> Optional[Locator]:
    root = _composer_root(page)
    rx = re.compile(r"(wyślij|wyslij|prześlij|przeslij|send)", re.I)

    candidates = root.locator("button[aria-label], [role='button'][aria-label]")
    n = min(candidates.count(), 160)
    for i in range(n):
        el = candidates.nth(i)
        try:
            if not el.is_visible():
                continue
            aria = (el.get_attribute("aria-label") or "").strip()
            if aria and rx.search(aria):
                return el
        except Exception:
            continue

    candidates2 = root.locator("button, [role='button']")
    n2 = min(candidates2.count(), 220)
    for i in range(n2):
        el = candidates2.nth(i)
        try:
            if not el.is_visible():
                continue
            el.hover()
            page.wait_for_timeout(150)
            if _tooltip_visible(page, r"\bPrze[śs]lij\b"):
                return el
        except Exception:
            continue

    return None


def send_message_with_retry(page: Page, timeout_ms: int, debug_dir: Optional[Path]) -> None:
    """
    Wysyłka musi być potwierdzona twardym sygnałem:
      - pojawia się STOP/Zatrzymaj/Cancel (generowanie), albo
      - pojawia się element odpowiedzi,
    a nie tylko tym, że przycisk Send zrobił się disabled.
    """
    stop_like = page.locator("text=/Stop|Zatrzymaj|Anuluj|Cancel|Stop generating/i")
    answer_area = page.locator(
        "[data-test-id*='response' i], [data-testid*='response' i], .response-container, .markdown, message-content"
    )

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        log(f"send: próba {attempt}/{max_retries}")

        # 1) Spróbuj kliknąć przycisk Send (jeśli znajdziesz)
        sent = False
        btn = _find_send_button(page)
        if btn:
            try:
                log("send: klikam przycisk 'Prześlij/Wyślij'")
                btn.click(force=True, timeout=timeout_ms)
                sent = True
            except Exception:
                dump_debug(page, debug_dir, f"send_click_failed_{attempt}")

        # 2) Fallback: ENTER w composerze (często najpewniejsze)
        if not sent:
            log("send: fallback -> Enter w composerze")
            try:
                comp = find_composer(page, timeout_ms=timeout_ms)
                comp.click(force=True, timeout=timeout_ms)
                page.keyboard.press("Enter")
                sent = True
            except Exception:
                dump_debug(page, debug_dir, f"send_enter_failed_{attempt}")

        # 3) Twarde potwierdzenie: czekaj na start generowania / odpowiedź
        log("send: czekam na twardy sygnał startu generowania (Stop/odpowiedź)...")
        t0 = time.time()
        while (time.time() - t0) < 8.0:
            try:
                if stop_like.count() > 0 and stop_like.first.is_visible():
                    log("send: potwierdzone ✅ (Stop/Cancel widoczny)")
                    return
            except Exception:
                pass

            try:
                if answer_area.count() > 0:
                    # czasem odpowiedź pojawia się od razu bez 'Stop'
                    log("send: potwierdzone ✅ (elementy odpowiedzi widoczne)")
                    return
            except Exception:
                pass

            page.wait_for_timeout(200)

        # 4) Jeśli brak potwierdzenia – zrób debug i ponów
        log("send: brak potwierdzenia wysłania – retry...")
        dump_debug(page, debug_dir, f"send_no_confirmation_{attempt}")
        page.wait_for_timeout(800)

    dump_debug(page, debug_dir, "send_failed_final")
    raise GeminiTimeoutError("Nie udało się potwierdzić wysłania wiadomości (brak Stop/odpowiedzi).")


def send_message(page: Page, timeout_ms: int, debug_dir: Optional[Path]) -> None:
    send_message_with_retry(page, timeout_ms, debug_dir)


def wait_generation_cycle(page: Page, appear_timeout_ms: int, done_timeout_ms: int, debug_dir: Optional[Path]) -> None:
    stop_like = page.locator("text=/Stop|Zatrzymaj|Anuluj|Cancel|Stop generating/i")
    mic_like = page.locator(
        "button[aria-label='Mikrofon'], button[aria-label='Microphone'], "
        "[role='button'][aria-label='Mikrofon'], [role='button'][aria-label='Microphone']"
    )

    answer_area = page.locator(
        "[data-test-id*='response'], [data-testid*='response'], .response-container, .markdown, message-content, "
        "button:has-text('👍'), button:has-text('👎')"
    )

    log("send: czekam na start generowania (Stop/odpowiedź)...")
    t0 = time.time()
    saw_stop = False
    while (time.time() - t0) * 1000 < appear_timeout_ms:
        page.wait_for_timeout(300)

        try:
            if stop_like.count() > 0 and stop_like.first.is_visible():
                saw_stop = True
                log("send: wykryto stan generowania (Stop/Cancel) ✅")
                break
        except Exception:
            pass

        try:
            if answer_area.count() > 0:
                log("send: wykryto elementy odpowiedzi ✅")
                break
        except Exception:
            pass

    if saw_stop:
        log("ready: czekam aż Stop/Cancel zniknie...")
        t1 = time.time()
        while (time.time() - t1) * 1000 < done_timeout_ms:
            page.wait_for_timeout(500)
            try:
                if stop_like.count() == 0 or not stop_like.first.is_visible():
                    break
            except Exception:
                break
    else:
        page.wait_for_timeout(500)

    log("ready: czekam na gotowość do kolejnego skanu (mikrofon/composer)...")
    t2 = time.time()
    while (time.time() - t2) * 1000 < done_timeout_ms:
        page.wait_for_timeout(500)

        try:
            if stop_like.count() > 0 and stop_like.first.is_visible():
                continue
        except Exception:
            pass

        try:
            if mic_like.count() > 0 and mic_like.first.is_visible():
                log("ready: mikrofon wrócił ✅ (można kolejny skan)")
                return
        except Exception:
            pass

        try:
            comp = page.locator("div[contenteditable='true']").first
            if comp.count() and comp.is_visible():
                log("ready: composer widoczny ✅ (można kolejny skan)")
                return
        except Exception:
            pass

    dump_debug(page, debug_dir, "ready_timeout")
    raise GeminiTimeoutError("Timeout czekania na powrót gotowości (mikrofon/composer).")


def cleanup_composer(page: Page, debug_dir: Optional[Path]) -> bool:
    log("cleanup: próba czyszczenia composera...")

    if get_composer_state(page) == ComposerState.ANALYZING:
        log("cleanup: wykryto stan ANALYZING! Wstrzymuję czyszczenie i czekam na gotowość...")
        wait_generation_cycle(
            page,
            appear_timeout_ms=UI_TIMEOUTS["CLEANUP_WAIT"],
            done_timeout_ms=UI_TIMEOUTS["GEN_DONE"],
            debug_dir=debug_dir
        )
        state = get_composer_state(page)
        if state in (ComposerState.READY, ComposerState.EMPTY):
            log("cleanup: ANALYZING zakończony pomyślnie. (False negative send detected)")
            return True
        log(f"cleanup: timeout czekania na koniec ANALYZING. Stan={state}")
        return False

    remove_btns = page.locator(
        "button[aria-label='Usuń plik'], button[aria-label='Remove file'], "
        "button:has-text('Usuń'), button:has-text('Remove'), .remove-attachment"
    )
    try:
        count = remove_btns.count()
        if count > 0:
            log(f"cleanup: klikam {count} przycisków usuwania załącznika")
            for i in range(count):
                try:
                    remove_btns.nth(i).click(timeout=2000)
                except Exception:
                    pass
            page.wait_for_timeout(500)
    except Exception as e:
        log(f"cleanup: błąd przy usuwaniu załącznika: {e}")

    try:
        comp = find_composer(page, timeout_ms=5000)
        if comp:
            comp.click(force=True)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.wait_for_timeout(500)
    except Exception as e:
        log(f"cleanup: błąd przy czyszczeniu tekstu: {e}")

    state = get_composer_state(page)
    log(f"cleanup: stan końcowy = {state}")

    if state in (ComposerState.READY, ComposerState.EMPTY):
        log("cleanup: SUCCESS ✅")
        return True

    log("cleanup: FAILED ❌ (nadal coś wisi lub analizuje)")
    dump_debug(page, debug_dir, "cleanup_failed")
    return False


# ----------------------------
# Response extraction (NEW)
# ----------------------------

def _candidate_response_locators(page: Page) -> list[Locator]:
    # Uwaga: Gemini zmienia DOM — bierzemy kilka “dobrych” heurystyk.
    sels = [
        "message-content",
        "[data-test-id*='response' i]",
        "[data-testid*='response' i]",
        ".response-container",
        ".markdown",
        "div:has(button:has-text('👍'))",
        "div:has(button:has-text('👎'))",
    ]
    return [page.locator(sel) for sel in sels]


def extract_latest_response_text(page: Page, timeout_ms: int, debug_dir: Optional[Path]) -> str:
    """
    Próbuje wyciągnąć tekst ostatniej odpowiedzi. To jest kluczowe do DB i plików.
    """
    t0 = time.time()
    last_err: Optional[Exception] = None

    while (time.time() - t0) * 1000 < timeout_ms:
        try:
            for loc in _candidate_response_locators(page):
                try:
                    n = loc.count()
                except Exception:
                    n = 0
                if n <= 0:
                    continue

                # Bierzemy “ostatni” element z danej heurystyki
                for idx in range(n - 1, max(-1, n - 8), -1):
                    el = loc.nth(idx)
                    try:
                        if not el.is_visible():
                            continue
                        txt = el.inner_text().strip()
                        # odfiltruj “puste” / UI-only
                        if txt and len(txt) >= 20:
                            return txt
                    except Exception as e:
                        last_err = e
                        continue
        except Exception as e:
            last_err = e

        page.wait_for_timeout(250)

    dump_debug(page, debug_dir, "extract_response_failed")
    raise GeminiTimeoutError(f"Nie udało się wyciągnąć tekstu odpowiedzi (timeout). last_err={last_err!r}")


# ----------------------------
# Output files (NEW)
# ----------------------------

def safe_stem(p: Path) -> str:
    # stabilna nazwa pliku wynikowego
    s = p.stem
    s = re.sub(r"[^\w.\-]+", "_", s, flags=re.UNICODE)
    return s[:180] if len(s) > 180 else s


def write_outputs(out_root: Optional[Path], img: Path, response_text: str, meta: Dict[str, Any]) -> None:
    if not out_root:
        return
    ensure_dir(out_root)

    stem = safe_stem(img)
    txt_path = out_root / f"{stem}.txt"
    json_path = out_root / f"{stem}.json"

    txt_path.write_text(response_text, encoding="utf-8")
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


# ----------------------------
# DB write (NEW)
# ----------------------------

def write_to_db_minimal(
    *,
    img: Path,
    response_text: str,
    meta: Dict[str, Any],
    started_at: datetime,
    finished_at: datetime,
) -> Tuple[int, int]:
    if not HAS_DB:
        raise RuntimeError("Brak db_writer/psycopg2 w środowisku (HAS_DB=False). Dodaj psycopg2-binary i plik db_writer.py.")

    writer = MinimalDbWriter(db_config_from_env())
    try:
        doc_id = writer.upsert_document(
            source_path=str(img),
            file_name=img.name,
            source_sha256=meta.get("source_sha256"),
            doc_type=meta.get("doc_type", "unknown"),
            confidence=meta.get("confidence"),
            issues=meta.get("issues"),
            pipeline=meta.get("pipeline", "two-step"),
            run_tag=meta.get("run_tag"),
            status=meta.get("status", "done"),
            processing_by=meta.get("processing_by"),
            processing_started_at=started_at,
            processing_finished_at=finished_at,
        )

        entry_id = writer.upsert_entry(
            doc_id=doc_id,
            entry_no=1,  # minimalnie: 1 entry na dokument
            entry_text=response_text,
            entry_json=meta,
            entry_type=meta.get("entry_type"),
            entry_date=meta.get("entry_date"),
            location=meta.get("location"),
        )

        writer.commit()
        return doc_id, entry_id
    except Exception:
        writer.rollback()
        raise
    finally:
        writer.close()


# ----------------------------
# Main
# ----------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--import-only", action="store_true", help="Only scan files and print them.")

    ap.add_argument("--out-root", default="")
    ap.add_argument("--debug-dir", default="")

    ap.add_argument("--prompts-file", default=str(Path.home() / "gemini_prompts.json"))
    ap.add_argument("--prompt-id", default=None)

    ap.add_argument("--profile-dir", required=False)
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--timeout-ms", type=int, default=UI_TIMEOUTS["PAGE_LOAD"])

    ap.add_argument("--wait-login", action="store_true",
                    help="Zatrzymaj się na ENTER po otwarciu Gemini (gdy trzeba ręcznie zalogować).")

    ap.add_argument("--send", dest="send", action="store_true", help="Po wklejeniu prompta wyślij. (domyślnie)")
    ap.add_argument("--no-send", dest="send", action="store_false", help="Nie wysyłaj automatycznie.")
    ap.set_defaults(send=True)

    ap.add_argument("--pause", dest="pause", action="store_true", help="Zatrzymaj się na końcu (ENTER).")
    ap.add_argument("--no-pause", dest="pause", action="store_false", help="Nie zatrzymuj się na końcu.")
    ap.set_defaults(pause=False)

    ap.add_argument("--pause-each", action="store_true", help="Zatrzymaj po KAŻDYM pliku (ENTER) — debug.")

    ap.add_argument("--attach-confirm-ms", type=int, default=UI_TIMEOUTS["ATTACH_CONFIRM"],
                    help="Ile maks. czekać na szybkie potwierdzenie załącznika w UI (ms).")

    ap.add_argument("--attach-hard-fail", action="store_true",
                    help="Jeśli nie wykryje załącznika w attach-confirm-ms — przerwij (tryb twardy). "
                         "Domyślnie soft (warning + debug i idziemy dalej).")

    ap.add_argument("--gen-appear-timeout-ms", type=int, default=UI_TIMEOUTS["GEN_APPEAR"],
                    help="Ile czekać na start generowania (Stop/odpowiedź) (ms).")
    ap.add_argument("--gen-done-timeout-ms", type=int, default=UI_TIMEOUTS["GEN_DONE"],
                    help="Ile czekać na zakończenie i powrót gotowości (ms).")

    # NEW: DB control / meta
    ap.add_argument("--db", dest="db", action="store_true", help="Zapisuj do PostgreSQL (domyślnie)")
    ap.add_argument("--no-db", dest="db", action="store_false", help="Nie zapisuj do PostgreSQL.")
    ap.set_defaults(db=True)

    ap.add_argument("--doc-type", default="unknown", help="doc_type do ocr_document (default: unknown)")
    ap.add_argument("--pipeline", default="two-step", help="pipeline label do ocr_document (default: two-step)")
    ap.add_argument("--run-tag", default="", help="Opcjonalny run_tag do ocr_document")

    return ap.parse_args()


def process_file_safe(
    page: Page,
    img: Path,
    prompt_text: str,
    args: argparse.Namespace,
    debug_dir: Optional[Path],
    out_root: Optional[Path],
) -> bool:
    """
    Przetwarza jeden plik z logiką retry i obsługą błędów.
    Zwraca True jeśli sukces, False jeśli błąd (po wyczerpaniu retries).
    """
    max_doc_attempts = 2
    metrics = DocumentMetrics(file_name=img.name, start_ts=time.time())

    for attempt in range(1, max_doc_attempts + 1):
        metrics.attempts = attempt
        started_at = datetime.now()

        try:
            log(f"Processing {img.name} (attempt {attempt}/{max_doc_attempts})")

            # 1) Upload
            upload_image(
                page,
                img,
                timeout_ms=args.timeout_ms,
                attach_confirm_ms=args.attach_confirm_ms,
                attach_hard_fail=args.attach_hard_fail,
                debug_dir=debug_dir
            )

            # 2) Paste prompt
            paste_prompt_fast(page, prompt_text, timeout_ms=args.timeout_ms, debug_dir=debug_dir)

            response_text = ""
            if args.send:
                # 3) Send & Wait
                send_message_with_retry(page, timeout_ms=args.timeout_ms, debug_dir=debug_dir)

                wait_generation_cycle(
                    page,
                    appear_timeout_ms=args.gen_appear_timeout_ms,
                    done_timeout_ms=args.gen_done_timeout_ms,
                    debug_dir=debug_dir
                )

                # 4) Extract response (NEW)
                response_text = extract_latest_response_text(
                    page,
                    timeout_ms=min(args.gen_done_timeout_ms, 60_000),
                    debug_dir=debug_dir
                )
                log(f"response: extracted {len(response_text)} chars ✅")
            else:
                log("send disabled (--no-send). Nie ma czego zapisywać (pomijam extraction/DB/output).")

            finished_at = datetime.now()

            # 5) Outputs + DB (NEW)
            if response_text:
                meta: Dict[str, Any] = {
                    "file_name": img.name,
                    "source_path": str(img),
                    "source_sha256": sha256_file(img),
                    "prompt_id": args.prompt_id,
                    "doc_type": args.doc_type,
                    "pipeline": args.pipeline,
                    "run_tag": (args.run_tag or None),
                    "processing_by": os.environ.get("OCR_WORKER_ID") or socket.gethostname(),
                    "status": "done",
                    "started_at": started_at.isoformat(),
                    "finished_at": finished_at.isoformat(),
                    "response_len": len(response_text),
                }

                # save files
                write_outputs(out_root, img, response_text, meta)

                # save DB
                if args.db:
                    doc_id, entry_id = write_to_db_minimal(
                        img=img,
                        response_text=response_text,
                        meta=meta,
                        started_at=started_at,
                        finished_at=finished_at,
                    )
                    log(f"DB: zapisano doc_id={doc_id} entry_id={entry_id} ✅")
                else:
                    log("DB: pominięto (--no-db).")

            metrics.finish("success")
            log(str(metrics))
            return True

        except (GeminiError, PlaywrightTimeoutError) as e:
            log(f"WARN: Błąd przy {img.name} (attempt {attempt}): {e}")
            dump_debug(page, debug_dir, f"error_{img.name}_att{attempt}")

            if attempt >= max_doc_attempts:
                metrics.finish("error", error_reason=str(e))

            try:
                if attempt < max_doc_attempts:
                    log("Próba cleanup przed kolejnym podejściem...")
                    if not cleanup_composer(page, debug_dir):
                        log("Cleanup failed, refreshing page...")
                        goto_gemini(page, timeout_ms=args.timeout_ms, debug_dir=debug_dir)
            except Exception as e2:
                log(f"Cleanup error: {e2}")

        except Exception as e:
            log(f"CRITICAL: Nieoczekiwany wyjątek przy {img.name}: {e}")
            dump_debug(page, debug_dir, f"critical_{img.name}")
            metrics.finish("error", error_reason=f"CRITICAL: {e}")
            log(str(metrics))
            return False

    log(f"ERROR: Wyczerpano limit prób dla {img.name}. Skipping.")
    log(str(metrics))
    return False


def main() -> int:
    args = parse_args()

    root = Path(os.path.expanduser(args.root)).resolve()
    out_root = Path(os.path.expanduser(args.out_root)).resolve() if args.out_root else None
    debug_dir = Path(os.path.expanduser(args.debug_dir)).resolve() if args.debug_dir else None

    if not args.import_only:
        if not args.profile_dir:
            log("Error: --profile-dir is required (unless --import-only is used).")
            return 1
        profile_dir = Path(os.path.expanduser(args.profile_dir)).resolve()
    else:
        profile_dir = None

    prompts_path = Path(os.path.expanduser(args.prompts_file)).resolve()

    # Load prompts
    try:
        log(f"Plik promptów: {prompts_path}")
        prompts_json = load_prompts(prompts_path)
        prompt_text = get_prompt_text(prompts_json, args.prompt_id)
        log(f"Prompt ID: {args.prompt_id or prompts_json.get('default_prompt_id')}")
    except Exception as e:
        if args.import_only:
            log(f"Warning: Failed to load prompts ({e}), but proceeding in import-only mode.")
            prompt_text = ""
        else:
            raise

    if args.import_only:
        log("Tryb IMPORT-ONLY: skanowanie plików...")
        count = 0
        for img in iter_images(root, args.recursive):
            print(f"FOUND: {img}")
            count += 1
            if args.limit and count >= args.limit:
                log(f"Limit {args.limit} reached.")
                break
        log(f"Skanowanie zakończone. Znaleziono: {count}")
        return 0

    log(f"Profil Playwright: {profile_dir}")
    log("Rozpoczynam przetwarzanie (streaming)...")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=(not args.headed),
            args=["--disable-dev-shm-usage", "--no-sandbox", "--start-maximized"],
            viewport=None,
        )
        page = context.new_page()

        try:
            goto_gemini(page, timeout_ms=args.timeout_ms, debug_dir=debug_dir)

            if args.wait_login:
                log("Jeśli widzisz login – zaloguj ręcznie w tym oknie, potem ENTER w terminalu.")
                input()

            count = 0
            for img in iter_images(root, args.recursive):
                count += 1
                log(f"--- [#{count}] {img} ---")

                success = process_file_safe(page, img, prompt_text, args, debug_dir, out_root)

                if not success:
                    log(f"SKIPPED: {img} (failed after retries)")

                if args.pause_each:
                    input("ENTER aby przejść do następnego pliku...")

                if args.limit and count >= args.limit:
                    log(f"Limit {args.limit} reached.")
                    break

            if args.pause:
                input("ENTER aby zakończyć run...")

            return 0

        finally:
            context.close()


if __name__ == "__main__":
    raise SystemExit(main())
