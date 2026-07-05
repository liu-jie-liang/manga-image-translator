"""
批量翻译脚本 — 韩中漫画翻译专用。

功能：
- 目录遍历（逐层，先翻译当前目录再进入子目录）
- 子目录名排序（复用 batch_common.py）
- 模型生命周期管理（加载一次 → 逐目录翻译 → 卸载）
- 进度续传（每目录 .translate_progress.json）
- 交互式入口（输入目录路径 + 是否重新翻译）

翻译器：Qwen3 14B (Ollama) — 韩文→简体中文
无降级链，失败即报错。

用法: python -m manga_translator.batch_ko
"""
import asyncio
import logging
import os
import sys
import time
import aiohttp
from typing import List

from manga_translator import Config
from manga_translator.utils import get_logger
from manga_translator.utils.log import init_logging
from manga_translator.batch_common import (
    IMAGE_EXTS,
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
)
from manga_translator.translators.qwen3_kozh import Qwen3KoZhTranslator

# ─── Logger ───

init_logging()
logger = get_logger('batch_ko')


# ═══════════════════════════════════════════════════════════════════════════════
# Model lifecycle
# ═══════════════════════════════════════════════════════════════════════════════

# Hardcoded config for 韩中漫画翻译
BATCH_PARAMS = {
    'translator': {
        'translator': 'qwen3_kozh',
        'target_lang': 'CHS',
    },
    'use_gpu_limited': True,
    'source_lang': 'ko',
    'kernel_size': 3,
    'attempts': 1,
    'save_quality': 100,
}

_translator_instance: MangaTranslatorLocal | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Translator probing
# ═══════════════════════════════════════════════════════════════════════════════

async def _probe_ollama() -> bool:
    """Check if Ollama API service is reachable.

    Sends a GET to {OLLAMA_HOST}/api/tags with a 3-second timeout.
    """
    ollama_root = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
    url = f'{ollama_root}/api/tags'
    try:
        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                return resp.status == 200
    except Exception:
        return False


async def _load_models():
    """Load all models once for the entire batch translation session.

    Detection, OCR, Inpainting 模型与日中翻译相同。
    """
    from manga_translator.detection import prepare as prepare_detection
    from manga_translator.ocr import prepare as prepare_ocr
    from manga_translator.inpainting import prepare as prepare_inpainting

    device = _detect_device()
    logger.info(f'Device: {device}')

    config = Config(**BATCH_PARAMS)

    logger.info('Loading detection model...')
    await prepare_detection(config.detector.detector)

    logger.info('Loading OCR model...')
    await prepare_ocr(config.ocr.ocr, device)

    logger.info('Loading inpainting model...')
    await prepare_inpainting(config.inpainter.inpainter, device)

    logger.info('All models loaded.')


async def _unload_models():
    """Unload all models after batch translation completes."""
    from manga_translator.detection import unload as unload_detection
    from manga_translator.ocr import unload as unload_ocr
    from manga_translator.inpainting import unload as unload_inpainting
    from manga_translator.config import Detector, Inpainter, Ocr

    logger.info('Unloading models...')

    await unload_inpainting(Inpainter.lama_large)
    await unload_ocr(Ocr.ocr48px)
    await unload_detection(Detector.default)

    logger.info('All models unloaded.')


def _get_translator() -> MangaTranslatorLocal:
    """Get or create the translator instance.

    Uses Qwen3KoZhTranslator via the custom_openai translator type.
    The MangaTranslatorLocal will dispatch to Qwen3KoZhTranslator
    when configured with translator='custom_openai' and the appropriate
    environment variables (CUSTOM_OPENAI_MODEL, CUSTOM_OPENAI_API_BASE).
    """
    global _translator_instance
    if _translator_instance is None:
        # Ensure environment variables are set for Qwen3KoZh
        if not os.environ.get('CUSTOM_OPENAI_MODEL'):
            os.environ['CUSTOM_OPENAI_MODEL'] = 'qwen3:14b-q4_k_m'
        if not os.environ.get('CUSTOM_OPENAI_API_BASE'):
            os.environ['CUSTOM_OPENAI_API_BASE'] = os.environ.get('CUSTOM_OPENAI_API_BASE', 'http://localhost:11434/v1')
        _translator_instance = MangaTranslatorLocal(BATCH_PARAMS)
    return _translator_instance


