
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from ocr_gemini.cli import _scan_images

class TestFileOrdering(unittest.TestCase):
    def test_scan_images_non_recursive_ordering_and_limit(self):
        """
        Verify that _scan_images sorts files alphabetically before applying limit (non-recursive).
        """
        input_dir = Path("/tmp/fake_dir")

        # Patch is_file on the class, not instance
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'is_dir', return_value=True), \
             patch.object(Path, 'is_file', return_value=True), \
             patch.object(Path, 'iterdir') as mock_iterdir:

            # Create real paths
            files = [
                Path("/tmp/fake_dir/z_image.png"),
                Path("/tmp/fake_dir/a_image.jpg"),
                Path("/tmp/fake_dir/m_image.png")
            ]

            # Simulate iterdir returning them in unsorted order
            mock_iterdir.return_value = files # Z, A, M

            # Call with limit 2
            result = _scan_images(input_dir, recursive=False, limit=2)

            # Expected: Sorted [A, M, Z], then limit 2 -> [A, M]
            # Path sorting is based on path string.
            # /tmp/fake_dir/a_image.jpg
            # /tmp/fake_dir/m_image.png
            # /tmp/fake_dir/z_image.png

            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].name, "a_image.jpg")
            self.assertEqual(result[1].name, "m_image.png")

    def test_scan_images_recursive_ordering_and_limit(self):
        """
        Verify that _scan_images sorts files alphabetically before applying limit (recursive).
        """
        input_dir = Path("/tmp/fake_dir")

        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'is_dir', return_value=True), \
             patch("os.walk") as mock_walk:

            # Mock os.walk structure
            # Structure:
            # /tmp/fake_dir
            #   - z.png
            #   /sub1
            #     - c.png
            #   /sub2
            #     - a.png

            # os.walk yield order could be anything.
            mock_walk.return_value = [
                ("/tmp/fake_dir", ["sub1", "sub2"], ["z.png"]),
                ("/tmp/fake_dir/sub2", [], ["a.png"]),
                ("/tmp/fake_dir/sub1", [], ["c.png"]),
            ]

            # Call with limit 2
            result = _scan_images(input_dir, recursive=True, limit=2)

            # Paths found:
            # /tmp/fake_dir/z.png
            # /tmp/fake_dir/sub2/a.png
            # /tmp/fake_dir/sub1/c.png

            # Sorted order (lexicographical):
            # /tmp/fake_dir/sub1/c.png  (sub1 < sub2 < z.png)
            # /tmp/fake_dir/sub2/a.png
            # /tmp/fake_dir/z.png

            # Limit 2 -> sub1/c.png, sub2/a.png

            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].name, "c.png")
            self.assertEqual(result[1].name, "a.png")

if __name__ == '__main__':
    unittest.main()
