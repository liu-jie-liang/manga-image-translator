"""
TDD: Test progress tracking in local.py.

Assertions:
- _load_progress returns empty set when no progress file exists
- _save_progress creates the file and loads correctly
- _load_progress skips completed files in list
- _clear_progress deletes the file
- retrans flag clears progress
"""
import os
import json
import tempfile

from manga_translator.mode.local import _load_progress, _save_progress, _clear_progress


class TestProgressTracking:
    """Tests for progress file management."""

    def test_load_empty_when_no_file(self):
        """No progress file → returns empty set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            completed = _load_progress(tmpdir)
            assert completed == set()

    def test_save_and_load(self):
        """Save completed files → load returns them."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _save_progress(tmpdir, 'page01.png')
            _save_progress(tmpdir, 'page02.png')

            completed = _load_progress(tmpdir)
            assert completed == {'page01.png', 'page02.png'}

    def test_save_is_idempotent(self):
        """Saving same file twice doesn't duplicate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _save_progress(tmpdir, 'page01.png')
            _save_progress(tmpdir, 'page01.png')

            completed = _load_progress(tmpdir)
            assert completed == {'page01.png'}

    def test_save_stores_sorted(self):
        """Progress file stores completed list alphabetically sorted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _save_progress(tmpdir, 'z.png')
            _save_progress(tmpdir, 'a.png')

            progress_path = os.path.join(tmpdir, '.translate_progress.json')
            with open(progress_path, 'r') as f:
                data = json.load(f)
            assert data['completed'] == ['a.png', 'z.png']

    def test_clear_progress(self):
        """_clear_progress removes the progress file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _save_progress(tmpdir, 'page01.png')
            assert os.path.exists(os.path.join(tmpdir, '.translate_progress.json'))

            _clear_progress(tmpdir)
            assert not os.path.exists(os.path.join(tmpdir, '.translate_progress.json'))

    def test_clear_progress_nonexistent(self):
        """_clear_progress on directory without progress file does not error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _clear_progress(tmpdir)  # Should not raise

    def test_load_after_clear(self):
        """After clear, load returns empty set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _save_progress(tmpdir, 'page01.png')
            _clear_progress(tmpdir)
            assert _load_progress(tmpdir) == set()

    def test_corrupted_file_returns_empty(self):
        """Corrupted JSON returns empty set gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, '.translate_progress.json'), 'w') as f:
                f.write('not valid json{{{')

            completed = _load_progress(tmpdir)
            assert completed == set()


class TestGetUncompletedFiles:
    """Integration test: combining _get_image_files with progress tracking."""

    def _get_uncompleted_files(self, directory: str) -> list[str]:
        """Return image files that haven't been translated yet."""
        from manga_translator.mode.local import _get_image_files
        all_files = _get_image_files(directory)
        completed = _load_progress(directory)
        return [f for f in all_files if f not in completed]

    def test_all_uncompleted_when_no_progress(self):
        """No progress file → all files are uncompleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from PIL import Image
            img = Image.new('RGB', (1, 1), color='red')
            img.save(os.path.join(tmpdir, 'page01.png'))
            img.save(os.path.join(tmpdir, 'page02.png'))

            result = self._get_uncompleted_files(tmpdir)
            assert result == ['page01.png', 'page02.png']

    def test_partially_completed(self):
        """Some files completed → only uncompleted returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from PIL import Image
            img = Image.new('RGB', (1, 1), color='red')
            img.save(os.path.join(tmpdir, 'page01.png'))
            img.save(os.path.join(tmpdir, 'page02.png'))
            img.save(os.path.join(tmpdir, 'page03.png'))

            _save_progress(tmpdir, 'page01.png')
            _save_progress(tmpdir, 'page03.png')

            result = self._get_uncompleted_files(tmpdir)
            assert result == ['page02.png']

    def test_all_completed(self):
        """All files completed → empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from PIL import Image
            img = Image.new('RGB', (1, 1), color='red')
            img.save(os.path.join(tmpdir, 'page01.png'))
            img.save(os.path.join(tmpdir, 'page02.png'))

            _save_progress(tmpdir, 'page01.png')
            _save_progress(tmpdir, 'page02.png')

            result = self._get_uncompleted_files(tmpdir)
            assert result == []

    def test_retrans_clears_progress(self):
        """After _clear_progress, all files are uncompleted again."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from PIL import Image
            img = Image.new('RGB', (1, 1), color='red')
            img.save(os.path.join(tmpdir, 'page01.png'))
            img.save(os.path.join(tmpdir, 'page02.png'))

            _save_progress(tmpdir, 'page01.png')
            _clear_progress(tmpdir)

            result = self._get_uncompleted_files(tmpdir)
            assert result == ['page01.png', 'page02.png']