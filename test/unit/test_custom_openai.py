"""
TDD: CustomOpenAiTranslator — OpenAI 兼容翻译基类。

方式A (Sakura Ollama) 和韩中 (Qwen3KoZh) 都继承此类。

测试范围：
- extract_capture_groups 正则提取
- _assemble_prompts 提示词拼接
- _request_translation 请求翻译（mock openai）
- 超时重试逻辑
- 响应解析
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock

# 确保 openai 模块可用（可能未安装）
_mock_openai_module = MagicMock()
_mock_openai_module.AsyncOpenAI = MagicMock()
_mock_openai_module.RateLimitError = type('RateLimitError', (Exception,), {})
_mock_openai_module.APIError = type('APIError', (Exception,), {})


# ─── extract_capture_groups 测试 ───

class TestExtractCaptureGroups:
    """正则提取测试"""

    def test_extract_default_regex(self):
        """默认正则 (.*) 匹配全部文本。"""
        from manga_translator.translators.custom_openai import CustomOpenAiTranslator
        t = CustomOpenAiTranslator()
        result = t.extract_capture_groups("hello world")
        assert result == "hello world"

    def test_extract_multiline(self):
        """多行文本通过 DOTALL 匹配。"""
        from manga_translator.translators.custom_openai import CustomOpenAiTranslator
        t = CustomOpenAiTranslator()
        result = t.extract_capture_groups("line1\nline2\nline3")
        assert "line1" in result

    def test_extract_numbered_tags(self):
        """带编号标签的文本提取。"""
        from manga_translator.translators.custom_openai import CustomOpenAiTranslator
        t = CustomOpenAiTranslator()
        text = "<|1|>苹果<|2|>香蕉<|3|>橘子"
        result = t.extract_capture_groups(text, r"<\|(\d+)\|>(.+)")
        assert "苹果" in result


# ─── _assemble_prompts 测试 ───

class TestAssemblePrompts:
    """提示词拼接测试"""

    def test_single_query(self):
        """单条查询返回一个 prompt 段。"""
        from manga_translator.translators.custom_openai import CustomOpenAiTranslator
        t = CustomOpenAiTranslator()
        prompts = list(t._assemble_prompts("EN", "CHS", ["hello"]))
        assert len(prompts) == 1
        prompt, size = prompts[0]
        assert size == 1
        assert "hello" in prompt

    def test_multiple_queries(self):
        """多条查询在一个 prompt 中返回。"""
        from manga_translator.translators.custom_openai import CustomOpenAiTranslator
        t = CustomOpenAiTranslator()
        prompts = list(t._assemble_prompts("EN", "CHS", ["hello", "world", "test"]))
        assert len(prompts) == 1
        prompt, size = prompts[0]
        assert size == 3
        assert "hello" in prompt
        assert "world" in prompt

    def test_empty_queries(self):
        """空查询列表返回空 prompt。"""
        from manga_translator.translators.custom_openai import CustomOpenAiTranslator
        t = CustomOpenAiTranslator()
        prompts = list(t._assemble_prompts("EN", "CHS", []))
        assert len(prompts) == 1
        _, size = prompts[0]
        assert size == 0


# ─── _request_translation 测试（mock openai） ───

class TestRequestTranslation:
    """请求翻译测试（mock openai.AsyncOpenAI）"""

    @pytest.mark.asyncio
    async def test_request_returns_content(self):
        """正常请求返回翻译内容。"""
        from manga_translator.translators.custom_openai import CustomOpenAiTranslator

        t = CustomOpenAiTranslator()
        mock_choice = MagicMock()
        mock_choice.message.content = "你好"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 10
        t.token_count = 0

        with patch.object(t.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            result = await t._request_translation("CHS", "hello")
            assert result == "你好"

    @pytest.mark.asyncio
    async def test_request_updates_token_count(self):
        """请求后更新 token 计数。"""
        from manga_translator.translators.custom_openai import CustomOpenAiTranslator

        t = CustomOpenAiTranslator()
        mock_choice = MagicMock()
        mock_choice.message.content = "你好"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 25
        t.token_count = 0

        with patch.object(t.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            await t._request_translation("CHS", "你好世界")
            assert t.token_count == 25
            assert t.token_count_last == 25


# ─── 超时和重试测试 ───

class TestRetryLogic:
    """超时重试逻辑测试"""

    @pytest.mark.asyncio
    async def test_ratelimit_retries(self):
        """速率限制后自动重试。"""
        from manga_translator.translators.custom_openai import CustomOpenAiTranslator
        try:
            import openai
            t = CustomOpenAiTranslator()
            mock_choice = MagicMock()
            mock_choice.message.content = "你好"
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]

            # 构造 RateLimitError（需 response.request 属性）
            mock_err_response = MagicMock()
            mock_err_response.request = MagicMock()

            # 第一次限流，第二次成功
            with patch.object(t.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
                mock_create.side_effect = [
                    openai.RateLimitError("rate limited", response=mock_err_response, body=None),
                    mock_response,
                ]
                # 缩短速率限制重试等待
                t._RATELIMIT_RETRY_ATTEMPTS = 3
                result = await t._translate("EN", "CHS", ["hello"])
                assert len(result) == 1
                assert mock_create.call_count == 2
        except ImportError:
            pytest.skip("openai not installed")


# ─── 翻译流程端到端测试 ───

class TestTranslateFlow:
    """翻译流程端到端测试"""

    @pytest.mark.asyncio
    async def test_translate_returns_same_count(self):
        """翻译返回的条目数与输入相同。"""
        from manga_translator.translators.custom_openai import CustomOpenAiTranslator

        t = CustomOpenAiTranslator()
        mock_choice = MagicMock()
        mock_choice.message.content = "<|1|>苹果\n<|2|>香蕉\n<|3|>橘子"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 20

        with patch.object(t.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            result = await t._translate("EN", "CHS", ["apple", "banana", "orange"])
            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_empty_queries(self):
        """空查询返回空结果（re.sub 已对 None 做防护）。"""
        from manga_translator.translators.custom_openai import CustomOpenAiTranslator

        t = CustomOpenAiTranslator()
        with patch.object(t.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_choice = MagicMock()
            mock_choice.message.content = ""  # 空响应，extract_capture_groups 返回 None
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 0
            mock_create.return_value = mock_response
            result = await t._translate("EN", "CHS", [])
            assert result == []
