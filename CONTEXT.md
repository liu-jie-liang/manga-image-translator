# manga-image-translator 上下文词汇表

## 领域术语

### 翻译流水线
- **滑动窗口 (Sliding Window)**: 以固定窗口大小（N页）为一组翻译单位，窗口在页序列上滑动，每个窗口翻译一个prompt，取中间页的翻译结果作为最终译文。首尾窗口特殊处理以覆盖边界页。参见 ADR-0001。
- **全局 ID (Global ID)**: 跨页面的文本框统一编号，格式为 `<|N|>`，在滑动窗口中用于将翻译结果映射回源页面和文本框。
- **OCR 缓存**: 进入滑动窗口前对所有页面预执行的 OCR，结果缓存以避免窗口滑动重复执行 OCR。
- **上下文拼接 (Context Assembly)**: 将前几页已翻译文本拼接为当前翻译的上文提示。现有实现通过 `_build_prev_context` 和 `--context-size` 控制。

### 翻译器
- **SakuraTranslator**: API 版 Sakura 翻译器（`translators/sakura.py`），通过 OpenAI 兼容 API 调用远程 Sakura 模型（如 Ollama 部署的 sakura-14b），内置日→中轻小说风格专用 prompt。通过 `SAKURA_API_BASE`、`SAKURA_MODEL`、`SAKURA_VERSION` 环境变量配置。
- **SakuraLocalTranslator**: 本地 GGUF 版 Sakura 翻译器（`translators/sakura_local.py`，新增），通过 `llama-cpp-python` 直连 GPU(MPS) 运行本地 GGUF 量化模型。模型常驻显存单例复用，消除 HTTP 往返延迟。通过 `SAKURA_GGUF_PATH` 环境变量指向 `.gguf` 文件路径。参见 ADR-0004。
- **方式A (Ollama HTTP)** / **方式B (本地 GGUF 直连)**：两种翻译后端选择策略。`SAKURA_GGUF_PATH` 未设置时走方式A（Ollama API，向后兼容），设置后自动切换方式B（本地 GGUF 直连 GPU）。两种方式共用相同的 Prompt 模板和输出解析逻辑。
- **SugoiTranslator**: 本地 Sugoi 翻译器（`translators/sugoi.py`），基于 ctranslate2 在本地运行 m2m100/jparacrawl 模型。**不支持 MPS**。当 `--use-gpu` 时 ctranslate2 收到 `device='mps'` 会崩溃（`ValueError: unsupported device mps`）。
- **调度翻译 (Dispatch Translation)**: 将文本列表分发给翻译器的统一入口，位于 `translators/__init__.py`。
- **两层翻译 (Two-Stage Translation)**: ChatGPT2Stage翻译器先做初步翻译，再结合上下文做润色。
- **翻译器选择策略**: `--use-gpu` 不能用于 sakura/sugoi 翻译器。正确策略是 `--use-gpu-limited`：Detection/OCR/Inpainting → MPS，翻译 → CPU（或 Ollama 网络）。

### 模型设备
- **MPS (Metal Performance Shaders)**: Apple Silicon Mac 的 GPU 后端，PyTorch 通过 `torch.backends.mps.is_available()` 检测。
- **统一内存 (Unified Memory)**: Apple Silicon 架构下 CPU 和 GPU 共享同一物理内存池，模型加载时不需要显式的设备间数据拷贝。
- **llama-cpp-python**: GGUF 模型推理库，原生支持 Apple Silicon Metal(MPS) 加速，通过 `n_gpu_layers=-1` 将全部模型层加载到 GPU。
- **GGUF**: 量化模型格式，sakura-14b 使用 Q4_K_M 量化（4.6 bit/参数），文件大小约 8.5GB。
- **ctranslate2 MPS 限制**: ctranslate2 库不支持 Apple MPS 设备。使用 SugoiTranslator（本地 sugoi/m2m100）时翻译必须在 CPU 上运行。
- **num_gpu (Ollama)**: Ollama 中控制将模型层加载到 GPU 的参数，999 表示所有层都在 GPU。
- **Q4_K_M**: 4-bit KM 量化格式，将 16-bit 权重压缩到约 4.6 bit/参数，在速度与质量之间平衡。

