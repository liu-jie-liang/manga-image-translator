"""
Script to run modeA (Ollama HTTP) and modeB (local GGUF) benchmarks sequentially.
CRITICAL: Env vars must be set BEFORE importing manga_translator modules,
because keys.py reads them at module import time.
"""
import os
import sys
import shutil

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test', 'e2e-materials')
OUTPUT_DIR = TEST_DIR + ' 汉化'


def _clear_module_cache():
    """Remove manga_translator modules from cache so re-import picks up new env vars."""
    to_remove = [k for k in sys.modules if k.startswith('manga_translator')]
    for k in to_remove:
        del sys.modules[k]


def run_mode(mode_name: str):
    """Run a single benchmark mode."""
    print("=" * 60)
    print(f"  RUNNING {mode_name}")
    print("=" * 60)

    # Clean output dir
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
        print(f"Cleaned output dir: {OUTPUT_DIR}")

    # Clear cached modules so new env vars take effect
    _clear_module_cache()

    # Import after env vars are set and cache cleared
    import asyncio
    from manga_translator.batch import batch_translate
    asyncio.run(batch_translate(TEST_DIR, retrans=True, benchmark=True))


if __name__ == '__main__':
    # ── Mode A: Ollama HTTP ──
    os.environ['SAKURA_API_BASE'] = 'http://192.168.1.15:11434/v1'
    os.environ['SAKURA_MODEL'] = 'sakura-14b-qwen2.5-v1.0'
    os.environ.pop('SAKURA_GGUF_PATH', None)
    run_mode("MODE A: Ollama HTTP")

    # ── Mode B: Local GGUF ──
    os.environ['SAKURA_GGUF_PATH'] = '/Users/liujieliang/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-Q4_K_M.gguf'
    os.environ['SAKURA_API_BASE'] = 'http://192.168.1.15:11434/v1'
    os.environ['SAKURA_MODEL'] = 'sakura-14b-qwen2.5-v1.0'
    run_mode("MODE B: Local GGUF")

    print("\n" + "=" * 60)
    print("  BOTH BENCHMARKS COMPLETE")
    print("=" * 60)