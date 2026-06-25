"""
批量翻译脚本 — 日中漫画翻译专用。

功能：
- 目录遍历（逐层，先翻译当前目录再进入子目录）
- 子目录名排序（纯数字 / 数字+字母 / 字母+数字 / 纯字母 / 其他）
- 模型生命周期管理（加载一次 → 逐目录翻译 → 卸载）
- 进度续传（每目录 .translate_progress.json）
- 交互式入口（输入目录路径 + 是否重新翻译）

用法: python -m manga_translator.batch
"""
import asyncio
import logging
import os
import sys
import re
import time
import aiohttp
from typing import List

from manga_translator import Config
from manga_translator.utils import get_logger
from manga_translator.utils.log import init_logging
from manga_translator.batch_common import (
    IMAGE_EXTS,
    _sort_key_dir,
    sort_subdirs,
    _detect_device,
    _get_image_files,
    _load_progress,
    _save_progress,
    _clear_progress,
    _clear_all_progress,
)
from manga_translator.mode.local import (
    MangaTranslatorLocal,
    _should_record_progress,
)
from manga_translator.benchmark import benchmark_context

# ─── Logger ───

init_logging()
logger = get_logger('batch')


# ═══════════════════════════════════════════════════════════════════════════════
# Model lifecycle
# ═══════════════════════════════════════════════════════════════════════════════

# Hardcoded config for 日中漫画翻译
BATCH_PARAMS = {
    'translator': {
        'translator': 'sakura',
        'target_lang': 'CHS',
    },
    'use_gpu_limited': True,
    'source_lang': 'ja',
    'kernel_size': 3,
    'attempts': 1,
    'save_quality': 100,
}

_translator_instance: MangaTranslatorLocal | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Translator fallback probing
# ═══════════════════════════════════════════════════════════════════════════════

def _probe_gguf() -> bool:
    """Check if SAKURA_GGUF_PATH points to an existing GGUF model file."""
    path = os.environ.get('SAKURA_GGUF_PATH', '')
    return bool(path) and os.path.isfile(path)


def _probe_galtrans() -> bool:
    """Check if GALTRANS_GGUF_PATH points to an existing Galtransl GGUF model file."""
    path = os.environ.get('GALTRANS_GGUF_PATH', '')
    return bool(path) and os.path.isfile(path)


async def _probe_ollama() -> bool:
    """Check if Ollama API service is reachable.

    Sends a GET to {OLLAMA_HOST}/api/tags with a 3-second timeout.
    Uses SAKURA_API_BASE to derive the Ollama host (strip /v1 suffix).
    """
    api_base = os.environ.get('SAKURA_API_BASE', 'http://localhost:11434/v1')
    # Strip trailing /v1 or /v1/ to get the Ollama root URL
    ollama_root = re.sub(r'/v1/?$', '', api_base)
    url = f'{ollama_root}/api/tags'
    try:
        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                return resp.status == 200
    except Exception:
        return False


async def _detect_translator_mode() -> str | None:
    """Detect the best available translator mode.

    Returns:
        'galtransl' if TRANSLATOR_MODE=galtransl and GALTRANS_GGUF_PATH is valid.
        'gguf' if SAKURA_GGUF_PATH points to a valid file (short-circuits).
        'ollama' if GGUF not available but Ollama API is reachable.
        None if neither is available.
    """
    # Check if user explicitly chose Mode C (galtransl)
    if os.environ.get('TRANSLATOR_MODE') == 'galtransl':
        if _probe_galtrans():
            logger.info('翻译器模式: 方式C (Galtransl GGUF)')
            return 'galtransl'
        else:
            logger.error('GALTRANS_GGUF_PATH 未设置或文件不存在，方式C不可用')
            return None

    if _probe_gguf():
        logger.info('翻译器模式: 方式B (本地 GGUF)')
        return 'gguf'
    if await _probe_ollama():
        logger.info('翻译器模式: 方式A (Ollama HTTP)')
        return 'ollama'
    logger.error('无可用翻译器: 请设置 SAKURA_GGUF_PATH 或确保 Ollama 服务可达')
    return None


