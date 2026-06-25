#!/usr/bin/env python3
"""
Diagnostic script: investigate why a specific image translates to empty results.

Usage:
    python test/e2e/debug_empty_translation.py /path/to/image.png

This script runs the full manga-translator pipeline on a single image and
diagnoses translation failures by instrumenting the translator layer.

WHAT IT CHECKS (without reading image text content):
  - OCR stage: how many text regions were detected (count only)
  - Translation stage:
    - Whether the model was invoked at all (prompt_tokens == 0?)
    - Whether the model returned a response (completion_tokens == 0?)
    - How many translations were returned vs expected
    - Whether parsing (regex extraction) produced empty results
  - Benchmark timing for each stage

NOTE: This script does NOT log the original OCR text or the raw translation
content to avoid exposing any sensitive content.
"""

import os
import sys
import time
import json
import copy
import logging
import traceback
from typing import List, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger('debug_diag')

# Suppress noise from other loggers
for name in ['PIL', 'urllib3', 'httpx']:
    logging.getLogger(name).setLevel(logging.WARNING)


# ─── Monkey-patch GaltranslLocalTranslator for diagnostics ───────────────

_original_translate = None
_diag_data = {
    'queries_count': 0,
    'non_empty_queries_count': 0,
    'translations_returned': 0,
    'empty_translations': 0,
    'prompt_tokens': 0,
    'completion_tokens': 0,
    'has_usage': False,
    'parse_success': False,
    'timing_ms': 0,
    'error': None,
    'raw_response_length': 0,
    'batch_size': 0,
}


def _instrumented_translate(self, from_lang, to_lang, queries: List[str]):
    """Instrumented version of GaltranslLocalTranslator._translate."""
    import asyncio

    _diag_data['queries_count'] = len(queries)
    _diag_data['non_empty_queries_count'] = sum(1 for q in queries if q.strip())
    _diag_data['batch_size'] = len(queries)

    if not queries:
        logger.warning('[DIAG] No queries to translate (OCR found no text)')
        return asyncio.ensure_future(_original_translate(self, from_lang, to_lang, queries))

    logger.info(f'[DIAG] Sending {len(queries)} queries to model '
                f'({_diag_data["non_empty_queries_count"]} non-empty)')

    # Create a coroutine wrapper to capture results
    async def wrapped():
        t0 = time.time()
        try:
            result = await _original_translate(self, from_lang, to_lang, queries)
            _diag_data['timing_ms'] = round((time.time() - t0) * 1000, 1)

            # Capture token usage from translator's _last_usage
            if hasattr(self, '_last_usage') and self._last_usage:
                _diag_data['prompt_tokens'] = self._last_usage.get('prompt_tokens', 0)
                _diag_data['completion_tokens'] = self._last_usage.get('completion_tokens', 0)
                _diag_data['has_usage'] = True
                logger.info(f'[DIAG] Token usage: prompt={_diag_data["prompt_tokens"]}, '
                            f'completion={_diag_data["completion_tokens"]}')
            else:
                _diag_data['has_usage'] = False
                logger.warning('[DIAG] No token usage data available')

            # Analyze translation results
            _diag_data['translations_returned'] = len(result)
            _diag_data['empty_translations'] = sum(1 for t in result if not t.strip())
            _diag_data['parse_success'] = len(result) > 0

            if result:
                logger.info(f'[DIAG] Translations: {len(result)} returned, '
                            f'{_diag_data["empty_translations"]} empty')
                if _diag_data['empty_translations'] == len(result):
                    logger.warning('[DIAG] ALL translations are empty! '
                                   'Model may have failed or response format is wrong')
                elif _diag_data['empty_translations'] > 0:
                    logger.warning(f'[DIAG] {_diag_data["empty_translations"]}/{len(result)} '
                                   'translations are empty')
            else:
                logger.warning('[DIAG] Model returned empty list! '
                               'Check regex parsing or model response format')

            return result

        except Exception as e:
            _diag_data['error'] = str(e)
            _diag_data['timing_ms'] = round((time.time() - t0) * 1000, 1)
            logger.error(f'[DIAG] Translation exception: {e}')
            raise

    return asyncio.ensure_future(wrapped())


