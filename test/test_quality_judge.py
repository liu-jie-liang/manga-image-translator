"""LLM-as-Judge 模块 TDD 测试。

测试范围：
- JudgeConfig 配置数据模型
- judge_prompt 生成
- parse_judge_response 解析
- JudgeResult 数据模型
"""

import pytest
import json
from manga_translator.quality_judge import (
    JudgeConfig,
    JudgeResult,
    build_judge_prompt,
    parse_judge_response,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_USER_TEMPLATE,
)


class TestJudgeConfig:
    """JudgeConfig 数据模型测试。"""

    def test_default_config(self):
        config = JudgeConfig()
        assert config.model == 'qwen3:14b-q4_k_m'
        assert config.temperature == 0.0
        assert config.top_p == 1.0
        assert config.repeat_penalty == 1.1
        assert config.seed == 42
        assert config.max_tokens == 256
        assert config.timeout == 60

    def test_custom_config(self):
        config = JudgeConfig(
            model='test-model',
            temperature=0.3,
            api_base='http://localhost:1234',
            timeout=30,
        )
        assert config.model == 'test-model'
        assert config.temperature == 0.3
        assert config.api_base == 'http://localhost:1234'
        assert config.timeout == 30

    def test_config_env_fallback(self):
        """配置应能从环境变量读取默认值。"""
        config = JudgeConfig()
        assert config.api_base is not None  # 至少有一个默认值


class TestJudgeResult:
    """JudgeResult 数据模型测试。"""

    def test_valid_result(self):
        result = JudgeResult(
            score=5,
            accuracy_ok=True,
            issues='无明显问题',
            revised='',
        )
        assert result.score == 5
        assert result.accuracy_ok is True
        assert result.is_acceptable is True  # >= 4 分

    def test_unacceptable_result(self):
        result = JudgeResult(score=3, accuracy_ok=False, issues='漏译', revised='补充翻译')
        assert result.is_acceptable is False  # < 4 分

    def test_borderline_result(self):
        result = JudgeResult(score=4, accuracy_ok=True, issues='轻微问题', revised='')
        assert result.is_acceptable is True

    def test_to_dict(self):
        result = JudgeResult(score=4, accuracy_ok=True, issues='小问题', revised='')
        d = result.to_dict()
        assert d['score'] == 4
        assert d['accuracy_ok'] is True
        assert d['is_acceptable'] is True

    def test_from_dict(self):
        d = {'score': 2, 'accuracy_ok': False, 'issues': '严重误译', 'revised': '修正建议'}
        result = JudgeResult.from_dict(d)
        assert result.score == 2
        assert result.is_acceptable is False


class TestBuildJudgePrompt:
    """judge prompt 构建测试。"""

    def test_system_prompt_content(self):
        """系统提示词应包含关键指令。"""
        assert '日译中审校员' in JUDGE_SYSTEM_PROMPT
        assert 'JSON' in JUDGE_SYSTEM_PROMPT
        assert '推理过程' in JUDGE_SYSTEM_PROMPT  # 禁止输出推理过程

    def test_user_template_content(self):
        """用户提示词模板应包含占位符。"""
        assert '{source_text}' in JUDGE_USER_TEMPLATE
        assert '{translation_text}' in JUDGE_USER_TEMPLATE

    def test_build_prompt(self):
        """构建 prompt 应正确替换占位符。"""
        user_prompt = build_judge_prompt(
            source_text='こんにちは',
            translation_text='你好',
        )
        assert 'こんにちは' in user_prompt
        assert '你好' in user_prompt
        assert '【日文原文】' in user_prompt
        assert '【中文译文】' in user_prompt


class TestParseJudgeResponse:
    """Judge 响应解析测试。"""

    def test_valid_json_response(self):
        response = json.dumps({
            'score': 5,
            'accuracy_ok': True,
            'issues': '无明显问题',
            'revised': '',
        })
        result = parse_judge_response(response)
        assert result is not None
        assert result.score == 5
        assert result.accuracy_ok is True

    def test_response_with_extra_text(self):
        """JSON 被多余文字包围时仍能解析。"""
        response = """好的，以下是评估结果：
        {"score": 4, "accuracy_ok": true, "issues": "轻微不自然", "revised": ""}
        评估完成。"""
        result = parse_judge_response(response)
        assert result is not None
        assert result.score == 4

    def test_response_int_score(self):
        """score 为整数时正常解析。"""
        response = json.dumps({
            'score': 3,
            'accuracy_ok': False,
            'issues': '有明显问题',
            'revised': '建议修改',
        })
        result = parse_judge_response(response)
        assert result.score == 3

    def test_invalid_score_range(self):
        """score 超出 1-5 范围应返回 None。"""
        response = json.dumps({
            'score': 0,
            'accuracy_ok': True,
            'issues': '',
            'revised': '',
        })
        result = parse_judge_response(response)
        assert result is None

    def test_invalid_json(self):
        """完全无效的 JSON 应返回 None。"""
        result = parse_judge_response('not a json at all')
        assert result is None

    def test_missing_fields(self):
        """缺少必要字段应返回 None。"""
        response = json.dumps({'score': 4})
        result = parse_judge_response(response)
        assert result is None

    def test_empty_response(self):
        """空响应应返回 None。"""
        result = parse_judge_response('')
        assert result is None
        result = parse_judge_response(None)
        assert result is None