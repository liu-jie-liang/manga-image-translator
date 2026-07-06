"""
TDD: batch.py — 日中批量翻译入口。

测试范围：
- batch_translate 不存在目录/空目录处理
- 输出路径 <dirname> 汉化 结构
- RETRANS 环境变量控制
- _detect_translator_mode 降级链（GGUF→Ollama→None）
- _translate_directory 流程
- benchmark 标志传递
"""
import os
import tempfile
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# ─── 输出路径构造 ───

class TestOutputPath:
    """输出路径 '<dirname> 汉化' 构造测试"""

    @pytest.mark.asyncio
    async def test_dest_dir_format(self):
        """目标目录是 <parent>/<dirname> 汉化。"""
        import manga_translator.batch as batch_mod
        with patch.object(batch_mod, '_detect_translator_mode', new_callable=AsyncMock) as mock_detect, \
             patch.object(batch_mod, '_load_models', new_callable=AsyncMock) as mock_load, \
             patch.object(batch_mod, '_unload_models', new_callable=AsyncMock) as mock_unload, \
             patch.object(batch_mod, '_traverse_and_translate', new_callable=AsyncMock) as mock_traverse:
            mock_detect.return_value = 'ollama'
            with tempfile.TemporaryDirectory() as tmpdir:
                test_dir = os.path.join(tmpdir, 'test_manga')
                os.makedirs(test_dir)
                # Create a test image
                from PIL import Image
                Image.new('RGB', (1, 1), color='red').save(os.path.join(test_dir, 'page01.png'))

                mock_traverse.return_value = None
                await batch_mod.batch_translate(test_dir, retrans=False)
                expected_dest = os.path.join(tmpdir, 'test_manga 汉化')
                mock_traverse.assert_called_once()
                call_args = mock_traverse.call_args[0]
                assert call_args[0] == test_dir
                assert call_args[1] == expected_dest


# ─── batch_translate 边界测试 ───

class TestBatchTranslateEdgeCases:
    """batch_translate 边界情况测试"""

    @pytest.mark.asyncio
    async def test_not_a_directory(self):
        """路径不存在时安全返回。"""
        import manga_translator.batch as batch_mod
        result = await batch_mod.batch_translate('/nonexistent/path/12345')
        assert result is None

    @pytest.mark.asyncio
    async def test_no_translator_available(self):
        """无可用翻译器时安全返回。"""
        import manga_translator.batch as batch_mod
        with patch.object(batch_mod, '_detect_translator_mode', new_callable=AsyncMock) as mock_detect:
            mock_detect.return_value = None
            with tempfile.TemporaryDirectory() as tmpdir:
                result = await batch_mod.batch_translate(tmpdir, retrans=False)
                assert result is None


# ─── RETRANS 控制 ───

class TestRetransFlag:
    """RETRANS 标志测试"""

    @pytest.mark.asyncio
    async def test_retrans_clears_progress(self):
        """retrans=True 时清除所有进度文件。"""
        import manga_translator.batch as batch_mod
        with patch.object(batch_mod, '_detect_translator_mode', new_callable=AsyncMock) as mock_detect, \
             patch.object(batch_mod, '_load_models', new_callable=AsyncMock) as mock_load, \
             patch.object(batch_mod, '_unload_models', new_callable=AsyncMock) as mock_unload, \
             patch.object(batch_mod, '_traverse_and_translate', new_callable=AsyncMock) as mock_traverse:
            mock_detect.return_value = 'ollama'
            mock_traverse.return_value = None

            with tempfile.TemporaryDirectory() as tmpdir:
                from manga_translator.batch_common import _save_progress, _load_progress
                _save_progress(tmpdir, 'page01.png')
                assert len(_load_progress(tmpdir)) == 1

                await batch_mod.batch_translate(tmpdir, retrans=True)
                assert len(_load_progress(tmpdir)) == 0


# ─── _detect_translator_mode 降级链 ───

class TestDetectTranslatorMode:
    """翻译器模式检测（降级链）"""

    @pytest.mark.asyncio
    async def test_galtransl_mode(self):
        """TRANSLATOR_MODE=galtransl + 文件存在 → 'galtransl'。"""
        import manga_translator.batch as batch_mod
        with patch.object(batch_mod, '_probe_galtrans', return_value=True):
            with patch.dict(os.environ, {'TRANSLATOR_MODE': 'galtransl'}):
                result = await batch_mod._detect_translator_mode()
                assert result == 'galtransl'

    @pytest.mark.asyncio
    async def test_galtransl_mode_no_file(self):
        """TRANSLATOR_MODE=galtransl 但文件不存在 → None。"""
        import manga_translator.batch as batch_mod
        with patch.object(batch_mod, '_probe_galtrans', return_value=False):
            with patch.dict(os.environ, {'TRANSLATOR_MODE': 'galtransl'}):
                result = await batch_mod._detect_translator_mode()
                assert result is None

    @pytest.mark.asyncio
    async def test_gguf_available_no_galtransl_env(self):
        """GGUF 文件存在，未设 TRANSLATOR_MODE=galtransl → 'gguf'。"""
        import manga_translator.batch as batch_mod
        with patch.object(batch_mod, '_probe_gguf', return_value=True), \
             patch.object(batch_mod, '_probe_ollama', new_callable=AsyncMock):
            with patch.dict(os.environ, {}, clear=True):
                result = await batch_mod._detect_translator_mode()
                assert result == 'gguf'

    @pytest.mark.asyncio
    async def test_fallback_to_ollama(self):
        """GGUF 不可用 → 回退到 Ollama。"""
        import manga_translator.batch as batch_mod
        with patch.object(batch_mod, '_probe_gguf', return_value=False), \
             patch.object(batch_mod, '_probe_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = True
            with patch.dict(os.environ, {}, clear=True):
                result = await batch_mod._detect_translator_mode()
                assert result == 'ollama'


# ─── 设备检测 ───

class TestDetectDevice:
    """设备检测测试"""

    def test_returns_string(self):
        """返回合法的设备字符串。"""
        from manga_translator.batch_common import _detect_device
        device = _detect_device()
        assert device in ('cuda', 'mps', 'cpu')

    def test_mps_on_mac(self):
        import torch
        from manga_translator.batch_common import _detect_device
        device = _detect_device()
        if torch.backends.mps.is_available():
            assert device == 'mps'
