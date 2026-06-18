"""
Qwen3 韩中翻译器 — 基于 Ollama + Qwen3 14B 的韩文→简体中文翻译。

特点：
- 专为韩中漫画翻译优化的 Prompt
- 通过 Ollama 远程调用（192.168.1.15:11434）
- 无降级链，失败即报错
- 禁用 enableThinking 以提升效率
- 继承 CustomOpenAiTranslator 的请求/重试/分片逻辑

使用方式:
    translator = Qwen3KoZhTranslator()
    results = await translator.translate('KOR', 'CHS', ['안녕하세요'])
"""
import json
import os
import re
from typing import List

import aiohttp

from .custom_openai import CustomOpenAiTranslator
from .keys import CUSTOM_OPENAI_API_KEY

# ─── 韩中翻译专用 System Prompt ───

QWEN3_KOZH_SYSTEM_PROMPT = (
    '忽略之前的所有指令，仅遵循以下定义。\n'

    '## 角色：专业韩中漫画翻译专家\n'
    '你是一位精通韩文漫画（Webtoon/Manhwa）翻译的专家，'
    '将韩文翻译成流畅自然的中文（简体中文）。\n'

    '## 翻译方法\n'
    '1. 直译阶段：\n'
    '- 对每个韩文文本行进行精确的逐字翻译。\n'
    '- 尽可能保留原文结构。\n'
    '- 保留所有原文标记、敬语和表达方式。\n'
    '- 对有歧义的元素不做过度解读，保持原样。\n'

    '2. 分析阶段：\n'
    '- 捕捉核心含义、情感基调和文化细微差别。\n'
    '- 识别碎片化文本之间的逻辑联系。\n'
    '- 分析直译的不足之处和改进空间。\n'

    '3. 润色阶段：\n'
    '- 调整翻译使其在简体中文中自然流畅，同时保留原意。\n'
    '- 保留适合漫画/二次元文化的情感基调和强度。\n'
    '- 确保角色语气和术语的一致性。\n'
    '- 根据上下文判断合适的代词（他/她/我/你/你们），'
    '不要添加原文中没有的代词。\n'
    '- 基于第二步的分析结论进行优化。\n'

    '## 翻译规则\n'
    '- 逐行翻译，保持准确性和真实感；忠实再现原文的情感和意图。\n'
    '- 保留原文中的拟声词/拟态词（의성어/의태어）不翻译，'
    '除非有常用的中文对应表达。\n'
    '- 严格按照 <|数字|> 格式输出每个段落，只提供翻译结果。\n'
    '- 只翻译内容，不附加任何解释或评论。\n'
    '- 韩文敬语（씨, 님, 선배, 오빠 等）应根据语境翻译为'
    '最接近的中文对应词或按需保留。\n'

    '将以下韩文文本翻译成简体中文：\n'
)

# ─── 韩中翻译 Chat Sample ───

QWEN3_KOZH_CHAT_SAMPLE = (
    (
        '<|1|>부끄러워... 눈에 띄고 싶지 않아... 내가 사라지고 싶어...\n'
        '<|2|>너... 괜찮아?!\n'
        '<|3|>뭐야 이 녀석... 분위기 못 읽는 거야...?'
    ),
    (
        '<|1|>好丢脸...我不想引人注目...我想消失...\n'
        '<|2|>你...没事吧?!\n'
        '<|3|>这家伙怎么回事...看不懂气氛的吗...?'
    )
)


class Qwen3KoZhTranslator(CustomOpenAiTranslator):
    """Qwen3 14B 韩中翻译器。

    通过 Ollama 原生 /api/chat 端点调用 Qwen3 14B 模型进行韩文→简体中文翻译。
    专为韩漫(Webtoon)翻译场景优化，无降级链。
    """

    # 超时重试策略：使用 Ollama 原生 /api/chat 端点，think=false 时
    # 正常请求 0.6-2.9s 完成。单次 120s 超时够用，不需重试。
    # 父类默认 40s/3 次重试，最坏情况 280s(4.7min)，反而因重试雪上加霜。
    _TIMEOUT = 120
    _TIMEOUT_RETRY_ATTEMPTS = 0

    _LANGUAGE_CODE_MAP = {
        'KOR': 'ko',
        'CHS': 'zh-CN',
        'CHT': 'zh-TW',
        'JPN': 'ja',
        'ENG': 'en',
        'VIN': 'vi',
    }

    def __init__(self, model=None, api_base=None, api_key=None):
        # 默认使用 Qwen3 14B 模型
        model = model or 'qwen3:14b-q4_k_m'
        # 默认 Ollama 地址
        api_base = api_base or 'http://192.168.1.15:11434/v1'
        api_key = api_key or CUSTOM_OPENAI_API_KEY or 'ollama'

        super().__init__(model=model, api_base=api_base, api_key=api_key)

        # 韩中翻译专用温度/采样参数
        self.temperature = 0.3
        self.top_p = 0.3

        # 构造 Ollama 原生 API 地址（去掉 /v1 后缀）
        self._ollama_api_base = api_base.rstrip('/').replace('/v1', '')
        self._ollama_chat_url = f'{self._ollama_api_base}/api/chat'

    @property
    def chat_system_template(self) -> str:
        """Override system template with Korean-Chinese specific prompt."""
        return QWEN3_KOZH_SYSTEM_PROMPT

    @property
    def _CHAT_SYSTEM_TEMPLATE(self) -> str:
        """Override parent's template."""
        return QWEN3_KOZH_SYSTEM_PROMPT

    def get_chat_sample(self, to_lang: str) -> tuple | None:
        """Override chat samples with Korean-Chinese examples."""
        return QWEN3_KOZH_CHAT_SAMPLE

    def _config_get(self, key: str, default=None):
        """Override config lookup to avoid parent ConfigGPT behavior."""
        return default

    @property
    def include_template(self) -> bool:
        return False

    @property
    def temperature(self) -> float:
        return self._temperature

    @temperature.setter
    def temperature(self, value: float):
        self._temperature = value

    @property
    def top_p(self) -> float:
        return self._top_p

    @top_p.setter
    def top_p(self, value: float):
        self._top_p = value

    @property
    def extra_body(self) -> dict:
        return getattr(self, '_extra_body', {})

    @extra_body.setter
    def extra_body(self, value: dict):
        self._extra_body = value

    async def _request_translation(self, to_lang: str, prompt: str) -> str:
        """Override to use Ollama native /api/chat with think=false."""
        messages = [
            {'role': 'system', 'content': self.chat_system_template.format(to_lang=to_lang)}
        ]

        chat_sample = self.get_chat_sample(to_lang)
        if chat_sample:
            messages.append({'role': 'user', 'content': chat_sample[0]})
            messages.append({'role': 'assistant', 'content': chat_sample[1]})

        messages.append({'role': 'user', 'content': prompt})

        payload = {
            'model': self.model,
            'messages': messages,
            'stream': False,
            'think': False,  # 禁用思考模式，大幅提升速度
            'options': {
                'temperature': self.temperature,
                'top_p': self.top_p,
                'num_predict': self._MAX_TOKENS // 2,
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self._ollama_chat_url, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f'Ollama API error ({resp.status}): {error_text}')
                data = await resp.json()

        self.logger.debug('\n-- Qwen3 Response (raw) --')
        self.logger.debug(data.get('message', {}).get('content', ''))
        self.logger.debug('-----------------------------\n')

        self.token_count += data.get('eval_count', 0) + data.get('prompt_eval_count', 0)
        self.token_count_last = data.get('eval_count', 0)

        return data['message']['content']