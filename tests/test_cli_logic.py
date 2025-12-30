from unittest.mock import MagicMock, patch

from ocr_gemini.cli import main


class TestCLI:
    @patch("ocr_gemini.cli.PlaywrightEngine")
    @patch("ocr_gemini.cli.argparse.ArgumentParser.parse_args")
    @patch("ocr_gemini.cli.db_config_from_env")
    def test_cli_execution_flow(self, mock_db_conf, mock_args, mock_engine_cls, tmp_path, capsys):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "1.jpg").touch()
        (input_dir / "2.png").touch()
        (input_dir / "ignore.txt").touch()

        out_dir = tmp_path / "out"
        profile_dir = tmp_path / "profile"

        # no DB in this test
        mock_db_conf.return_value.dsn = None

        mock_args.return_value = MagicMock(
            input_dir=input_dir,
            out_dir=out_dir,
            profile_dir=profile_dir,
            limit=None,
            headless=False,
            debug_dir=None,
            # Stage 1.5
            resume=False,
            force=False,
            # Stage 2.0
            retry_failed=False,
            max_attempts=3,
            retry_backoff_seconds=0,
            retry_error_kinds="transient,unknown",
        )

        mock_engine = mock_engine_cls.return_value
        mock_engine.ocr.return_value.text = "OCR Output"

        main()

        captured = capsys.readouterr()
        assert "Processing 2 images" in captured.out
        assert mock_engine.start.called
        assert mock_engine.stop.called

    @patch("ocr_gemini.cli.PlaywrightEngine")
    @patch("ocr_gemini.cli.argparse.ArgumentParser.parse_args")
    @patch("ocr_gemini.cli.db_config_from_env")
    def test_cli_limit(self, mock_db_conf, mock_args, mock_engine_cls, tmp_path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "1.jpg").touch()
        (input_dir / "2.jpg").touch()
        (input_dir / "3.jpg").touch()

        mock_db_conf.return_value.dsn = None

        mock_args.return_value = MagicMock(
            input_dir=input_dir,
            out_dir=tmp_path / "out",
            profile_dir=tmp_path / "profile",
            limit=2,
            headless=False,
            debug_dir=None,
            # Stage 1.5
            resume=False,
            force=False,
            # Stage 2.0
            retry_failed=False,
            max_attempts=3,
            retry_backoff_seconds=0,
            retry_error_kinds="transient,unknown",
        )

        main()

        mock_engine = mock_engine_cls.return_value
        assert mock_engine.ocr.call_count == 2
