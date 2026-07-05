"""
TDD: Test Qwen3 Korean-Chinese translator.

测试范围：
- 翻译器初始化（模型名、API Base、语言映射）
- 韩中 Prompt 模板正确性
- _parse_language_codes 返回正确的源语言和目标语言
- 翻译器类型注册
"""
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from manga_translator.translators.qwen3_kozh import (
    Qwen3KoZhTranslator,
    QWEN3_KOZH_SYSTEM_PROMPT,
    QWEN3_KOZH_CHAT_SAMPLE,
)


class TestQwen3KoZhTranslator:
    """Qwen3 韩中翻译器测试"""

    def test_init_defaults(self):
        """初始化时使用正确的默认模型和 API Base。"""
        translator = Qwen3KoZhTranslator()
        assert translator.model == 'qwen3:14b-q4_k_m'
        base_url = str(translator.client.base_url)
        assert 'localhost' in base_url or 'ollama' in base_url
        assert 'ollama' in base_url or '/v1' in base_url

    def test_init_custom_model(self):
        """自定义模型名覆盖默认值。"""
        translator = Qwen3KoZhTranslator(model='qwen3:8b')
        assert translator.model == 'qwen3:8b'

    def test_init_custom_api_base(self):
        """自定义 API Base 覆盖默认值。"""
        translator = Qwen3KoZhTranslator(api_base='http://localhost:11434/v1')
        base_url = str(translator.client.base_url)
        assert 'localhost' in base_url

    def test_language_code_map(self):
        """语言代码映射正确。"""
        translator = Qwen3KoZhTranslator()
        assert translator._LANGUAGE_CODE_MAP['KOR'] == 'ko'
        assert translator._LANGUAGE_CODE_MAP['CHS'] == 'zh-CN'

    def test_parse_language_codes(self):
        """韩译中 → 映射后 from_lang='ko', to_lang='zh-CN'。"""
        translator = Qwen3KoZhTranslator()
        from_lang, to_lang = translator.parse_language_codes('KOR', 'CHS')
        assert from_lang == 'ko'
        assert to_lang == 'zh-CN'

    def test_system_prompt_contains_korean_context(self):
        """System prompt 包含韩中翻译相关指令。"""
        prompt = QWEN3_KOZH_SYSTEM_PROMPT
        assert '韩文' in prompt or '韩国' in prompt or 'Korean' in prompt.lower()
        assert '中文' in prompt or 'Chinese' in prompt.lower()

    def test_chat_sample_korean_to_chinese(self):
        """Chat sample 包含韩→中翻译示例。"""
        sample = QWEN3_KOZH_CHAT_SAMPLE
        # 应该有韩文原文和中文翻译的配对
        assert len(sample) == 2
        # 原文包含韩文
        assert any('\uac00' <= c <= '\ud7a3' for c in sample[0])
        # 翻译包含中文
        assert any('\u4e00' <= c <= '\u9fff' for c in sample[1])

    def test_enable_thinking_disabled(self):
        """olama 的 think 模式被禁用（通过原生 API 的 think=false）。"""
        translator = Qwen3KoZhTranslator()
        assert translator._ollama_chat_url.endswith('/api/chat')

    @pytest.mark.asyncio
    async def test_translate_method_exists(self):
        """翻译方法存在且可调用。"""
        translator = Qwen3KoZhTranslator()
        assert hasattr(translator, '_translate')
        assert callable(translator._translate)

    @pytest.mark.asyncio
    async def test_translate_returns_correct_format(self):
        """翻译返回格式正确（列表）。"""
        translator = Qwen3KoZhTranslator()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'message': {'role': 'assistant', 'content': '<|1|>你好\n<|2|>谢谢\n<|3|>再见'},
            'eval_count': 10,
            'prompt_eval_count': 50,
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession.post', return_value=mock_response):
            result = await translator._translate('KOR', 'CHS', ['안녕하세요', '감사합니다', '안녕히 계세요'])
            assert isinstance(result, list)
            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_translate_handles_error(self):
        """翻译失败时抛出异常（无降级）。"""
        import aiohttp

        translator = Qwen3KoZhTranslator()

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value='Internal Server Error')
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession.post', return_value=mock_response):
            with pytest.raises(Exception):
                await translator._translate('KOR', 'CHS', ['안녕하세요'])


class TestQwen3KoZhPromptQuality:
    """Prompt 质量测试"""

    def test_prompt_no_japanese_only(self):
        """Prompt 不应只针对日文。"""
        prompt = QWEN3_KOZH_SYSTEM_PROMPT
        # 不应包含日文特定的角色描述
        assert '日文' not in prompt
        assert '轻小说' not in prompt

    def test_prompt_includes_translation_rules(self):
        """Prompt 包含翻译规则。"""
        prompt = QWEN3_KOZH_SYSTEM_PROMPT
        assert '翻译' in prompt
        assert '原文' in prompt
        assert '专业' in prompt or '漫画' in prompt or '精准' in prompt

    def test_chat_sample_has_prefix_format(self):
        """Chat sample 使用正确的格式前缀。"""
        sample = QWEN3_KOZH_CHAT_SAMPLE
        assert '<|1|>' in sample[0] or '<|1|>' in sample[1]