"""Sakura 本地 GGUF 翻译器 (方式B)

通过 llama-cpp-python 直连 GPU(MPS) 运行本地 GGUF 量化模型。
模型常驻显存单例复用，消除 HTTP 往返延迟。

使用方式:
    export SAKURA_GGUF_PATH=/path/to/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf

若未设置 SAKURA_GGUF_PATH，回退到方式A (Ollama HTTP, sakura.py)。
"""

import os
import re
import atexit
import logging
from typing import List

from .common import CommonTranslator

logger = logging.getLogger(__name__)


class SakuraLocalTranslator(CommonTranslator):
    """本地 GGUF Sakura 翻译器。

    将 Sakura 14B Qwen2.5 GGUF 模型加载到 Apple Silicon GPU(MPS)，
    模型常驻显存为单例，整个翻译会话复用。
    """

    # ---- 类级单例 ----
    _model = None              # llama_cpp.Llama 实例 (或 None)
    _loaded_gguf_path = None   # 已加载的 GGUF 路径 (不与 _gguf_path() 方法冲突)

    # ---- Sakura v0.9 Prompt 模板 (与 sakura.py 完全一致) ----
    _CHAT_SYSTEM_TEMPLATE = (
        '你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，'
        '并联系上下文正确使用人称代词，注意不要翻译为繁体中文，也不要添加原文中没有的代词。'
    )

    _LANGUAGE_CODE_MAP = {
        'CHS': 'Simplified Chinese',
        'JPN': 'Japanese'
    }

    def __init__(self):
        super().__init__()
        self.temperature = 0.3
        self.top_p = 0.3

    # ================================================================
    # 环境变量 → 方式选择
    # ================================================================

    @staticmethod
    def _use_local() -> bool:
        """判断是否使用本地 GGUF 方式。

        规则: SAKURA_GGUF_PATH 指向的文件存在 → True，否则 → False。
        """
        p = SakuraLocalTranslator._gguf_path()
        return p is not None and os.path.isfile(p)

    @staticmethod
    def _gguf_path() -> str | None:
        """返回 SAKURA_GGUF_PATH 环境变量值。"""
        return os.getenv('SAKURA_GGUF_PATH')

    # ================================================================
    # 模型生命周期 (单例)
    # ================================================================

    @classmethod
    def load_model(cls, gguf_path: str | None = None):
        """加载 GGUF 模型到 GPU，已加载则跳过。

        Args:
            gguf_path: GGUF 文件路径，若为 None 则从 SAKURA_GGUF_PATH 读取。
        """
        if cls._model is not None:
            logger.debug('SakuraLocal: 模型已加载，复用单例')
            return

        path = gguf_path or cls._gguf_path()
        if not path:
            raise FileNotFoundError('SAKURA_GGUF_PATH 未设置或无效')

        logger.info(f'SakuraLocal: 加载 GGUF 模型 {path} ...')
        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError(
                '请安装 llama-cpp-python: '
                'CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python'
            )

        n_gpu_layers = int(os.getenv('SAKURA_GGUF_N_GPU_LAYERS', '-1'))
        n_ctx = int(os.getenv('SAKURA_GGUF_N_CTX', '4096'))

        cls._model = Llama(
            model_path=path,
            n_gpu_layers=n_gpu_layers,
            n_ctx=n_ctx,
            verbose=False,
        )
        cls._loaded_gguf_path = path
        logger.info(
            f'SakuraLocal: 模型加载完成 '
            f'(n_gpu_layers={n_gpu_layers}, n_ctx={n_ctx})'
        )

    @classmethod
    def unload_model(cls):
        """释放模型单例，归还显存。"""
        if cls._model is not None:
            logger.info('SakuraLocal: 释放模型')
            cls._model.close()
            cls._model = None
            cls._loaded_gguf_path = None

    @classmethod
    def is_model_loaded(cls) -> bool:
        """检查模型是否已加载。"""
        return cls._model is not None

    # ================================================================
    # Prompt 构建 (复用 sakura.py 格式)
    # ================================================================

    @staticmethod
    def _preprocess_queries(queries: List[str]) -> List[str]:
        """为每条文本添加「」标记。"""
        return [f'「{q}」' for q in queries]

    def _build_prompt(self, queries: List[str]) -> dict:
        """构建 Sakura v0.9 格式的 chat prompt。

        Returns:
            {'system': str, 'user': str}
        """
        processed = self._preprocess_queries(queries)
        raw_text = '\n'.join(processed)
        return {
            'system': self._CHAT_SYSTEM_TEMPLATE,
            'user': f'将下面的日文文本翻译成中文：\n{raw_text}',
        }

    @staticmethod
    def _parse_response(response: str) -> List[str]:
        """从模型输出中提取每句翻译（去除「」标记）。

        匹配规则: 以「开头、」结尾的行。
        """
        pattern = re.compile(r'「(.+?)」')
        return pattern.findall(response)

    # ================================================================
    # 翻译入口 (CommonTranslator 协议)
    # ================================================================

    async def _translate(
        self, from_lang: str, to_lang: str, queries: List[str]
    ) -> List[str]:
        """翻译文本列表。

        作为 CommonTranslator 协议实现，所有异步翻译调用走此方法。
        """
        if not queries:
            return []

        logger.debug(f'SakuraLocal 原文: {queries}')

        # 若未设置 GGUF 路径，回退到方式A (由调用方处理)
        if not self._use_local():
            raise RuntimeError(
                'SAKURA_GGUF_PATH 未设置，无法使用本地 GGUF 翻译。'
                '请设置环境变量或使用 SakuraTranslator (Ollama HTTP)。'
            )

        # 自动加载模型
        self.load_model()

        prompt = self._build_prompt(queries)
        logger.debug('-- SakuraLocal Prompt --\n' + prompt['user'] + '\n\n')

        # 计算 max_tokens: 输入字符数 × 2，最少 512
        raw_len = sum(len(q) for q in queries)
        max_tokens = max(raw_len * 2, 512)

        try:
            result = self._model.create_chat_completion(
                messages=[
                    {'role': 'system', 'content': prompt['system']},
                    {'role': 'user', 'content': prompt['user']},
                ],
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.error(f'SakuraLocal 推理失败: {e}')
            raise

        response = result['choices'][0]['message']['content']
        logger.debug('-- SakuraLocal Response --\n' + response + '\n\n')

        translations = self._parse_response(response)
        logger.debug(f'SakuraLocal 译文: {translations}')
        return translations


# ---- atexit 自动释放模型 ----
atexit.register(SakuraLocalTranslator.unload_model)