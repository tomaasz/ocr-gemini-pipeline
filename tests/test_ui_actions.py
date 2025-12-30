import unittest
from unittest.mock import MagicMock, patch

from ocr_gemini.ui.actions import (
    send_message,
    UIActionTimeoutError,
    wait_for_generation_complete,
)


def _make_signal(visible: bool = True, count: int = 1) -> MagicMock:
    """
    Helper: creates a Playwright-like Locator mock with:
      - .count() -> int
      - .first.is_visible() -> bool
    """
    loc = MagicMock()
    loc.count.return_value = count
    loc.first.is_visible.return_value = visible
    return loc


class TestSendLogic(unittest.TestCase):
    def setUp(self):
        self.page = MagicMock()
        # keyboard is used by fallback path
        self.page.keyboard = MagicMock()
        # default: any locator query yields a "confirmation signal"
        self.page.locator.side_effect = lambda *_args, **_kwargs: _make_signal(True, 1)

    @patch("ocr_gemini.ui.actions._find_send_button")
    @patch("ocr_gemini.ui.actions._find_composer")
    def test_send_success_via_button(self, mock_find_composer, mock_find_send_button):
        """Scenario A: Button found, click succeeds, confirmation signal appears."""
        mock_btn = MagicMock()
        mock_find_send_button.return_value = mock_btn
        mock_find_composer.return_value = MagicMock()

        send_message(self.page, send_timeout_ms=50, confirm_timeout_ms=50)

        mock_btn.click.assert_called()
        self.page.keyboard.press.assert_not_called()

    @patch("ocr_gemini.ui.actions._find_send_button")
    @patch("ocr_gemini.ui.actions._find_composer")
    def test_send_success_via_fallback_enter(self, mock_find_composer, mock_find_send_button):
        """Scenario B: Button missing, Enter fallback used, confirmation signal appears."""
        mock_find_send_button.return_value = None
        mock_composer = MagicMock()
        mock_find_composer.return_value = mock_composer

        send_message(self.page, send_timeout_ms=50, confirm_timeout_ms=50)

        mock_composer.click.assert_called()
        self.page.keyboard.press.assert_called_with("Enter")

    @patch("ocr_gemini.ui.actions._find_send_button")
    @patch("ocr_gemini.ui.actions._find_composer")
    @patch("ocr_gemini.ui.actions.save_debug_artifacts")
    def test_send_failure_timeout(self, mock_save_debug, mock_find_composer, mock_find_send_button):
        """Scenario C: No confirmation signal -> UIActionTimeoutError + debug artifacts."""
        mock_find_send_button.return_value = None
        mock_find_composer.return_value = MagicMock()

        # All locator queries return "no confirmation"
        self.page.locator.side_effect = lambda *_args, **_kwargs: _make_signal(False, 0)

        with self.assertRaises(UIActionTimeoutError):
            send_message(self.page, send_timeout_ms=20, confirm_timeout_ms=20)

        self.assertTrue(mock_save_debug.called)

    @patch("ocr_gemini.ui.actions.wait_for_generation_complete")
    @patch("ocr_gemini.ui.actions._find_send_button")
    @patch("ocr_gemini.ui.actions._find_composer")
    def test_send_calls_wait_generation(
        self, mock_find_composer, mock_find_send_button, mock_wait_generation
    ):
        """Scenario: Send succeeds, confirmation succeeds -> calls wait_for_generation_complete."""
        mock_btn = MagicMock()
        mock_find_send_button.return_value = mock_btn
        mock_find_composer.return_value = MagicMock()

        send_message(self.page, send_timeout_ms=50, confirm_timeout_ms=50)

        mock_wait_generation.assert_called_once()


class TestWaitGeneration(unittest.TestCase):
    def setUp(self):
        self.page = MagicMock()
        # Mock stop button locator
        self.stop_locator = MagicMock()
        self.page.locator.return_value = self.stop_locator
        # .first.wait_for(...) calls
        self.first = self.stop_locator.first

    def test_wait_normal_flow(self):
        """Scenario: Stop visible then hidden."""
        wait_for_generation_complete(self.page, timeout_ms=100)
        # Should wait for visible first, then hidden
        self.first.wait_for.assert_any_call(state="visible", timeout=5000)
        self.first.wait_for.assert_any_call(state="hidden", timeout=100)

    def test_wait_never_visible(self):
        """Scenario: Stop never visible (timeout on first wait) -> should not raise."""
        # Simulate timeout on wait_for(visible)
        self.first.wait_for.side_effect = [Exception("Timeout"), None]

        wait_for_generation_complete(self.page, timeout_ms=100)

        # Verify it proceeded to check hidden
        self.assertEqual(self.first.wait_for.call_count, 2)

    @patch("ocr_gemini.ui.actions.save_debug_artifacts")
    def test_wait_timeout_on_hidden(self, mock_save_debug):
        """Scenario: Stop visible, but never becomes hidden -> raises TimeoutError."""
        # First call succeeds (visible), second fails (hidden timeout)
        self.first.wait_for.side_effect = [None, Exception("Timeout")]

        with self.assertRaises(UIActionTimeoutError):
            wait_for_generation_complete(self.page, timeout_ms=100)

        self.assertTrue(mock_save_debug.called)