### 渲染
- **文本框 (TextBlock)**: OCR 检测到的单个文字区域，包含多边形坐标、识别文本和翻译文本。
- **文本行合并 (Textline Merge)**: 将检测到的文本行按阅读顺序和空间位置合并为逻辑文本区块。

### 测试
- **TDD (Test-Driven Development)**: 测试驱动开发：红-绿-重构循环。先写测试（红），再实现代码（绿），最后重构改进。
- **Fixtures**: pytest 的测试数据提供机制，在 `test/fixtures/` 目录中定义模拟数据。

## 翻译流水线阶段耗时（实测）

硬件: Apple M4 Pro / 64GB / macOS，Ollama sakura-14b-qwen2.5-v1.0 @ 192.168.1.15:11434，use_gpu_limited。

### 157 页全量实测（第13话完整翻译）

| 阶段 | 总耗时 | 平均/页 | 占比 |
|------|--------|---------|------|
| Detection (文字检测) | 42.1s | 0.3s | 4% |
| OCR (文字识别) | 150.9s | 1.0s | 14% |
| **翻译 (Translation)** | **483.1s** | **3.2s** | **46%** |
| Inpainting (文字擦除) | 242.0s | 1.6s | 23% |
| 模型加载+渲染+IO | 142.8s | 0.9s | 13% |

**关键结论：**
- 总耗时：157页 → 1061s（**17.7 分钟**），平均 6.8s/页
- 翻译是**绝对瓶颈**（46%），所有翻译请求都要通过 Ollama API 网络往返，单页逐次推理，无法通过并发减少总推理时间（Ollama 单 GPU 串行处理）
- 稳定性：排除首次加载后，avg=6.7s  min=0.4s  max=23.1s  σ=3.0s  cv=0.45 → 轻度波动
- 推测：第13-23话（约440页）→ ~50 分钟

### 批量并发翻译优化结果

尝试 batch=50 并发=3：因为 Ollama 单 GPU 串行化处理，且大批次存在输出截断丢文本问题，实测加速比 **~1.0x**，翻译覆盖率降为 69%，**不推荐使用**。结论：保持逐页翻译是稳定基线。

### 方式A vs 方式B 性能实测对比（2026-06-10）

基准：5页相同漫画素材，同一台机器，use_gpu_limited（det/ocr/inpaint → MPS），仅翻译后端不同。

#### 5 页对比

| 指标 | 方式A (Ollama HTTP) | 方式B (本地 GGUF) | 差异 |
|------|---------------------|-------------------|------|
| 总耗时 | 31.7s | 31.0s | B 快 2% |
| 平均/页 | 6.3s | 6.2s | B 快 2% |
| 翻译阶段 | 13.1s (41.4%) | 12.5s (40.3%) | B 快 5% |
| Detection | 1.8s (5.7%) | 1.8s (5.7%) | 相同 |
| OCR | 3.9s (12.2%) | 3.9s (12.4%) | 相同 |
| Inpainting | 7.9s (24.8%) | 7.8s (25.2%) | 相同 |
| 模型首次加载 | 3.2s (含 det/ocr/inpaint) | 10.3s (GGUF to MPS) | B 慢（一次性） |
| 后续模型复用 | 0s (Ollama 常驻) | 0s (单例常驻显存) | 相同 |
| 稳定性 CV | 0.23 (稳定) | 0.21 (稳定) | 相当 |

#### 翻译质量

| 原文 | 方式A | 方式B |
|------|-------|-------|
| いや…この場合は以下と表現すべきか？ | 不对……这种情况下应该说『以下』吗？ | 不……这种情况应该用**以下犯上来形容**吧？ |

方式B（本地 GGUF）正确识别了日语惯用语「以下犯上」（匹夫之怒，以下犯上），方式A 将其误解为片假名「以下」。

#### 结论

