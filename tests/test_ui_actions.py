import unittest
from unittest.mock import MagicMock, patch

from ocr_gemini.ui.actions import send_message, UIActionTimeoutError


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
