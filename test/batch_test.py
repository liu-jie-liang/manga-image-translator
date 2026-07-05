#!/usr/bin/env python3
"""测试 Ollama Sakura 大批量翻译速度"""
import time
import asyncio
import openai

async def test():
    client = openai.AsyncOpenAI(
        api_key='empty',
        base_url=os.environ.get('SAKURA_API_BASE', 'http://localhost:11434/v1')
    )
    texts = [
        '第61話', '敗戦決定', 'あ～あ～', '全滅必至だ',
        'ゴーレム軍団が', 'アンデッド軍団に', 'メタメタです',
        'いや…', '相手でも', 'はずだな', 'ますねー',
        '以下と表現', 'これは先が', '戦力的には', 'この場合は',
        'すべきか？', '勝ちの目は', '思いやられ', 'ですよね？',
        '司令塔が無能', '十分にあった', '負けてないん',
        '想像以上だな', 'という訳でも', '…ある意味では',
        '無能かもしれん', 'ゴーレム軍団は', 'アンデッド軍団',
        'ないんですよね？', '私の名前は太郎です',
        '第62話33', '第63話', '第64話93', '第65話123',
        'やはり強い', 'これは驚き', '信じられない',
        '助けてくれ', '危ない！', 'どうした？', '待ってくれ',
        '何故だ', 'わかった', '行くぞ', '了解です',
        '任せてくれ', '戦闘開始', '逃げるな', 'まだ終わってない',
    ]

    for mult in [1, 5, 10]:
        batch = texts * mult
        queries = [f'「{t}」' for t in batch]
        raw = '\n'.join(queries)
        raw_len = len(raw)

        print(f'--- 批量 {len(batch)} 条, 共 {raw_len} 字符 ---')
        t0 = time.time()
        resp = await client.chat.completions.create(
            model='sakura-14b-qwen2.5-v1.0:latest',
            messages=[{
                'role': 'system',
                'content': '你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文。'
            }, {
                'role': 'user',
                'content': f'将下面的日文文本翻译成中文：\n{raw}'
            }],
            temperature=0.1, top_p=0.3,
            max_tokens=max(raw_len * 2, 512),
        )
        dt = time.time() - t0
        output = resp.choices[0].message.content
        lines = [l.strip('「」') for l in output.split('\n') if l.strip().startswith('「')]
        match_rate = len(lines) / len(batch) if batch else 0
        print(f'  耗时: {dt:.1f}s')
        print(f'  结果: {len(lines)}/{len(batch)} 匹配({match_rate:.0%})')
        print(f'  tok/s: {resp.usage.completion_tokens/dt:.0f}')
        print(f'  样本: {batch[0]} => {lines[0] if lines else "N/A"}')
        print()

asyncio.run(test())