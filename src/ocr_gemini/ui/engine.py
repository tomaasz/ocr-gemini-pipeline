from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Protocol


@dataclass(frozen=True)
class OcrResult:
    text: str
    data: Dict[str, Any]


class OcrEngine(Protocol):
    def ocr(self, image_path: Path, prompt_id: str) -> OcrResult: ...