def _instrumented_parse_response(response: str) -> List[str]:
    """Instrumented version of GaltranslLocalTranslator._parse_response."""
    _diag_data['raw_response_length'] = len(response)

    results = _original_parse_response(response)
    _diag_data['parse_success'] = len(results) > 0

    if not results and response.strip():
        logger.warning(f'[DIAG] _parse_response returned NO matches! '
                       f'Response length: {len(response)} chars. '
                       'Response likely not in expected 「...」 format.')
    return results


# Store original for restore
_original_parse_response = None


def patch_translator():
    """Apply diagnostic monkey-patches to translator classes."""
    global _original_translate, _original_parse_response

    from manga_translator.translators.galtransl_local import GaltranslLocalTranslator
    from manga_translator.translators.sakura_local import SakuraLocalTranslator

    # Patch Galtransl
    if hasattr(GaltranslLocalTranslator, '_translate'):
        _original_translate = GaltranslLocalTranslator._translate
        GaltranslLocalTranslator._translate = _instrumented_translate
        logger.info('[DIAG] Patched GaltranslLocalTranslator._translate')

    # Patch SakuraLocal too
    if hasattr(SakuraLocalTranslator, '_translate'):
        _original_translate_sakura = SakuraLocalTranslator._translate
        SakuraLocalTranslator._translate = _instrumented_translate
        logger.info('[DIAG] Patched SakuraLocalTranslator._translate')

    # Patch parse_response for Galtransl
    _original_parse_response = GaltranslLocalTranslator._parse_response
    GaltranslLocalTranslator._parse_response = _instrumented_parse_response
    logger.info('[DIAG] Patched GaltranslLocalTranslator._parse_response')


def restore_translator():
    """Restore original translator methods."""
    global _original_translate, _original_parse_response

    from manga_translator.translators.galtransl_local import GaltranslLocalTranslator
    from manga_translator.translators.sakura_local import SakuraLocalTranslator

    if _original_translate:
        GaltranslLocalTranslator._translate = _original_translate
        SakuraLocalTranslator._translate = _original_translate
    if _original_parse_response:
        GaltranslLocalTranslator._parse_response = _original_parse_response
    logger.info('[DIAG] Restored original translator methods')


# ─── Diagnostic runner ──────────────────────────────────────────────────

