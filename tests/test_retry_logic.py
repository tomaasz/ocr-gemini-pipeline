import sys
from unittest.mock import MagicMock

# Mock psycopg2 before importing src
sys.modules["psycopg2"] = MagicMock()

import pytest
from src.ocr_gemini.engine.errors import classify_error, ErrorKind
from src.ocr_gemini.engine.retry_logic import decide_retry_action
from src.ocr_gemini.config import PipelineConfig
from pathlib import Path

# --- Classification Tests ---

def test_classify_error_timeout_by_name():
    class TimeoutError(Exception): pass
    e = TimeoutError("Timeout occurred")
    assert classify_error(e) == ErrorKind.TRANSIENT

def test_classify_error_playwright_target_closed():
    class TargetClosedError(Exception): pass
    e = TargetClosedError("Target closed")
    assert classify_error(e) == ErrorKind.TRANSIENT

def test_classify_error_message_detached():
    e = Exception("Element is detached from DOM")
    assert classify_error(e) == ErrorKind.TRANSIENT

def test_classify_error_permanent_file_not_found():
    e = FileNotFoundError("missing.jpg")
    assert classify_error(e) == ErrorKind.PERMANENT

def test_classify_error_permanent_auth():
    e = Exception("Please login to continue")
    assert classify_error(e) == ErrorKind.PERMANENT

def test_classify_error_unknown():
    e = Exception("Some random error")
    assert classify_error(e) == ErrorKind.UNKNOWN

# --- Retry Logic Tests ---

@pytest.fixture
def base_cfg():
    return PipelineConfig(
        ocr_root=Path("/tmp"),
        out_root=Path("/tmp"),
        prompt_id="test",
        retry_failed=False,
        max_attempts=3,
        pipeline_name="test-pipeline",
        retry_error_kinds=["transient", "unknown"]
    )

def test_decide_fresh_run(base_cfg):
    """Scenario: No previous run exists."""
    action = decide_retry_action(None, base_cfg)
    assert action["should_process"] is True
    assert action["attempt_no"] == 1
    assert action["parent_run_id"] is None

def test_decide_fresh_run_retry_failed_only(base_cfg):
    """Scenario: No previous run, but --retry-failed is on (should skip)."""
    base_cfg.retry_failed = True
    action = decide_retry_action(None, base_cfg)
    assert action["should_process"] is False
    assert "No prior run" in action["reason"]

def test_decide_pipeline_change_resets_attempts(base_cfg):
    """
    Scenario: Pipeline name changed, so repo returned None (no history).
    This confirms that a 'new' run behavior is triggered, resetting attempt count.
    """
    # Simulate repo logic: if pipeline differs, get_latest_run returns None.
    # So we pass None as last_run.
    last_run = None
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is True
    assert action["attempt_no"] == 1
    assert action["parent_run_id"] is None

def test_decide_already_done(base_cfg):
    """Scenario: Previous run is done."""
    last_run = {"status": "done", "attempt_no": 1, "error_kind": None, "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is False
    assert "Already done" in action["reason"]

def test_decide_force_override_done(base_cfg):
    """Scenario: Previous run is done, but --force is on."""
    base_cfg.force = True
    last_run = {"status": "done", "attempt_no": 1, "error_kind": None, "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is True
    assert action["attempt_no"] == 2
    assert action["parent_run_id"] == 10

def test_decide_failed_no_retry_flag(base_cfg):
    """Scenario: Failed, but neither --retry-failed nor --resume is set."""
    last_run = {"status": "failed", "attempt_no": 1, "error_kind": "transient", "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is False

def test_decide_failed_retryable_transient(base_cfg):
    """Scenario: Failed transiently, --retry-failed is on."""
    base_cfg.retry_failed = True
    last_run = {"status": "failed", "attempt_no": 1, "error_kind": "transient", "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is True
    assert action["attempt_no"] == 2
    assert action["parent_run_id"] == 10

def test_decide_failed_retryable_unknown(base_cfg):
    """Scenario: Failed unknown (default retry), --retry-failed is on."""
    base_cfg.retry_failed = True
    last_run = {"status": "failed", "attempt_no": 1, "error_kind": "unknown", "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is True

def test_decide_failed_permanent(base_cfg):
    """Scenario: Failed permanently, should not retry."""
    base_cfg.retry_failed = True
    last_run = {"status": "failed", "attempt_no": 1, "error_kind": "permanent", "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is False
    assert "Permanent error" in action["reason"]

def test_decide_max_attempts_reached(base_cfg):
    """Scenario: Max attempts reached."""
    base_cfg.retry_failed = True
    base_cfg.max_attempts = 3
    last_run = {"status": "failed", "attempt_no": 3, "error_kind": "transient", "run_id": 30}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is False
    assert "Max attempts reached" in action["reason"]

def test_decide_max_attempts_not_reached(base_cfg):
    """Scenario: Max attempts not reached (2 < 3)."""
    base_cfg.retry_failed = True
    base_cfg.max_attempts = 3
    last_run = {"status": "failed", "attempt_no": 2, "error_kind": "transient", "run_id": 20}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is True
    assert action["attempt_no"] == 3

def test_decide_resume_skipped_false(base_cfg):
    """Scenario: Previously skipped. --resume should NOT retry it (requires force)."""
    base_cfg.resume = True
    last_run = {"status": "skipped", "attempt_no": 1, "error_kind": None, "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is False
    assert "use --force" in action["reason"]

def test_decide_force_skipped(base_cfg):
    """Scenario: Previously skipped. --force SHOULD retry it."""
    base_cfg.force = True
    last_run = {"status": "skipped", "attempt_no": 1, "error_kind": None, "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is True
    assert "Force retry" in action["reason"]

def test_decide_skipped_no_flags(base_cfg):
    """Scenario: Previously skipped, no flags."""
    last_run = {"status": "skipped", "attempt_no": 1, "error_kind": None, "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is False