async def _load_models(translator_mode: str | None = None):
    """Load all models once for the entire batch translation session.

    Args:
        translator_mode: 'gguf' | 'ollama' | 'galtransl' | None. Determines whether to load
                         the local GGUF model or rely on remote Ollama.
    """
    from manga_translator.detection import prepare as prepare_detection
    from manga_translator.ocr import prepare as prepare_ocr
    from manga_translator.inpainting import prepare as prepare_inpainting
    from manga_translator.translators import prepare as prepare_translation
    from manga_translator.translators.sakura_local import SakuraLocalTranslator
    from manga_translator.translators.galtransl_local import GaltranslLocalTranslator

    device = _detect_device()
    logger.info(f'Device: {device}')

    # Build config to determine model names
    config = Config(**BATCH_PARAMS)

    logger.info('Loading detection model...')
    await prepare_detection(config.detector.detector)

    logger.info('Loading OCR model...')
    await prepare_ocr(config.ocr.ocr, device)

    logger.info('Loading inpainting model...')
    await prepare_inpainting(config.inpainter.inpainter, device)

    logger.info('Loading translation model...')
    await prepare_translation(config.translator.translator_gen)

    # Load GGUF model based on translator mode
    if translator_mode == 'gguf':
        gguf_path = os.environ.get('SAKURA_GGUF_PATH')
        if gguf_path:
            logger.info(f'Loading Sakura GGUF model: {gguf_path}')
            SakuraLocalTranslator.load_model(gguf_path)
    elif translator_mode == 'galtransl':
        gguf_path = os.environ.get('GALTRANS_GGUF_PATH')
        if gguf_path:
            logger.info(f'Loading Galtransl GGUF model: {gguf_path}')
            GaltranslLocalTranslator.load_model(gguf_path)
    elif translator_mode == 'ollama':
        logger.info('使用远程 Ollama，跳过本地 GGUF 加载')
    # else: no translation model to load (error case handled by caller)

    logger.info('All models loaded.')


async def _unload_models(translator_mode: str | None = None):
    """Unload all models after batch translation completes.

    Args:
        translator_mode: 'gguf' | 'ollama' | 'galtransl' | None.
    """
    from manga_translator.detection import unload as unload_detection
    from manga_translator.ocr import unload as unload_ocr
    from manga_translator.inpainting import unload as unload_inpainting
    from manga_translator.translators import unload as unload_translation, Translator
    from manga_translator.config import Detector, Inpainter, Ocr
    from manga_translator.translators.sakura_local import SakuraLocalTranslator
    from manga_translator.translators.galtransl_local import GaltranslLocalTranslator

    logger.info('Unloading models...')

    if translator_mode == 'gguf':
        SakuraLocalTranslator.unload_model()
    elif translator_mode == 'galtransl':
        GaltranslLocalTranslator.unload_model()
    await unload_translation(Translator.sakura)
    await unload_inpainting(Inpainter.lama_large)
    await unload_ocr(Ocr.ocr48px)
    await unload_detection(Detector.default)

    logger.info('All models unloaded.')


def _get_translator() -> MangaTranslatorLocal:
    """Get or create the translator instance."""
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = MangaTranslatorLocal(BATCH_PARAMS)
    return _translator_instance


# ═══════════════════════════════════════════════════════════════════════════════
# Directory traversal and translation
# ═══════════════════════════════════════════════════════════════════════════════

async def _translate_directory(dir_path: str, dest_dir: str, retrans: bool, benchmark: bool = False):
    """Translate a single directory's images (non-recursive)."""
    translator = _get_translator()
    params = dict(BATCH_PARAMS)
    params['retrans'] = retrans
    params['overwrite'] = True  # Always overwrite existing files

    if benchmark:
        # Benchmark mode: handle per-file lifecycle manually for instrumentation
        logger.info(f'Benchmark translating directory: {dir_path}')
        os.makedirs(dest_dir, exist_ok=True)

        image_files = _get_image_files(dir_path)
        completed = _load_progress(dir_path) if not retrans else set()
        pending_files = [f for f in image_files if f not in completed]

        if not pending_files:
            logger.info('No images found to translate in this directory.')
            return

        logger.info(f'Found {len(image_files)} images, {len(pending_files)} pending translation')

        file_ext = params.get('format')
        for f in pending_files:
            file_path = os.path.join(dir_path, f)
            p, ext = os.path.splitext(f)
            output_dest = os.path.join(dest_dir, f'{p}.{file_ext or ext[1:]}')

            # Per-page benchmark instrumentation
            benchmark_context.start_page(f)
            _t_page_start = time.time()

            try:
                success = await translator.translate_file(file_path, output_dest, params, Config(**BATCH_PARAMS))
                if success:
                    # Skip progress recording if translation was empty (text existed but all empty)
                    last_ctx = getattr(translator, '_last_translation_ctx', None)
                    if last_ctx is None or _should_record_progress(last_ctx):
                        _save_progress(dir_path, f)
                    _t_page_elapsed = time.time() - _t_page_start
                    benchmark_context._active_page.total_elapsed = _t_page_elapsed
            except Exception as e:
                logger.error(f'Error translating {f}: {e}')
                benchmark_context._active_page.error = str(e)
            finally:
                benchmark_context.finish_page()
    else:
        # Normal mode: delegate to translate_path
        logger.info(f'Translating directory: {dir_path}')
        await translator.translate_path(dir_path, dest_dir, params)


