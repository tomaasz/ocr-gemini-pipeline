from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..debug import save_debug_artifacts
from ..utils import retry_call, wait_for_generation_complete
from .engine import OcrEngine, OcrResult


class PlaywrightEngine(OcrEngine):
    """
    Concrete implementation of OcrEngine using Playwright for browser automation.

    This engine handles the full lifecycle of a browser session to interact with
    the generative AI interface.
    """

    def __init__(
        self, debug_dir: Optional[Path] = None, timeout_ms: int = 180000
    ) -> None:
        """
        Initialize the PlaywrightEngine.

        Args:
            debug_dir: Directory to save debug artifacts on failure.
            timeout_ms: Global timeout for UI operations in milliseconds.

        TODO:
            - Initialize Playwright instance (browser lifecycle management).
            - Set up browser context and page management strategies.
            - Configure browser launch options (headless, args, etc.).
        """
        self.debug_dir = debug_dir
        self.timeout_ms = timeout_ms

    def ocr(self, image_path: Path, prompt_id: str) -> OcrResult:
        """
        Perform OCR on a given image using the Playwright-driven UI.

        This method orchestrates the interaction with the web interface:
        1. Navigates to the target URL.
        2. Uploads the image.
        3. Enters the prompt.
        4. Waits for generation to complete.
        5. Extracts the result.

        Error handling and reliability:
        - Uses `retry_call` for transient failures (e.g., network glitches, element interaction).
        - Uses `wait_for_generation_complete` to poll for completion status.
        - Triggers `save_debug_artifacts` on critical failures or before raising exceptions.

        Args:
            image_path: Path to the image file to process.
            prompt_id: Identifier for the prompt to use.

        Returns:
            OcrResult containing the extracted text and metadata.

        Raises:
            NotImplementedError: Method is not yet implemented.

        TODO:
            - Implement selectors / locators for UI elements (upload button, prompt area, result container).
            - Implement the interaction flow using Playwright page objects.
            - Wire up retry and wait logic using the imported helper functions.
            - Ensure debug artifacts are saved in `except` blocks.
        """
        raise NotImplementedError("PlaywrightEngine.ocr() is not yet implemented.")
