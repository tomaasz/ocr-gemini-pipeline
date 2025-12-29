from playwright.sync_api import sync_playwright
from pathlib import Path

GEMINI_URL = "https://gemini.google.com/app"
PROFILE_DIR = str(Path.home() / ".pw_gemini_profile")

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        viewport={"width": 1400, "height": 900},
    )
    page = ctx.new_page()
    page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=120_000)
    print("\nZALOGUJ SIĘ RĘCZNIE w oknie. Jak skończysz, wróć tu i naciśnij ENTER.\n")
    input()
    ctx.close()
