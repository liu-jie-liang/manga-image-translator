#!/usr/bin/env python
"""E2E test script for 方式B (GGUF) - 158 images."""
import os, asyncio, time, json, shutil, sys

os.environ['SAKURA_GGUF_PATH'] = os.path.expanduser('~/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf')
os.environ.setdefault('SAKURA_API_BASE', 'http://localhost:11434/v1')
os.environ['SAKURA_MODEL'] = 'sakura-14b-qwen2.5-v1.0'

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

from manga_translator.batch import batch_translate

async def main():
    test_dir = 'test/e2e-materials'
    dest = os.path.join('test', 'e2e-materials 汉化')
    if os.path.exists(dest):
        shutil.rmtree(dest)

    start = time.time()
    await batch_translate(test_dir, retrans=True)
    elapsed = time.time() - start

    result_dir = os.path.join('test', 'e2e-materials 汉化')
    img_count = 0
    if os.path.isdir(result_dir):
        img_count = len([f for f in os.listdir(result_dir) if f.endswith(('.png','.jpg','.jpeg','.webp'))])

    result = {
        'mode': 'GGUF (方式B)',
        'total_images': 158,
        'translated_images': img_count,
        'elapsed_seconds': round(elapsed, 1),
        'elapsed_minutes': round(elapsed/60, 1),
        'avg_seconds_per_image': round(elapsed/img_count, 1) if img_count else 0,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))

    os.makedirs('test/results', exist_ok=True)
    with open('test/results/gguf_perf.json', 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

asyncio.run(main())