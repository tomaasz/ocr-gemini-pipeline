
import unittest
import re
from pathlib import Path
from unittest.mock import MagicMock, patch
from ocr_gemini.ui.actions import _try_filechooser_upload, upload_image, ImageUploadFailed, MENU_DETECTION_TIMEOUT_MS

class TestPolishUploadDetection(unittest.TestCase):
    def setUp(self):
        self.page = MagicMock()
        self.page.locator.return_value.count.return_value = 0
        self.image_path = Path("/tmp/fake_image.png")
        self.page.url = "https://gemini.google.com/app"

    @patch("ocr_gemini.ui.actions._composer_root")
    def test_regex_button_matches_polish(self, mock_composer_root):
        """
        Indirectly verify the regex by mocking the DOM elements to have Polish labels.
        """
        # Labels to test
        labels = [
            ("aria-label", "Otwórz menu przesyłania pliku"),
            ("aria-label", "Przesyłania pliku"),
            ("inner_text", "Wczytaj"),
            ("inner_text", "Załącz"),
            ("inner_text", "Dodaj"),
            ("aria-label", "Prześlij zdjęcie"),
        ]

        for attr, text in labels:
            with self.subTest(label=text):
                self._verify_match(mock_composer_root, attr, text)

    def _verify_match(self, mock_composer_root, attr, text):
        # Reset mocks
        self.page.reset_mock()
        mock_root = MagicMock()
        mock_composer_root.return_value = mock_root

        # Setup candidate
        mock_candidates = MagicMock()
        mock_candidates.count.return_value = 1
        btn = MagicMock()
        btn.is_visible.return_value = True

        if attr == "aria-label":
            btn.get_attribute.side_effect = lambda a: text if a == "aria-label" else ""
            btn.inner_text.return_value = ""
        else:
            btn.get_attribute.return_value = ""
            btn.inner_text.return_value = text

        mock_candidates.nth.return_value = btn
        mock_root.locator.return_value = mock_candidates

        # Mock expect_file_chooser to succeed immediately
        cm_success = MagicMock()
        cm_success.__exit__.return_value = None
        fc_info = MagicMock()
        fc_info.value = MagicMock()
        cm_success.__enter__.return_value = fc_info
        self.page.expect_file_chooser.return_value = cm_success

        # Run
        result = _try_filechooser_upload(self.page, "/tmp/f.png", 1000)

        self.assertTrue(result, f"Failed to detect button with {attr}='{text}'")
        self.assertTrue(self.page.expect_file_chooser.called)

    @patch("ocr_gemini.ui.actions._composer_root")
    @patch("ocr_gemini.ui.actions.save_debug_artifacts")
    def test_upload_via_polish_menu_trigger(self, mock_save_debug, mock_composer_root):
        """
        Verifies that a button with 'Otwórz menu przesyłania pliku' triggers the menu flow
        WITHOUT wrapping the initial click in expect_file_chooser.
        """
        mock_root = MagicMock()
        mock_composer_root.return_value = mock_root

        # 1. Setup candidate button: The "+" button
        mock_candidates = MagicMock()
        mock_candidates.count.return_value = 1
        plus_button = MagicMock()
        plus_button.is_visible.return_value = True
        plus_button.get_attribute.side_effect = lambda attr: "Otwórz menu przesyłania pliku" if attr == "aria-label" else ""
        plus_button.inner_text.return_value = "+"
        mock_candidates.nth.return_value = plus_button
        mock_root.locator.return_value = mock_candidates

        # 2. Setup Menu and Menu Item
        def locator_side_effect(selector, **kwargs):
            m = MagicMock()
            if "role='menu'" in selector or "mat-mdc-menu-panel" in selector:
                # The menu container
                m.first.is_visible.return_value = True

                # Mock the items inside the menu
                items = MagicMock()

                # The "Prześlij plik" item
                target_item = MagicMock()
                target_item.is_visible.return_value = True

                # filter(has_text=...).first -> target_item
                items.filter.return_value.first = target_item
                m.locator.return_value = items
                return m

            if "img" in selector or "attachment" in selector:
                # Success signal (preview)
                m.first.wait_for.return_value = None
                return m

            return m

        self.page.locator.side_effect = locator_side_effect

        # 3. Setup expect_file_chooser
        cm_success = MagicMock()
        cm_success.__exit__.return_value = None
        fc_info = MagicMock()
        fc_info.value = MagicMock()
        cm_success.__enter__.return_value = fc_info

        self.page.expect_file_chooser.side_effect = [cm_success, MagicMock()] # Should only be called once

        # Run
        upload_image(self.page, self.image_path, timeout_ms=1000)

        # Assertions
        # 1. The initial button should have been clicked.
        plus_button.click.assert_called()

        # 2. expect_file_chooser should have been called exactly once (for the menu item)
        self.assertEqual(self.page.expect_file_chooser.call_count, 1, "Should have skipped the blind expect_file_chooser")

    @patch("ocr_gemini.ui.actions._composer_root")
    @patch("ocr_gemini.ui.actions.save_debug_artifacts")
    def test_legacy_fallback_preserved(self, mock_save_debug, mock_composer_root):
        """
        Anti-regression: If button is generic 'Add' (not explicit menu), it MUST attempt direct file chooser first.
        """
        mock_root = MagicMock()
        mock_composer_root.return_value = mock_root

        # 1. Generic button (e.g. English "Add")
        mock_candidates = MagicMock()
        mock_candidates.count.return_value = 1
        btn = MagicMock()
        btn.is_visible.return_value = True
        btn.get_attribute.side_effect = lambda attr: "Add" if attr == "aria-label" else ""
        btn.inner_text.return_value = "+"
        mock_candidates.nth.return_value = btn
        mock_root.locator.return_value = mock_candidates

        # 2. expect_file_chooser:
        # Should be called immediately for the direct attempt.
        cm_success = MagicMock()
        cm_success.__exit__.return_value = None
        fc_info = MagicMock()
        fc_info.value = MagicMock()
        cm_success.__enter__.return_value = fc_info

        self.page.expect_file_chooser.return_value = cm_success

        # Mocks for success signal
        def locator_side_effect(selector, **kwargs):
            m = MagicMock()
            if "img" in selector or "attachment" in selector:
                m.first.wait_for.return_value = None
                return m
            return m
        self.page.locator.side_effect = locator_side_effect

        # Run
        upload_image(self.page, self.image_path, timeout_ms=1000)

        # Assertions
        # Should have called expect_file_chooser on the FIRST try (direct)
        self.assertEqual(self.page.expect_file_chooser.call_count, 1)
        # And it succeeded.

    @patch("ocr_gemini.ui.actions._composer_root")
    @patch("ocr_gemini.ui.actions.save_debug_artifacts")
    def test_failure_artifacts(self, mock_save_debug, mock_composer_root):
        """
        Anti-regression: On failure (no path works), artifacts MUST be saved.
        """
        mock_root = MagicMock()
        mock_composer_root.return_value = mock_root

        # Setup: No valid buttons found
        mock_root.locator.return_value.count.return_value = 0
        self.page.frames = []

        # Make fallback inputs fail wait_for
        def locator_side_effect(selector, **kwargs):
             m = MagicMock()
             if "input" in selector and "file" in selector:
                 m.first.wait_for.side_effect = Exception("Timeout")
                 return m
             # Default fallback
             m.count.return_value = 0
             return m

        self.page.locator.side_effect = locator_side_effect

        with self.assertRaises(ImageUploadFailed):
            upload_image(self.page, self.image_path, timeout_ms=100)

        # Verify artifacts saved
        self.assertTrue(mock_save_debug.called)
        args, _ = mock_save_debug.call_args
        self.assertEqual(args[2], "upload_failed_explicit")

if __name__ == '__main__':
    unittest.main()
