import time
import pytest
from gemini_metrics import DocumentMetrics

def test_metrics_success():
    m = DocumentMetrics(file_name="test.jpg", start_ts=time.time())
    time.sleep(0.01)
    m.finish("success")

    assert m.outcome == "success"
    assert m.duration_s > 0
    assert "METRICS: file=test.jpg | status=success" in str(m)

def test_metrics_error():
    m = DocumentMetrics(file_name="fail.jpg", start_ts=time.time())
    m.attempts = 2
    m.finish("error", error_reason="Timeout")

    assert m.outcome == "error"
    assert m.error_reason == "Timeout"
    assert m.attempts == 2
    assert "reason=Timeout" in str(m)
