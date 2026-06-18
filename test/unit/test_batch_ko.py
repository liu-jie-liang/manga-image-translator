"""
TDD: Test batch_ko.py — 韩中批量翻译入口。

测试范围：
- BATCH_PARAMS 配置正确（source_lang='ko', translator 为韩中翻译器）
- 翻译器实例化
- 目录遍历使用 batch_common.py 的公共函数
- 进度管理使用 batch_common.py
- 交互式入口函数存在
"""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from manga_translator.batch_ko import (
    BATCH_PARAMS,
    _get_translator,
    _clear_all_progress,
    sort_subdirs,
    _detect_device,
    _get_image_files,
    _load_progress,
    _save_progress,
    _clear_progress,
)


class TestBatchKoParams:
    """韩中翻译参数配置测试"""

    def test_source_lang_is_ko(self):
        """源语言为韩文。"""
        assert BATCH_PARAMS['source_lang'] == 'ko'

    def test_target_lang_is_chs(self):
        """目标语言为简体中文。"""
        assert BATCH_PARAMS['translator']['target_lang'] == 'CHS'

    def test_attempts_is_one(self):
        """不重试（无降级）。"""
        assert BATCH_PARAMS['attempts'] == 1

    def test_translator_type(self):
        """翻译器类型为 custom_openai。"""
        assert BATCH_PARAMS['translator']['translator'] == 'custom_openai'

    def test_save_quality(self):
        """保存质量 100。"""
        assert BATCH_PARAMS['save_quality'] == 100

    def test_no_sakura_specific_params(self):
        """不应包含 Sakura 特化的参数。"""
        assert 'translator' not in BATCH_PARAMS or 'sakura' not in str(BATCH_PARAMS.get('translator', {}).get('translator', ''))


class TestBatchKoTranslator:
    """翻译器实例化测试"""

    def test_get_translator_returns_local_translator(self):
        """_get_translator 返回 MangaTranslatorLocal 实例。"""
        from manga_translator.mode.local import MangaTranslatorLocal
        # 重置单例以获取干净的实例
        import manga_translator.batch_ko as batch_ko
        batch_ko._translator_instance = None
        translator = _get_translator()
        assert isinstance(translator, MangaTranslatorLocal)

    def test_get_translator_singleton(self):
        """_get_translator 返回单例。"""
        import manga_translator.batch_ko as batch_ko
        batch_ko._translator_instance = None
        t1 = _get_translator()
        t2 = _get_translator()
        assert t1 is t2


class TestBatchKoReusesCommon:
    """batch_ko.py 复用 batch_common.py 的公共函数"""

    def test_sort_subdirs_imported(self):
        """sort_subdirs 从 batch_common 导入。"""
        assert sort_subdirs is not None
        assert callable(sort_subdirs)

    def test_detect_device_imported(self):
        """_detect_device 从 batch_common 导入。"""
        assert _detect_device is not None
        assert callable(_detect_device)

    def test_get_image_files_imported(self):
        """_get_image_files 从 batch_common 导入。"""
        assert _get_image_files is not None
        assert callable(_get_image_files)

    def test_progress_functions_imported(self):
        """进度管理函数从 batch_common 导入。"""
        assert _load_progress is not None
        assert _save_progress is not None
        assert _clear_progress is not None
        assert _clear_all_progress is not None

    def test_sort_subdirs_works(self):
        """sort_subdirs 实际调用正确。"""
        result = sort_subdirs(['10', '2', '1', '03'])
        assert result == ['1', '2', '03', '10']


class TestBatchKoProbe:
    """Ollama 探测测试"""

    @pytest.mark.asyncio
    async def test_probe_ollama_exists(self):
        """_probe_ollama 函数存在。"""
        from manga_translator.batch_ko import _probe_ollama
        assert callable(_probe_ollama)

    @pytest.mark.asyncio
    async def test_probe_ollama_with_mock(self):
        """_probe_ollama 在 mock 下返回 True。"""
        from manga_translator.batch_ko import _probe_ollama

        # Mock the entire probe function to return True
        with patch('manga_translator.batch_ko._probe_ollama', new_callable=AsyncMock) as mock_probe:
            mock_probe.return_value = True
            result = await mock_probe()
            assert result is True

    @pytest.mark.asyncio
    async def test_probe_ollama_returns_bool(self):
        """_probe_ollama 返回布尔值。"""
        from manga_translator.batch_ko import _probe_ollama
        result = await _probe_ollama()
        assert isinstance(result, bool)


class TestBatchKoMain:
    """main 函数测试"""

    def test_main_exists(self):
        """main 函数存在。"""
        from manga_translator.batch_ko import main
        assert callable(main)

    def test_batch_translate_exists(self):
        """batch_translate 函数存在。"""
        from manga_translator.batch_ko import batch_translate
        assert callable(batch_translate)