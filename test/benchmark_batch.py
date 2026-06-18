"""批量翻译性能实测 (Iteration 5 后新执行链路)

测量：
  1. 模型加载时间
  2. 目录排序遍历开销
  3. 逐目录翻译阶段耗时（Detection/OCR/翻译/Inpainting）
  4. 进度 I/O 开销
  5. 总端到端时间

Usage:
    python test/benchmark_batch.py [n_pages_per_dir]

默认每个子目录取 3 页，共 4 个目录（根层 + 3 子目录）= 12 页
"""
import os, sys, time, asyncio, logging, shutil, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('MANGA_TRANSLATOR_SETTINGS', '{}')

# ============================================================================
# 方式A: Ollama HTTP 配置
# ============================================================================
os.environ['SAKURA_API_BASE'] = 'http://192.168.1.15:11434/v1'
os.environ['SAKURA_MODEL'] = 'sakura-14b-qwen2.5-v1.0:latest'
os.environ['SAKURA_VERSION'] = '0.9'
os.environ['USE_GPU_LIMITED'] = 'true'

from manga_translator.utils import init_logging, set_log_level
init_logging()
set_log_level(logging.WARNING)

# ============================================================================
class StageTimer:
    """收集各阶段耗时数据"""
    def __init__(self):
        self.data: dict[str, list[float]] = {}
    def add(self, name: str, duration: float):
        self.data.setdefault(name, []).append(duration)

timer = StageTimer()

# ============================================================================
# Monkey-patch: 为四个子阶段注入计时
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
def _fmt_time(seconds: float) -> str:
    if seconds >= 60:
        return f"{seconds/60:.1f} min ({seconds:.1f}s)"
    return f"{seconds:.1f}s"

def _stats(name: str) -> tuple:
    vals = timer.data.get(name, [])
    if not vals:
        return (0, 0, 0, 0, 0)
    return (sum(vals), sum(vals)/len(vals), min(vals), max(vals), len(vals))

