from unittest.mock import MagicMock, patch, call
from pathlib import Path
import pytest
from ocr_gemini.cli import main
import sys

class TestCLI:
    @patch("ocr_gemini.cli.PlaywrightEngine")
    @patch("ocr_gemini.cli.argparse.ArgumentParser.parse_args")
    def test_cli_execution_flow(self, mock_args, mock_engine_cls, tmp_path, capsys):
        # Setup input files
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "1.jpg").touch()
        (input_dir / "2.png").touch()
        (input_dir / "ignore.txt").touch()

        out_dir = tmp_path / "out"
        profile_dir = tmp_path / "profile"

        # Setup args
        mock_args.return_value = MagicMock(
            input_dir=input_dir,
            out_dir=out_dir,
            profile_dir=profile_dir,
            limit=None,
            headless=False,
            debug_dir=None
        )

        # Setup Engine Mock
        mock_engine = mock_engine_cls.return_value
        mock_engine.ocr.return_value.text = "OCR Output"

        # Run
        main()

        # Verify Engine Init
        mock_engine_cls.assert_called_with(
            profile_dir=profile_dir,
            headless=False,
            debug_dir=out_dir / "debug"
        )

        # Verify Start/Stop
        mock_engine.start.assert_called_once()
        mock_engine.stop.assert_called_once()

        # Verify OCR calls (sequential)
        assert mock_engine.ocr.call_count == 2
        # Check files processed
        calls = mock_engine.ocr.call_args_list
        files_processed = sorted([c[0][0].name for c in calls])
        assert files_processed == ["1.jpg", "2.png"]

        # Verify output files
        assert (out_dir / "1.txt").read_text(encoding="utf-8") == "OCR Output"
        assert (out_dir / "2.txt").read_text(encoding="utf-8") == "OCR Output"

    @patch("ocr_gemini.cli.PlaywrightEngine")
    @patch("ocr_gemini.cli.argparse.ArgumentParser.parse_args")
    def test_cli_limit(self, mock_args, mock_engine_cls, tmp_path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "1.jpg").touch()
        (input_dir / "2.jpg").touch()
        (input_dir / "3.jpg").touch()

        mock_args.return_value = MagicMock(
            input_dir=input_dir,
            out_dir=tmp_path / "out",
            profile_dir=tmp_path / "profile",
            limit=2,
            headless=False,
            debug_dir=None
        )

        main()

        mock_engine = mock_engine_cls.return_value
        assert mock_engine.ocr.call_count == 2
