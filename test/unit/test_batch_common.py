"""
TDD: Test batch_common.py — 日中/韩中批量翻译共享模块。

测试范围：
- IMAGE_EXTS 常量
- _sort_key_dir / sort_subdirs 目录排序
- _detect_device 设备检测
- _get_image_files 图片文件扫描
- _load_progress / _save_progress / _clear_progress 进度管理
- _clear_all_progress 递归清理
"""
import os
import json
import tempfile
import pytest
from PIL import Image

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


# ─── IMAGE_EXTS 常量 ───

class TestImageExts:
    def test_webp_supported(self):
        """WEBP 格式在常量中。"""
        assert '.webp' in IMAGE_EXTS

    def test_all_common_formats(self):
        """常见图片格式都在常量中。"""
        assert '.png' in IMAGE_EXTS
        assert '.jpg' in IMAGE_EXTS
        assert '.jpeg' in IMAGE_EXTS
        assert '.bmp' in IMAGE_EXTS


# ─── 目录排序 ───

class TestSortKeyDir:
    def test_pure_digits(self):
        """纯数字 → (0, int_value, '', name)"""
        assert _sort_key_dir('10') == (0, 10, '', '10')
        assert _sort_key_dir('001') == (0, 1, '', '001')

    def test_digits_then_letters(self):
        """数字+字母 → (1, int, letters, name)"""
        key = _sort_key_dir('01a')
        assert key[0] == 1
        assert key[1] == 1
        assert key[2] == 'a'

    def test_letters_then_digits(self):
        """字母+数字 → (2, letters, int, name)"""
        key = _sort_key_dir('ch10')
        assert key[0] == 2
        assert key[1] == 'ch'
        assert key[2] == 10

    def test_pure_letters(self):
        """纯字母 → (2, letters, 0, name)"""
        key = _sort_key_dir('bonus')
        assert key[0] == 2
        assert key[1] == 'bonus'
        assert key[2] == 0

    def test_other(self):
        """其他 → (3, 0, 0, name.lower())"""
        key = _sort_key_dir('!meta')
        assert key[0] == 3
        assert key[1] == 0
        assert key[2] == 0
        assert key[3] == '!meta'


class TestSortSubdirs:
    def test_pure_numbers(self):
        assert sort_subdirs(['10', '2', '1', '03', '100']) == ['1', '2', '03', '10', '100']

    def test_digits_then_letters(self):
        assert sort_subdirs(['02b', '01a', '02a', '01b']) == ['01a', '01b', '02a', '02b']

    def test_letters_then_digits(self):
        assert sort_subdirs(['ch5', 'ch1', 'ch10', 'ch2']) == ['ch1', 'ch2', 'ch5', 'ch10']

    def test_letters_only(self):
        assert sort_subdirs(['bonus', 'alpha', 'zebra', 'a']) == ['a', 'alpha', 'bonus', 'zebra']

    def test_other_patterns(self):
        result = sort_subdirs(['_extra', '!meta', '.hidden'])
        assert result == ['!meta', '.hidden', '_extra']

    def test_mixed_all(self):
        dirs = ['bonus', '!meta', '001', '02a', 'ch10', '10', 'extra', '01_a', '_hidden', 'ch-2']
        result = sort_subdirs(dirs)
        expected = [
            '001', '10',
            '01_a', '02a',
            'bonus', 'ch-2', 'ch10', 'extra',
            '!meta', '_hidden',
        ]
        assert result == expected

    def test_empty(self):
        assert sort_subdirs([]) == []


# ─── 设备检测 ───

class TestDetectDevice:
    def test_returns_string(self):
        device = _detect_device()
        assert device in ('cuda', 'mps', 'cpu')

    def test_mps_on_mac(self):
        import torch
        device = _detect_device()
        if torch.backends.mps.is_available():
            assert device == 'mps'


# ─── 图片文件扫描 ───

class TestGetImageFiles:
    def test_flat_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Image.new('RGB', (1, 1), color='red').save(os.path.join(tmpdir, 'page01.png'))
            Image.new('RGB', (1, 1), color='red').save(os.path.join(tmpdir, 'page02.webp'))
            files = _get_image_files(tmpdir)
            assert files == ['page01.png', 'page02.webp']

    def test_skips_subdirectories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Image.new('RGB', (1, 1), color='red').save(os.path.join(tmpdir, 'page01.png'))
            os.makedirs(os.path.join(tmpdir, 'sub'))
            Image.new('RGB', (1, 1), color='red').save(os.path.join(tmpdir, 'sub', 'page02.png'))
            files = _get_image_files(tmpdir)
            assert files == ['page01.png']

    def test_skips_non_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Image.new('RGB', (1, 1), color='red').save(os.path.join(tmpdir, 'page01.png'))
            with open(os.path.join(tmpdir, 'readme.txt'), 'w') as f:
                f.write('hello')
            files = _get_image_files(tmpdir)
            assert files == ['page01.png']

    def test_skips_progress_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Image.new('RGB', (1, 1), color='red').save(os.path.join(tmpdir, 'page01.png'))
            with open(os.path.join(tmpdir, '.translate_progress.json'), 'w') as f:
                json.dump({'completed': ['page01.png']}, f)
            files = _get_image_files(tmpdir)
            assert files == ['page01.png']

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert _get_image_files(tmpdir) == []


# ─── 进度管理 ───

class TestProgress:
    def test_load_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert _load_progress(tmpdir) == set()

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _save_progress(tmpdir, 'page01.png')
            _save_progress(tmpdir, 'page02.png')
            assert _load_progress(tmpdir) == {'page01.png', 'page02.png'}

    def test_save_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _save_progress(tmpdir, 'page01.png')
            _save_progress(tmpdir, 'page01.png')
            assert _load_progress(tmpdir) == {'page01.png'}

    def test_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _save_progress(tmpdir, 'page01.png')
            _clear_progress(tmpdir)
            assert _load_progress(tmpdir) == set()

    def test_clear_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _clear_progress(tmpdir)  # Should not raise

    def test_corrupted_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, '.translate_progress.json'), 'w') as f:
                f.write('not valid json{{{')
            assert _load_progress(tmpdir) == set()


# ─── 递归清理 ───

class TestClearAllProgress:
    def test_clears_recursively(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            sub1 = os.path.join(tmpdir, 'sub1')
            sub2 = os.path.join(tmpdir, 'sub1', 'sub2')
            os.makedirs(sub2)

            # Create progress files
            _save_progress(tmpdir, 'page01.png')
            _save_progress(sub1, 'page02.png')
            _save_progress(sub2, 'page03.png')

            # Verify they exist
            assert os.path.exists(os.path.join(tmpdir, '.translate_progress.json'))
            assert os.path.exists(os.path.join(sub1, '.translate_progress.json'))
            assert os.path.exists(os.path.join(sub2, '.translate_progress.json'))

            _clear_all_progress(tmpdir)

            # Verify they're gone
            assert not os.path.exists(os.path.join(tmpdir, '.translate_progress.json'))
            assert not os.path.exists(os.path.join(sub1, '.translate_progress.json'))
            assert not os.path.exists(os.path.join(sub2, '.translate_progress.json'))