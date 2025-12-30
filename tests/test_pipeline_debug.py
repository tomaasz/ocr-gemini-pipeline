import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path

from ocr_gemini.pipeline import Pipeline, PipelineConfig
from ocr_gemini.ui.engine import OcrResult
from ocr_gemini.files import DiscoveredFile

@pytest.fixture
def mock_engine():
    engine = Mock()
    engine.page = MagicMock() # The page object we want to inspect
    return engine

@pytest.fixture
def pipeline_config(tmp_path):
    return PipelineConfig(
        ocr_root=tmp_path / "in",
        out_root=tmp_path / "out",
        prompt_id="test_prompt",
        debug_dir=tmp_path / "debug"
    )

def test_pipeline_debug_artifacts_on_error(pipeline_config, mock_engine, monkeypatch):
    """
    Integration test: Ensure pipeline calls save_debug_artifacts on error.
    """
    # Create input file
    (pipeline_config.ocr_root).mkdir(parents=True)
    input_file = pipeline_config.ocr_root / "test.jpg"
    input_file.write_text("dummy")

    # Mock save_debug_artifacts to avoid actual file I/O and verify call
    mock_save = Mock()
    monkeypatch.setattr("ocr_gemini.pipeline.save_debug_artifacts", mock_save)

    # Configure engine to raise exception
    mock_engine.ocr.side_effect = RuntimeError("OCR Failed")

    # Mock DB writer to avoid real DB connection attempts
    mock_db = Mock()
    mock_db.upsert_document.return_value = 1
    mock_db.upsert_entry.return_value = 1

    pipeline = Pipeline(pipeline_config, db_writer=mock_db, engine=mock_engine)

    # Run pipeline - expect exception to bubble up?
    # The current pipeline code re-raises exception after handling metrics/artifacts.
    with pytest.raises(RuntimeError, match="OCR Failed"):
        pipeline.run()

    # Verify save_debug_artifacts was called
    assert mock_save.called
    args, _ = mock_save.call_args
    page_arg, debug_dir_arg, label_arg = args

    assert page_arg == mock_engine.page
    assert debug_dir_arg == pipeline_config.debug_dir
    assert "error_test.jpg" in label_arg
