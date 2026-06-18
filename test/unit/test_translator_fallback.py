"""
TDD: 翻译器降级选择逻辑测试。

测试覆盖:
1. GGUF 文件探测 (_probe_gguf)
2. Ollama 可达性探测 (_probe_ollama)
3. 降级选择入口 (_detect_translator_mode)
4. 短路求值：GGUF 存在时跳过 Ollama 探测
5. 边界情况：环境变量缺失、文件不存在、网络不可达
"""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from manga_translator.batch import _probe_gguf, _probe_ollama, _detect_translator_mode


# ─── _probe_gguf 测试 ───

class TestProbeGguf:
    """GGUF 文件探测测试"""

    def test_gguf_path_set_and_file_exists(self, tmp_path):
        """SAKURA_GGUF_PATH 指向存在的文件 → True"""
        gguf_file = tmp_path / 'test-model.gguf'
        gguf_file.write_text('dummy')
        with patch.dict(os.environ, {'SAKURA_GGUF_PATH': str(gguf_file)}):
            assert _probe_gguf() is True

    def test_gguf_path_not_set(self):
        """SAKURA_GGUF_PATH 未设置 → False"""
        with patch.dict(os.environ, {}, clear=True):
            with patch.dict(os.environ, {}, clear=True):
                pass
        # 清除环境变量后测试
        with patch.dict(os.environ, {'SAKURA_GGUF_PATH': ''}, clear=True):
            assert _probe_gguf() is False

    def test_gguf_path_set_but_file_not_exists(self, tmp_path):
        """SAKURA_GGUF_PATH 指向不存在的文件 → False"""
        fake_path = str(tmp_path / 'nonexistent.gguf')
        with patch.dict(os.environ, {'SAKURA_GGUF_PATH': fake_path}):
            assert _probe_gguf() is False

    def test_gguf_path_is_dir_not_file(self, tmp_path):
        """SAKURA_GGUF_PATH 指向目录而非文件 → False"""
        with patch.dict(os.environ, {'SAKURA_GGUF_PATH': str(tmp_path)}):
            assert _probe_gguf() is False


# ─── _probe_ollama 测试 ───

class TestProbeOllama:
    """Ollama 可达性探测测试"""

    @pytest.mark.asyncio
    async def test_ollama_reachable(self):
        """Ollama 返回 200 → True"""
        with patch('aiohttp.ClientSession') as mock_session_cls:
            mock_session = MagicMock()
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_get = AsyncMock()
            mock_get.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_get.__aexit__ = AsyncMock(return_value=None)
            mock_session.get = MagicMock(return_value=mock_get)
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await _probe_ollama()
            assert result is True

    @pytest.mark.asyncio
    async def test_ollama_unreachable_timeout(self):
        """Ollama 超时 → False"""
        with patch('aiohttp.ClientSession') as mock_session_cls:
            mock_session = MagicMock()
            mock_session.get = AsyncMock(side_effect=Exception('Connection timeout'))
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await _probe_ollama()
            assert result is False

    @pytest.mark.asyncio
    async def test_ollama_returns_error_status(self):
        """Ollama 返回非 200 → False"""
        with patch('aiohttp.ClientSession') as mock_session_cls:
            mock_session = MagicMock()
            mock_resp = AsyncMock()
            mock_resp.status = 500
            mock_get = AsyncMock()
            mock_get.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_get.__aexit__ = AsyncMock(return_value=None)
            mock_session.get = MagicMock(return_value=mock_get)
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await _probe_ollama()
            assert result is False

    @pytest.mark.asyncio
    async def test_ollama_uses_custom_api_base(self):
        """使用自定义 SAKURA_API_BASE，验证 api/tags 端点正确推导"""
        with patch.dict(os.environ, {'SAKURA_API_BASE': 'http://192.168.1.15:11434/v1'}), \
             patch('aiohttp.ClientSession') as mock_session_cls:
            mock_session = MagicMock()
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_get = AsyncMock()
            mock_get.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_get.__aexit__ = AsyncMock(return_value=None)
            mock_session.get = MagicMock(return_value=mock_get)
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await _probe_ollama()
            assert result is True
            # 验证使用了正确的 URL（/v1 被剥离，访问 /api/tags）
            mock_session.get.assert_called_once()
            call_args = mock_session.get.call_args[0][0]
            assert '192.168.1.15:11434/api/tags' in call_args
            assert '/v1/api/tags' not in call_args


# ─── _detect_translator_mode 测试 ───

class TestDetectTranslatorMode:
    """降级选择入口测试"""

    @pytest.mark.asyncio
    async def test_gguf_available_skips_ollama(self, tmp_path):
        """GGUF 文件存在 → 直接返回 'gguf'，不探测 Ollama"""
        gguf_file = tmp_path / 'model.gguf'
        gguf_file.write_text('dummy')
        with patch.dict(os.environ, {'SAKURA_GGUF_PATH': str(gguf_file)}):
            with patch('manga_translator.batch._probe_ollama') as mock_probe_ollama:
                result = await _detect_translator_mode()
                assert result == 'gguf'
                mock_probe_ollama.assert_not_called()

    @pytest.mark.asyncio
    async def test_gguf_unavailable_ollama_available(self):
        """GGUF 不可用但 Ollama 可达 → 返回 'ollama'"""
        with patch('manga_translator.batch._probe_gguf', return_value=False), \
             patch('manga_translator.batch._probe_ollama', return_value=True):
            result = await _detect_translator_mode()
            assert result == 'ollama'

    @pytest.mark.asyncio
    async def test_neither_available(self):
        """GGUF 和 Ollama 都不可用 → 返回 None"""
        with patch('manga_translator.batch._probe_gguf', return_value=False), \
             patch('manga_translator.batch._probe_ollama', return_value=False):
            result = await _detect_translator_mode()
            assert result is None

    @pytest.mark.asyncio
    async def test_gguf_unavailable_ollama_unreachable(self):
        """GGUF 不可用，Ollama 探测失败 → 返回 None"""
        with patch('manga_translator.batch._probe_gguf', return_value=False), \
             patch('manga_translator.batch._probe_ollama', return_value=False):
            result = await _detect_translator_mode()
            assert result is None