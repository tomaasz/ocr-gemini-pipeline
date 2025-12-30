import argparse
import sys
from pathlib import Path

from .engine.playwright_engine import PlaywrightEngine

def main() -> None:
    parser = argparse.ArgumentParser(description="OCR Gemini CLI Runner")
    parser.add_argument("--input-dir", type=Path, required=True, help="Directory containing images")
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory to save results")
    parser.add_argument("--profile-dir", type=Path, required=True, help="Directory for browser profile")
    parser.add_argument("--limit", type=int, help="Max number of images to process")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--debug-dir", type=Path, help="Directory for debug artifacts")

    args = parser.parse_args()

    input_dir: Path = args.input_dir
    out_dir: Path = args.out_dir
    profile_dir: Path = args.profile_dir

    if not input_dir.exists():
        print(f"Error: Input directory {input_dir} does not exist.")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    debug_dir = args.debug_dir if args.debug_dir else out_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    # Scan images
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    images = sorted([
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    ])

    if not images:
        print(f"No images found in {input_dir}")
        return

    if args.limit:
        images = images[:args.limit]

    print(f"Processing {len(images)} images...")

    engine = PlaywrightEngine(
        profile_dir=profile_dir,
        headless=args.headless,
        debug_dir=debug_dir
    )

    try:
        print("Starting engine...")
        engine.start()

        for i, img_path in enumerate(images):
            print(f"[{i+1}/{len(images)}] Processing {img_path.name}...")
            try:
                result = engine.ocr(img_path, prompt_id="Transcribe text")

                # Save result
                out_txt = out_dir / f"{img_path.stem}.txt"
                out_txt.write_text(result.text, encoding="utf-8")
                print(f"  OK: Saved to {out_txt}")

            except Exception as e:
                print(f"  FAILED: {e}")
                # Continue to next image

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        print("Stopping engine...")
        engine.stop()

if __name__ == "__main__":
    main()
