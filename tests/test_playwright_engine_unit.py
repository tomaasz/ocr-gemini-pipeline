from unittest.mock import MagicMock, patch, call
from pathlib import Path
import pytest
from ocr_gemini.engine.playwright_engine import PlaywrightEngine
from ocr_gemini.ui import actions

class TestPlaywrightEngine:
    @pytest.fixture
    def mock_session(self):
        with patch("ocr_gemini.engine.playwright_engine.BrowserSession") as mock:
            yield mock

    @pytest.fixture
    def mock_actions(self):
        with patch("ocr_gemini.engine.playwright_engine.actions") as mock:
            yield mock

    def test_init(self, mock_session):
        engine = PlaywrightEngine(profile_dir=Path("/tmp"), headless=True)
        assert engine.profile_dir == Path("/tmp")
        assert engine.headless is True
        mock_session.assert_called_once()

    def test_start_stop(self, mock_session):
        engine = PlaywrightEngine(profile_dir=Path("/tmp"))
        engine.start()
        engine.session.start.assert_called_with(headless=False, profile_dir=Path("/tmp"))

        engine.stop()
        engine.session.stop.assert_called_once()

    def test_ocr_flow(self, mock_session, mock_actions):
        engine = PlaywrightEngine(profile_dir=Path("/tmp"))
        # Mock page
        mock_page = MagicMock()
        mock_page.url = "https://gemini.google.com/app"
        engine.session.page = mock_page

        # Mock actions
        mock_actions.get_last_response.return_value = "Result text"

        # Mock composer
        mock_composer = MagicMock()
        mock_page.locator.return_value.first = mock_composer

        res = engine.ocr(Path("test.png"), prompt_id="test")

        # Verify navigation (skipped if on url)
        mock_page.goto.assert_not_called()

        # Verify upload
        mock_actions.upload_image.assert_called_once()

        # Verify prompt fill
        mock_page.locator.assert_any_call("div[contenteditable='true']")
        mock_composer.fill.assert_called_with("test")

        # Verify send
        mock_actions.send_message.assert_called_once()

        # Verify result
        assert res.text == "Result text"
        assert res.data["status"] == "success"

    def test_ocr_navigates_if_not_on_site(self, mock_session, mock_actions):
        engine = PlaywrightEngine(profile_dir=Path("/tmp"))
        mock_page = MagicMock()
        mock_page.url = "about:blank"
        engine.session.page = mock_page

        # Mock composer to avoid failure
        mock_page.locator.return_value.first = MagicMock()

        engine.ocr(Path("test.png"), "prompt")

        mock_page.goto.assert_called_with("https://gemini.google.com/app", timeout=60000)
