#!/usr/bin/env python3
"""E2E 10-image test for all 4 translation modes.

Each mode: full translation (retrans=true, 10 images) → resume (retrans=false, +2 images)
Results saved to test/results/e2e_10img_*.json

用法:
  python test/e2e_10img_all.py --all            # 运行全部 4 种方式
  python test/e2e_10img_all.py --mode ollama     # 仅方式A (Ollama Sakura)
  python test/e2e_10img_all.py --mode gguf       # 仅方式B (Sakura GGUF)
  python test/e2e_10img_all.py --mode galtransl  # 仅方式C (Galtransl GGUF)
  python test/e2e_10img_all.py --mode qwen3      # 仅韩中 (Qwen3 Ollama)
"""

import os
import sys
import json
import time
import shutil
import subprocess
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('e2e_10img')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIR = os.path.join(
    PROJECT_ROOT,
    '带着攻略的最强魔法师【1-67话11-67是生肉】'
    '【「攻略本」を駆使する最強の魔法使い／盡情活用「攻略本」的最強魔法師】',
    '12',
)
TEMP_BASE = os.path.join(PROJECT_ROOT, 'test', 'e2e-10img-temp')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'test', 'results')

IMAGE_NAMES = [f'{i:03d}.jpg' for i in range(1, 13)]  # 001.jpg ~ 012.jpg
FULL_IMAGES = IMAGE_NAMES[:10]   # 001~010
EXTRA_IMAGES = IMAGE_NAMES[10:]  # 011~012

MODE_CONFIG = {
    'ollama': {
        'label': '方式A (Ollama Sakura)',
        'env': {
            'SAKURA_MODEL': 'sakura-14b-qwen2.5-v1.0',
            'SAKURA_API_BASE': 'http://localhost:11434/v1',
        },
        'env_unset': ['SAKURA_GGUF_PATH', 'TRANSLATOR_MODE'],
        'module': 'manga_translator.batch',
        'has_benchmark': True,
    },
    'gguf': {
        'label': '方式B (Sakura GGUF)',
        'env': {
            'SAKURA_GGUF_PATH': os.path.expanduser(
                '~/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf'
            ),
            'SAKURA_MODEL': 'sakura-14b-qwen2.5-v1.0',
            'SAKURA_API_BASE': 'http://localhost:11434/v1',
        },
        'env_unset': ['TRANSLATOR_MODE'],
        'module': 'manga_translator.batch',
        'has_benchmark': True,
    },
    'galtransl': {
        'label': '方式C (Galtransl GGUF)',
        'env': {
            'TRANSLATOR_MODE': 'galtransl',
            'GALTRANS_GGUF_PATH': os.path.expanduser(
                '~/.ollama/models/gguf/Sakura-Galtransl-14B-v3.8-Q4_K_M.gguf'
            ),
            'RETRANS': 'true',
        },
        'env_unset': ['SAKURA_GGUF_PATH'],
        'module': 'manga_translator.batch',
        'has_benchmark': True,
    },
    'qwen3': {
        'label': '韩中 (Qwen3 Ollama)',
        'env': {
            'CUSTOM_OPENAI_API_BASE': 'http://localhost:11434/v1',
            'CUSTOM_OPENAI_MODEL': 'qwen3:14b-q4_k_m',
        },
        'env_unset': [],
        'module': 'manga_translator.batch_ko',
        'has_benchmark': False,
    },
}


def prepare_temp_dir(mode: str) -> str:
    """Create temp dir and copy 10 test images."""
    temp_dir = os.path.join(TEMP_BASE, mode)
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    for img in FULL_IMAGES:
        src = os.path.join(SOURCE_DIR, img)
        dst = os.path.join(temp_dir, img)
        shutil.copy2(src, dst)

    logger.info(f'Prepared {len(FULL_IMAGES)} images in {temp_dir}')
    return temp_dir


def add_extra_images(temp_dir: str) -> list:
    """Add extra images for resume test."""
    added = []
    for img in EXTRA_IMAGES:
        src = os.path.join(SOURCE_DIR, img)
        dst = os.path.join(temp_dir, img)
        shutil.copy2(src, dst)
        added.append(img)
    logger.info(f'Added {len(added)} extra images: {added}')
    return added


