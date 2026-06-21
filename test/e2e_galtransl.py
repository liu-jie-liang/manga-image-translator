#!/usr/bin/env python3
"""Galtransl (方式C) 端到端测试

使用 Galtransl GGUF 模型翻译测试图片集，验证全链路功能。
用法: python test/e2e_galtransl.py
"""

import os
import sys
import asyncio
import logging
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from manga_translator.translators.galtransl_local import GaltranslLocalTranslator
from manga_translator import Config

logger = logging.getLogger('e2e_galtransl')


async def main():
    """E2E 测试主流程"""
    galtrans_path = os.environ.get('GALTRANS_GGUF_PATH')
    if not galtrans_path or not os.path.isfile(galtrans_path):
        print('=' * 60)
        print('GALTRANS_GGUF_PATH 未设置或文件不存在，跳过 E2E 测试')
        print('请设置: export GALTRANS_GGUF_PATH=/path/to/Sakura-Galtransl-14B-v3.8-Q4_K_M.gguf')
        print('=' * 60)
        return

    print('=' * 60)
    print('  Galtransl 方式C 端到端测试')
    print('=' * 60)
    print(f'模型: {galtrans_path}')
    print()

    # 加载模型
    print('加载 Galtransl 模型...')
    t0 = time.time()
    GaltranslLocalTranslator.load_model(galtrans_path)
    load_time = time.time() - t0
    print(f'模型加载完成 ({load_time:.1f}s)')
    print()

    # 测试翻译
    translator = GaltranslLocalTranslator()
    test_cases = [
        # 正常文本
        ['こんにちは、今日はいい天気ですね。'],
        # 多句文本
        ['おはようございます', '今日も頑張りましょう', 'さようなら'],
        # R18 相关词汇测试
        ['感じる', '気持ちいい', 'やめて'],
    ]

    for i, queries in enumerate(test_cases):
        print(f'--- 测试用例 {i+1} ---')
        print(f'原文: {queries}')
        try:
            t0 = time.time()
            result = await translator._translate('JPN', 'CHS', queries)
            elapsed = time.time() - t0
            print(f'译文: {result}')
            print(f'耗时: {elapsed:.1f}s')
            success = len(result) > 0 and all(r for r in result)
            print(f'结果: {"PASS" if success else "FAIL (空翻译)"}')
        except Exception as e:
            print(f'错误: {e}')
            print(f'结果: FAIL')
        print()

    # 卸载模型
    print('卸载模型...')
    GaltranslLocalTranslator.unload_model()
    print('完成!')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())