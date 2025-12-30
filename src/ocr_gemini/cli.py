# src/ocr_gemini/cli.py
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Set

from .config import PipelineConfig
from .db import db_config_from_env
from .db.repo import OcrRepo
from .engine.errors import ErrorKind, classify_error
from .engine.playwright_engine import PlaywrightEngine
from .engine.retry_logic import decide_retry_action
from .files import sha256_file

IMAGE_EXTS: Set[str] = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def _scan_images(input_dir: Path, recursive: bool, limit: int) -> List[Path]:
    """
    Fast scan for images.
    - recursive=False: only direct children (iterdir)
    - recursive=True: os.walk (streaming) + early stop when limit reached

    Returns list of image paths (sorted for determinism).
    """
    found: List[Path] = []

    if not input_dir.exists() or not input_dir.is_dir():
        return found

    # normalize
    lim = int(limit) if limit else 0

    if not recursive:
        for p in input_dir.iterdir():
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                found.append(p)

        # Sort ALL found, then slice to ensure deterministic order regardless of FS iteration
        found.sort()
        if lim:
            return found[:lim]
        return found

    # recursive walk
    for root, dirnames, filenames in os.walk(input_dir, followlinks=False):
        # optionally prune hidden dirs
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        for fn in filenames:
            p = Path(root) / fn
            if p.suffix.lower() in IMAGE_EXTS:
                found.append(p)

    # Sort ALL found, then slice
    found.sort()
    if lim:
        return found[:lim]
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR Gemini CLI Runner")
    parser.add_argument("--input-dir", type=Path, required=True, help="Directory containing images")
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory to save results")
    parser.add_argument("--profile-dir", type=Path, required=True, help="Directory for browser profile")
    parser.add_argument("--limit", type=int, help="Max number of images to process")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--debug-dir", type=Path, help="Directory for debug artifacts")

    # NEW
    parser.add_argument("--recursive", action="store_true", help="Scan input directory recursively")

    # Stage 1.5 args
    parser.add_argument("--resume", action="store_true", help="Resume failed/missing runs only")
    parser.add_argument("--force", action="store_true", help="Force re-processing even if done")

    # Stage 2.0 args
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed documents (requires DB)")
    parser.add_argument("--max-attempts", type=int, default=3, help="Max attempts per document")
    parser.add_argument("--retry-backoff-seconds", type=int, default=0, help="Wait between attempts (seconds)")
    parser.add_argument(
        "--retry-error-kinds",
        type=str,
        default="transient,unknown",
        help="Comma-separated list of error kinds to retry",
    )

    args = parser.parse_args()

    retry_kinds = [k.strip().lower() for k in (args.retry_error_kinds or "").split(",") if k.strip()]

    cfg = PipelineConfig(
        ocr_root=args.input_dir,
        out_root=args.out_dir,
        prompt_id="Transcribe text",
        limit=args.limit or 0,
        debug_dir=args.debug_dir if args.debug_dir else args.out_dir / "debug",
        resume=bool(args.resume),
        force=bool(args.force),
        pipeline_name="gemini-ui-cli",
        retry_failed=bool(args.retry_failed),
        max_attempts=int(args.max_attempts),
        retry_backoff_seconds=int(args.retry_backoff_seconds),
        retry_error_kinds=retry_kinds,
    )

    if not cfg.ocr_root.exists():
        print(f"Error: Input directory {cfg.ocr_root} does not exist.")
        sys.exit(1)

    cfg.out_root.mkdir(parents=True, exist_ok=True)
    if cfg.debug_dir:
        cfg.debug_dir.mkdir(parents=True, exist_ok=True)

    # Initialize DB Repo if DSN available
    repo: Optional[OcrRepo] = None
    db_cfg = db_config_from_env()
    if getattr(db_cfg, "dsn", None):
        try:
            repo = OcrRepo(db_cfg)
            print("DB Write-back enabled.")
        except Exception as e:
            print(f"Warning: Failed to initialize DB repo: {e}")

    # Validation for retry-failed
    if cfg.retry_failed and not repo:
        print("Error: --retry-failed requires DB connection.")
        sys.exit(1)

    # FAST scan (with early stop on limit)
    images = _scan_images(cfg.ocr_root, recursive=bool(args.recursive), limit=int(cfg.limit))

    if not images:
        print(f"No images found in {cfg.ocr_root}")
        return

    print(f"Processing {len(images)} images...")

    engine = PlaywrightEngine(
        profile_dir=args.profile_dir,
        headless=args.headless,
        debug_dir=cfg.debug_dir,
    )

    try:
        print("Starting engine...")
        engine.start()

        for i, img_path in enumerate(images):
            print(f"[{i + 1}/{len(images)}] Checking {img_path.name}...")

            run_id = None
            doc_id = None
            last_run = None

            attempt_no = 1
            parent_run_id = None

            if repo:
                try:
                    s256 = sha256_file(img_path)
                    doc_id = repo.get_or_create_document(str(img_path), s256)
                    last_run = repo.get_latest_run(doc_id, cfg.pipeline_name)

                    decision = decide_retry_action(last_run, cfg)

                    if not decision.get("should_process", True):
                        print(f"  SKIPPING: {decision.get('reason', 'no reason')}")
                        continue

                    attempt_no = int(decision.get("attempt_no", 1))
                    parent_run_id = decision.get("parent_run_id", None)

                except Exception as e:
                    print(f"  DB Error (pre-flight): {e}")
                    if cfg.retry_failed:
                        print("  Aborting document due to DB error with --retry-failed.")
                        continue
                    attempt_no = 1
                    parent_run_id = None

            # Backoff (between attempts)
            if attempt_no > 1 and cfg.retry_backoff_seconds > 0:
                print(f"  Waiting {cfg.retry_backoff_seconds}s before retry...")
                time.sleep(cfg.retry_backoff_seconds)

            # Create run row
            if repo:
                run_id = repo.create_run(
                    doc_id,
                    cfg.pipeline_name,
                    status="queued",
                    attempt_no=attempt_no,
                    parent_run_id=parent_run_id,
                )

            # Recovery loop (within attempt)
            max_recovery_retries = 1
            recovery_count = 0

            while True:
                try:
                    if repo and run_id:
                        repo.mark_run_status(run_id, "processing")
                        repo.mark_step(run_id, "engine_start", "started")

                    result = engine.ocr(img_path, prompt_id=cfg.prompt_id)

                    out_txt = cfg.out_root / f"{img_path.stem}.txt"
                    out_txt.write_text(result.text, encoding="utf-8")
                    print(f"  OK: Saved to {out_txt}")

                    if repo and run_id:
                        repo.mark_run_status(run_id, "done", out_path=str(out_txt))
                        repo.mark_step(run_id, "engine_finish", "done")

                    break

                except Exception as e:
                    kind = classify_error(e)
                    print(f"  Error: {e} [{kind.value}]")

                    # Recovery attempt (transient only)
                    if kind == ErrorKind.TRANSIENT and recovery_count < max_recovery_retries:
                        recovery_count += 1
                        print(f"  Attempting recovery ({recovery_count}/{max_recovery_retries})...")

                        if repo and run_id:
                            repo.mark_step(run_id, "recover_refresh", "started")

                        try:
                            engine.recover()
                            if repo and run_id:
                                repo.mark_step(run_id, "recover_refresh", "done")
                        except Exception as rec_e:
                            print(f"  Recovery failed: {rec_e}")
                            if repo and run_id:
                                repo.mark_step(
                                    run_id,
                                    "recover_refresh",
                                    "failed",
                                    error_message=str(rec_e),
                                )

                        continue

                    # Final failure for this attempt
                    if repo and run_id:
                        repo.mark_run_status(
                            run_id,
                            "failed",
                            error_message=str(e),
                            error_kind=kind.value,
                        )
                        repo.mark_step(
                            run_id,
                            "engine_finish",
                            "failed",
                            error_message=str(e),
                        )
                    break

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        print("Stopping engine...")
        try:
            engine.stop()
        except Exception:
            pass

        if repo:
            try:
                repo.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
