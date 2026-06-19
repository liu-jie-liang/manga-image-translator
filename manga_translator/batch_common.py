"""
批量翻译公共模块 — 日中/韩中翻译共享的通用逻辑。

包含：
- IMAGE_EXTS 图片扩展名常量
- 目录排序 (_sort_key_dir, sort_subdirs)
- 设备检测 (_detect_device)
- 图片文件扫描 (_get_image_files)
- 进度管理 (_load_progress, _save_progress, _clear_progress, _clear_all_progress)

用法:
    from manga_translator.batch_common import sort_subdirs, _get_image_files, ...
"""
import json
import logging
import os
import re
from typing import List

from PIL import Image

from manga_translator.utils import get_logger, natural_sort

# ─── Supported image file extensions ───

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif', '.gif'}


# ═══════════════════════════════════════════════════════════════════════════════
# Device detection
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_device() -> str:
    """Detect the best available device."""
    import torch
    if torch.cuda.is_available():
        return 'cuda'
    elif torch.backends.mps.is_available():
        return 'mps'
    else:
        return 'cpu'


# ═══════════════════════════════════════════════════════════════════════════════
# Directory sorting
# ═══════════════════════════════════════════════════════════════════════════════

# Category order for sort keys
_CAT_PURE_DIGITS = 0
_CAT_DIGITS_LETTERS = 1
_CAT_LETTERS_DIGITS = 2
_CAT_OTHER = 3


def _sort_key_dir(name: str) -> tuple:
    """Generate a sort key tuple for a directory name."""
    # 1. Pure digits: ^\d+$
    if re.match(r'^\d+$', name):
        return (_CAT_PURE_DIGITS, int(name), '', name)

    # 2. Digits + letters (with optional _ or - separator): ^\d+[_-]?[a-zA-Z]
    m = re.match(r'^(\d+)[_-]?([a-zA-Z].*)$', name)
    if m:
        return (_CAT_DIGITS_LETTERS, int(m.group(1)), m.group(2).lower(), name)

    # 3. Letters + digits (with optional _ or - separator): ^[a-zA-Z]+[_-]?\d+
    m = re.match(r'^([a-zA-Z]+)[_-]?(\d+.*)', name)
    if m:
        return (_CAT_LETTERS_DIGITS, m.group(1).lower(), int(re.match(r'\d+', m.group(2)).group()), name)

    # 4. Pure letters → 等同于字母+数字0
    if re.match(r'^[a-zA-Z]+$', name):
        return (_CAT_LETTERS_DIGITS, name.lower(), 0, name)

    # 5. Others → natural sort, placed last
    return (_CAT_OTHER, 0, 0, name.lower())


def sort_subdirs(dir_names: List[str]) -> List[str]:
    """Sort directory names by batch translation rules."""
    return sorted(dir_names, key=_sort_key_dir)


# ═══════════════════════════════════════════════════════════════════════════════
# Image file scanning
# ═══════════════════════════════════════════════════════════════════════════════

PROGRESS_FILE = '.translate_progress.json'


def _get_image_files(path: str) -> List[str]:
    """获取目录下当前层级的图片文件列表（不递归子目录）。

    跳过：子目录、非图片文件、.thumb、.translate_progress.json。
    """
    if not os.path.isdir(path):
        return []
    entries = os.listdir(path)
    files = []
    for entry in entries:
        full_path = os.path.join(path, entry)
        # 跳过子目录
        if os.path.isdir(full_path):
            continue
        # 跳过 .thumb
        if entry.lower() == '.thumb':
            continue
        # 跳过进度文件
        if entry == PROGRESS_FILE:
            continue
        # 跳过非图片扩展名
        ext = os.path.splitext(entry)[1].lower()
        if ext not in IMAGE_EXTS:
            continue
        # 验证可以被PIL打开
        try:
            img = Image.open(full_path)
            img.verify()
        except Exception:
            continue
        files.append(entry)
    return natural_sort(files)


# ═══════════════════════════════════════════════════════════════════════════════
# Progress management
# ═══════════════════════════════════════════════════════════════════════════════

def _load_progress(path: str) -> set:
    """从目录中加载已完成翻译的图片文件名集合。"""
    progress_path = os.path.join(path, PROGRESS_FILE)
    if not os.path.exists(progress_path):
        return set()
    try:
        with open(progress_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return set(data.get('completed', []))
    except Exception:
        return set()


def _save_progress(path: str, filename: str):
    """记录一张已完成翻译的图片到进度文件。"""
    progress_path = os.path.join(path, PROGRESS_FILE)
    completed = _load_progress(path)
    completed.add(filename)
    # 按文件名排序存储
    data = {'completed': sorted(completed)}
    with open(progress_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _clear_progress(path: str):
    """删除目录下的进度文件（retrans）。
    
    如果因权限问题无法操作（如沙箱环境），则跳过。
    """
    progress_path = os.path.join(path, PROGRESS_FILE)
    if os.path.exists(progress_path):
        try:
            os.remove(progress_path)
        except PermissionError:
            logger = get_logger('batch_common')
            logger.warning(f'Cannot clear progress file (permission denied): {progress_path}')


def _clear_all_progress(root_dir: str):
    """Recursively clear all progress files under root_dir."""
    count = 0
    for dirpath, _, _ in os.walk(root_dir):
        _clear_progress(dirpath)
        count += 1
    return count