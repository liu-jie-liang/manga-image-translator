"""
TDD: Test local.py non-recursive scan and image filtering.

Assertions:
- os.listdir only processes current directory (no subdirectories)
- Non-image files are skipped
- .translate_progress.json is skipped
- Empty directories don't cause errors
"""
import os
import json
import tempfile
import pytest
from PIL import Image

from manga_translator.mode.local import _get_image_files


def _create_test_image(path: str):
    """Create a 1x1 pixel test image."""
    img = Image.new('RGB', (1, 1), color='red')
    img.save(path)


class TestGetImageFiles:
    """Tests for _get_image_files() — non-recursive image file discovery."""

    def test_flat_directory_images_only(self):
        """Flat directory with only image files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_test_image(os.path.join(tmpdir, 'page01.png'))
            _create_test_image(os.path.join(tmpdir, 'page02.jpg'))
            _create_test_image(os.path.join(tmpdir, 'page03.webp'))

            files = _get_image_files(tmpdir)
            assert files == ['page01.png', 'page02.jpg', 'page03.webp']

    def test_skips_non_image_files(self):
        """Non-image files (txt, zip, etc.) are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_test_image(os.path.join(tmpdir, 'page01.png'))
            with open(os.path.join(tmpdir, 'readme.txt'), 'w') as f:
                f.write('hello')
            with open(os.path.join(tmpdir, 'data.zip'), 'w') as f:
                f.write('fake')

            files = _get_image_files(tmpdir)
            assert files == ['page01.png']

    def test_skips_subdirectories(self):
        """Subdirectories are not recursed into."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_test_image(os.path.join(tmpdir, 'page01.png'))
            subdir = os.path.join(tmpdir, 'sub_chapter')
            os.makedirs(subdir)
            _create_test_image(os.path.join(subdir, 'page02.png'))

            files = _get_image_files(tmpdir)
            assert files == ['page01.png']

    def test_skips_progress_file(self):
        """.translate_progress.json is skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_test_image(os.path.join(tmpdir, 'page01.png'))
            with open(os.path.join(tmpdir, '.translate_progress.json'), 'w') as f:
                json.dump({'completed': ['page01.png']}, f)

            files = _get_image_files(tmpdir)
            assert files == ['page01.png']

    def test_skips_dot_thumb(self):
        """.thumb file is skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_test_image(os.path.join(tmpdir, 'page01.png'))
            os.makedirs(os.path.join(tmpdir, '.thumb'))

            files = _get_image_files(tmpdir)
            assert files == ['page01.png']

    def test_empty_directory(self):
        """Empty directory returns empty list, no error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = _get_image_files(tmpdir)
            assert files == []

    def test_directory_with_only_non_images(self):
        """Directory with only non-image files returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'readme.txt'), 'w') as f:
                f.write('hello')
            os.makedirs(os.path.join(tmpdir, 'subdir'))

            files = _get_image_files(tmpdir)
            assert files == []

    def test_natural_sort_order(self):
        """Image files are returned in natural sort order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_test_image(os.path.join(tmpdir, 'page10.png'))
            _create_test_image(os.path.join(tmpdir, 'page2.png'))
            _create_test_image(os.path.join(tmpdir, 'page1.png'))

            files = _get_image_files(tmpdir)
            assert files == ['page1.png', 'page2.png', 'page10.png']

    def test_all_supported_extensions(self):
        """All supported image extensions are recognized."""
        from manga_translator.batch import IMAGE_EXTS
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = []
            for ext in sorted(IMAGE_EXTS):
                filename = f'test{ext}'
                _create_test_image(os.path.join(tmpdir, filename))
                expected.append(filename)

            files = _get_image_files(tmpdir)
            assert files == expected

    def test_case_insensitive_extensions(self):
        """Image extensions are matched case-insensitively."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_test_image(os.path.join(tmpdir, 'page.PNG'))
            _create_test_image(os.path.join(tmpdir, 'page2.JPG'))

            files = _get_image_files(tmpdir)
            assert 'page.PNG' in files
            assert 'page2.JPG' in files