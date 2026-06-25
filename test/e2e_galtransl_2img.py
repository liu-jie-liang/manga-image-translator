#!/usr/bin/env python3
"""
方式C (Galtransl GGUF) E2E 测试 - 2+1 张图片

测试场景:
  场景1 - 首次翻译: 2 张图片, retrans=True → 全部翻译, progress 记录
  场景2 - 续传: 添加第3张, retrans=False → 只翻新图片, 已有图片跳过
  场景3 - 重翻覆盖: retrans=True → 3 张全部重翻, overwrite 始终生效

用法:
  export TRANSLATOR_MODE=galtransl
  export GALTRANS_GGUF_PATH=/path/to/Sakura-Galtransl-14B-v3.8-Q4_K_M.gguf
  python test/e2e_galtransl_2img.py
"""

import os, sys, asyncio, time, json, shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['TRANSLATOR_MODE'] = 'galtransl'

from manga_translator.batch import batch_translate

SRC = 'test/e2e-materials'
DIR = 'test/e2e-temp-galtransl'
DEST = f'{DIR} 汉化'  # batch.py 用 f'{dirname} 汉化' 格式
PROGRESS = os.path.join(DIR, '.translate_progress.json')
IMAGES = ['001.jpg', '002.jpg']
NEW_IMAGE = '003.jpg'

def check(phase: str, ok: bool, detail: str = ''):
    icon = 'PASS' if ok else 'FAIL'
    print(f'  [{icon}] {phase}: {detail}')

async def main():
    gguf_path = os.environ.get('GALTRANS_GGUF_PATH', '')
    if not gguf_path or not os.path.isfile(gguf_path):
        print('GALTRANS_GGUF_PATH not set or file not found, skip')
        return

    for d in [DIR, DEST]:
        if os.path.exists(d):
            shutil.rmtree(d)

    passed = True

    # =============================================
    # 场景 1: 首次翻译 (2 张, retrans=True)
    # =============================================
    print('')
    print('=' * 60)
    print('【场景1】首次翻译: 2 张图片, retrans=True')
    print('=' * 60)
    os.makedirs(DIR, exist_ok=True)
    for img in IMAGES:
        shutil.copy2(os.path.join(SRC, img), os.path.join(DIR, img))

    t0 = time.time()
    await batch_translate(DIR, retrans=True)
    elapsed1 = time.time() - t0
    print(f'  耗时: {elapsed1:.1f}s')

    dest_files = sorted(os.listdir(DEST)) if os.path.isdir(DEST) else []
    n1 = len(dest_files)
    check('翻译图片数', n1 == 2, f'预期 2, 实际 {n1}')
    if n1 != 2: passed = False

    has_p = os.path.isfile(PROGRESS)
    completed = json.load(open(PROGRESS))['completed'] if has_p else []
    check('Progress 记录', len(completed) == 2, f'预期 2, 实际 {len(completed)}: {completed}')
    if len(completed) != 2: passed = False

    # =============================================
    # 场景 2: 续传 (添加第3张, retrans=False)
    # =============================================
    print('')
    print('=' * 60)
    print('【场景2】续传: 添加第3张图片, retrans=False')
    print('=' * 60)
    shutil.copy2(os.path.join(SRC, NEW_IMAGE), os.path.join(DIR, NEW_IMAGE))

    t0 = time.time()
    await batch_translate(DIR, retrans=False)
    elapsed2 = time.time() - t0
    print(f'  耗时: {elapsed2:.1f}s (预期仅翻 1 张新图)')

    dest_files = sorted(os.listdir(DEST)) if os.path.isdir(DEST) else []
    n2 = len(dest_files)
    check('汉化目录图片数', n2 == 3, f'预期 3, 实际 {n2}: {dest_files}')
    if n2 != 3: passed = False

    has_p = os.path.isfile(PROGRESS)
    completed = json.load(open(PROGRESS))['completed'] if has_p else []
    check('Progress 记录增长', len(completed) == 3, f'预期 3, 实际 {len(completed)}: {completed}')
    if len(completed) != 3: passed = False

    # =============================================
    # 场景 3: 重翻覆盖 (retrans=True)
    # =============================================
    print('')
    print('=' * 60)
    print('【场景3】重翻覆盖: retrans=True, overwrite 始终生效')
    print('=' * 60)

    t0 = time.time()
    await batch_translate(DIR, retrans=True)
    elapsed3 = time.time() - t0
    print(f'  耗时: {elapsed3:.1f}s')

    dest_files = sorted(os.listdir(DEST)) if os.path.isdir(DEST) else []
    n3 = len(dest_files)
    check('重翻后图片数', n3 == 3, f'预期 3, 实际 {n3}')
    if n3 != 3: passed = False

    has_p = os.path.isfile(PROGRESS)
    completed = json.load(open(PROGRESS))['completed'] if has_p else []
    check('重翻后 Progress 记录', len(completed) == 3, f'预期 3, 实际 {len(completed)}: {completed}')
    if len(completed) != 3: passed = False

    # =============================================
    # 总结果
    # =============================================
    print('')
    print('=' * 60)
    if passed:
        print('PASS: 方式C E2E 测试全部通过!')
    else:
        print('FAIL: 方式C E2E 测试有异常')
    print('=' * 60)

    for d in [DIR, DEST]:
        if os.path.exists(d):
            shutil.rmtree(d)
    print(f'已清理: {DIR} 和 {DEST}')

    sys.exit(0 if passed else 1)

if __name__ == '__main__':
    asyncio.run(main())