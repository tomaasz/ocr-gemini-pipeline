from __future__ import annotations

from pathlib import Path

from ocr_gemini.engine.core import OcrEngine, OcrResult

class FakeEngine(OcrEngine):
    def ocr(self, image_path: Path, prompt_id: str) -> OcrResult:
        return OcrResult(
            text=f"FAKE OCR: {image_path.name} (prompt_id={prompt_id})",
            data={"engine": "fake", "prompt_id": prompt_id, "file": image_path.name},
        )