def collect_benchmark_data(benchmark_context):
    """Collect pipeline stage averages from benchmark context."""
    stages = {}
    try:
        pages = benchmark_context.pages
        if not pages:
            return stages
        successful = [p for p in pages if p.error is None]
        if not successful:
            return stages
        stage_names = ['detection', 'ocr', 'translation', 'inpainting', 'rendering']
        for name in stage_names:
            values = [getattr(p, name).elapsed for p in successful
                      if getattr(p, name).elapsed > 0]
            if values:
                stages[name] = {
                    'count': len(values),
                    'avg_s': round(sum(values) / len(values), 2),
                    'min_s': round(min(values), 2),
                    'max_s': round(max(values), 2),
                }
        # Token throughput
        total_completion = sum(p.completion_tokens for p in successful)
        total_translation = sum(p.translation.elapsed for p in successful)
        total_prompt = sum(p.prompt_tokens for p in successful)
        if total_translation > 0:
            stages['_tokens'] = {
                'prompt_tokens': total_prompt,
                'completion_tokens': total_completion,
                'total_tokens': total_prompt + total_completion,
                'tokens_per_sec': round(total_completion / total_translation, 2),
            }
    except Exception as e:
        logger.warning(f'Failed to collect benchmark data: {e}')
    return stages


def run_translation(mode: str, temp_dir: str, retrans: bool) -> dict:
    """Run translation via the appropriate batch module. Returns result dict."""
    os.chdir(PROJECT_ROOT)
    config = MODE_CONFIG[mode]

    # Set environment variables
    for key, val in config['env'].items():
        os.environ[key] = val
    for key in config['env_unset']:
        os.environ.pop(key, None)

    # Import the right module
    module_name = config['module']
    if module_name == 'manga_translator.batch':
        from manga_translator.batch import batch_translate
        from manga_translator.benchmark import benchmark_context
        translate_fn = lambda: batch_translate(temp_dir, retrans=retrans, benchmark=True)
    elif module_name == 'manga_translator.batch_ko':
        from manga_translator.batch_ko import batch_translate
        translate_fn = lambda: batch_translate(temp_dir, retrans=retrans)

    # Run
    import asyncio
    t0 = time.time()
    asyncio.run(translate_fn())
    elapsed = time.time() - t0

    dest_dir = f'{temp_dir} 汉化'
    dest_count = len([
        f for f in os.listdir(dest_dir)
        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
    ]) if os.path.isdir(dest_dir) else 0

    progress_file = os.path.join(temp_dir, '.translate_progress.json')
    if os.path.isfile(progress_file):
        with open(progress_file) as f:
            progress_data = json.load(f)
        progress_count = len(progress_data.get('completed', []))
    else:
        progress_count = 0

    result = {
        'mode': mode,
        'label': config['label'],
        'retrans': retrans,
        'elapsed_s': round(elapsed, 1),
        'dest_count': dest_count,
        'progress_count': progress_count,
    }

    # Collect benchmark data if available
    if config['has_benchmark'] and module_name == 'manga_translator.batch':
        try:
            from manga_translator.benchmark import benchmark_context
            stages = collect_benchmark_data(benchmark_context)
            if stages:
                result['stages'] = stages
        except Exception as e:
            logger.warning(f'Benchmark collection failed: {e}')

    return result


def cleanup_temp_dir(mode: str):
    """Remove temp dir and its漢化 output."""
    temp_dir = os.path.join(TEMP_BASE, mode)
    dest_dir = f'{temp_dir} 汉化'
    for d in [temp_dir, dest_dir]:
        if os.path.exists(d):
            shutil.rmtree(d)


