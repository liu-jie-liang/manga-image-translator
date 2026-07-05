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

    def test_text_regions_none_with_text_content_skips_progress(self):
        """text_regions=None (translation failed) but text was detected → skip progress."""
        ctx = Context()
        ctx.result = 'fake_image_data'
        ctx.text_regions = None  # translation completely failed
        ctx.textlines = [_make_textline('original japanese text')]
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

    def test_params_overwrite_always_true_retrans_true(self):
        """Verify _translate_directory sets overwrite=True when retrans=True."""
        from manga_translator.batch import _translate_directory
        from unittest.mock import AsyncMock, patch

        with patch('manga_translator.batch._get_translator') as mock_get_translator:
            mock_translator = AsyncMock()
            mock_translator.translate_path = AsyncMock()
            mock_get_translator.return_value = mock_translator

            with patch('manga_translator.batch._get_image_files', return_value=[]):
                import asyncio
                asyncio.run(_translate_directory('/fake/src', '/fake/dest', retrans=True))

                call_args = mock_translator.translate_path.call_args
                params = call_args[0][2]  # 3rd positional arg
                assert params['overwrite'] is True
                assert params['retrans'] is True

    def test_params_overwrite_always_true_retrans_false(self):
        """Verify _translate_directory sets overwrite=True when retrans=False."""
        from manga_translator.batch import _translate_directory
        from unittest.mock import AsyncMock, patch

        with patch('manga_translator.batch._get_translator') as mock_get_translator:
            mock_translator = AsyncMock()
            mock_translator.translate_path = AsyncMock()
            mock_get_translator.return_value = mock_translator

            with patch('manga_translator.batch._get_image_files', return_value=[]):
                import asyncio
                asyncio.run(_translate_directory('/fake/src', '/fake/dest', retrans=False))

                call_args = mock_translator.translate_path.call_args
                params = call_args[0][2]  # 3rd positional arg
                assert params['overwrite'] is True
                assert params['retrans'] is False

    def test_translate_file_overwrites_when_dest_exists(self):
        """Verify translate_file logs overwrite message when dest exists."""
        from manga_translator.mode.local import MangaTranslatorLocal
        from unittest.mock import AsyncMock, patch, MagicMock
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, 'src.png')
            dest = os.path.join(tmpdir, 'dest.png')
            with open(src, 'w') as f:
                f.write('')
            with open(dest, 'w') as f:
                f.write('')

            translator = MangaTranslatorLocal.__new__(MangaTranslatorLocal)
            translator.attempts = 3
            translator.save_text = False
            translator.save_text_file = False
            translator.prep_manual = False
            translator.ignore_errors = False
            translator.save_quality = 95
            translator.disable_rendering = False
            translator._last_translation_ctx = None

            with patch.object(translator, '_translate_file', new_callable=AsyncMock) as mock_translate:
                mock_translate.return_value = True
                with patch('manga_translator.mode.local.logger') as mock_logger:
                    import asyncio
                    asyncio.run(translator.translate_file(src, dest, {}, MagicMock()))

                    overwrite_logged = any(
                        'Overwriting' in str(call) for call in mock_logger.info.call_args_list
                    )
                    assert overwrite_logged, 'Should log "Overwriting existing file"'

    def test_translate_file_no_skip_when_overwrite_true(self):
        """Verify translate_file does NOT skip when dest exists and overwrite=True."""
        from manga_translator.mode.local import MangaTranslatorLocal
        from unittest.mock import AsyncMock, patch, MagicMock
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, 'src.png')
            dest = os.path.join(tmpdir, 'dest.png')
            with open(src, 'w') as f:
                f.write('')
            with open(dest, 'w') as f:
                f.write('')

            translator = MangaTranslatorLocal.__new__(MangaTranslatorLocal)
            translator.attempts = 3
            translator.save_text = False
            translator.save_text_file = False
            translator.prep_manual = False
            translator.ignore_errors = False
            translator.save_quality = 95
            translator.disable_rendering = False
            translator._last_translation_ctx = None

            with patch.object(translator, '_translate_file', new_callable=AsyncMock) as mock_translate:
                mock_translate.return_value = True
                import asyncio
                asyncio.run(translator.translate_file(src, dest, {}, MagicMock()))

                mock_translate.assert_called_once()