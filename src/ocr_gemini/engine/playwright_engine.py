from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..debug import save_debug_artifacts
from ..ui import actions
from .core import OcrEngine, OcrResult
from .browser_session import BrowserSession


class PlaywrightEngine(OcrEngine):
    """
    Concrete implementation of OcrEngine using Playwright for browser automation.
    Sequential, single-session.
    """

    def __init__(
        self,
        profile_dir: Path,
        headless: bool = False,
        debug_dir: Optional[Path] = None,
        timeout_ms: int = 180000,
    ) -> None:
        """
        Initialize the PlaywrightEngine.

        Args:
            profile_dir: Directory for the persistent browser profile.
            headless: Whether to run the browser in headless mode.
            debug_dir: Directory to save debug artifacts on failure.
            timeout_ms: Global timeout for UI operations in milliseconds.
        """
        self.profile_dir = profile_dir
        self.headless = headless
        self.debug_dir = debug_dir
        self.timeout_ms = timeout_ms
        self.session = BrowserSession()

    def start(self) -> None:
        """Starts the browser session."""
        self.session.start(headless=self.headless, profile_dir=self.profile_dir)

    def stop(self) -> None:
        """Stops the browser session."""
        self.session.stop()

    def recover(self) -> None:
        """
        Attempts to recover the session from a transient error state.
        Currently implements a simple page reload.
        """
        if self.session.page:
            try:
                self.session.page.reload()
            except Exception as e:
                raise RuntimeError(f"Recovery (reload) failed: {e}") from e

    def ocr(self, image_path: Path, prompt_id: str) -> OcrResult:
        """
        Perform OCR on a given image using the Playwright-driven UI.

        Args:
            image_path: Path to the image file.
            prompt_id: text to use as prompt (or ID).
        """
        try:
            page = self.session.page
        except RuntimeError as e:
            raise RuntimeError("Engine not started. Call start() before ocr().") from e

        try:
            # 1. Navigate (if needed)
            if "gemini.google.com" not in (page.url or ""):
                page.goto("https://gemini.google.com/app", timeout=60000)

            # 2. Upload image (robust implementation lives in actions.upload_image)
            actions.upload_image(
                page,
                image_path,
                timeout_ms=30000,
                debug_dir=self.debug_dir,
            )

            # 3. Enter Prompt
            prompt_text = prompt_id if prompt_id else "Extract text from this image."

            composer = page.locator("div[contenteditable='true']").first
            composer.click()
            composer.fill(prompt_text)

            # 4. Send and Wait
            actions.send_message(
                page,
                debug_dir=self.debug_dir,
                generation_timeout_ms=self.timeout_ms,
            )

            # 5. Get Result
            text = actions.get_last_response(page)

            return OcrResult(
                text=text,
                data={"image": str(image_path), "status": "success"},
            )

        except Exception:
            try:
                save_debug_artifacts(page, self.debug_dir, f"ocr_failed_{image_path.name}")
            except Exception:
                pass
            raise
