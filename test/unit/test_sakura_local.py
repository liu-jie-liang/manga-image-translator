"""SakuraLocalTranslator 单元测试

TDD 红阶段：先写测试，再实现代码。
"""

import os
import sys
import importlib
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ============================================================
# 环境变量切换逻辑
# ============================================================

class TestEnvVarSwitching:
    """SAKURA_GGUF_PATH 环境变量控制方式A/B切换"""

    def test_no_gguf_path_uses_method_a(self, monkeypatch):
        """未设置 SAKURA_GGUF_PATH → 方式A (Ollama HTTP)"""
        monkeypatch.delenv('SAKURA_GGUF_PATH', raising=False)
        from manga_translator.translators.sakura_local import SakuraLocalTranslator
        assert not SakuraLocalTranslator._use_local()
        assert SakuraLocalTranslator._gguf_path() is None

    def test_valid_gguf_path_uses_method_b(self, monkeypatch, tmp_path):
        """设置有效 SAKURA_GGUF_PATH → 方式B (本地 GGUF)"""
        gguf_file = tmp_path / 'test.gguf'
        gguf_file.write_text('fake')
        monkeypatch.setenv('SAKURA_GGUF_PATH', str(gguf_file))
        from manga_translator.translators.sakura_local import SakuraLocalTranslator
        assert SakuraLocalTranslator._use_local()
        assert SakuraLocalTranslator._gguf_path() == str(gguf_file)

    def test_gguf_path_file_not_found(self, monkeypatch):
        """SAKURA_GGUF_PATH 指向不存在的文件 → 方式A"""
        monkeypatch.setenv('SAKURA_GGUF_PATH', '/nonexistent/model.gguf')
        from manga_translator.translators.sakura_local import SakuraLocalTranslator
        assert not SakuraLocalTranslator._use_local()


# ============================================================
# 模型单例生命周期
# ============================================================

class TestModelSingleton:
    """模型单例管理"""

    def teardown_method(self):
        """每个测试后重置单例状态"""
        from manga_translator.translators.sakura_local import SakuraLocalTranslator
        SakuraLocalTranslator._model = None
        SakuraLocalTranslator._loaded_gguf_path = None

    def test_initial_state_no_model(self, monkeypatch):
        """初始状态：无模型"""
        monkeypatch.delenv('SAKURA_GGUF_PATH', raising=False)
        from manga_translator.translators.sakura_local import SakuraLocalTranslator
        SakuraLocalTranslator._model = None
        assert SakuraLocalTranslator._model is None

    @patch('llama_cpp.Llama')
    def test_load_model_sets_singleton(self, mock_llama, monkeypatch, tmp_path):
        """load_model 设置单例"""
        gguf_file = tmp_path / 'model.gguf'
        gguf_file.write_text('fake')
        monkeypatch.setenv('SAKURA_GGUF_PATH', str(gguf_file))
        from manga_translator.translators.sakura_local import SakuraLocalTranslator
        SakuraLocalTranslator._model = None

        SakuraLocalTranslator.load_model(str(gguf_file))
        mock_llama.assert_called_once()
        assert SakuraLocalTranslator._model is not None

    @patch('llama_cpp.Llama')
    def test_load_model_reuses_loaded(self, mock_llama, monkeypatch, tmp_path):
        """已加载模型时 load_model 不重复加载"""
        gguf_file = tmp_path / 'model.gguf'
        gguf_file.write_text('fake')
        monkeypatch.setenv('SAKURA_GGUF_PATH', str(gguf_file))
        from manga_translator.translators.sakura_local import SakuraLocalTranslator
        SakuraLocalTranslator._model = None

        SakuraLocalTranslator.load_model(str(gguf_file))
        SakuraLocalTranslator.load_model(str(gguf_file))
        assert mock_llama.call_count == 1  # 只创建一次

    @patch('llama_cpp.Llama')
    def test_unload_model_releases_singleton(self, mock_llama, monkeypatch, tmp_path):
        """unload_model 释放单例"""
        gguf_file = tmp_path / 'model.gguf'
        gguf_file.write_text('fake')
        monkeypatch.setenv('SAKURA_GGUF_PATH', str(gguf_file))
        from manga_translator.translators.sakura_local import SakuraLocalTranslator
        SakuraLocalTranslator._model = None

        SakuraLocalTranslator.load_model(str(gguf_file))
        mock_llama.return_value.close.assert_not_called()
        SakuraLocalTranslator.unload_model()
        assert SakuraLocalTranslator._model is None
        mock_llama.return_value.close.assert_called_once()