def run_single_mode(mode: str) -> dict:
    """Run full + resume test for a single mode."""
    config = MODE_CONFIG[mode]
    label = config['label']
    logger.info(f'{"=" * 60}')
    logger.info(f'Testing: {label}')
    logger.info(f'{"=" * 60}')

    # Phase 1: Full translation
    temp_dir = prepare_temp_dir(mode)
    logger.info(f'--- Full translation (retrans=true, {len(FULL_IMAGES)} images) ---')
    result_full = run_translation(mode, temp_dir, retrans=True)
    logger.info(f'Full result: {json.dumps(result_full, ensure_ascii=False)}')

    # Phase 2: Resume (add 2 images, retrans=false)
    added = add_extra_images(temp_dir)
    logger.info(f'--- Resume translation (retrans=false, +{len(added)} images) ---')
    result_resume = run_translation(mode, temp_dir, retrans=False)
    logger.info(f'Resume result: {json.dumps(result_resume, ensure_ascii=False)}')

    # Cleanup
    cleanup_temp_dir(mode)

    combined = {
        'mode': mode,
        'label': label,
        'date': time.strftime('%Y-%m-%d'),
        'full': result_full,
        'resume': result_resume,
        'total_elapsed_s': round(result_full['elapsed_s'] + result_resume['elapsed_s'], 1),
    }
    return combined


def run_mode_subprocess(mode: str) -> dict:
    """Run a single mode test in a subprocess (clean model isolation)."""
    result = subprocess.run(
        [sys.executable, __file__, '--mode', mode],
        capture_output=True,
        text=True,
        timeout=3600,
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        logger.error(f'{mode} failed:\nSTDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}')
        return None
    # Parse JSON from last line of stdout
    for line in reversed(result.stdout.strip().split('\n')):
        line = line.strip()
        if line.startswith('{'):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def main():
    parser = argparse.ArgumentParser(description='E2E 10-image test')
    parser.add_argument('--mode', choices=['ollama', 'gguf', 'galtransl', 'qwen3'],
                        help='Run single mode')
    parser.add_argument('--all', action='store_true',
                        help='Run all 4 modes (via subprocess for isolation)')
    args = parser.parse_args()

    if args.mode:
        # Single mode - run directly
        result = run_single_mode(args.mode)
        os.makedirs(RESULTS_DIR, exist_ok=True)
        out_file = os.path.join(RESULTS_DIR, f'e2e_10img_{args.mode}.json')
        with open(out_file, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        # Print JSON as last line for --all subprocess parsing
        print(json.dumps(result, ensure_ascii=False))
        logger.info(f'Results saved to {out_file}')
        return

    if args.all:
        modes = ['ollama', 'gguf', 'galtransl', 'qwen3']
        all_results = []
        failed = []

        for mode in modes:
            logger.info(f'{"=" * 60}')
            logger.info(f'Starting subprocess for {mode}...')
            logger.info(f'{"=" * 60}')
            result = run_mode_subprocess(mode)
            if result:
                all_results.append(result)
                logger.info(f'{mode} PASS: total {result["total_elapsed_s"]}s')
            else:
                failed.append(mode)
                logger.error(f'{mode} FAILED')

        # Save aggregate results
        os.makedirs(RESULTS_DIR, exist_ok=True)
        aggregate = {
            'date': time.strftime('%Y-%m-%d'),
            'results': all_results,
            'failed': failed,
        }
        out_file = os.path.join(RESULTS_DIR, 'e2e_10img_all.json')
        with open(out_file, 'w') as f:
            json.dump(aggregate, f, indent=2, ensure_ascii=False)

        print()
        print('=' * 60)
        print('E2E 10-Image Test Summary')
        print('=' * 60)
        for r in all_results:
            print(f'  {r["label"]}: total {r["total_elapsed_s"]}s')
            print(f'    Full: {r["full"]["elapsed_s"]}s, {r["full"]["dest_count"]} images')
            print(f'    Resume: {r["resume"]["elapsed_s"]}s, {r["resume"]["dest_count"]} images')
            if 'stages' in r['full']:
                print(f'    Stages: {json.dumps(r["full"]["stages"], ensure_ascii=False)}')
        if failed:
            print(f'  FAILED: {", ".join(failed)}')
        print(f'Saved to {out_file}')
        return

    parser.print_help()


if __name__ == '__main__':
    main()
