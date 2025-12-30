import pytest
import time
from unittest.mock import Mock, call
from src.ocr_gemini.utils import retry_call, wait_for_generation_complete

class MyError(Exception):
    pass

def test_retry_call_success():
    """Test that it returns result immediately on success."""
    fn = Mock(return_value="success")
    result = retry_call(fn, retries=3, backoff_ms=10, retry_on=(MyError,))
    assert result == "success"
    assert fn.call_count == 1

def test_retry_call_eventual_success():
    """Test that it retries and eventually succeeds."""
    fn = Mock(side_effect=[MyError("fail1"), MyError("fail2"), "success"])
    result = retry_call(fn, retries=3, backoff_ms=10, retry_on=(MyError,))
    assert result == "success"
    assert fn.call_count == 3

def test_retry_call_exhausted():
    """Test that it raises exception after retries exhausted."""
    fn = Mock(side_effect=MyError("fail"))
    with pytest.raises(MyError):
        retry_call(fn, retries=2, backoff_ms=10, retry_on=(MyError,))
    assert fn.call_count == 3  # 1 initial + 2 retries

def test_retry_call_wrong_exception():
    """Test that it doesn't retry on unspecified exceptions."""
    fn = Mock(side_effect=ValueError("wrong"))
    with pytest.raises(ValueError):
        retry_call(fn, retries=3, backoff_ms=10, retry_on=(MyError,))
    assert fn.call_count == 1

def test_wait_for_generation_complete_success():
    """Test that it returns when completed."""
    has_comp = Mock(side_effect=[False, False, True])

    wait_for_generation_complete(has_comp, timeout_ms=1000, poll_interval_ms=10)
    assert has_comp.call_count == 3

def test_wait_for_generation_complete_timeout():
    """Test that it raises TimeoutError."""
    has_comp = Mock(return_value=False)

    with pytest.raises(TimeoutError):
        wait_for_generation_complete(has_comp, timeout_ms=50, poll_interval_ms=10)
