# manga-image-translator 上下文词汇表

## 领域术语

### 翻译流水线
- **滑动窗口 (Sliding Window)**: 以固定窗口大小（N页）为一组翻译单位，窗口在页序列上滑动，每个窗口翻译一个prompt，取中间页的翻译结果作为最终译文。首尾窗口特殊处理以覆盖边界页。参见 ADR-0001。
- **全局 ID (Global ID)**: 跨页面的文本框统一编号，格式为 `<|N|>`，在滑动窗口中用于将翻译结果映射回源页面和文本框。
- **OCR 缓存**: 进入滑动窗口前对所有页面预执行的 OCR，结果缓存以避免窗口滑动重复执行 OCR。
- **上下文拼接 (Context Assembly)**: 将前几页已翻译文本拼接为当前翻译的上文提示。现有实现通过 `_build_prev_context` 和 `--context-size` 控制。

### 翻译器
- **调度翻译 (Dispatch Translation)**: 将文本列表分发给翻译器的统一入口，位于 `translators/__init__.py`。
- **两层翻译 (Two-Stage Translation)**: ChatGPT2Stage翻译器先做初步翻译，再结合上下文做润色。

### 模型设备
- **MPS (Metal Performance Shaders)**: Apple Silicon Mac 的 GPU 后端，PyTorch 通过 `torch.backends.mps.is_available()` 检测。
- **统一内存 (Unified Memory)**: Apple Silicon 架构下 CPU 和 GPU 共享同一物理内存池，模型加载时不需要显式的设备间数据拷贝。
- **num_gpu (Ollama)**: Ollama 中控制将模型层加载到 GPU 的参数，999 表示所有层都在 GPU。
- **Q4_K_M**: 4-bit KM 量化格式，将 16-bit 权重压缩到约 4.6 bit/参数，在速度与质量之间平衡。

### 渲染
- **文本框 (TextBlock)**: OCR 检测到的单个文字区域，包含多边形坐标、识别文本和翻译文本。
- **文本行合并 (Textline Merge)**: 将检测到的文本行按阅读顺序和空间位置合并为逻辑文本区块。

### 测试
- **TDD (Test-Driven Development)**: 测试驱动开发：红-绿-重构循环。先写测试（红），再实现代码（绿），最后重构改进。
- **Fixtures**: pytest 的测试数据提供机制，在 `test/fixtures/` 目录中定义模拟数据。

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
│   └── sakura.py           # Sakura 模型翻译器
├── detection/              # 文字检测
├── ocr/                    # OCR 识别
├── inpainting/             # 文字擦除
└── rendering/              # 译文渲染
```