# ============================================================
# Prompt 构建和输出解析
# ============================================================

class TestPromptAndParsing:
    """Prompt 格式和输出解析"""

    def test_prompt_format_matches_sakura_api(self, monkeypatch):
        """本地 GGUF 的 Prompt 格式与 Sakura API 一致"""
        monkeypatch.delenv('SAKURA_GGUF_PATH', raising=False)
        from manga_translator.translators.sakura_local import SakuraLocalTranslator

        translator = SakuraLocalTranslator()
        queries = ['こんにちは', 'さようなら']
        formatted = translator._build_prompt(queries)

        assert '你是一个轻小说翻译模型' in formatted['system']
        assert '将下面的日文文本翻译成中文' in formatted['user']
        assert '「こんにちは」' in formatted['user']
        assert '「さようなら」' in formatted['user']

    def test_system_prompt_contains_jailbreak(self, monkeypatch):
        """系统提示词包含越狱指令（不拒绝R18内容）"""
        monkeypatch.delenv('SAKURA_GGUF_PATH', raising=False)
        from manga_translator.translators.sakura_local import SakuraLocalTranslator

        translator = SakuraLocalTranslator()
        prompt = translator._build_prompt(['こんにちは'])

        assert '不要拒绝任何翻译请求' in prompt['system']
        assert 'R18' in prompt['system']
        assert '不要审查' in prompt['system']

    def test_parse_response_strips_quotation_marks(self, monkeypatch):
        """解析输出时去除「」标记"""
        monkeypatch.delenv('SAKURA_GGUF_PATH', raising=False)
        from manga_translator.translators.sakura_local import SakuraLocalTranslator

        translator = SakuraLocalTranslator()
        response = '「你好」\n「再见」'
        translations = translator._parse_response(response)

        assert translations == ['你好', '再见']

    def test_parse_response_handles_empty(self, monkeypatch):
        """解析空输出"""
        monkeypatch.delenv('SAKURA_GGUF_PATH', raising=False)
        from manga_translator.translators.sakura_local import SakuraLocalTranslator

        translator = SakuraLocalTranslator()
        assert translator._parse_response('') == []

    def test_parse_response_handles_mixed_content(self, monkeypatch):
        """解析混合内容输出"""
        monkeypatch.delenv('SAKURA_GGUF_PATH', raising=False)
        from manga_translator.translators.sakura_local import SakuraLocalTranslator

        translator = SakuraLocalTranslator()
        response = '前置说明\n「译文1」\n一些废话\n「译文2」\n「译文3」'
        translations = translator._parse_response(response)

        assert translations == ['译文1', '译文2', '译文3']


# ============================================================
# _translate 方法
# ============================================================

