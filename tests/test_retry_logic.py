import pytest
from pathlib import Path

from ocr_gemini.engine.errors import classify_error, ErrorKind
from ocr_gemini.engine.retry_logic import decide_retry_action
from ocr_gemini.config import PipelineConfig


# --- Classification Tests ---

def test_classify_error_timeout_by_name():
    class TimeoutError(Exception):
        pass

    e = TimeoutError("Timeout occurred")
    assert classify_error(e) == ErrorKind.TRANSIENT


def test_classify_error_playwright_target_closed():
    class TargetClosedError(Exception):
        pass

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
        retry_error_kinds=["transient", "unknown"],
        resume=False,
        force=False,
        retry_backoff_seconds=0,
    )


def test_decide_fresh_run(base_cfg):
    action = decide_retry_action(None, base_cfg)
    assert action["should_process"] is True
    assert action["attempt_no"] == 1
    assert action["parent_run_id"] is None


def test_decide_fresh_run_retry_failed_only(base_cfg):
    base_cfg.retry_failed = True
    action = decide_retry_action(None, base_cfg)
    assert action["should_process"] is False
    assert "No prior run" in action["reason"]


def test_decide_already_done(base_cfg):
    last_run = {"status": "done", "attempt_no": 1, "error_kind": None, "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is False
    assert "Already done" in action["reason"]


def test_decide_force_override_done(base_cfg):
    base_cfg.force = True
    last_run = {"status": "done", "attempt_no": 1, "error_kind": None, "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is True
    assert action["attempt_no"] == 2
    assert action["parent_run_id"] == 10


def test_decide_failed_no_retry_flag(base_cfg):
    last_run = {"status": "failed", "attempt_no": 1, "error_kind": "transient", "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is False


def test_decide_failed_retryable_transient(base_cfg):
    base_cfg.retry_failed = True
    last_run = {"status": "failed", "attempt_no": 1, "error_kind": "transient", "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is True
    assert action["attempt_no"] == 2
    assert action["parent_run_id"] == 10


def test_decide_failed_retryable_unknown(base_cfg):
    base_cfg.retry_failed = True
    last_run = {"status": "failed", "attempt_no": 1, "error_kind": "unknown", "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is True


def test_decide_failed_permanent(base_cfg):
    base_cfg.retry_failed = True
    last_run = {"status": "failed", "attempt_no": 1, "error_kind": "permanent", "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is False
    assert "Permanent error" in action["reason"]


def test_decide_max_attempts_reached(base_cfg):
    base_cfg.retry_failed = True
    base_cfg.max_attempts = 3
    last_run = {"status": "failed", "attempt_no": 3, "error_kind": "transient", "run_id": 30}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is False
    assert "Max attempts reached" in action["reason"]


def test_decide_max_attempts_not_reached(base_cfg):
    base_cfg.retry_failed = True
    base_cfg.max_attempts = 3
    last_run = {"status": "failed", "attempt_no": 2, "error_kind": "transient", "run_id": 20}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is True
    assert action["attempt_no"] == 3


def test_decide_resume_skipped_false(base_cfg):
    base_cfg.resume = True
    last_run = {"status": "skipped", "attempt_no": 1, "error_kind": None, "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is False
    assert "use --force" in action["reason"]


def test_decide_force_skipped(base_cfg):
    base_cfg.force = True
    last_run = {"status": "skipped", "attempt_no": 1, "error_kind": None, "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is True
    assert "Force retry" in action["reason"]


def test_decide_skipped_no_flags(base_cfg):
    last_run = {"status": "skipped", "attempt_no": 1, "error_kind": None, "run_id": 10}
    action = decide_retry_action(last_run, base_cfg)
    assert action["should_process"] is False
