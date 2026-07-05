"""LLM-as-Judge 翻译质量评分模块

使用 Qwen3-14B-Q4_K_M 通过 Ollama 对日译中翻译结果进行自动化评分。

评分维度：
- 准确性：无漏译、误译、增译
- 地道性：符合中文表达习惯
- 术语一致性：专有名词翻译统一、合理

评分规则：
- 5 分：几乎完美
- 4 分：可接受，轻微问题
- 3 分：有明显问题，需人工复审
- ≤2 分：严重误译或语义偏离
"""

import json
import re
import logging
from dataclasses import dataclass, field
from typing import Optional, List

import aiohttp

logger = logging.getLogger('quality_judge')


# ═══════════════════════════════════════════════════════════════════════════════
# 系统提示词（Qwen3-14B-Q4_K_M 专用，经用户调试）
# ═══════════════════════════════════════════════════════════════════════════════

JUDGE_SYSTEM_PROMPT = """你是一名专业的日译中审校员。
你的任务是对"日文原文 + 中文译文"进行严格但不过度敏感的评估。

必须遵守以下原则：
1. 允许在不改变原意的前提下，补全日文中省略的主语、宾语或逻辑关系，此类补全不算增译。
2. 不单独评判敬语种类（尊敬语/谦让语等），只判断整体敬语强度是否与原文一致。
3. 不鼓励过度直译，只要意思准确、表达自然即可。
4. 禁止输出推理过程，仅输出最终评分与结论。
5. 输出必须严格遵守 JSON 格式，不得有任何多余文字。"""