async def _traverse_and_translate(
    root_path: str, dest_root: str, retrans: bool, benchmark: bool = False
):
    """Recursively traverse and translate directories layer by layer.

    For each level:
    1. Translate current directory's images
    2. Collect subdirectories, sort by rules, recurse into each
    """
    # Translate current directory
    await _translate_directory(root_path, dest_root, retrans, benchmark)

    # Get subdirectories
    if not os.path.isdir(root_path):
        return

    try:
        entries = os.listdir(root_path)
    except PermissionError:
        logger.warning(f'Permission denied: {root_path}')
        return

    subdirs = []
    for entry in entries:
        entry_path = os.path.join(root_path, entry)
        if os.path.isdir(entry_path):
            subdirs.append(entry)

    if not subdirs:
        return

    # Sort subdirectories by batch translation rules
    sorted_subdirs = sort_subdirs(subdirs)
    logger.info(f'Subdirectories sorted: {sorted_subdirs}')

    # Recurse into each subdirectory
    for subdir in sorted_subdirs:
        subdir_path = os.path.join(root_path, subdir)
        dest_subdir = os.path.join(dest_root, subdir)
        await _traverse_and_translate(subdir_path, dest_subdir, retrans, benchmark)


async def batch_translate(root_dir: str, retrans: bool = False, benchmark: bool = False):
    """Main batch translation entry point.

    Args:
        root_dir: Path to the root directory containing images and subdirectories.
        retrans: If True, clear all progress files and re-translate everything.
        benchmark: If True, collect per-page performance metrics and generate reports.
    """
    root_dir = os.path.abspath(os.path.expanduser(root_dir))

    if not os.path.isdir(root_dir):
        logger.error(f'Not a directory: {root_dir}')
        return

    # Detect best available translator (fallback chain)
    translator_mode = await _detect_translator_mode()
    if translator_mode is None:
        logger.error('=' * 60)
        logger.error('无可用翻译器，翻译中止。')
        logger.error('请设置环境变量:')
        logger.error('  方式C: export GALTRANS_GGUF_PATH=/path/to/Sakura-Galtransl-14B-v3.8-Q4_K_M.gguf')
        logger.error('  方式B: export SAKURA_GGUF_PATH=/path/to/model.gguf')
        logger.error('  方式A: export SAKURA_API_BASE=http://192.168.1.15:11434/v1')
        logger.error('=' * 60)
        return

    # For galtransl mode, use galtransl translator instead of sakura
    if translator_mode == 'galtransl':
        BATCH_PARAMS['translator']['translator'] = 'galtransl'
    else:
        BATCH_PARAMS['translator']['translator'] = 'sakura'

    # Determine output directory: <parent>/<dirname> 汉化
    parent_dir = os.path.dirname(root_dir)
    dir_name = os.path.basename(root_dir)
    dest_root = os.path.join(parent_dir, f'{dir_name} 汉化')

    logger.info(f'Source: {root_dir}')
    logger.info(f'Destination: {dest_root}')
    logger.info(f'Retranslate: {retrans}')
    if benchmark:
        logger.info(f'Benchmark mode: enabled')
        benchmark_context.reset()

    # Clear all progress files if retrans
    if retrans:
        _clear_all_progress(root_dir)

    # Load models once
    await _load_models(translator_mode)

    _session_start = time.time() if benchmark else 0

    try:
        # Traverse and translate
        await _traverse_and_translate(root_dir, dest_root, retrans, benchmark)
        _session_elapsed = time.time() - _session_start if benchmark else 0

        logger.info('=' * 60)
        logger.info('批量翻译完成!')
        logger.info(f'翻译结果保存到: {dest_root}')
        logger.info('=' * 60)

        # Benchmark post-processing
        if benchmark:
            logger.info('=' * 60)
            logger.info(f'共翻译 {len(benchmark_context.pages)} 页，总耗时 {_session_elapsed:.1f}s')
            logger.info('=' * 60)
            _save_benchmark_data(translator_mode, _session_elapsed)
    finally:
        # Unload models
        await _unload_models(translator_mode)