async def diagnose_image(image_path: str):
    """Run diagnostic on a single image."""

    if not os.path.isfile(image_path):
        logger.error(f'Image not found: {image_path}')
        return

    logger.info('=' * 60)
    logger.info(f'Diagnostic run for: {image_path}')
    logger.info('=' * 60)

    # Setup - create translator config
    from manga_translator import MangaTranslator, Config
    from manga_translator.config import TranslatorConfig, DetectorConfig, OcrConfig, InpainterConfig, RenderConfig
    from manga_translator.mode.local import MangaTranslatorLocal

    # Determine translator mode from environment
    translator_mode = os.environ.get('TRANSLATOR_MODE', 'galtransl')

    params = {
        'translator': TranslatorConfig(
            translator='galtransl' if translator_mode == 'galtransl' else 'sakura',
            target_lang='CHS',
            translator_chain=None,
            no_text_lang_skip=None,
            skip_lang=None,
            gpt_config=None,
        ),
        'detector': DetectorConfig(),
        'ocr': OcrConfig(),
        'inpainter': InpainterConfig(),
        'render': RenderConfig(),
    }

    # Load models
    from manga_translator.batch import _load_models
    await _load_models(translator_mode)

    config = Config(**params)

    # Run translation
    translator = MangaTranslatorLocal()
    translator.prep_manual = False
    translator.save_text = False

    img = Image.open(image_path)
    logger.info(f'Image size: {img.size}, mode: {img.mode}')

    # Patch before translating
    _diag_data.clear()
    patch_translator()

    try:
        t0 = time.time()
        ctx = await translator.translate(img, config)
        total_ms = round((time.time() - t0) * 1000, 1)
    finally:
        restore_translator()

    # Report results
    logger.info('')
    logger.info('=' * 60)
    logger.info('DIAGNOSTIC REPORT')
    logger.info('=' * 60)

    # Check if text_regions exist
    has_regions = hasattr(ctx, 'text_regions') and ctx.text_regions is not None
    region_count = len(ctx.text_regions) if has_regions else 0
    logger.info(f'Text regions after filter: {region_count}'
                f' (hasattr={hasattr(ctx, "text_regions")})')

    # Check textlines
    has_textlines = hasattr(ctx, 'textlines') and ctx.textlines is not None
    textline_count = len(ctx.textlines) if has_textlines else 0
    logger.info(f'Textlines (OCR): {textline_count}')

    # Check if result was produced
    has_result = ctx.result is not None if hasattr(ctx, 'result') else False
    logger.info(f'Result image produced: {has_result}')

    # Translation diagnostics
    logger.info('')
    logger.info('--- Translation Stage ---')
    logger.info(f'Queries sent to model: {_diag_data["queries_count"]}')
    logger.info(f'Non-empty queries: {_diag_data["non_empty_queries_count"]}')
    logger.info(f'Model invoked: {"Yes" if _diag_data["has_usage"] else "No"}')
    logger.info(f'Prompt tokens: {_diag_data["prompt_tokens"]}')
    logger.info(f'Completion tokens: {_diag_data["completion_tokens"]}')
    logger.info(f'Translations returned: {_diag_data["translations_returned"]}')
    logger.info(f'Empty translations: {_diag_data["empty_translations"]}')
    logger.info(f'Parse success: {_diag_data["parse_success"]}')
    logger.info(f'Raw response length: {_diag_data["raw_response_length"]} chars')
    logger.info(f'Translation timing: {_diag_data["timing_ms"]} ms')
    logger.info(f'Total pipeline timing: {total_ms} ms')
    if _diag_data['error']:
        logger.error(f'Translation error: {_diag_data["error"]}')

    # Diagnosis
    logger.info('')
    logger.info('--- DIAGNOSIS ---')
    if _diag_data['error']:
        logger.error(f'TRANSLATION FAILED: {_diag_data["error"]}')
    elif _diag_data['prompt_tokens'] == 0 and _diag_data['completion_tokens'] == 0:
        logger.warning('CAUSE: Model was NOT invoked - '
                       'prompt_tokens=0 and completion_tokens=0. '
                       'Check if model loaded correctly or was bypassed.')
    elif _diag_data['completion_tokens'] == 0 and _diag_data['prompt_tokens'] > 0:
        logger.warning('CAUSE: Model received input but returned NO output - '
                       'completion_tokens=0. Model may have crashed during inference.')
    elif _diag_data['translations_returned'] == 0 and _diag_data['raw_response_length'] > 0:
        logger.warning('CAUSE: Model responded but regex parsing produced NO matches. '
                       'The model response format may not match the expected 「...」 pattern.')
    elif _diag_data['translations_returned'] > 0 and _diag_data['empty_translations'] == _diag_data['translations_returned']:
        logger.warning('CAUSE: All translations returned are empty strings. '
                       'Model may be refusing to translate or returning malformed content.')
    elif _diag_data['translations_returned'] > 0 and _diag_data['empty_translations'] > 0:
        logger.warning(f'CAUSE: {_diag_data["empty_translations"]}/{_diag_data["translations_returned"]} '
                       'translations are empty. Partial failure.')
    elif region_count == 0 and _diag_data['queries_count'] > 0:
        logger.warning('CAUSE: Model translated text, but ALL results were filtered out '
                       'by post-processing (likely empty translation filter).')
    elif region_count == 0 and _diag_data['queries_count'] == 0:
        logger.info('NO TEXT DETECTED: OCR found no text in the image.')
    elif region_count > 0:
        logger.info('SUCCESS: Translation produced text regions with content.')
    else:
        logger.info('No diagnosis available. Check the raw metrics above.')

    logger.info('=' * 60)
    return ctx


def main():
    if len(sys.argv) < 2:
        print('Usage: python test/e2e/debug_empty_translation.py <image_path>')
        print('')
        print('Environment variables:')
        print('  TRANSLATOR_MODE=galtransl  (default, uses Galtransl GGUF)')
        print('  TRANSLATOR_MODE=sakura     (uses Sakura GGUF)')
        print('  GALTRANS_GGUF_PATH=...     (required for galtransl mode)')
        print('  SAKURA_GGUF_PATH=...       (required for sakura mode)')
        sys.exit(1)

    image_path = sys.argv[1]

    import asyncio
    asyncio.run(diagnose_image(image_path))


if __name__ == '__main__':
    main()