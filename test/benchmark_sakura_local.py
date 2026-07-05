"""实测本地 GGUF (方式B) 翻译性能并对比 Ollama HTTP (方式A)

Usage:
    # 先跑方式A (Ollama HTTP)
    python test/benchmark.py 30

    # 再跑方式B (本地 GGUF 直连 GPU)
    SAKURA_GGUF_PATH=~/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf python test/benchmark_sakura_local.py 30
"""
import os, sys, time, asyncio, logging, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('MANGA_TRANSLATOR_SETTINGS', '{}')

# ============================================================================
# 方式B: 本地 GGUF 配置
# ============================================================================
DEFAULT_GGUF = os.path.expanduser('~/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf')
os.environ['SAKURA_GGUF_PATH'] = os.getenv('SAKURA_GGUF_PATH', DEFAULT_GGUF)
os.environ['SAKURA_MODEL'] = 'sakura-14b-qwen2.5-v1.0:latest'
os.environ['SAKURA_VERSION'] = '0.9'

from manga_translator.utils import init_logging, set_log_level
init_logging()
set_log_level(logging.WARNING)

# ============================================================================
class StageTimer:
    def __init__(self):
        self.data: dict[str, list[float]] = {}
    def add(self, n: str, d: float):
        self.data.setdefault(n, []).append(d)

timer = StageTimer()

# ============================================================================
# Monkey-patch: 为四个子阶段注入计时 (与 benchmark.py 完全一致)
# ============================================================================
import manga_translator.manga_translator as mt

_orig_detect = mt.MangaTranslator._run_detection
_orig_ocr = mt.MangaTranslator._run_ocr
_orig_trans = mt.MangaTranslator._run_text_translation
_orig_inpaint = mt.MangaTranslator._run_inpainting

async def _timed_detect(self, config, ctx):
    t = time.time()
    r = await _orig_detect(self, config, ctx)
    timer.add("Detection(文字检测)", time.time() - t)
    return r

async def _timed_ocr(self, config, ctx):
    t = time.time()
    r = await _orig_ocr(self, config, ctx)
    timer.add("OCR(文字识别)", time.time() - t)
    return r

async def _timed_trans(self, config, ctx):
    t = time.time()
    r = await _orig_trans(self, config, ctx)
    timer.add("翻译(Translation)", time.time() - t)
    return r

async def _timed_inpaint(self, config, ctx):
    t = time.time()
    r = await _orig_inpaint(self, config, ctx)
    timer.add("文字擦除(Inpainting)", time.time() - t)
    return r

mt.MangaTranslator._run_detection = _timed_detect
mt.MangaTranslator._run_ocr = _timed_ocr
mt.MangaTranslator._run_text_translation = _timed_trans
mt.MangaTranslator._run_inpainting = _timed_inpaint

