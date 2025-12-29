import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import os
import sys

# Add root to sys.path to allow importing gemini_ocr
sys.path.append(str(Path(__file__).parent.parent))

from gemini_ocr import iter_images

@pytest.fixture
def fs_structure(tmp_path):
    # Create structure:
    # root/
    #   a.jpg
    #   b.txt
    #   sub/
    #     c.png
    #     d.jpg
    #   sub2/
    #     e.webp

    (tmp_path / "a.jpg").touch()
    (tmp_path / "b.txt").touch()
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.png").touch()
    (tmp_path / "sub" / "d.jpg").touch()
    (tmp_path / "sub2").mkdir()
    (tmp_path / "sub2" / "e.webp").touch()
    return tmp_path

def test_iter_images_flat(fs_structure):
    results = list(iter_images(fs_structure, recursive=False))
    names = sorted([p.name for p in results])
    assert names == ["a.jpg"]

def test_iter_images_recursive(fs_structure):
    results = list(iter_images(fs_structure, recursive=True))
    names = sorted([p.name for p in results])
    assert names == ["a.jpg", "c.png", "d.jpg", "e.webp"]

def test_no_rglob_usage(fs_structure):
    with patch("pathlib.Path.rglob", side_effect=RuntimeError("rglob called!")):
        with patch("pathlib.Path.glob", side_effect=RuntimeError("glob called!")):
            results = list(iter_images(fs_structure, recursive=True))
            assert len(results) == 4

def test_iter_images_is_generator(fs_structure):
    gen = iter_images(fs_structure, recursive=True)
    assert iter(gen) is gen


def test_limit_stops_recursion(fs_structure):
    # Verify that we stop scanning subdirectories if we stop consuming the generator.
    # Structure:
    # root/
    #   a.jpg
    #   b.txt
    #   sub/
    #     c.png
    #     d.jpg
    #   sub2/
    #     e.webp

    # We will mock os.scandir to track which directories are opened.
    # iter_images sorts entries by name.
    # Root contains: a.jpg, b.txt, sub, sub2.
    # Sorted order: a.jpg, b.txt, sub, sub2.

    # If we consume 1 item (a.jpg) and close, 'sub' and 'sub2' should NOT be scanned.

    original_scandir = os.scandir
    scanned_paths = []

    def side_effect(path):
        scanned_paths.append(Path(path).name)
        return original_scandir(path)

    with patch("os.scandir", side_effect=side_effect):
        gen = iter_images(fs_structure, recursive=True)
        # Consume 1 item
        item = next(gen)
        assert item.name == "a.jpg"

        # Close the generator explicitly (simulate break)
        gen.close()

    # Check that we did NOT scan subdirectories
    # Root dir name is random, but 'sub' and 'sub2' are fixed names.
    assert "sub" not in scanned_paths
    assert "sub2" not in scanned_paths
