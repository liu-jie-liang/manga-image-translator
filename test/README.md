## Tests

### Installation

```bash
pip install pytest pytest-asyncio
```

### Usage:

Run all unit tests
```bash
pytest test/unit/ -v
```

Run specific test file
```bash
pytest test/unit/test_batch_sort.py -v
```

### Test Structure

```
test/
├── unit/                          # 单元测试（全部 mock 外部依赖，数量详见 CONTEXT.md）
│   ├── test_batch.py              # 批量翻译编排层
│   ├── test_batch_ko.py           # 韩中批量翻译入口
│   ├── test_batch_progress.py     # 进度跟踪
│   ├── test_batch_sort.py         # 目录排序规则
│   ├── test_custom_openai.py      # GPT 基类翻译器
│   ├── test_empty_translation_progress.py  # 空翻译结果守卫
│   ├── test_galtransl_local.py    # Galtransl GGUF 翻译器
│   ├── test_local_norecurse.py    # 非递归图片扫描
│   ├── test_mode_local.py         # 核心翻译引擎层
│   ├── test_qwen3_kozh.py         # Qwen3 韩中翻译器
│   ├── test_sakura.py             # Sakura API 翻译器（方式A）
│   ├── test_sakura_local.py       # Sakura GGUF 翻译器（方式B）
│   ├── test_sliding_window.py     # 滑动窗口翻译策略
│   └── test_translator_fallback.py  # 翻译器降级链
├── e2e_gguf.py                    # 方式B E2E 测试
├── e2e_gguf_2img.py               # 方式B 场景化 E2E
├── e2e_galtransl.py               # 方式C E2E 测试
├── e2e_galtransl_2img.py          # 方式C 场景化 E2E
├── run_dual_benchmark.py          # 双翻译器 benchmark
├── benchmark_sakura_local.py      # Sakura 本地 benchmark
└── results/                       # benchmark 输出目录
```

To disable stdout capture add `-s --log-cli-level=DEBUG`
