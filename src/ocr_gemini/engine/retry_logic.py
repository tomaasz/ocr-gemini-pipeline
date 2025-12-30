from __future__ import annotations
from typing import Optional, Dict, Any, List
from ..config import PipelineConfig
from .errors import ErrorKind

def decide_retry_action(
    last_run: Optional[Dict[str, Any]],
    cfg: PipelineConfig
) -> Dict[str, Any]:
    """
    Decides whether to process a document based on its history and config.
    Returns a dict with:
      - should_process: bool
      - reason: str (log message)
      - attempt_no: int (next attempt number)
      - parent_run_id: Optional[int]
    """

    # Defaults for a fresh run
    action = {
        "should_process": True,
        "reason": "New document",
        "attempt_no": 1,
        "parent_run_id": None
    }

    if not last_run:
        # No history (or pipeline mismatch led to no history returned)
        if cfg.retry_failed:
             action["should_process"] = False
             action["reason"] = "No prior run (and --retry-failed is set)"
        return action

    status = last_run['status']
    prev_attempts = last_run.get('attempt_no') or 1
    prev_kind = last_run.get('error_kind')
    run_id = last_run['run_id']

    # Parent linkage for next attempt
    action["attempt_no"] = prev_attempts + 1
    action["parent_run_id"] = run_id

    if cfg.force:
        action["should_process"] = True
        action["reason"] = "Force retry"
        return action

    if status == 'done':
        action["should_process"] = False
        action["reason"] = "Already done"
        return action

    if status == 'skipped':
        # Skipped items are not retried by default, even with --resume/--retry-failed.
        # They require --force.
        action["should_process"] = False
        action["reason"] = "Previously skipped (use --force to retry)"
        return action

    if status == 'failed':
        if not (cfg.retry_failed or cfg.resume):
            action["should_process"] = False
            action["reason"] = "Failed (use --resume or --retry-failed)"
            return action

        # Check max attempts
        if prev_attempts >= cfg.max_attempts:
            action["should_process"] = False
            action["reason"] = f"Max attempts reached ({prev_attempts})"
            return action

        # Check error kind
        if prev_kind == ErrorKind.PERMANENT.value:
            action["should_process"] = False
            action["reason"] = f"Permanent error ({prev_kind})"
            return action

        # Check retryable kinds
        kind_to_check = prev_kind if prev_kind else "unknown"
        if kind_to_check in cfg.retry_error_kinds:
             action["should_process"] = True
             action["reason"] = f"Retrying {kind_to_check} failure"
        else:
             action["should_process"] = False
             action["reason"] = f"Error kind '{kind_to_check}' not in retry list"

        return action

    # Status 'processing' or 'queued' - usually implies interrupted or stuck.
    if status in ('processing', 'queued'):
         if cfg.resume or cfg.retry_failed:
              action["should_process"] = True
              action["reason"] = f"Resuming incomplete run ({status})"
         else:
              action["should_process"] = False
              action["reason"] = f"Status {status} (use --resume to reset)"

    return action