JUDGE_USER_TEMPLATE = """【日文原文】
{source_text}

【中文译文】
{translation_text}

请按以下标准评分（1–5 分）：
1. 准确性：无漏译、误译、增译
2. 地道性：符合中文表达习惯
3. 术语一致性：专有名词翻译统一、合理

评分规则：
- 5 分：几乎完美，仅需极细微润色
- 4 分：可接受，有轻微问题但不影响理解
- 3 分：有明显问题，需人工复审
- ≤2 分：严重误译或语义偏离

请输出 JSON：
{{
  "score": 1–5,
  "accuracy_ok": true/false,
  "issues": "用一句话指出具体问题（如无则写'无明显问题'）",
  "revised": "仅在 ≤3 分时给出简要修改建议，否则留空"
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class JudgeConfig:
    """Judge 模型配置。

    推理参数经过专门调试，针对 Qwen3-14B-Q4_K_M 量化模型优化。
    """

    # Ollama 端点
    api_base: str = "http://localhost:11434"

    # 模型名称
    model: str = "qwen3:14b-q4_k_m"

    # 推理参数（打分必须 deterministic）
    temperature: float = 0.0
    top_p: float = 1.0
    repeat_penalty: float = 1.1
    seed: int = 42

    # 输出限制
    max_tokens: int = 256

    # 请求超时
    timeout: int = 60


@dataclass
class JudgeResult:
    """单次 Judge 评分结果。"""

    score: int = 0                       # 1-5 分
    accuracy_ok: bool = False            # 准确性是否通过
    issues: str = ""                     # 问题描述
    revised: str = ""                    # 修改建议（≤3 分时有值）

    @property
    def is_acceptable(self) -> bool:
        """翻译是否可接受（≥4 分）。"""
        return self.score >= 4

    def to_dict(self) -> dict:
        return {
            'score': self.score,
            'accuracy_ok': self.accuracy_ok,
            'issues': self.issues,
            'revised': self.revised,
            'is_acceptable': self.is_acceptable,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'JudgeResult':
        return cls(
            score=int(d.get('score', 0)),
            accuracy_ok=bool(d.get('accuracy_ok', False)),
            issues=str(d.get('issues', '')),
            revised=str(d.get('revised', '')),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Prompt 构建
# ═══════════════════════════════════════════════════════════════════════════════

def build_judge_prompt(source_text: str, translation_text: str) -> str:
    """构建 Judge 用户提示词。

    Args:
        source_text: 日文原文
        translation_text: 中文译文

    Returns:
        格式化后的用户提示词
    """
    return JUDGE_USER_TEMPLATE.format(
        source_text=source_text,
        translation_text=translation_text,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 响应解析
# ═══════════════════════════════════════════════════════════════════════════════

def parse_judge_response(response: Optional[str]) -> Optional[JudgeResult]:
    """解析 Judge 模型的 JSON 响应。

    使用正则提取 JSON 块，兼容 Q4 量化后可能出现的格式波动。

    Args:
        response: 模型原始响应文本

    Returns:
        JudgeResult 或 None（解析失败）
    """
    if not response:
        return None

    # 尝试提取 JSON 对象
    json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', response, re.DOTALL)
    if not json_match:
        # 尝试更宽松的匹配
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)

    if not json_match:
        logger.warning(f'无法从响应中提取 JSON: {response[:200]}')
        return None

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        logger.warning(f'JSON 解析失败: {json_match.group()[:200]}')
        return None

    # 验证必要字段
    if 'score' not in data:
        return None
    if 'accuracy_ok' not in data:
        return None

    score = data.get('score')
    if not isinstance(score, (int, float)):
        return None
    score = int(score)
    if score < 1 or score > 5:
        return None

    return JudgeResult.from_dict(data)


# ═══════════════════════════════════════════════════════════════════════════════
# Ollama 调用
# ═══════════════════════════════════════════════════════════════════════════════

async def _call_ollama_generate(
    config: JudgeConfig,
    system_prompt: str,
    user_prompt: str,
) -> Optional[str]:
    """调用 Ollama /api/generate 端点。

    Args:
        config: Judge 配置
        system_prompt: 系统提示词
        user_prompt: 用户提示词

    Returns:
        模型响应文本，或 None（调用失败）
    """
    url = f"{config.api_base}/api/generate"
    payload = {
        'model': config.model,
        'prompt': user_prompt,
        'system': system_prompt,
        'stream': False,
        'options': {
            'temperature': config.temperature,
            'top_p': config.top_p,
            'repeat_penalty': config.repeat_penalty,
            'seed': config.seed,
        },
    }

    try:
        timeout = aiohttp.ClientTimeout(total=config.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    logger.error(f'Ollama API 错误: HTTP {resp.status}')
                    return None
                data = await resp.json()
                return data.get('response', '')
    except aiohttp.ClientError as e:
        logger.error(f'Ollama 请求失败: {e}')
        return None
    except Exception as e:
        logger.error(f'Judge 调用异常: {e}')
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# 单次评分
# ═══════════════════════════════════════════════════════════════════════════════

async def judge_single(
    source_text: str,
    translation_text: str,
    config: Optional[JudgeConfig] = None,
) -> Optional[JudgeResult]:
    """对单条翻译进行评分。

    Args:
        source_text: 日文原文
        translation_text: 中文译文
        config: Judge 配置（可选，使用默认配置）

    Returns:
        JudgeResult 或 None
    """
    if config is None:
        config = JudgeConfig()

    user_prompt = build_judge_prompt(source_text, translation_text)
    response = await _call_ollama_generate(config, JUDGE_SYSTEM_PROMPT, user_prompt)

    if response is None:
        return None

    return parse_judge_response(response)


# ═══════════════════════════════════════════════════════════════════════════════
# 批量评分
# ═══════════════════════════════════════════════════════════════════════════════

async def judge_batch(
    source_texts: List[str],
    translation_texts: List[str],
    config: Optional[JudgeConfig] = None,
) -> List[Optional[JudgeResult]]:
    """批量评分。

    Args:
        source_texts: 日文原文列表
        translation_texts: 中文译文列表（与 source_texts 一一对应）
        config: Judge 配置（可选）

    Returns:
        JudgeResult 列表（与输入一一对应）
    """
    results = []
    for src, tgt in zip(source_texts, translation_texts):
        result = await judge_single(src, tgt, config)
        results.append(result)
    return results