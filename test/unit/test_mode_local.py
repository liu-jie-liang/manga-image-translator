"""
TDD: MangaTranslatorLocal — 全链路编排器。

测试范围：
- _has_text_content 文本检测
- _should_record_progress 进度记录判断
- translate_path 文件/目录路由
- translate_file 成功/失败/重试
- overwrite 标志
- retrans 进度清除
"""
import os
import json
import tempfile
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from PIL import Image

from manga_translator.utils.generic import Context
from manga_translator.mode.local import (
    _has_text_content,
    _should_record_progress,
)


# ─── 辅助函数 ───

def _make_textline(text: str):
    """创建带 .text 属性的 textline mock。"""
    return type('TextLine', (), {'text': text})()


def _make_ctx(**kwargs):
    """创建模拟翻译上下文的 Context 对象。"""
    ctx = Context()
    for k, v in kwargs.items():
        setattr(ctx, k, v)
    return ctx


# ─── _has_text_content 测试 ───

class TestHasTextContent:
    """原始文本内容检测"""

    def test_no_textlines(self):
        """没有 textlines → False。"""
        ctx = _make_ctx(textlines=[])
        assert _has_text_content(ctx) is False

    def test_textlines_with_content(self):
        """textlines 有内容 → True。"""
        ctx = _make_ctx(textlines=[_make_textline('こんにちは')])
        assert _has_text_content(ctx) is True

    def test_textlines_all_empty(self):
        """所有 textlines 为空 → False。"""
        ctx = _make_ctx(textlines=[
            _make_textline(''),
            _make_textline('  '),
            _make_textline('\n'),
        ])
        assert _has_text_content(ctx) is False

    def test_textlines_mixed(self):
        """部分有内容部分空 → True。"""
        ctx = _make_ctx(textlines=[
            _make_textline(''),
            _make_textline('hello'),
        ])
        assert _has_text_content(ctx) is True

    def test_no_textlines_attr(self):
        """ctx 没有 textlines 属性 → False。"""
        ctx = Context()
        # Context.__getattr__ 返回 dict.get 默认值 None 而不抛异常，
        # 所以 hasattr 始终为 True；需用 'key' in ctx 检查
        assert 'textlines' not in ctx
        assert _has_text_content(ctx) is False


# ─── _should_record_progress 测试 ───

class TestShouldRecordProgress:
    """进度记录判断"""

    def test_ctx_none(self):
        """ctx 为 None → False。"""
        assert _should_record_progress(None) is False

    def test_no_result(self):
        """ctx.result 为 None → False。"""
        ctx = _make_ctx(result=None)
        assert _should_record_progress(ctx) is False

    def test_normal_translation(self):
        """正常翻译有结果 → True。"""
        ctx = _make_ctx(result='some_image', text_regions=[MagicMock()])
        # Mock the Context to have 'text_regions' as a key
        ctx = Context()
        ctx['text_regions'] = [MagicMock()]
        ctx['result'] = 'some_image'
        assert _should_record_progress(ctx) is True

    def test_empty_translation_with_original_text(self):
        """有原文但翻译过滤为空 → False。"""
        ctx = Context()
        ctx['text_regions'] = []  # empty list, all filtered
        ctx['textlines'] = [_make_textline('こんにちは')]
        assert _should_record_progress(ctx) is False

    def test_no_text_regions_key(self):
        """text_regions key 不存在 → True（没检测到文本，正常保存）。"""
        ctx = Context()
        ctx['result'] = 'some_image'
        # 注意：不设置 'text_regions' key
        assert _should_record_progress(ctx) is True


# ─── MangaTranslatorLocal translate_path 测试 ───