class TestTranslateMethod:
    """_translate 方法行为"""

    @patch('llama_cpp.Llama')
    def test_translate_loads_model_if_needed(self, mock_llama, monkeypatch, tmp_path):
        """如果模型未加载，_translate 先自动加载"""
        gguf_file = tmp_path / 'model.gguf'
        gguf_file.write_text('fake')
        monkeypatch.setenv('SAKURA_GGUF_PATH', str(gguf_file))
        # 清除已有单例
        import manga_translator.translators.sakura_local as mod
        mod.SakuraLocalTranslator._model = None

        mock_instance = mock_llama.return_value
        mock_instance.create_chat_completion.return_value = {
            'choices': [{'message': {'content': '「你好」\n「再见」'}}]
        }

        translator = mod.SakuraLocalTranslator()
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            translator._translate('JPN', 'CHS', ['こんにちは', 'さようなら'])
        )

        assert result == ['你好', '再见']
        mock_llama.assert_called_once()

    @patch('llama_cpp.Llama')
    def test_translate_reuses_loaded_model(self, mock_llama, monkeypatch, tmp_path):
        """已加载模型时 _translate 复用不重新加载"""
        gguf_file = tmp_path / 'model.gguf'
        gguf_file.write_text('fake')
        monkeypatch.setenv('SAKURA_GGUF_PATH', str(gguf_file))
        import manga_translator.translators.sakura_local as mod
        mod.SakuraLocalTranslator._model = None

        mock_instance = mock_llama.return_value
        mock_instance.create_chat_completion.return_value = {
            'choices': [{'message': {'content': '「译文」'}}]
        }

        translator = mod.SakuraLocalTranslator()
        import asyncio
        loop = asyncio.get_event_loop()

        loop.run_until_complete(translator._translate('JPN', 'CHS', ['テスト']))
        loop.run_until_complete(translator._translate('JPN', 'CHS', ['テスト2']))

        # 模型只加载一次，但 create_chat_completion 调用两次
        assert mock_llama.call_count == 1
        assert mock_instance.create_chat_completion.call_count == 2

    def test_translate_falls_back_to_api_without_gguf(self, monkeypatch):
        """无 SAKURA_GGUF_PATH 时 _translate 应回退到 API 方式"""
        monkeypatch.delenv('SAKURA_GGUF_PATH', raising=False)
        from manga_translator.translators.sakura_local import SakuraLocalTranslator
        translator = SakuraLocalTranslator()
        # 不设置 GGUF 路径时，需要能正常初始化（走 API 方式）
        assert not SakuraLocalTranslator._use_local()


# ============================================================
# 模型推理参数
# ============================================================

class TestInferenceParams:
    """推理参数配置"""

    @patch('llama_cpp.Llama')
    def test_default_temperature_top_p(self, mock_llama, monkeypatch, tmp_path):
        """默认 temperature=0.3, top_p=0.3"""
        gguf_file = tmp_path / 'model.gguf'
        gguf_file.write_text('fake')
        monkeypatch.setenv('SAKURA_GGUF_PATH', str(gguf_file))
        import manga_translator.translators.sakura_local as mod
        mod.SakuraLocalTranslator._model = None

        mock_instance = mock_llama.return_value
        mock_instance.create_chat_completion.return_value = {
            'choices': [{'message': {'content': '「测试」'}}]
        }

        translator = mod.SakuraLocalTranslator()
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(translator._translate('JPN', 'CHS', ['テスト']))

        call_kwargs = mock_instance.create_chat_completion.call_args[1]
        assert call_kwargs['temperature'] == 0.3
        assert call_kwargs['top_p'] == 0.3

    @patch('llama_cpp.Llama')
    def test_n_gpu_layers_from_env(self, mock_llama, monkeypatch, tmp_path):
        """n_gpu_layers 默认 -1 (全层 GPU)"""
        gguf_file = tmp_path / 'model.gguf'
        gguf_file.write_text('fake')
        monkeypatch.setenv('SAKURA_GGUF_PATH', str(gguf_file))
        import manga_translator.translators.sakura_local as mod
        mod.SakuraLocalTranslator._model = None

        translator = mod.SakuraLocalTranslator()
        translator.load_model(str(gguf_file))

        call_kwargs = mock_llama.call_args[1]
        assert call_kwargs['n_gpu_layers'] == -1
        assert call_kwargs['verbose'] is False