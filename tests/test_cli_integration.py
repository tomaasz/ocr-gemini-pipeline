import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys
from ocr_gemini.cli import main

@pytest.fixture
def mock_args(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "img1.png").touch()

    out_dir = tmp_path / "out"
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()

    return ["cmd", "--input-dir", str(input_dir), "--out-dir", str(out_dir), "--profile-dir", str(profile_dir), "--headless"]

@patch("ocr_gemini.cli.PlaywrightEngine")
@patch("ocr_gemini.cli.OcrRepo")
@patch("ocr_gemini.cli.db_config_from_env")
@patch("ocr_gemini.cli.sha256_file", return_value="hash123")
def test_cli_flow_with_db(mock_sha, mock_db_conf, mock_repo_cls, mock_engine_cls, mock_args, monkeypatch):
    monkeypatch.setattr(sys, "argv", mock_args)

    # Mock DB config
    mock_db_conf.return_value.dsn = "postgres://..."

    # Mock Repo
    repo = mock_repo_cls.return_value
    repo.get_or_create_document.return_value = 1
    repo.has_successful_run.return_value = False
    repo.create_run.return_value = 100

    # Mock Engine
    engine = mock_engine_cls.return_value
    engine.ocr.return_value.text = "OCR Text"

    main()

    repo.get_or_create_document.assert_called()
    repo.create_run.assert_called_with(1, "gemini-ui-cli", status='queued')
    repo.mark_run_status.assert_any_call(100, 'processing')
    # assert done is called with some out_path
    call_args_list = repo.mark_run_status.call_args_list
    assert any(c[0][1] == 'done' for c in call_args_list)
    engine.ocr.assert_called()

@patch("ocr_gemini.cli.PlaywrightEngine")
@patch("ocr_gemini.cli.OcrRepo")
@patch("ocr_gemini.cli.db_config_from_env")
@patch("ocr_gemini.cli.sha256_file", return_value="hash123")
def test_cli_idempotency_skip(mock_sha, mock_db_conf, mock_repo_cls, mock_engine_cls, mock_args, monkeypatch):
    monkeypatch.setattr(sys, "argv", mock_args)

    mock_db_conf.return_value.dsn = "postgres://..."
    repo = mock_repo_cls.return_value
    repo.get_or_create_document.return_value = 1
    # Document already has successful run
    repo.has_successful_run.return_value = True

    main()

    # Should skip
    # verify create_run called with 'skipped'
    repo.create_run.assert_called_with(1, "gemini-ui-cli", status='skipped')

    # verify engine NOT called
    mock_engine_cls.return_value.ocr.assert_not_called()

@patch("ocr_gemini.cli.PlaywrightEngine")
@patch("ocr_gemini.cli.OcrRepo")
@patch("ocr_gemini.cli.db_config_from_env")
@patch("ocr_gemini.cli.sha256_file", return_value="hash123")
def test_cli_force_run(mock_sha, mock_db_conf, mock_repo_cls, mock_engine_cls, mock_args, monkeypatch):
    monkeypatch.setattr(sys, "argv", mock_args + ["--force"])

    mock_db_conf.return_value.dsn = "postgres://..."
    repo = mock_repo_cls.return_value
    repo.get_or_create_document.return_value = 1
    repo.has_successful_run.return_value = True
    repo.create_run.return_value = 101

    main()

    # Should run even if done
    repo.create_run.assert_called_with(1, "gemini-ui-cli", status='queued')
    mock_engine_cls.return_value.ocr.assert_called()
