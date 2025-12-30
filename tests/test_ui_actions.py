import unittest
from unittest.mock import MagicMock, patch, call
from src.ocr_gemini.ui.actions import send_message, UIActionTimeoutError

class TestSendLogic(unittest.TestCase):

    def setUp(self):
        self.page = MagicMock()
        self.debug_dir = None

    @patch("src.ocr_gemini.ui.actions._find_send_button")
    @patch("src.ocr_gemini.ui.actions._find_composer")
    def test_send_success_via_button(self, mock_find_composer, mock_find_send_button):
        """Scenario A: Button found, click succeeds, 'Stop' appears immediately."""
        # 1. Setup _find_send_button to return a mock button
        mock_btn = MagicMock()
        mock_find_send_button.return_value = mock_btn

        # 2. Setup confirmation signal (Stop button visible)
        # The code checks: stop_like.count() > 0 and stop_like.first.is_visible()
        stop_signal = MagicMock()
        stop_signal.count.return_value = 1
        stop_signal.first.is_visible.return_value = True

        # page.locator is used to find stop_like
        def locator_side_effect(selector):
            if "Stop" in selector:
                return stop_signal
            return MagicMock()
        self.page.locator.side_effect = locator_side_effect

        send_message(self.page, send_timeout_ms=100, confirm_timeout_ms=100)

        # Assert button was clicked
        mock_btn.click.assert_called()
        # Assert fallback (Enter) was NOT used
        self.page.keyboard.press.assert_not_called()

    @patch("src.ocr_gemini.ui.actions._find_send_button")
    @patch("src.ocr_gemini.ui.actions._find_composer")
    def test_send_success_via_fallback(self, mock_find_composer, mock_find_send_button):
        """Scenario B: Button missing, Enter fallback succeeds, response appears."""
        # 1. _find_send_button returns None
        mock_find_send_button.return_value = None

        # 2. _find_composer returns a mock composer
        mock_composer = MagicMock()
        mock_find_composer.return_value = mock_composer

        # 3. Setup confirmation signal (Response area visible)
        response_area = MagicMock()
        response_area.count.return_value = 1

        # page.locator is used to find response_area
        def locator_side_effect(selector):
            if "Stop" in selector:
                return MagicMock(count=lambda: 0) # No stop button
            if "response" in selector:
                return response_area
            return MagicMock()
        self.page.locator.side_effect = locator_side_effect

        send_message(self.page, send_timeout_ms=100, confirm_timeout_ms=100)

        # Assert composer was clicked and Enter pressed
        mock_composer.click.assert_called()
        self.page.keyboard.press.assert_called_with("Enter")

    @patch("src.ocr_gemini.ui.actions._find_send_button")
    @patch("src.ocr_gemini.ui.actions._find_composer")
    @patch("src.ocr_gemini.ui.actions.save_debug_artifacts")
    def test_send_failure_timeout(self, mock_save_debug, mock_find_composer, mock_find_send_button):
        """Scenario C: Timeout (no confirmation signal) -> verify UIActionTimeoutError raised."""
        # 1. Button missing
        mock_find_send_button.return_value = None

        # 2. Composer found
        mock_composer = MagicMock()
        mock_find_composer.return_value = mock_composer

        # 3. No confirmation signals
        self.page.locator.return_value.count.return_value = 0

        with self.assertRaises(UIActionTimeoutError):
            send_message(self.page, send_timeout_ms=50, confirm_timeout_ms=50)

        # Assert save_debug_artifacts was called (multiple times likely)
        self.assertTrue(mock_save_debug.called)
