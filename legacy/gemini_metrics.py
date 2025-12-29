import time
import json
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class DocumentMetrics:
    file_name: str
    start_ts: float
    end_ts: float = 0.0
    duration_s: float = 0.0
    attempts: int = 0
    outcome: str = "unknown"  # success, error, skipped
    error_reason: Optional[str] = None

    def finish(self, outcome: str, error_reason: Optional[str] = None):
        self.end_ts = time.time()
        self.duration_s = round(self.end_ts - self.start_ts, 2)
        self.outcome = outcome
        self.error_reason = error_reason

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    def __str__(self) -> str:
        err_str = f" | reason={self.error_reason}" if self.error_reason else ""
        return (f"METRICS: file={self.file_name} | status={self.outcome} | "
                f"attempts={self.attempts} | duration={self.duration_s}s{err_str}")