- **5页规模**：两种方式性能几乎持平（31.7s vs 31.0s），翻译阶段差异 5% 在网络波动范围内。
- **模型加载**：GGUF 首次加载 10.3s（一次性），Ollama 随服务启动自动加载，页面翻译中感知不到。
- **翻译质量**：方式B 略优（正确识别惯用语）。
- **稳定性**：两者相当（CV 0.23 vs 0.21）。
- **预期大页数优势**：157页全量翻译时，方式A 翻译阶段耗时 483s（46%），若方式B 保持 5% 优势，预计节省 ~24s。实际可能更多，因为 GGUF 直连消除了 Ollama 内部 HTTP 解析/序列化开销。
- **真正优势场景**：当 Ollama 服务不可用或网络不稳定时，方式B 完全不依赖外部服务。
- **多批次并行的潜力**：方式B 通过 `llama-cpp-python` 的 `Llama.create_chat_completion` 直接调用，理论上可通过多个 `Llama` 实例（如 batch）实现并行推理，不受 Ollama 单 GPU 串行化限制。

## 项目架构

```
manga_translator/
├── manga_translator.py     # 核心翻译管道
├── sliding_window.py       # 滑动窗口翻译策略（新增）
├── mode/local.py           # 本地模式入口（批量处理图片）
├── translators/            # 翻译器实现
│   ├── common_gpt.py       # GPT 类翻译器基类
│   ├── custom_openai.py    # 自定义 OpenAI 兼容 API（Ollama 用此）
│   ├── chatgpt.py          # OpenAI ChatGPT 翻译器
│   ├── sakura.py           # Sakura API 翻译器（Ollama HTTP, 方式A）
│   ├── sakura_local.py     # Sakura 本地 GGUF 翻译器（llama-cpp-python + MPS, 方式B, 新增）
│   └── sugoi.py            # Sugoi 本地翻译器（ctranslate2，不支持 MPS）
├── detection/              # 文字检测
├── ocr/                    # OCR 识别
├── inpainting/             # 文字擦除
└── rendering/              # 译文渲染
```

## 迭代报告 (Iteration Report)

### Iteration 4: GGUF 本地直连 GPU 翻译（2026-06-10）

**目标**: 新增方式B（本地 GGUF 直连 GPU），对比方式A（Ollama HTTP），不降低质量的前提下提升速度/稳定性。

**已完成**:
- [x] ADR-0004: 本地 GGUF 直连 GPU 翻译架构决策
- [x] `translators/sakura_local.py`: 核心实现（单例、MPS、Prompt 一致）
- [x] `test/unit/test_sakura_local.py`: 16 个单元测试（env var 切换、单例、Prompt、解析、参数）全部通过
- [x] `translators/__init__.py`: 自动路由（`SAKURA_GGUF_PATH` 设置 → 方式B，否则 → 方式A）
- [x] `translators/keys.py`: 新增 `SAKURA_GGUF_PATH` 环境变量
- [x] `test/benchmark_sakura_local.py`: 5页实测，方式A vs 方式B 对比报告已写入上方

**实测结论**:
- 5页级：方式B 比方式A 总体快 2%，翻译阶段快 5%
- 质量：方式B 在惯用语识别上优于方式A
- 稳定性：两者相当
- 模型加载：GGUF 10.3s 一次性（单例常驻），Ollama 随服务启动自动加载

**文件清单**:
| 文件 | 状态 | 说明 |
|------|------|------|
| `manga_translator/translators/sakura_local.py` | 新增 | 核心实现（150行） |
| `test/unit/test_sakura_local.py` | 新增 | 16 单元测试 |
| `test/benchmark_sakura_local.py` | 新增 | A/B 对比 benchmark |
| `manga_translator/translators/keys.py` | 修改 | +1 env var |
| `manga_translator/translators/__init__.py` | 修改 | +2 行 import, 自动路由 |
| `docs/adr/0004-local-gguf-gpu-translation.md` | 新增 | 架构决策记录 |
| `CONTEXT.md` | 修改 | 术语 + 性能报告 |