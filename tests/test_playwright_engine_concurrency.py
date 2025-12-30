from unittest.mock import MagicMock
from src.ocr_gemini.ui.playwright_engine import PlaywrightEngine
from src.ocr_gemini.ui.worker_pool import WorkerPool

def test_engine_initializes_worker_pool():
    engine = PlaywrightEngine(workers=2)
    assert engine.worker_pool.size == 2
    assert isinstance(engine.worker_pool, WorkerPool)

def test_engine_default_worker_pool():
    engine = PlaywrightEngine()
    assert engine.worker_pool.size == 1
