import json
import time
from pathlib import Path

import pytest

from ocr_gemini.metrics import DocumentMetrics


def test_finish_sets_end_and_duration_and_outcome(monkeypatch):
    # kontrolujemy czas, żeby test był deterministyczny
    t0 = 1000.00
    t1 = 1001.23

    m = DocumentMetrics(file_name="a.jpg", start_ts=t0)

    monkeypatch.setattr(time, "time", lambda: t1)
    m.finish(outcome="success")

    assert m.end_ts == t1
    assert m.duration_s == round(t1 - t0, 2)
    assert m.outcome == "success"
    assert m.error_reason is None


def test_finish_sets_error_reason(monkeypatch):
    t0 = 2000.0
    t1 = 2000.5

    m = DocumentMetrics(file_name="b.jpg", start_ts=t0)

    monkeypatch.setattr(time, "time", lambda: t1)
    m.finish(outcome="error", error_reason="timeout")

    assert m.outcome == "error"
    assert m.error_reason == "timeout"
    assert m.duration_s == round(t1 - t0, 2)


def test_to_json_returns_valid_json():
    m = DocumentMetrics(file_name="c.jpg", start_ts=123.0)
    m.attempts = 2
    m.finish(outcome="skipped", error_reason="already_processed")

    s = m.to_json()
    obj = json.loads(s)

    assert obj["file_name"] == "c.jpg"
    assert obj["attempts"] == 2
    assert obj["outcome"] == "skipped"
    assert obj["error_reason"] == "already_processed"
    assert isinstance(obj["start_ts"], (int, float))
    assert isinstance(obj["end_ts"], (int, float))
    assert isinstance(obj["duration_s"], (int, float))


def test_str_contains_key_fields(monkeypatch):
    t0 = 3000.0
    t1 = 3002.0

    m = DocumentMetrics(file_name="d.jpg", start_ts=t0)
    m.attempts = 3

    monkeypatch.setattr(time, "time", lambda: t1)
    m.finish(outcome="error", error_reason="bad_ui_state")

    s = str(m)
    assert "METRICS:" in s
    assert "file=d.jpg" in s
    assert "status=error" in s
    assert "attempts=3" in s
    assert "duration=" in s
    assert "reason=bad_ui_state" in s
