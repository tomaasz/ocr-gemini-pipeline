import argparse
import sys
import os
import time
from pathlib import Path

from .engine.playwright_engine import PlaywrightEngine
from .engine.errors import classify_error, ErrorKind
from .engine.retry_logic import decide_retry_action
from .config import PipelineConfig
from .db import db_config_from_env
from .db.repo import OcrRepo
from .files import sha256_file

def main() -> None:
    parser = argparse.ArgumentParser(description="OCR Gemini CLI Runner")
    parser.add_argument("--input-dir", type=Path, required=True, help="Directory containing images")
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory to save results")
    parser.add_argument("--profile-dir", type=Path, required=True, help="Directory for browser profile")
    parser.add_argument("--limit", type=int, help="Max number of images to process")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--debug-dir", type=Path, help="Directory for debug artifacts")

    # Stage 1.5 args
    parser.add_argument("--resume", action="store_true", help="Resume failed/missing runs only")
    parser.add_argument("--force", action="store_true", help="Force re-processing even if done")

    # Stage 2.0 args
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed documents (requires DB)")
    parser.add_argument("--max-attempts", type=int, default=3, help="Max attempts per document")
    parser.add_argument("--retry-backoff-seconds", type=int, default=0, help="Wait between attempts (seconds)")
    parser.add_argument("--retry-error-kinds", type=str, default="transient,unknown", help="Comma-separated list of error kinds to retry")

    args = parser.parse_args()

    # Parse error kinds
    retry_kinds = [k.strip().lower() for k in args.retry_error_kinds.split(",")]

    # Build PipelineConfig
    cfg = PipelineConfig(
        ocr_root=args.input_dir,
        out_root=args.out_dir,
        prompt_id="Transcribe text", # default
        limit=args.limit or 0,
        debug_dir=args.debug_dir if args.debug_dir else args.out_dir / "debug",
        resume=args.resume,
        force=args.force,
        pipeline_name="gemini-ui-cli",
        retry_failed=args.retry_failed,
        max_attempts=args.max_attempts,
        retry_backoff_seconds=args.retry_backoff_seconds,
        retry_error_kinds=retry_kinds
    )

    if not cfg.ocr_root.exists():
        print(f"Error: Input directory {cfg.ocr_root} does not exist.")
        sys.exit(1)

    cfg.out_root.mkdir(parents=True, exist_ok=True)
    if cfg.debug_dir:
        cfg.debug_dir.mkdir(parents=True, exist_ok=True)

    # Initialize DB Repo if DSN available
    repo = None
    db_cfg = db_config_from_env()
    if db_cfg.dsn:
        try:
            repo = OcrRepo(db_cfg)
            print("DB Write-back enabled.")
        except Exception as e:
            print(f"Warning: Failed to initialize DB repo: {e}")

    # Validation for retry-failed
    if cfg.retry_failed and not repo:
        print("Error: --retry-failed requires DB connection.")
        sys.exit(1)

    # Scan images
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    images = sorted([
        p for p in cfg.ocr_root.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    ])

    if not images:
        print(f"No images found in {cfg.ocr_root}")
        return

    if cfg.limit:
        images = images[:cfg.limit]

    print(f"Processing {len(images)} images...")

    engine = PlaywrightEngine(
        profile_dir=args.profile_dir,
        headless=args.headless,
        debug_dir=cfg.debug_dir
    )

    try:
        print("Starting engine...")
        engine.start()

        for i, img_path in enumerate(images):
            print(f"[{i+1}/{len(images)}] Checking {img_path.name}...")

            run_id = None
            doc_id = None
            last_run = None

            # --- Decision Logic ---
            attempt_no = 1
            parent_run_id = None

            if repo:
                try:
                    s256 = sha256_file(img_path)
                    doc_id = repo.get_or_create_document(str(img_path), s256)
                    last_run = repo.get_latest_run(doc_id, cfg.pipeline_name)

                    decision = decide_retry_action(last_run, cfg)

                    if not decision["should_process"]:
                        print(f"  SKIPPING: {decision['reason']}")
                        # If previously processed but we are skipping, we don't need to do anything
                        # unless we want to record a 'skipped' status for this CLI execution?
                        # The requirements say "record each attempt".
                        # If we explicitly skip, we might not need an ocr_run row unless we want to log the skip.
                        # Stage 1.5 had logic to insert 'skipped' if skipping done items.
                        # Let's preserve that behavior if it's a "fresh" skip (e.g. no run exists but we skip?? No, that's impossible).
                        # If we skip because it's done, we can log it if we want, but usually unnecessary spam.
                        # Only if we skip for a reason that might be interesting?
                        # For now, just continue.
                        continue

                    attempt_no = decision["attempt_no"]
                    parent_run_id = decision["parent_run_id"]

                except Exception as e:
                    print(f"  DB Error (pre-flight): {e}")
                    if cfg.retry_failed:
                        print("  Aborting document due to DB error with --retry-failed.")
                        continue
                    # Fallback to process if not strictly depending on history
                    # If DB failed, we can't get last run, so we default to process (attempt 1)
                    pass

            # Backoff (between attempts)
            if attempt_no > 1 and cfg.retry_backoff_seconds > 0:
                 print(f"  Waiting {cfg.retry_backoff_seconds}s before retry...")
                 time.sleep(cfg.retry_backoff_seconds)

            # --- Execution ---
            if repo:
                 run_id = repo.create_run(
                     doc_id,
                     cfg.pipeline_name,
                     status='queued',
                     attempt_no=attempt_no,
                     parent_run_id=parent_run_id
                 )

            # Recovery loop (within attempt)
            max_recovery_retries = 1
            recovery_count = 0

            while True:
                try:
                    if repo and run_id:
                        repo.mark_run_status(run_id, 'processing')
                        repo.mark_step(run_id, 'engine_start', 'started')

                    result = engine.ocr(img_path, prompt_id=cfg.prompt_id)

                    # Save result
                    out_txt = cfg.out_root / f"{img_path.stem}.txt"
                    out_txt.write_text(result.text, encoding="utf-8")
                    print(f"  OK: Saved to {out_txt}")

                    if repo and run_id:
                        repo.mark_run_status(run_id, 'done', out_path=str(out_txt))
                        repo.mark_step(run_id, 'engine_finish', 'done')

                    break # Success, exit recovery loop

                except Exception as e:
                    # Classify error
                    kind = classify_error(e)
                    print(f"  Error: {e} [{kind.value}]")

                    # Recovery Attempt
                    if kind == ErrorKind.TRANSIENT and recovery_count < max_recovery_retries:
                         recovery_count += 1
                         print(f"  Attempting recovery ({recovery_count}/{max_recovery_retries})...")
                         if repo and run_id:
                             repo.mark_step(run_id, 'recover_refresh', 'started')

                         try:
                             engine.recover()
                             if repo and run_id:
                                 repo.mark_step(run_id, 'recover_refresh', 'done')
                         except Exception as rec_e:
                             print(f"  Recovery failed: {rec_e}")
                             if repo and run_id:
                                 repo.mark_step(run_id, 'recover_refresh', 'failed', str(rec_e))

                         continue # Retry loop

                    # Final Failure for this attempt
                    if repo and run_id:
                         repo.mark_run_status(run_id, 'failed', error_message=str(e), error_kind=kind.value)
                         repo.mark_step(run_id, 'engine_finish', 'failed', error_message=str(e))

                    break # Exit recovery loop

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        print("Stopping engine...")
        engine.stop()
        if repo:
            repo.close()

if __name__ == "__main__":
    main()
