from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence


DEFAULT_IMAGE_EXTS: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff")


@dataclass(frozen=True)
class DiscoveredFile:
    path: Path
    rel_path: Path
    file_name: str
    sha256: Optional[str] = None


def is_image_file(path: Path, exts: Sequence[str] = DEFAULT_IMAGE_EXTS) -> bool:
    if not path.is_file():
        return False
    return path.suffix.lower() in set(e.lower() for e in exts)


def iter_files(
    root: Path,
    *,
    recursive: bool,
    exts: Sequence[str] = DEFAULT_IMAGE_EXTS,
    limit: int = 0,
) -> Iterator[DiscoveredFile]:
    """
    Stream discovery of image files.
    - Uses os.scandir (fast, low memory)
    - Deterministic order (sorted by name per directory)
    """
    root = root.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Input root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Input root is not a directory: {root}")

    yielded = 0

    def _scan_dir(dir_path: Path) -> Iterable[Path]:
        # sort for deterministic behavior
        with os.scandir(dir_path) as it:
            entries = sorted(it, key=lambda e: e.name.lower())
        for e in entries:
            p = Path(e.path)
            if e.is_file():
                if is_image_file(p, exts=exts):
                    yield p
            elif e.is_dir() and recursive:
                yield from _scan_dir(p)

    for p in _scan_dir(root):
        rel = p.relative_to(root)
        yield DiscoveredFile(path=p, rel_path=rel, file_name=p.name, sha256=None)
        yielded += 1
        if limit and yielded >= limit:
            break


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """
    Compute sha256 of a file using streaming reads.
    Default chunk_size=1MB (fast enough, low memory).
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def with_sha256(items: Iterable[DiscoveredFile]) -> Iterator[DiscoveredFile]:
    """Yield DiscoveredFile with sha256 computed."""
    for it in items:
        yield DiscoveredFile(
            path=it.path,
            rel_path=it.rel_path,
            file_name=it.file_name,
            sha256=sha256_file(it.path),
        )
