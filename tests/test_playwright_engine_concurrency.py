import os
from unittest.mock import patch
from ocr_gemini.ui.playwright_engine import PlaywrightEngine
from ocr_gemini.ui.worker_pool import WorkerPool

def test_engine_initializes_worker_pool():
    engine = PlaywrightEngine(workers=2)
    assert engine.worker_pool.size == 2
    assert isinstance(engine.worker_pool, WorkerPool)

def test_engine_default_worker_pool():
    # Ensure env var doesn't interfere if not set
    with patch.dict(os.environ, {}, clear=True):
        engine = PlaywrightEngine()
        assert engine.worker_pool.size == 1

def test_engine_env_var_worker_pool():
    with patch.dict(os.environ, {"OCR_MAX_WORKERS": "5"}):
        engine = PlaywrightEngine()
        assert engine.worker_pool.size == 5

def test_engine_explicit_overrides_env_var():
    with patch.dict(os.environ, {"OCR_MAX_WORKERS": "5"}):
        engine = PlaywrightEngine(workers=3)
        assert engine.worker_pool.size == 3