# ============================================================================
async def main():
    from manga_translator.mode.local import MangaTranslatorLocal
    from manga_translator.translators.sakura_local import SakuraLocalTranslator

    image_dir = Path(__file__).resolve().parent.parent / "test/materials/chapter-13"
    n_images = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    images = sorted([p for p in image_dir.glob("*.jpg")])[:n_images]
    dest_dir = image_dir.parent / "c13-bench-local"

    shutil.rmtree(str(dest_dir), ignore_errors=True)
    dest_dir.mkdir(parents=True, exist_ok=True)

    gguf_path = os.environ['SAKURA_GGUF_PATH']
    print(f"测试规模: {n_images} 页")
    print(f"翻译器:   sakura_local (本地 GGUF + llama-cpp-python + MPS)")
    print(f"GGUF:     {gguf_path}")
    print(f"策略:     use_gpu_limited (det/ocr/inpaint→MPS, 翻译→本地GGUF/MPS)")
    print()

    # 预热: 加载模型到显存
    print("预热: 加载 GGUF 模型到 GPU ...", end=" ", flush=True)
    t_load = time.time()
    SakuraLocalTranslator.load_model(gguf_path)
    load_time = time.time() - t_load
    print(f"{load_time:.1f}s")

    params = {
        'use_gpu_limited': True,
        'translator': 'sakura',
        'config_file': 'config.json',
        'verbose': False,
        'ignore_errors': True,
        'format': 'png',
        'kernel_size': 3,
        'attempts': 0,
    }

    translator = MangaTranslatorLocal(params)
    page_times = []

    t_total = time.time()
    for i, img_path in enumerate(images):
        t_p = time.time()
        out_name = img_path.stem + '.png'
        out_path = str(dest_dir / out_name)
        print(f"  [{i+1}/{n_images}] {img_path.name} ...", end=" ", flush=True)
        await translator.translate_path(str(img_path), out_path, params)
        d = time.time() - t_p
        page_times.append(d)
        print(f"{d:.1f}s")

    total = time.time() - t_total

    # ============ 报告 ============
    print("\n" + "=" * 70)
    print("  翻译性能实测报告 (方式B: 本地 GGUF)")
    print("=" * 70)
    print(f"  硬件:     Apple M4 Pro / 64GB / macOS")
    print(f"  翻译器:   sakura_local (llama-cpp-python + MPS)")
    print(f"  GGUF:     {gguf_path}")
    print(f"  策略:     use_gpu_limited (det/ocr/inpaint→MPS, 翻译→本地GGUF/MPS)")
    print(f"  测试页:   {n_images} 页")
    print(f"  总耗时:   {total:.1f}s")
    print(f"  平均每页: {total/n_images:.1f}s")
    print(f"  模型加载: {load_time:.1f}s (一次性, 常驻显存)")

    # 首次页面
    first_page = page_times[0]
    other_avg = sum(page_times[1:]) / (n_images - 1) if n_images > 1 else 0
    print(f"  首次翻译: {first_page:.1f}s")
    if n_images > 1:
        print(f"  后续每页: {other_avg:.1f}s")

    # 分阶段
    print(f"\n  {'阶段':<30} {'总耗时':>8} {'占比':>8} {'平均':>10} {'次数':>5}")
    print("  " + "-" * 68)

    stage_order = [
        "Detection(文字检测)",
        "OCR(文字识别)",
        "翻译(Translation)",
        "文字擦除(Inpainting)",
    ]
    accounted = 0
    for name in stage_order:
        vals = timer.data.get(name, [])
        s = sum(vals)
        if s > 0:
            cnt = len(vals)
            avg = s / cnt
            pct = s / total * 100
            accounted += s
            print(f"  {name:<30} {s:>7.1f}s {pct:>7.1f}% {avg:>9.1f}s {cnt:>5}")

    remaining = total - accounted
    if remaining > 0.1:
        pct = remaining / total * 100
        print(f"  {'模型加载+渲染+IO':<30} {remaining:>7.1f}s {pct:>7.1f}%")

    # 瓶颈
    print(f"\n  {'瓶颈排序':─^65}")
    items = [(k, sum(v)) for k, v in timer.data.items() if v]
    items.append(("模型加载+渲染+IO", remaining))
    items.sort(key=lambda x: x[1], reverse=True)
    for i, (name, s) in enumerate(items):
        pct = s / total * 100
        bar = "█" * int(pct / 2)
        print(f"  {i+1}. {name:<28} {bar} {pct:.0f}% ({s:.1f}s)")

    # 稳定性
    if n_images >= 2:
        print(f"\n  {'稳定性分析':─^65}")
        pg = page_times[1:]
        avg_p = sum(pg) / len(pg)
        mn = min(pg)
        mx = max(pg)
        var = sum((t - avg_p) ** 2 for t in pg) / len(pg)
        cv = (var ** 0.5) / avg_p if avg_p > 0 else 0
        label = "稳定" if cv < 0.3 else "轻度波动" if cv < 0.5 else "不稳定"
        print(f"  排除首次加载后: avg={avg_p:.1f}s  min={mn:.1f}s  max={mx:.1f}s  σ={var**0.5:.1f}s  cv={cv:.2f} → {label}")

    print()


if __name__ == '__main__':
    asyncio.run(main())