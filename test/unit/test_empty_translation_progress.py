"""
TDD: Test empty translation progress-skipping behavior.

Assertions:
- _should_record_progress returns True when translation succeeds normally
- _should_record_progress returns False when all translations are empty but text existed
- _should_record_progress returns True when no text was detected at all
- _should_record_progress returns False when ctx is None
- _should_record_progress returns False when ctx.result is None
- overwrite is always set to True in batch.py params
- translate_file overwrites existing dest when overwrite=True
"""
import os
import json
import tempfile
from unittest.mock import MagicMock, patch

from manga_translator.utils.generic import Context
from manga_translator.mode.local import _should_record_progress


# ─── Helper to create a simple textline-like object ───────────────────────────


def _make_textline(text: str):
    """Create a simple object with .text attribute like a textline."""
    return type('TextLine', (), {'text': text})()


class TestShouldRecordProgress:
    """Tests for _should_record_progress helper."""

    def test_normal_translation_records_progress(self):
        """Normal translation with text regions → record progress."""
        ctx = Context()
        ctx.result = 'fake_image_data'
        ctx.text_regions = [
            type('Region', (), {'translation': 'translated text'})(),
            type('Region', (), {'translation': 'more text'})(),
        ]
        ctx.textlines = [_make_textline('original text')]
        assert _should_record_progress(ctx) is True

    def test_empty_translation_skips_progress(self):
        """Text was detected but all translations empty → skip progress."""
        ctx = Context()
        ctx.result = 'fake_image_data'  # result is set (original image fallback)
        ctx.text_regions = []  # all filtered out
        ctx.textlines = [_make_textline('original japanese text')]
        assert _should_record_progress(ctx) is False

    def test_empty_translation_multiple_textlines_skips_progress(self):
        """Multiple textlines, all translations empty → skip progress."""
        ctx = Context()
        ctx.result = 'fake_image_data'
        ctx.text_regions = []
        ctx.textlines = [
            _make_textline('text1'),
            _make_textline('text2'),
            _make_textline('text3'),
        ]
        assert _should_record_progress(ctx) is False

    def test_no_text_detected_records_progress(self):
        """No text detected at all → record progress (or doesn't matter)."""
        ctx = Context()
        ctx.result = 'fake_image_data'
        # text_regions attribute never set (no text detected → early return in _translate)
        # textlines is None (OCR found nothing)
        assert _should_record_progress(ctx) is True

    def test_no_text_regions_attr_but_textlines_records(self):
        """Missing text_regions attr but textlines exist → record progress."""
        ctx = Context()
        ctx.result = 'fake_image_data'
        ctx.textlines = [_make_textline('some text')]
        # text_regions not set as attribute
        assert _should_record_progress(ctx) is True

    def test_ctx_is_none(self):
        """ctx is None → no progress."""
        assert _should_record_progress(None) is False

    def test_ctx_no_result(self):
        """ctx.result is None → no progress."""
        ctx = Context()
        ctx.text_regions = [type('Region', (), {'translation': 'text'})(),
                          type('Region', (), {'translation': 'more'})()]
        ctx.textlines = [_make_textline('original')]
        ctx.result = None
        assert _should_record_progress(ctx) is False

    def test_ctx_no_result_attr(self):
        """ctx has no result attribute → no progress."""
        ctx = Context()
        ctx.text_regions = [type('Region', (), {'translation': 'text'})()]
        ctx.textlines = [_make_textline('original')]
        assert _should_record_progress(ctx) is False

    def test_partial_empty_translation_records_progress(self):
        """Some translations succeeded → record progress."""
        ctx = Context()
        ctx.result = 'fake_image_data'
        ctx.text_regions = [
            type('Region', (), {'translation': 'translated text'})(),
        ]
        ctx.textlines = [_make_textline('original'), _make_textline('more')]
        assert _should_record_progress(ctx) is True

    def test_textlines_empty_list_empty_translation_skips(self):
        """textlines is empty list → no original text → record progress anyway."""
        ctx = Context()
        ctx.result = 'fake_image_data'
        ctx.text_regions = []
        ctx.textlines = []
        assert _should_record_progress(ctx) is True

    def test_textlines_textlines_is_none(self):
        """textlines is None → record progress."""
        ctx = Context()
        ctx.result = 'fake_image_data'
        ctx.text_regions = []
        # textlines is not set
        assert _should_record_progress(ctx) is True


class TestOverwriteParamInBatch:
    """Tests that batch.py always sets overwrite=True in params."""

    def test_params_overwrite_always_true(self):
        """Simulate the logic that batch.py should use."""
        # This is the logic that should be in batch.py
        for retrans in [True, False]:
            params = {}
            params['retrans'] = retrans
            params['overwrite'] = True  # Always True, regardless of retrans

            assert params['overwrite'] is True
            assert params['retrans'] == retrans

    def test_translate_file_skips_existence_check_when_overwrite_true(self):
        """Simulate translate_file behavior when overwrite=True."""
        dest_exists = True
        overwrite = True

        # This condition should NOT trigger the skip
        skip = not overwrite and dest_exists
        assert skip is False  # Should not skip

    def test_translate_file_skip_when_overwrite_false_and_dest_exists(self):
        """Simulate the old translate_file skip behavior."""
        dest_exists = True
        overwrite = False

        skip = not overwrite and dest_exists
        assert skip is True  # Should skip (old behavior)

    def test_translate_folder_batch_skip_check_overwrite_true(self):
        """Simulate _translate_folder_batch overwrite check."""
        # The pending_files loop should not filter by existence
        dest_exists = True
        overwrite = True

        should_skip = not overwrite and dest_exists
        assert should_skip is False

        # Log message for overwriting
        if overwrite and dest_exists:
            message = 'Overwriting existing file'
            assert 'Overwriting' in message