# ═══════════════════════════════════════════════════════════════════════════════
# Directory traversal and translation
# ═══════════════════════════════════════════════════════════════════════════════

async def _translate_directory(dir_path: str, dest_dir: str, retrans: bool):
    """Translate a single directory's images (non-recursive)."""
    translator = _get_translator()
    params = dict(BATCH_PARAMS)
    params['retrans'] = retrans
    if retrans:
        params['overwrite'] = True
    logger.info(f'Translating directory: {dir_path}')
    await translator.translate_path(dir_path, dest_dir, params)


async def _traverse_and_translate(
    root_path: str, dest_root: str, retrans: bool
):
    """Recursively traverse and translate directories layer by layer.

    For each level:
    1. Translate current directory's images
    2. Collect subdirectories, sort by rules, recurse into each
    """
    # Translate current directory
    await _translate_directory(root_path, dest_root, retrans)

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
        await _traverse_and_translate(subdir_path, dest_subdir, retrans)


async def batch_translate(root_dir: str, retrans: bool = False):
    """Main batch translation entry point for Korean-Chinese.

    Args:
        root_dir: Path to the root directory containing images and subdirectories.
        retrans: If True, clear all progress files and re-translate everything.
    """
    root_dir = os.path.abspath(os.path.expanduser(root_dir))

    if not os.path.isdir(root_dir):
        logger.error(f'Not a directory: {root_dir}')
        return

    # Check Ollama availability
    if not await _probe_ollama():
        logger.error('=' * 60)
        logger.error('Ollama 服务不可达，翻译中止。')
        logger.error(f'请确保 Ollama 在 {ollama_root} 运行')
        logger.error('且已拉取 qwen3:14b-q4_k_m 模型')
        logger.error('=' * 60)
        return

    # Determine output directory: <parent>/<dirname> 汉化
    parent_dir = os.path.dirname(root_dir)
    dir_name = os.path.basename(root_dir)
    dest_root = os.path.join(parent_dir, f'{dir_name} 汉化')

    logger.info(f'Source: {root_dir}')
    logger.info(f'Destination: {dest_root}')
    logger.info(f'Retranslate: {retrans}')
    logger.info('Translator: Qwen3 14B (Ollama) — 韩文→简体中文')

    # Clear all progress files if retrans
    if retrans:
        _clear_all_progress(root_dir)

    # Load models once
    await _load_models()

    try:
        # Traverse and translate
        await _traverse_and_translate(root_dir, dest_root, retrans)

        logger.info('=' * 60)
        logger.info('韩中批量翻译完成!')
        logger.info(f'翻译结果保存到: {dest_root}')
        logger.info('=' * 60)
    finally:
        # Unload models
        await _unload_models()


# ═══════════════════════════════════════════════════════════════════════════════
# Interactive entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Interactive entry point."""
    print('=' * 60)
    print('  韩中漫画批量翻译工具')
    print('  翻译器: Qwen3 14B (Ollama)')
    print('  韩文 → 简体中文')
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

    # Retranslate?
    retrans_input = input('是否重新翻译整个目录？(清空所有进度记录) [y/N]: ').strip().lower()
    retrans = retrans_input in ('y', 'yes')

    print()
    print(f'源目录: {os.path.abspath(dir_path)}')
    print(f'重新翻译: {"是" if retrans else "否（续传模式）"}')
    print()

    confirm = input('确认开始翻译？[Y/n]: ').strip().lower()
    if confirm in ('n', 'no'):
        print('已取消。')
        return

    print()
    asyncio.run(batch_translate(dir_path, retrans))


if __name__ == '__main__':
    main()