import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from ocr_gemini.ui.actions import upload_image, ImageUploadFailed

class TestUploadLogic(unittest.TestCase):
    def setUp(self):
        self.page = MagicMock()
        self.image_path = Path("/tmp/fake_image.png")
        self.page.url = "https://gemini.google.com/app"

    @patch("ocr_gemini.ui.actions._composer_root")
    @patch("ocr_gemini.ui.actions.save_debug_artifacts")
    def test_upload_failure_no_path(self, mock_save_debug, mock_composer_root):
        """
        Verifies correct exception when no upload path (direct or menu) works.
        """
        mock_root = MagicMock()
        mock_composer_root.return_value = mock_root

        # Candidate button exists
        mock_candidates = MagicMock()
        mock_candidates.count.return_value = 1
        mock_button = MagicMock()
        mock_button.is_visible.return_value = True
        mock_button.get_attribute.side_effect = lambda attr: "add" if attr == "aria-label" else ""
        mock_button.inner_text.return_value = "Add"
        mock_candidates.nth.return_value = mock_button
        mock_root.locator.return_value = mock_candidates

        # 1. Direct path fails (Timeout)
        cm_fail = MagicMock()
        cm_fail.__exit__.side_effect = Exception("Timeout")
        self.page.expect_file_chooser.return_value = cm_fail

        # 2. Menu path fails (Menu not visible or not found)
        # We simulate menu not found by making locator return empty/invisible for menu check
        # But wait, logic uses page.locator(...)
        # We need to ensure page.locator does NOT return a visible menu
        # self.page.locator(...) returns MagicMock by default, which is "visible" by default truthiness if not checked properly?
        # NO, is_visible() returns MagicMock object which is truthy.
        # So we MUST mock is_visible to return False for menu.

        def locator_side_effect(selector, **kwargs):
            m = MagicMock()
            # If looking for menu
            if "role='menu'" in selector:
                m.first.is_visible.return_value = False
                return m
            # If looking for input[type=file] fallback
            if "input" in selector and "file" in selector:
                # Fallback wait_for fails
                m.first.wait_for.side_effect = Exception("Timeout")
                return m

            return m

        self.page.locator.side_effect = locator_side_effect
        self.page.frames = []

        with self.assertRaises(ImageUploadFailed) as cm:
            upload_image(self.page, self.image_path, timeout_ms=100)

        self.assertIn("Could not establish upload path", str(cm.exception))
        self.assertTrue(mock_save_debug.called)

    @patch("ocr_gemini.ui.actions._composer_root")
    def test_upload_menu_flow_success(self, mock_composer_root):
        """
        Verifies successful upload via menu flow.
        """
        mock_root = MagicMock()
        mock_composer_root.return_value = mock_root

        mock_candidates = MagicMock()
        mock_candidates.count.return_value = 1
        add_button = MagicMock()
        add_button.is_visible.return_value = True
        add_button.get_attribute.side_effect = lambda attr: "add" if attr == "aria-label" else ""
        add_button.inner_text.return_value = "Add"
        mock_candidates.nth.return_value = add_button
        mock_root.locator.return_value = mock_candidates

        # expect_file_chooser sequence: 1. Fail (Timeout), 2. Success
        cm_fail = MagicMock()
        cm_fail.__exit__.side_effect = Exception("Timeout waiting for chooser 1")

        cm_success = MagicMock()
        cm_success.__exit__.return_value = None
        fc_info = MagicMock()
        fc_info.value = MagicMock()
        cm_success.__enter__.return_value = fc_info

        self.page.expect_file_chooser.side_effect = [cm_fail, cm_success]

        # Locator strategy
        def locator_side_effect(selector, **kwargs):
            m = MagicMock()
            if "role='menu'" in selector or "mat-mdc-menu-panel" in selector:
                # Menu found and visible
                m.first.is_visible.return_value = True

                items = MagicMock()
                target_item = MagicMock()
                target_item.is_visible.return_value = True
                items.filter.return_value.first = target_item
                m.locator.return_value = items
                return m

            # Preview check success
            if "img" in selector or "attachment" in selector:
                # _wait_for_preview calls loc.first.wait_for(...)
                m.first.wait_for.return_value = None
                return m

            return m

        self.page.locator.side_effect = locator_side_effect

        # Should succeed
        upload_image(self.page, self.image_path, timeout_ms=5000)

    @patch("ocr_gemini.ui.actions._composer_root")
    @patch("ocr_gemini.ui.actions.save_debug_artifacts")
    def test_upload_success_signal_missing(self, mock_save_debug, mock_composer_root):
        """
        Verifies failure when upload path works but preview never appears.
        """
        mock_root = MagicMock()
        mock_composer_root.return_value = mock_root

        # Setup candidate -> Direct path succeeds immediately for simplicity
        mock_candidates = MagicMock()
        mock_candidates.count.return_value = 1
        mock_button = MagicMock()
        mock_button.is_visible.return_value = True
        mock_button.get_attribute.side_effect = lambda attr: "add" if attr == "aria-label" else ""
        mock_button.inner_text.return_value = "Add"
        mock_candidates.nth.return_value = mock_button
        mock_root.locator.return_value = mock_candidates

        # Direct chooser succeeds
        cm_success = MagicMock()
        cm_success.__exit__.return_value = None
        fc_info = MagicMock()
        fc_info.value = MagicMock()
        cm_success.__enter__.return_value = fc_info
        self.page.expect_file_chooser.return_value = cm_success

        # Locator strategy: Preview check FAILS
        def locator_side_effect(selector, **kwargs):
            m = MagicMock()
            if "img" in selector or "attachment" in selector:
                # _wait_for_preview calls loc.first.wait_for(...)
                # Simulate timeout waiting for visible
                m.first.wait_for.side_effect = Exception("Timeout waiting for preview")
                return m
            return m

        self.page.locator.side_effect = locator_side_effect

        with self.assertRaises(ImageUploadFailed) as cm:
            upload_image(self.page, self.image_path, timeout_ms=100)

        self.assertIn("Upload triggered but success signal (preview) did not appear", str(cm.exception))
        self.assertTrue(mock_save_debug.called)

if __name__ == '__main__':
    unittest.main()