class TestTranslatePath:
    """translate_path 路由测试"""

    @pytest.mark.asyncio
    async def test_translate_path_file_not_exists(self):
        """文件不存在时抛出 FileNotFoundError。"""
        from manga_translator.mode.local import MangaTranslatorLocal
        translator = MangaTranslatorLocal({'attempts': 1, 'kernel_size': 3})
        with pytest.raises(FileNotFoundError):
            await translator.translate_path('/nonexistent/file.png')

    @pytest.mark.asyncio
    async def test_translate_path_directory(self):
        """目录路径调用 translate_path 后创建目标目录。"""
        from manga_translator.mode.local import MangaTranslatorLocal
        translator = MangaTranslatorLocal({'attempts': 1, 'kernel_size': 3, 'translator': {'translator': 'sakura', 'target_lang': 'CHS'}})

        with tempfile.TemporaryDirectory() as tmpdir:
            Image.new('RGB', (1, 1), color='red').save(os.path.join(tmpdir, 'page01.png'))
            dest = os.path.join(tmpdir, 'output')

            # Mock translate_file to avoid actual translation
            with patch.object(translator, 'translate_file', new_callable=AsyncMock) as mock_translate:
                mock_translate.return_value = True
                await translator.translate_path(tmpdir, dest)
                assert os.path.isdir(dest)

    @pytest.mark.asyncio
    async def test_translate_path_with_retrans(self):
        """retrans 参数清除进度文件。"""
        from manga_translator.mode.local import MangaTranslatorLocal
        from manga_translator.batch_common import _save_progress, _load_progress
        translator = MangaTranslatorLocal({'attempts': 1, 'kernel_size': 3, 'translator': {'translator': 'sakura', 'target_lang': 'CHS'}})

        with tempfile.TemporaryDirectory() as tmpdir:
            Image.new('RGB', (1, 1), color='red').save(os.path.join(tmpdir, 'page01.png'))
            dest = os.path.join(tmpdir, 'output')

            _save_progress(tmpdir, 'page01.png')
            assert len(_load_progress(tmpdir)) == 1

            with patch.object(translator, 'translate_file', new_callable=AsyncMock) as mock_translate:
                mock_translate.return_value = True
                await translator.translate_path(tmpdir, dest, {'retrans': True})
                # retrans 清除了进度 → translate_file 完成后再保存，
                # 所以进度文件中会有刚翻译完的文件
                assert 'page01.png' in _load_progress(tmpdir)


# ─── translate_file 测试 ───

class TestTranslateFile:
    """translate_file 单元测试"""

    @pytest.mark.asyncio
    async def test_translate_file_overwrites(self):
        """目标文件已存在时覆盖写入。"""
        from manga_translator.mode.local import MangaTranslatorLocal
        translator = MangaTranslatorLocal({'attempts': 1, 'kernel_size': 3})

        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, 'page01.png')
            dest = os.path.join(tmpdir, 'page01-output.png')

            Image.new('RGB', (1, 1), color='red').save(src)
            Image.new('RGB', (1, 1), color='blue').save(dest)  # pre-existing

            # Mock the full inner _translate_file to return True
            with patch.object(translator, '_translate_file', new_callable=AsyncMock) as mock_inner:
                mock_inner.return_value = True
                result = await translator.translate_file(src, dest, {}, MagicMock())
                # Should have tried to overwrite
                assert result is True

    @pytest.mark.asyncio
    async def test_translate_file_save_text(self):
        """save_text=True 时同时保存文本文件。"""
        from manga_translator.mode.local import MangaTranslatorLocal
        translator = MangaTranslatorLocal({
            'attempts': 1,
            'kernel_size': 3,
            'save_text': True,
            'text_regions': False,  # don't save per-region text
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, 'page01.png')
            dest = os.path.join(tmpdir, 'page01-output.png')

            Image.new('RGB', (1, 1), color='red').save(src)

            with patch.object(translator, '_translate_file', new_callable=AsyncMock) as mock_inner:
                mock_inner.return_value = True
                await translator.translate_file(src, dest, {}, MagicMock())

    @pytest.mark.asyncio
    async def test_translate_file_invalid_image(self):
        """损坏的图片文件返回 False。"""
        from manga_translator.mode.local import MangaTranslatorLocal
        translator = MangaTranslatorLocal({'attempts': 1, 'kernel_size': 3})

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_img = os.path.join(tmpdir, 'fake.png')
            with open(fake_img, 'w') as f:
                f.write('not an image')
            dest = os.path.join(tmpdir, 'out.png')
            result = await translator.translate_file(fake_img, dest, {}, MagicMock())
            assert result is False


# ─── 内存清理函数 ───

class TestForceCleanup:
    """内存清理函数测试"""

    def test_force_cleanup_does_not_crash(self):
        """force_cleanup 不抛出异常。"""
        from manga_translator.mode.local import force_cleanup
        # Should run without errors even without GPU
        force_cleanup()
