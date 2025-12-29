from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_stem(name: str, *, max_len: int = 180) -> str:
    """
    Create a filesystem-safe stem from a filename (without extension).
    Keeps [A-Za-z0-9._-], replaces others with '_'.
    """
    stem = Path(name).stem
    stem = _SAFE_STEM_RE.sub("_", stem).strip("._-")
    if not stem:
        stem = "file"
    return stem[:max_len]


@dataclass(frozen=True)
class OutputPaths:
    base_dir: Path
    txt_path: Path
    json_path: Path
    meta_path: Path


def make_output_paths(out_root: Path, rel_path: Path, file_name: str) -> OutputPaths:
    """
    Output layout:
      out_root/<rel_dir>/<safe_stem>/
        result.txt
        result.json
        meta.json
    """
    out_root = out_root.expanduser().resolve()
    rel_dir = rel_path.parent  # preserve directory structure
    base_dir = out_root / rel_dir / safe_stem(file_name)
    return OutputPaths(
        base_dir=base_dir,
        txt_path=base_dir / "result.txt",
        json_path=base_dir / "result.json",
        meta_path=base_dir / "meta.json",
    )


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_outputs(
    *,
    out_root: Path,
    rel_path: Path,
    file_name: str,
    text: Optional[str],
    data_json: Optional[Dict[str, Any]],
    meta: Dict[str, Any],
) -> OutputPaths:
    """
    Write output artifacts for a processed file.
    - text -> result.txt (if provided)
    - data_json -> result.json (if provided)
    - meta -> meta.json (always)
    """
    paths = make_output_paths(out_root, rel_path, file_name)

    ensure_dir(paths.base_dir)

    if text is not None:
        write_text(paths.txt_path, text)

    if data_json is not None:
        write_json(paths.json_path, data_json)

    write_json(paths.meta_path, meta)

    return paths