def _save_benchmark_data(translator_mode: str, session_elapsed: float):
    """Save raw benchmark data to JSON for post-processing."""
    import json
    from datetime import datetime

    from manga_translator.benchmark import compute_benchmark_statistics

    mode_label = (
        'modeC' if translator_mode == 'galtransl'
        else 'modeA' if translator_mode == 'ollama'
        else 'modeB'
    )
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    output_dir = os.path.join('test', 'results', 'benchmark', mode_label)
    os.makedirs(output_dir, exist_ok=True)

    # Save raw per-page data
    raw_path = os.path.join(output_dir, f'{timestamp}.json')
    pages_data = []
    for page in benchmark_context.pages:
        pages_data.append({
            'page_index': page.page_index,
            'image_name': page.image_name,
            'detection': page.detection.to_dict(),
            'ocr': page.ocr.to_dict(),
            'translation': page.translation.to_dict(),
            'inpainting': page.inpainting.to_dict(),
            'rendering': page.rendering.to_dict(),
            'total_elapsed': page.total_elapsed,
            'ocr_text_count': page.ocr_text_count,
            'translated_text_count': page.translated_text_count,
            'prompt_tokens': page.prompt_tokens,
            'completion_tokens': page.completion_tokens,
            'translation_ttfb': page.translation_ttfb,
            'error': page.error,
            'retry_count': page.retry_count,
        })
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump({
            'mode': mode_label,
            'translator_mode': translator_mode,
            'session_elapsed': session_elapsed,
            'total_pages': len(pages_data),
            'pages': pages_data,
        }, f, ensure_ascii=False, indent=2)
    logger.info(f'Benchmark raw data saved: {raw_path}')

    # Compute and save statistics
    stats = compute_benchmark_statistics(benchmark_context.pages, session_elapsed)
    stats_path = os.path.join(output_dir, f'{timestamp}-stats.json')
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    logger.info(f'Benchmark statistics saved: {stats_path}')

    # Also save to default path for report generation
    default_path = os.path.join(output_dir, 'latest.json')
    with open(default_path, 'w', encoding='utf-8') as f:
        json.dump({
            'mode': mode_label,
            'translator_mode': translator_mode,
            'session_elapsed': session_elapsed,
            'total_pages': len(pages_data),
            'pages': pages_data,
            'statistics': stats,
        }, f, ensure_ascii=False, indent=2)
    logger.info(f'Benchmark latest data saved: {default_path}')

    # Generate Markdown report
    from manga_translator.report_generator import (
        generate_benchmark_report,
        save_report,
        save_per_page_csv,
    )
    report_md = generate_benchmark_report(
        mode_label=mode_label,
        translator_mode=translator_mode,
        session_elapsed=session_elapsed,
        stats=stats,
        pages=pages_data,
        oom_detected=benchmark_context.oom_detected,
        oom_message=benchmark_context.oom_message,
    )
    report_path = save_report(report_md, mode_label, timestamp)
    logger.info(f'Benchmark Markdown report saved: {report_path}')

    csv_path = save_per_page_csv(pages_data, mode_label, timestamp)
    logger.info(f'Benchmark per-page CSV saved: {csv_path}')


# ═══════════════════════════════════════════════════════════════════════════════
# Interactive entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Interactive entry point."""
    print('=' * 60)
    print('  日中漫画批量翻译工具')
    print('=' * 60)
    print()

    # Input directory path
    while True:
        dir_path = input('请输入要翻译的目录路径: ').strip()
        if not dir_path:
            print('路径不能为空，请重新输入。')
            continue
        dir_path = os.path.expanduser(dir_path)
        if not os.path.isdir(dir_path):
            print(f'目录不存在: {dir_path}')
            continue
        break

    # Retranslate? (override via RETRANS env var)
    retrans_env = os.environ.get('RETRANS', '').strip().lower()
    if retrans_env in ('true', '1', 'yes'):
        retrans = True
        print('> 环境变量 RETRANS=true → 全量重新翻译')
    else:
        retrans_input = input('是否重新翻译整个目录？(清空所有进度记录) [y/N]: ').strip().lower()
        retrans = retrans_input in ('y', 'yes')

    # Benchmark mode? (override via BENCHMARK env var)
    bench_env = os.environ.get('BENCHMARK', '').strip().lower()
    if bench_env in ('false', '0', 'no'):
        benchmark = False
        print('> 环境变量 BENCHMARK=false → 不启用基准测试')
    else:
        bench_input = input('是否启用性能基准测试模式？(记录每页耗时/Token等指标) [y/N]: ').strip().lower()
        benchmark = bench_input in ('y', 'yes')

    print()
    print(f'源目录: {os.path.abspath(dir_path)}')
    print(f'重新翻译: {"是" if retrans else "否（续传模式）"}')
    print(f'基准测试: {"是" if benchmark else "否"}')
    print()

    confirm = input('确认开始翻译？[Y/n]: ').strip().lower()
    if confirm in ('n', 'no'):
        print('已取消。')
        return

    print()
    asyncio.run(batch_translate(dir_path, retrans, benchmark))


if __name__ == '__main__':
    main()