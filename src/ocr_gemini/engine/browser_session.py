from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page, Playwright

class BrowserSession:
    """
    Manages a single persistent browser session.
    Enforces strict sequential execution (no concurrency).
    """
    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def start(self, headless: bool, profile_dir: Path) -> None:
        """
        Starts the persistent browser context.
        """
        from playwright.sync_api import sync_playwright

        if self._context:
            return

        self._playwright = sync_playwright().start()

        # Ensure profile directory exists
        profile_dir.mkdir(parents=True, exist_ok=True)

        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            # Basic evasion to avoid immediate detection, though full evasion is complex
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 720}
        )

        # Get or create the first page
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = self._context.new_page()

    def stop(self) -> None:
        """
        Closes the browser context and stops Playwright.
        """
        if self._context:
            self._context.close()
            self._context = None
            self._page = None

        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    @property
    def page(self) -> Page:
        """Returns the active page. Raises RuntimeError if not started."""
        if not self._page:
            raise RuntimeError("BrowserSession not started. Call start() first.")
        return self._page
