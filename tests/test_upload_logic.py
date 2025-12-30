import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from ocr_gemini.ui.actions import upload_image, UIActionTimeoutError, UIActionError

class TestUploadReproduction(unittest.TestCase):
    def setUp(self):
        self.page = MagicMock()
        self.image_path = Path("/tmp/fake_image.png")
        self.page.url = "https://gemini.google.com/app"

    @patch("ocr_gemini.ui.actions._composer_root")
    @patch("ocr_gemini.ui.actions.save_debug_artifacts")
    def test_upload_failure_no_input_no_chooser(self, mock_save_debug, mock_composer_root):
        print("\n--- Running test_upload_failure_no_input_no_chooser ---")
        mock_root = MagicMock()
        mock_composer_root.return_value = mock_root

        mock_candidates = MagicMock()
        mock_candidates.count.return_value = 1
        mock_button = MagicMock()
        mock_button.is_visible.return_value = True
        mock_button.get_attribute.side_effect = lambda attr: "add" if attr == "aria-label" else ""
        mock_button.inner_text.return_value = "Add"
        mock_candidates.nth.return_value = mock_button
        mock_root.locator.return_value = mock_candidates

        cm_fail = MagicMock()
        cm_fail.__exit__.side_effect = Exception("Timeout")
        self.page.expect_file_chooser.return_value = cm_fail

        # Ensure preview check fails too (loc.count() > 0)
        # But here we want it to timeout.
        # If loc.count() returns mock, it raises TypeError.
        # So we should mock it to return 0.

        # We can set side_effect on page.locator to handle preview.
        # But test_upload_failure_no_input_no_chooser relies on mocking page.locator.return_value...

        preview_mock = MagicMock()
        preview_mock.first.count.return_value = 0 # Wait, loc.count() is on locator, not first?
        # loc = page.locator(...).first
        # loc.count() ? No. locator(...).first is a locator.
        # .count() is usually called on the locator BEFORE .first?
        # In upload_image:
        # loc = page.locator(preview_selector).first
        # if loc.count() > 0 ...
        # This seems wrong in upload_image?
        # Locator.first refers to the first matching element.
        # Does .first have .count()?
        # Playwright Locator API: .first returns a Locator. .count() returns number of elements matching the locator.
        # If locator was specific to one element, count is 1 or 0.

        # Anyway, we need to mock it.

        mock_loc_preview = MagicMock()
        mock_loc_preview.count.return_value = 0

        # We need to make sure page.locator(...).first returns mock_loc_preview
        self.page.locator.return_value.first = mock_loc_preview
        # But wait, we also mock wait_for on it.
        self.page.locator.return_value.first.wait_for.side_effect = Exception("Timeout")

        self.page.frames = []

        with self.assertRaises(UIActionError):
            upload_image(self.page, self.image_path, timeout_ms=100)

        self.assertTrue(mock_save_debug.called)

    @patch("ocr_gemini.ui.actions._composer_root")
    def test_upload_menu_flow_simulation(self, mock_composer_root):
        print("\n--- Running test_upload_menu_flow_simulation ---")
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

        cm_fail = MagicMock()
        cm_fail.__exit__.side_effect = Exception("Timeout waiting for chooser 1")

        cm_success = MagicMock()
        cm_success.__exit__.return_value = None
        fc_info = MagicMock()
        fc_info.value = MagicMock()
        cm_success.__enter__.return_value = fc_info

        self.page.expect_file_chooser.side_effect = [cm_fail, cm_success]

        def locator_side_effect(selector, **kwargs):
            if "role='menu'" in selector or "mat-mdc-menu-panel" in selector:
                m = MagicMock()
                m.first.is_visible.return_value = True
                items = MagicMock()
                target_item = MagicMock()
                target_item.is_visible.return_value = True
                items.filter.return_value.first = target_item
                m.locator.return_value = items
                return m

            # For preview selector (or anything else)
            loc = MagicMock()
            loc.first = loc # make loc.first return itself for chaining
            loc.count.return_value = 1 # Found it!
            loc.is_visible.return_value = True
            return loc

        self.page.locator.side_effect = locator_side_effect

        try:
            upload_image(self.page, self.image_path, timeout_ms=5000)
        except UIActionError as e:
            self.fail(f"upload_image raised UIActionError: {e}")

if __name__ == '__main__':
    unittest.main()
