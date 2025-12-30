import argparse
import sys
import os
from pathlib import Path

from .engine.playwright_engine import PlaywrightEngine
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

    args = parser.parse_args()

    # Build PipelineConfig
    cfg = PipelineConfig(
        ocr_root=args.input_dir,
        out_root=args.out_dir,
        prompt_id="Transcribe text", # default
        limit=args.limit or 0,
        debug_dir=args.debug_dir if args.debug_dir else args.out_dir / "debug",
        resume=args.resume,
        force=args.force,
        pipeline_name="gemini-ui-cli"
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
            print(f"[{i+1}/{len(images)}] Processing {img_path.name}...")

            run_id = None
            doc_id = None

            if repo:
                try:
                    # Calculate sha256
                    s256 = sha256_file(img_path)
                    doc_id = repo.get_or_create_document(str(img_path), s256)

                    has_done = repo.has_successful_run(doc_id, cfg.pipeline_name)

                    if has_done and not cfg.force:
                        print(f"  SKIPPING: Already done (and --force not set).")
                        repo.create_run(doc_id, cfg.pipeline_name, status='skipped')
                        continue

                    # Create queued run
                    run_id = repo.create_run(doc_id, cfg.pipeline_name, status='queued')

                except Exception as e:
                    print(f"  DB Error (pre-flight): {e}")
                    # Proceed without DB for this run
                    pass

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

            except Exception as e:
                print(f"  FAILED: {e}")
                if repo and run_id:
                     repo.mark_run_status(run_id, 'failed', error_message=str(e))
                     repo.mark_step(run_id, 'engine_finish', 'failed', error_message=str(e))
                # Continue to next image

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        print("Stopping engine...")
        engine.stop()
        if repo:
            repo.close()

if __name__ == "__main__":
    main()
