"""
TDD: SakuraTranslator — 方式A Ollama HTTP 翻译器。

测试范围：
- 文本预处理（emoji 移除、假名扩展、「」标记）
- 翻译请求（mock openai.AsyncOpenAI）
- 重复检测/质量检查
- 行数对齐检查
- 单行回退翻译
- 代码风格切换
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# ─── 文本预处理 ───

class TestPreprocessQueries:
    """查询文本预处理测试"""

    def test_enlarge_small_kana(self):
        """小写假名转大写。"""
        from manga_translator.translators.sakura import SakuraTranslator
        result = SakuraTranslator.enlarge_small_kana('さくらきょうこ')
        assert 'よ' in result

    def test_enlarge_small_kana_katakana(self):
        """小写片假名转大写。"""
        from manga_translator.translators.sakura import SakuraTranslator
        result = SakuraTranslator.enlarge_small_kana('キュゥべえ')
        assert 'ユ' in result

    def test_enlarge_no_change_for_normal(self):
        """普通假名不变。"""
        from manga_translator.translators.sakura import SakuraTranslator
        result = SakuraTranslator.enlarge_small_kana('あいうえお')
        assert result == 'あいうえお'

    def test_preprocess_adds_brackets(self):
        """预处理添加「」标记。"""
        from manga_translator.translators.sakura import SakuraTranslator
        s = SakuraTranslator()
        result = s._preprocess_queries(['こんにちは'])
        assert '「こんにちは」' == result[0]


# ─── 行数对齐检查 ───

class TestCheckAlign:
    """行数对齐测试"""

    def test_aligned_returns_true(self):
        """行数匹配返回 True。"""
        from manga_translator.translators.sakura import SakuraTranslator
        s = SakuraTranslator()
        assert s._check_align(['a', 'b'], 'x\ny') is True

    def test_misaligned_returns_false(self):
        """行数不匹配返回 False。"""
        from manga_translator.translators.sakura import SakuraTranslator
        s = SakuraTranslator()
        assert s._check_align(['a', 'b', 'c'], 'x\ny') is False


# ─── 重复检测 ───

class TestDetectRepeats:
    """重复文本检测测试"""

    def test_no_repeats(self):
        """正常文本不触发重复检测。"""
        from manga_translator.translators.sakura import SakuraTranslator
        s = SakuraTranslator()
        assert s._detect_repeats('正常なテキスト', threshold=3) is False

    def test_detect_short_repeats(self):
        """短重复模式被检测到。"""
        from manga_translator.translators.sakura import SakuraTranslator
        s = SakuraTranslator()
        # "哈哈" repeated many times (> threshold)
        text = '哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈'
        # With threshold=3, the repeat count should exceed
        is_repeated, _, count, pattern, _ = s.detect_and_caculate_repeats(text, threshold=3, remove_all=False)
        assert is_repeated is True


# ─── 翻译请求测试（mock openai） ───

class TestSakuraRequestTranslation:
    """Sakura API 翻译请求测试"""

    @pytest.mark.asyncio
    async def test_request_returns_content(self):
        """正常请求返回翻译内容。"""
        from manga_translator.translators.sakura import SakuraTranslator

        s = SakuraTranslator()
        mock_choice = MagicMock()
        mock_choice.message.content = '你好世界'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        with patch.object(s.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            result = await s._request_translation(['こんにちは世界'])
            assert result == '你好世界'

    @pytest.mark.asyncio
    async def test_request_captures_usage(self):
        """请求后捕获 token usage。"""
        from manga_translator.translators.sakura import SakuraTranslator

        s = SakuraTranslator()
        mock_choice = MagicMock()
        mock_choice.message.content = '你好'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        with patch.object(s.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            await s._request_translation(['hello'])
            assert s._last_usage is not None
            assert s._last_usage['prompt_tokens'] == 10
            assert s._last_usage['completion_tokens'] == 5


# ─── 翻译流程端到端测试 ───

class TestSakuraTranslate:
    """Sakura 翻译流程端到端测试"""

    @pytest.mark.asyncio
    async def test_translate_single_query(self):
        """单条查询翻译成功。"""
        from manga_translator.translators.sakura import SakuraTranslator

        s = SakuraTranslator()
        mock_choice = MagicMock()
        mock_choice.message.content = '你好'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        with patch.object(s.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            result = await s._translate('JPN', 'CHS', ['こんにちは'])
            assert len(result) == 1
            assert '「' not in result[0]  # 括号被移除
            assert '」' not in result[0]


# ─── GPT 风格切换 ───

class TestStyleSwitch:
    """翻译风格切换测试"""

    def test_set_style_updates_params(self):
        """切换风格后参数更新。"""
        from manga_translator.translators.sakura import SakuraTranslator
        s = SakuraTranslator()
        s._set_gpt_style('normal')
        assert s.temperature == 0.3
        assert s.top_p == 0.3
        s._set_gpt_style('precise')
        assert s.temperature == 0.1
