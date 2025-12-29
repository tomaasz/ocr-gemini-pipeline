import pytest

from gemini_ocr import ComposerState, get_composer_state

# === Selektory 1:1 z gemini_ocr.py ===
STOP_SELECTOR = "text=/Stop|Zatrzymaj|Anuluj|Cancel|Stop generating/i"
ATTACHMENT_SELECTOR = "img[src^='blob:']"
COMPOSER_SELECTOR = "div[contenteditable='true']"


class FakeLocator:
    def __init__(self, *, count=0, visible=False, text=""):
        self._count = count
        self._visible = visible
        self._text = text

    def count(self):
        return self._count

    @property
    def first(self):
        return self

    def is_visible(self):
        return self._visible

    def inner_text(self):
        return self._text


class FakePage:
    """
    Minimalny fake Page, żeby testować logikę get_composer_state()
    bez uruchamiania Playwright.
    """
    def __init__(self, mapping):
        self.mapping = mapping

    def locator(self, selector):
        return self.mapping.get(selector, FakeLocator(count=0, visible=False, text=""))


def test_state_analyzing_when_stop_visible():
    page = FakePage({
        STOP_SELECTOR: FakeLocator(count=1, visible=True),
    })
    assert get_composer_state(page) == ComposerState.ANALYZING


def test_state_attached_when_attachment_present_and_not_analyzing():
    page = FakePage({
        STOP_SELECTOR: FakeLocator(count=0, visible=False),
        ATTACHMENT_SELECTOR: FakeLocator(count=1, visible=True),
    })
    assert get_composer_state(page) == ComposerState.ATTACHED


def test_state_empty_when_composer_visible_but_text_empty():
    page = FakePage({
        STOP_SELECTOR: FakeLocator(count=0, visible=False),
        ATTACHMENT_SELECTOR: FakeLocator(count=0, visible=False),
        COMPOSER_SELECTOR: FakeLocator(count=1, visible=True, text="   "),
    })
    assert get_composer_state(page) == ComposerState.EMPTY


def test_state_ready_when_composer_has_text():
    page = FakePage({
        STOP_SELECTOR: FakeLocator(count=0, visible=False),
        ATTACHMENT_SELECTOR: FakeLocator(count=0, visible=False),
        COMPOSER_SELECTOR: FakeLocator(count=1, visible=True, text="hello"),
    })
    assert get_composer_state(page) == ComposerState.READY
