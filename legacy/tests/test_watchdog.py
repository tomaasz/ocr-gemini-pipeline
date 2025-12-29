import pytest
from pathlib import Path
from unittest.mock import MagicMock, call, patch
import sys

# Add root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from gemini_ocr import process_file_safe, GeminiTimeoutError, GeminiRuntimeError, GeminiError

@pytest.fixture
def mock_page():
    return MagicMock()

@pytest.fixture
def mock_args():
    args = MagicMock()
    args.timeout_ms = 100
    args.attach_confirm_ms = 100
    args.attach_hard_fail = True
    args.gen_appear_timeout_ms = 100
    args.gen_done_timeout_ms = 100
    args.send = True
    return args

def test_process_file_safe_success(mock_page, mock_args):
    # Mock helpers to succeed immediately
    with patch("gemini_ocr.upload_image") as mock_upload, \
         patch("gemini_ocr.paste_prompt_fast") as mock_paste, \
         patch("gemini_ocr.send_message_with_retry") as mock_send, \
         patch("gemini_ocr.wait_generation_cycle") as mock_wait:

        result = process_file_safe(mock_page, Path("test.jpg"), "prompt", mock_args, None)

        assert result is True
        mock_upload.assert_called_once()
        mock_paste.assert_called_once()
        mock_send.assert_called_once()
        mock_wait.assert_called_once()

def test_process_file_safe_retry_then_success(mock_page, mock_args):
    # Mock upload to fail first time, then succeed
    with patch("gemini_ocr.upload_image") as mock_upload, \
         patch("gemini_ocr.paste_prompt_fast") as mock_paste, \
         patch("gemini_ocr.send_message_with_retry") as mock_send, \
         patch("gemini_ocr.wait_generation_cycle") as mock_wait, \
         patch("gemini_ocr.cleanup_composer", return_value=True) as mock_cleanup:

        mock_upload.side_effect = [GeminiTimeoutError("Upload timeout"), None]

        result = process_file_safe(mock_page, Path("test.jpg"), "prompt", mock_args, None)

        assert result is True
        assert mock_upload.call_count == 2
        mock_cleanup.assert_called_once()

def test_process_file_safe_exhaust_retries(mock_page, mock_args):
    # Mock upload to always fail
    with patch("gemini_ocr.upload_image") as mock_upload, \
         patch("gemini_ocr.cleanup_composer", return_value=True) as mock_cleanup, \
         patch("gemini_ocr.goto_gemini") as mock_goto:

        mock_upload.side_effect = GeminiTimeoutError("Upload timeout")

        result = process_file_safe(mock_page, Path("test.jpg"), "prompt", mock_args, None)

        assert result is False
        # Default max_doc_attempts is 2
        assert mock_upload.call_count == 2
        assert mock_cleanup.call_count == 1 # Called after 1st failure

def test_process_file_safe_critical_error(mock_page, mock_args):
    # Mock unexpected error (e.g. out of memory, or some logic error)
    with patch("gemini_ocr.upload_image") as mock_upload:
        mock_upload.side_effect = Exception("Critical logic error")

        result = process_file_safe(mock_page, Path("test.jpg"), "prompt", mock_args, None)

        assert result is False
        assert mock_upload.call_count == 1 # Should not retry on unexpected Exception (unless mapped to GeminiError)
