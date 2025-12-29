from pathlib import Path
import pytest

from ocr_gemini.files import iter_files, sha256_file


def _touch(p: Path, content: bytes = b"x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)


def test_sha256_file_is_deterministic(tmp_path: Path):
    f = tmp_path / "a.bin"
    _touch(f, b"hello")

    h1 = sha256_file(f)
    h2 = sha256_file(f)

    assert h1 == h2
    assert isinstance(h1, str)
    assert len(h1) == 64


def _paths(files):
    # iter_files zwraca Path albo DiscoveredFile(path=...)
    return [getattr(x, "path", x) for x in files]


def test_iter_files_non_recursive_returns_only_top_level(tmp_path: Path):
    _touch(tmp_path / "a.jpg")
    _touch(tmp_path / "b.png")
    _touch(tmp_path / "sub" / "c.jpg")

    files = _paths(iter_files(tmp_path, recursive=False))
    names = {p.name for p in files}

    assert names == {"a.jpg", "b.png"}


def test_iter_files_recursive_finds_nested(tmp_path: Path):
    _touch(tmp_path / "a.jpg")
    _touch(tmp_path / "sub" / "c.jpg")

    files = _paths(iter_files(tmp_path, recursive=True))
    names = {p.name for p in files}

    assert names == {"a.jpg", "c.jpg"}


def test_iter_files_order_is_deterministic(tmp_path: Path):
    _touch(tmp_path / "z.jpg")
    _touch(tmp_path / "a.jpg")
    _touch(tmp_path / "m.jpg")

    files1 = _paths(iter_files(tmp_path, recursive=False))
    files2 = _paths(iter_files(tmp_path, recursive=False))

    assert files1 == files2
    assert [p.name for p in files1] == sorted(p.name for p in files1)


@pytest.mark.parametrize("recursive", [False, True])
def test_iter_files_skips_non_files(tmp_path: Path, recursive: bool):
    (tmp_path / "dir").mkdir()

    files = _paths(iter_files(tmp_path, recursive=recursive))

    assert all(p.is_file() for p in files)
