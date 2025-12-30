import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ocr_gemini.debug import save_debug_artifacts


@pytest.fixture
def temp_debug_dir(tmp_path):
    d = tmp_path / "debug_out"
    d.mkdir()
    return d


def test_save_debug_artifacts_no_dir():
    # Should be no-op
    page = MagicMock()
    save_debug_artifacts(page, None, "test")
    assert not page.screenshot.called
    assert not page.content.called


def test_save_debug_artifacts_no_page(temp_debug_dir):
    # Should be no-op + log (no exception)
    save_debug_artifacts(None, temp_debug_dir, "test")
    # directory should remain empty
    assert len(list(temp_debug_dir.iterdir())) == 0


def test_save_debug_artifacts_success(temp_debug_dir):
    page = MagicMock()
    page.content.return_value = "<html></html>"
    page.url = "http://example.com"

    save_debug_artifacts(page, temp_debug_dir, "test_label")

    files = list(temp_debug_dir.iterdir())
    # Expect 2 files written by python (html, meta)
    # Screenshot is written by Playwright (mocked here, so no file on disk)
    assert len(files) == 2

    # Verify extensions
    exts = sorted([f.suffix for f in files])
    assert exts == [".html", ".txt"]

    # Verify content call
    page.content.assert_called_once()
    page.screenshot.assert_called_once()

    # Verify screenshot path argument
    args, kwargs = page.screenshot.call_args
    assert "test_label" in str(kwargs['path'])
    assert ".png" in str(kwargs['path'])


def test_save_debug_artifacts_sanitization(temp_debug_dir):
    page = MagicMock()
    page.content.return_value = ""
    unsafe_label = "bad/label with spaces & stuff" * 5

    save_debug_artifacts(page, temp_debug_dir, unsafe_label)

    files = list(temp_debug_dir.iterdir())
    assert len(files) > 0
    filename = files[0].name

    # Check strict chars
    assert " " not in filename
    assert "/" not in filename
    assert "&" not in filename

    # Check length limit (timestamp is ~15 chars, label limit 50)
    # 15 + 1 + 50 + ext (4) = ~70 chars max
    assert len(filename) < 80


def test_save_debug_artifacts_duck_typing(temp_debug_dir):
    # Object without screenshot method should not crash
    class FakePage:
        pass

    page = FakePage()
    save_debug_artifacts(page, temp_debug_dir, "test")

    # Should create metadata file only
    files = list(temp_debug_dir.iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".txt"
