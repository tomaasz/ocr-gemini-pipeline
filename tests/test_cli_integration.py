import sys
from unittest.mock import patch

import pytest

from ocr_gemini.cli import main


@pytest.fixture
def mock_args(tmp_path):
    input_dir = tmp_path / "input"
    out_dir = tmp_path / "out"
    profile_dir = tmp_path / "profile"
    input_dir.mkdir()
    out_dir.mkdir()
    profile_dir.mkdir()

    # one image
    (input_dir / "img1.png").write_bytes(b"fake")

    return [
        "cmd",
        "--input-dir",
        str(input_dir),
        "--out-dir",
        str(out_dir),
        "--profile-dir",
        str(profile_dir),
    ]


@patch("ocr_gemini.cli.PlaywrightEngine")
@patch("ocr_gemini.cli.OcrRepo")
@patch("ocr_gemini.cli.db_config_from_env")
@patch("ocr_gemini.cli.sha256_file", return_value="hash123")
def test_cli_flow_with_db(mock_sha, mock_db_conf, mock_repo_cls, mock_engine_cls, mock_args, monkeypatch):
    monkeypatch.setattr(sys, "argv", mock_args)

    # DB enabled
    mock_db_conf.return_value.dsn = "postgres://..."

    # Repo
    repo = mock_repo_cls.return_value
    repo.get_or_create_document.return_value = 1
    # IMPORTANT: provide a real dict to avoid MagicMock leakage into decision logic
    repo.get_latest_run.return_value = None
    repo.create_run.return_value = 100

    # Engine
    engine = mock_engine_cls.return_value
    engine.ocr.return_value.text = "OCR Text"

    main()

    repo.get_or_create_document.assert_called()

    # Stage 2.x: create_run has attempt_no and parent_run_id
    assert repo.create_run.called
    args, kwargs = repo.create_run.call_args
    assert args[0] == 1
    assert args[1] == "gemini-ui-cli"
    assert kwargs["status"] == "queued"
    assert kwargs["attempt_no"] == 1
    assert kwargs.get("parent_run_id") is None


@patch("ocr_gemini.cli.PlaywrightEngine")
@patch("ocr_gemini.cli.OcrRepo")
@patch("ocr_gemini.cli.db_config_from_env")
@patch("ocr_gemini.cli.sha256_file", return_value="hash123")
def test_cli_idempotency_skip(mock_sha, mock_db_conf, mock_repo_cls, mock_engine_cls, mock_args, monkeypatch):
    """
    Stage 2.x semantics:
    - If decide_retry_action says "skip", we do NOT create a new ocr_run row with status='skipped'.
      We simply skip processing.
    """
    monkeypatch.setattr(sys, "argv", mock_args)

    mock_db_conf.return_value.dsn = "postgres://..."
    repo = mock_repo_cls.return_value
    repo.get_or_create_document.return_value = 1

    # simulate "already done"
    repo.get_latest_run.return_value = {"status": "done", "attempt_no": 1, "error_kind": None, "run_id": 10}

    # engine should NOT be used
    engine = mock_engine_cls.return_value
    engine.ocr.return_value.text = "OCR Text"

    main()

    # Should skip without creating a new run row
    repo.create_run.assert_not_called()
    engine.ocr.assert_not_called()


@patch("ocr_gemini.cli.PlaywrightEngine")
@patch("ocr_gemini.cli.OcrRepo")
@patch("ocr_gemini.cli.db_config_from_env")
@patch("ocr_gemini.cli.sha256_file", return_value="hash123")
def test_cli_force_run(mock_sha, mock_db_conf, mock_repo_cls, mock_engine_cls, mock_args, monkeypatch):
    monkeypatch.setattr(sys, "argv", mock_args + ["--force"])

    mock_db_conf.return_value.dsn = "postgres://..."
    repo = mock_repo_cls.return_value
    repo.get_or_create_document.return_value = 1

    # previously done, but --force should process again
    repo.get_latest_run.return_value = {"status": "done", "attempt_no": 1, "error_kind": None, "run_id": 10}
    repo.create_run.return_value = 101

    engine = mock_engine_cls.return_value
    engine.ocr.return_value.text = "OCR Text"

    main()

    assert repo.create_run.called
    args, kwargs = repo.create_run.call_args
    assert args[0] == 1
    assert args[1] == "gemini-ui-cli"
    assert kwargs["status"] == "queued"
    assert kwargs["attempt_no"] == 2  # done->force => next attempt
    assert kwargs.get("parent_run_id") == 10
