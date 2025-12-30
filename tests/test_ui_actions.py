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

    @patch("ocr_gemini.ui.actions.wait_for_generation_complete")
    @patch("ocr_gemini.ui.actions._find_send_button")
    @patch("ocr_gemini.ui.actions._find_composer")
    def test_send_success_via_button(
        self, mock_find_composer, mock_find_send_button, mock_wait_gen
    ):
        """Scenario A: Button found, click succeeds, confirmation signal appears."""
        mock_btn = MagicMock()
        mock_find_send_button.return_value = mock_btn
        mock_find_composer.return_value = MagicMock()

        send_message(self.page, send_timeout_ms=50, confirm_timeout_ms=50)

        mock_btn.click.assert_called()
        self.page.keyboard.press.assert_not_called()
        mock_wait_gen.assert_called()

    @patch("ocr_gemini.ui.actions.wait_for_generation_complete")
    @patch("ocr_gemini.ui.actions._find_send_button")
    @patch("ocr_gemini.ui.actions._find_composer")
    def test_send_success_via_fallback_enter(
        self, mock_find_composer, mock_find_send_button, mock_wait_gen
    ):
        """Scenario B: Button missing, Enter fallback used, confirmation signal appears."""
        mock_find_send_button.return_value = None
        mock_composer = MagicMock()
        mock_find_composer.return_value = mock_composer

        send_message(self.page, send_timeout_ms=50, confirm_timeout_ms=50)

        mock_composer.click.assert_called()
        self.page.keyboard.press.assert_called_with("Enter")
        mock_wait_gen.assert_called()

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

        # We need distinct mocks for "Stop" locator and "Answer" locator.
        # page.locator is called twice in function.
        # 1st call: stop_like
        # 2nd call: answer_area
        self.stop_locator = MagicMock()
        self.answer_locator = MagicMock()

        self.page.locator.side_effect = [self.stop_locator, self.answer_locator]

        # Shortcuts for verification
        self.stop_first = self.stop_locator.first
        self.answer_first = self.answer_locator.first

    def test_wait_normal_flow(self):
        """Scenario: Stop visible then hidden. Stability check clean."""
        # Stop visible succeeds, Stop hidden succeeds
        # Stability check: stop visible? -> False
        self.stop_first.is_visible.return_value = False

        wait_for_generation_complete(self.page, timeout_ms=100, stability_ms=50)

        # Should wait for visible first, then hidden
        self.stop_first.wait_for.assert_any_call(state="visible", timeout=5000)
        self.stop_first.wait_for.assert_any_call(state="hidden", timeout=100)
        # And stability wait
        self.page.wait_for_timeout.assert_called_with(50)

    def test_wait_fast_generation(self):
        """Scenario: Stop never visible, but Answer IS visible -> Success."""
        # wait_for(visible) raises Timeout
        self.stop_first.wait_for.side_effect = Exception("Timeout")

        # Answer visible check -> True
        self.answer_locator.count.return_value = 1
        self.answer_first.is_visible.return_value = True

        wait_for_generation_complete(self.page, timeout_ms=100)

        # Should catch exception and return cleanly

    @patch("ocr_gemini.ui.actions.save_debug_artifacts")
    def test_wait_failure_no_signal(self, mock_save_debug):
        """Scenario: Stop never visible AND Answer NOT visible -> Failure."""
        self.stop_first.wait_for.side_effect = Exception("Timeout")

        # Answer not visible
        self.answer_locator.count.return_value = 1
        self.answer_first.is_visible.return_value = False

        with self.assertRaisesRegex(UIActionTimeoutError, "never appeared"):
            wait_for_generation_complete(self.page, timeout_ms=100)

        self.assertTrue(mock_save_debug.called)

    @patch("ocr_gemini.ui.actions.save_debug_artifacts")
    def test_wait_timeout_on_hidden(self, mock_save_debug):
        """Scenario: Stop visible, but never becomes hidden -> raises TimeoutError."""
        # First call succeeds (visible), second fails (hidden timeout)
        self.stop_first.wait_for.side_effect = [None, Exception("Timeout")]

        with self.assertRaisesRegex(UIActionTimeoutError, "Generation stuck"):
            wait_for_generation_complete(self.page, timeout_ms=100)

        self.assertTrue(mock_save_debug.called)

    def test_wait_stability_flicker(self):
        """Scenario: Stop hidden, but flickers back during stability check."""
        # 1. Stop visible OK
        # 2. Stop hidden OK
        # 3. Stability check: is_visible -> True (Flicker!)
        # 4. Wait for hidden again OK

        self.stop_first.wait_for.side_effect = [None, None, None]
        self.stop_first.is_visible.return_value = True # Flicker

        wait_for_generation_complete(self.page, timeout_ms=100, stability_ms=50)

        # Check wait_for calls: visible(5000), hidden(100), hidden(100)
        calls = self.stop_first.wait_for.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0].kwargs['state'], 'visible')
        self.assertEqual(calls[1].kwargs['state'], 'hidden')
        self.assertEqual(calls[2].kwargs['state'], 'hidden')
