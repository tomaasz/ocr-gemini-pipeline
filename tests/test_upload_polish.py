
import unittest
import re
from unittest.mock import MagicMock, patch
from ocr_gemini.ui.actions import _try_filechooser_upload, MENU_DETECTION_TIMEOUT_MS

class TestPolishUploadDetection(unittest.TestCase):
    def setUp(self):
        self.page = MagicMock()
        self.page.locator.return_value.count.return_value = 0

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

if __name__ == '__main__':
    unittest.main()