# ============================================================================
async def main():
    from manga_translator.mode.local import MangaTranslatorLocal
    from manga_translator.batch import sort_subdirs

    materials = Path(__file__).resolve().parent / "materials"
    bench_root = materials / "batch-bench"

    # 清理之前的输出和进度
    out_dir = bench_root.parent / (bench_root.name + " 汉化")
    shutil.rmtree(str(out_dir), ignore_errors=True)
    for d in bench_root.rglob("*"):
        if d.is_dir():
            pf = d / ".translate_progress.json"
            if pf.exists():
                pf.unlink()

    n_per_dir = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print("=" * 72)
    print("批量翻译性能实测 — Iteration 5 新执行链路")
    print("=" * 72)
    print(f"翻译器:   sakura (Ollama HTTP @ 192.168.1.15:11434)")
    print(f"策略:     use_gpu_limited (det/ocr/inpaint → MPS, 翻译 → Ollama)")
    print(f"测试目录: {bench_root}")
    print(f"目录结构: 根层 + 3 子目录 (01/纯数字, 02a/数字+字母, b3/字母+数字)")
    print()

    # ---- 统计页面数 ----
    IMG_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff', '.gif'}
    dir_image_counts = {}
    total_pages = 0
    for d in sorted(bench_root.rglob("*")):
        if d.is_dir():
            files = sorted([f for f in d.iterdir() if f.suffix.lower() in IMG_EXTS
                           and f.name != '.translate_progress.json'])
            if n_per_dir and len(files) > n_per_dir:
                files = files[:n_per_dir]
            dir_image_counts[str(d)] = len(files)
            total_pages += sum(dir_image_counts.values())

    print(f"总页数:   {total_pages} 页 ({sum(1 for v in dir_image_counts.values() if v > 0)} 个目录)")
    for d, cnt in dir_image_counts.items():
        if cnt > 0:
            print(f"  {Path(d).name}/ → {cnt} 页")
    print()

    # ---- 阶段 1: 目录排序遍历 ----
    print("[1/3] 目录排序遍历开销 ...", end=" ", flush=True)
    t_sort = time.time()
    subdirs = [entry for entry in bench_root.iterdir() if entry.is_dir()]
    subdir_names = [e.name for e in subdirs]
    sorted_names = sort_subdirs(subdir_names)
    sorted_dirs = [str(bench_root / name) for name in sorted_names]
    sort_time = time.time() - t_sort
    print(f"{sort_time*1000:.1f}ms")
    print(f"  排序结果: {' → '.join(sorted_names)}")

    # ---- 阶段 2: 模型加载 ----
    print("\n[2/3] 加载翻译模型 ...", end=" ", flush=True)
    t_load = time.time()
    # MangaTranslatorLocal 需要的参数（防止 parse_init_params 中 key 缺失崩溃）
    translator_params = {
        'translator': 'sakura',
        'use_gpu_limited': True,
        'use_gpu': False,
        'source_lang': 'ja',
        'target_lang': 'zh-cn',
        'kernel_size': 5,
        'verbose': False,
        'use_mtpe': False,
        'font_path': None,
        'models_ttl': 0,
        'batch_size': 1,
        'ignore_errors': False,
        'model_dir': None,
        'input': [],
        'save_text': False,
        'load_text': False,
        'pre_dict': None,
        'post_dict': None,
        'disable_memory_optimization': False,
        'batch_concurrent': False,
        'prep_manual': False,
        'context_size': 0,
        'attempts': -1,
        'skip_no_text': False,
        'text_output_file': None,
        'save_quality': 95,
        'text_regions': None,
        'save_text_file': None,
    }
    local = MangaTranslatorLocal(translator_params)
    load_time = time.time() - t_load
    print(f"{_fmt_time(load_time)}")

    # ---- 阶段 3: 逐目录翻译 ----
    print("\n[3/3] 逐目录翻译 ...")
    total_start = time.time()
    dir_results = []

    # 先翻译根目录
    root_images = sorted([f for f in bench_root.iterdir() if f.suffix.lower() in
                         {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff', '.gif'}])
    if n_per_dir:
        root_images = root_images[:n_per_dir]

    if root_images:
        t_dir_start = time.time()
        timer_before = {k: len(v) for k, v in timer.data.items()}

        await local.translate_path(
            str(bench_root),
            dest=str(out_dir),
            params=dict(translator_params, retrans=False),
        )

        dir_time = time.time() - t_dir_start
        # 计算本目录新增的 stage 耗时
        stage_times = {}
        for stage_name in ["Detection(文字检测)", "OCR(文字识别)", "翻译(Translation)", "文字擦除(Inpainting)"]:
            new_count = len(timer.data.get(stage_name, [])) - timer_before.get(stage_name, 0)
            all_vals = timer.data.get(stage_name, [])
            if new_count > 0:
                stage_times[stage_name] = sum(all_vals[-new_count:])

        dir_results.append({
            'name': '(根目录)',
            'pages': len(root_images),
            'time': dir_time,
            'stages': stage_times,
        })
        print(f"  ✓ (根目录)  {len(root_images)} 页 → {_fmt_time(dir_time)}")

    # 翻译子目录
    for subdir in sorted_dirs:
        images = sorted([f for f in Path(subdir).iterdir() if f.suffix.lower() in
                        {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff', '.gif'}])
        if n_per_dir:
            images = images[:n_per_dir]
        if not images:
            continue

        t_dir_start = time.time()
        timer_before = {k: len(v) for k, v in timer.data.items()}

        await local.translate_path(
            subdir,
            dest=str(out_dir / Path(subdir).name),
            params=dict(translator_params, retrans=False),
        )

        dir_time = time.time() - t_dir_start
        stage_times = {}
        for stage_name in ["Detection(文字检测)", "OCR(文字识别)", "翻译(Translation)", "文字擦除(Inpainting)"]:
            new_count = len(timer.data.get(stage_name, [])) - timer_before.get(stage_name, 0)
            all_vals = timer.data.get(stage_name, [])
            if new_count > 0:
                stage_times[stage_name] = sum(all_vals[-new_count:])

        dir_results.append({
            'name': Path(subdir).name,
            'pages': len(images),
            'time': dir_time,
            'stages': stage_times,
        })
        print(f"  ✓ {Path(subdir).name:8s}  {len(images)} 页 → {_fmt_time(dir_time)}")

    total_time = time.time() - total_start

    # ---- 总览 ----
    total_pages_translated = sum(r['pages'] for r in dir_results)
    print(f"\n{'='*72}")
    print(f"实测结果汇总")
    print(f"{'='*72}")
    print(f"总页数:      {total_pages_translated} 页")
    print(f"总目录数:    {len(dir_results)} 个")
    print(f"模型加载:    {_fmt_time(load_time)}")
    print(f"排序遍历:    {sort_time*1000:.1f}ms")
    print(f"逐目录翻译:  {_fmt_time(total_time)}")
    print(f"总耗时:      {_fmt_time(load_time + total_time)}")
    if total_pages_translated > 0:
        print(f"平均每页:    {total_time/total_pages_translated:.1f}s")

    # ---- 分目录明细 ----
    print(f"\n{'─'*72}")
    print(f"分目录耗时明细")
    print(f"{'─'*72}")
    print(f"{'目录':<12} {'页数':>4} {'总耗时':>10} {'平均/页':>8}")
    print(f"{'─'*12} {'─'*4} {'─'*10} {'─'*8}")
    for r in dir_results:
        avg = r['time']/r['pages'] if r['pages'] > 0 else 0
        print(f"{r['name']:<12} {r['pages']:>4} {_fmt_time(r['time']):>10} {f'{avg:.1f}s':>8}")

    # ---- 阶段级分析 ----
    print(f"\n{'─'*72}")
    print(f"阶段级耗时分析（全部页面汇总）")
    print(f"{'─'*72}")
    stage_names = ["Detection(文字检测)", "OCR(文字识别)", "翻译(Translation)", "文字擦除(Inpainting)"]
    print(f"{'阶段':<22} {'总耗时':>10} {'平均/页':>8} {'占比':>6} {'最慢':>8} {'最快':>8}")
    print(f"{'─'*22} {'─'*10} {'─'*8} {'─'*6} {'─'*8} {'─'*8}")

    stage_total_time = sum(_stats(s)[0] for s in stage_names)
    for s in stage_names:
        total, avg, mn, mx, _ = _stats(s)
        pct = total / stage_total_time * 100 if stage_total_time > 0 else 0
        print(f"{s:<22} {_fmt_time(total):>10} {f'{avg:.1f}s':>8} {f'{pct:.1f}%':>6} {f'{mx:.1f}s':>8} {f'{mn:.1f}s':>8}")

    # ---- 进度 I/O 开销 ----
    progress_files = list(bench_root.rglob(".translate_progress.json"))
    print(f"\n{'─'*72}")
    print(f"进度 I/O")
    print(f"{'─'*72}")
    print(f"进度文件数:  {len(progress_files)} 个")
    for pf in progress_files:
        size = pf.stat().st_size
        with open(pf) as f:
            data = json.load(f)
        print(f"  {pf.relative_to(bench_root)}  → {len(data.get('completed',[]))} 条记录, {size} bytes")

    # ---- 清理 ----
    shutil.rmtree(str(out_dir), ignore_errors=True)
    for pf in progress_files:
        pf.unlink()

    print(f"\n✓ 实测完成，已清理输出目录和进度文件")
    return {
        'total_pages': total_pages_translated,
        'total_dirs': len(dir_results),
        'load_time': load_time,
        'sort_time': sort_time,
        'translate_time': total_time,
        'total_time': load_time + total_time,
        'dir_results': dir_results,
        'stage_data': {s: dict(zip(['total','avg','min','max','count'], _stats(s))) for s in stage_names},
    }


if __name__ == '__main__':
    asyncio.run(main())