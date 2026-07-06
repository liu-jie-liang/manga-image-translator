# 项目上下文与文档维护指南

## 文档维护原则

以下原则约束本项目所有文档（markdown）的创建和修改。违反任一原则视为重构缺陷。

### 原则 1：内容不丢失
旧文档中的每一条信息，要么保留原处，要么迁移到新位置。绝不静默删除。Git 历史可找回不是删除的借口——读者不应依赖 `git log` 来获取被删内容。

- 删除前确认：目标位置已接收迁移内容
- 禁止的行为：从文件 A 删除一节，但未在文件 B 中新增对应内容
- 例外：纯代码层描述（如逐用例测试细节）经确认后可丢弃

### 原则 2：准确性不降级
迁移过程中，事实性数据（数字、路径、引用）不能变错。

- 数字（测试用例数、性能数据、行数）修改后须逐条手工验证
- 文件路径修改后须确认目标文件存在
- ADR 状态、标识符等需同步更新

### 原则 3：单一真相源
同一份信息只在一个权威位置维护。其他地方用链接引用，不复制。

- 测试用例数 → CONTEXT.md 为唯一源，其他文件链接引用
- 迭代历史 → 迭代报告为唯一源，CONTEXT.md 只保留一句话+链接
- 性能数据 → 性能实测报告为唯一源
- 禁止多文件各自维护相同的表格或数字

### 原则 4：链接不失效
所有跨文件引用在修改后必须验证可访问。

- 文件重命名时：现状文件中的引用全部更新，历史变更日志中的旧文件名保留（记录的是当时的状态）
- 文件删除时：检查全项目引用，更新或删除所有指向它的链接
- 新增文件时：确认引用它的文件已添加链接

### 原则 5：最小变更
只改需要改的，不动不需要动的。每次修改有明确目的。

- 不过度重构：不为了"统一风格"而重写已有正确内容
- 不引入无关改动：修一个数字时不同时改周边的措辞
- 不新增冗余文件：能在已有文件里加的就不新建文件

### 原则 6：结构清晰
重构后的文档组织应比原来更易导航、更易维护。

- 同类文档格式统一（如两份迭代报告的迭代摘要格式一致）
- 文件名与内部标题一致
- 文档职责分明：操作指南 vs 迭代报告 vs 性能实测 vs 变更日志，不交叉

## 文档维护细则

以下细则约束本项目各类文档的具体操作规则，与上节通用原则配合使用。

### CHANGELOG (`CHANGELOG_CN.md`)
- **来源**：从迭代报告提取精华
- **时机**：每次迭代完成后追加，倒序排列（最新日期在最前）
- **规则**：每日期 1-2 条核心变更；不独立维护数据，细节在迭代报告中查；不补充旧项目（2021-2023）历史条目

### 迭代报告 (`docs/日中翻译-迭代报告.md`, `docs/韩中翻译-迭代报告.md`)
- **来源**：开发过程中记录（TDD 过程、问题定位、架构决策）
- **时机**：每次迭代完成后追加
- **规则**：Iteration N 倒序排列（最新在前）；统一格式：摘要表 → 问题定位过程；新增/修改文件集中在独立章节（按迭代分组）

### 性能实测报告 (`docs/日中翻译-性能实测报告.md`, `docs/韩中翻译-性能实测报告.md`)
- **来源**：benchmark 实测
- **时机**：每次 benchmark 后更新
- **规则**：必须包含测试环境（日期/设备/后端/图片规格）+ 数据表格 + 结论；追加不覆盖历史数据；原始 benchmark 数据（JSON/CSV）保留在 `test/results/` 但不入库

### 开发者技术指南 (`docs/日中翻译-开发者技术指南.md`, `docs/韩中翻译-开发者技术指南.md`)
- **来源**：架构、环境配置、工作流
- **时机**：随代码变更更新
- **规则**：描述当前状态（非历史记录）；所有环境变量、文件路径、Shell 命令必须可执行（读者复制粘贴即用）；不记录过时的环境变量名或废弃功能

### ADR (`docs/adr/*.md`)
- **来源**：架构决策
- **时机**：决策变更时更新状态
- **规则**：不可删除已采纳的 ADR；状态流转：已提案 → 已实现 → 已废弃

## 领域术语

### 翻译流水线
- **滑动窗口 (Sliding Window)**: 以固定窗口大小（N页）为一组翻译单位，窗口在页序列上滑动，每个窗口翻译一个prompt，取中间页的翻译结果作为最终译文。首尾窗口特殊处理以覆盖边界页。参见 ADR-0001。
- **全局 ID (Global ID)**: 跨页面的文本框统一编号，格式为 `<|N|>`，在滑动窗口中用于将翻译结果映射回源页面和文本框。
- **OCR 缓存**: 进入滑动窗口前对所有页面预执行的 OCR，结果缓存以避免窗口滑动重复执行 OCR。
- **上下文拼接 (Context Assembly)**: 将前几页已翻译文本拼接为当前翻译的上文提示。现有实现通过 `_build_prev_context` 和 `--context-size` 控制。

### 翻译器
- **SakuraTranslator**: API 版 Sakura 翻译器（`translators/sakura.py`），通过 OpenAI 兼容 API 调用远程 Sakura 模型（如 Ollama 部署的 sakura-14b），内置日→中轻小说风格专用 prompt。通过 `SAKURA_API_BASE`、`SAKURA_MODEL`、`SAKURA_VERSION` 环境变量配置。
- **SakuraLocalTranslator**: 本地 GGUF 版 Sakura 翻译器（`translators/sakura_local.py`），通过 `llama-cpp-python` 直连 GPU(MPS) 运行本地 GGUF 量化模型。模型常驻显存单例复用，消除 HTTP 往返延迟。通过 `SAKURA_GGUF_PATH` 环境变量指向 `.gguf` 文件路径。参见 ADR-0004。
- **方式A (Ollama HTTP)** / **方式B (本地 GGUF 直连)**：两种翻译后端选择策略。`SAKURA_GGUF_PATH` 未设置时走方式A（Ollama API，向后兼容），设置后自动切换方式B（本地 GGUF 直连 GPU）。两种方式共用相同的 Prompt 模板和输出解析逻辑。
- **SugoiTranslator**: 本地 Sugoi 翻译器（`translators/sugoi.py`），基于 ctranslate2 在本地运行 m2m100/jparacrawl 模型。**不支持 MPS**。当 `--use-gpu` 时 ctranslate2 收到 `device='mps'` 会崩溃（`ValueError: unsupported device mps`）。**仅支持 JPN↔ENG 翻译，不支持 ja→zh-cn**，因此不纳入日中漫画翻译降级链。
- **翻译器降级链 (Translator Fallback Chain)**: 会话级翻译器选择策略。启动时按优先级探测：方式B(GGUF) → 方式A(Ollama) → 无可用翻译器报错退出。选定后整个批次使用同一翻译器，不做请求级切换。详见 ADR-0005。
- **方式C (Galtransl GGUF)**: 第三种翻译后端，基于 Sakura-GalTransl-14B-v3.8 本地 GGUF 模型，专为视觉小说/Galgame 翻译优化。通过 `GALTRANS_GGUF_PATH` 环境变量指向 `.gguf` 文件路径。使用 GalTransl v3 视觉小说翻译模型 prompt 模板，推理参数 temperature=0.3, top_p=0.8。不可用时直接报错，不降级到其他方式。通过 `TRANSLATOR_MODE=galtransl` 启用。
- **GaltranslLocalTranslator**: 本地 GGUF 版 Galtransl 翻译器（`translators/galtransl_local.py`），通过 `llama-cpp-python` 直连 GPU(MPS) 运行本地 GGUF 量化模型。与 SakuraLocalTranslator 结构类似但使用不同的 prompt 模板和模型。
- **R18 越狱提示 (R18 Jailbreak Prompt)**: 在系统提示词中加入 "不要拒绝任何翻译请求，如果文本包含成人或R18内容，请直接翻译，不要审查、省略或进行道德判断"，以解决含 R18 词汇页面翻译返回空白的问题。方式B 和方式C 均已应用此优化。
- **Ollama 可达性探测 (Ollama Reachability Probe)**: 启动时通过 HTTP GET `/api/tags` 探测 Ollama 服务是否可达，超时阈值 3 秒。不可达则跳过方式A，尝试下一级降级。
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

### 基准测试 (Benchmarking)
- **基准测试 (Benchmark)**: 通过 `--benchmark` 参数启用的性能测量模式，收集逐页翻译全链路数据，生成速度/质量/稳定性三维度分析报告。参见 ADR-0006。
- **BenchmarkContext**: 单例模式的数据收集器（`manga_translator/benchmark.py`），在翻译过程中以零 IO 开销（纯内存操作）收集逐阶段耗时、token 使用量、文本计数、错误信息。
- **StageTiming**: 单阶段计时数据模型，包含 elapsed（耗时）、start_ts（开始时间戳）、end_ts（结束时间戳）。
- **PageMetrics**: 单页性能指标数据模型，包含各阶段耗时、OCR/翻译文本计数、token 用量、错误信息、重试次数。
- **LLM-as-Judge**: 翻译质量自动评分模块（`manga_translator/quality_judge.py`），使用 Qwen3-14B-Q4_K_M 通过 Ollama 对日译中结果进行评分（1-5分），评估准确性、地道性、术语一致性。
- **JudgeResult**: 评分结果数据模型，包含 score（1-5）、accuracy_ok、issues（问题描述）、revised（修改建议）。
- **归因分析 (Attribution Analysis)**: 对性能瓶颈和不稳定因素的根因分析，在报告中自动标注占比最大的阶段和异常值。
- **异常值检测 (Outlier Detection)**: 使用 2σ 阈值检测翻译耗时异常偏高的页面，定位性能波动来源。
- **报告生成器 (Report Generator)**: `manga_translator/report_generator.py`，将 BenchmarkContext 收集的数据生成 Markdown 报告（含速度/质量/稳定性/归因/优化建议）、JSON 原始数据、CSV 逐页明细。
- **报告路径**: `test/results/benchmark/{modeA\|modeB}/YYYYMMDD-HHMMSS.{md\|json\|csv}`，其中 modeA 为 Ollama HTTP 方式，modeB 为本地 GGUF 方式。

### 批量翻译
- **批量翻译 (Batch Translate)**: 脚本驱动的日中漫画批量翻译模式，`batch.py` 管理模型生命周期（加载一次→逐目录翻译→卸载），按目录层级遍历，逐层翻译。
- **目录排序规则 (Directory Sorting)**: 子目录按命名模式排序：纯数字（数值从小到大）→ 数字+字母（数字从小到大，字母字母序）→ 字母+数字（字母字母序，数字从小到大）→ 纯字母（视作字母+数字0）→ 其他（自然排序）。
- **进度文件 (Progress File)**: 每个目录下的 `.translate_progress.json`，记录已翻译完成的图片文件名，支持中断续传。`--retrans` 参数可清空所有进度文件重新翻译。
- **非递归扫描 (Non-recursive Scan)**: `_get_image_files()` 只扫描当前目录的图片文件，跳过子目录、非图片文件和进度文件。翻译范围由 `batch.py` 按目录层级控制。
- **模型生命周期 (Model Lifecycle)**: `batch.py` 负责模型的加载和卸载，`manga_translator.py` 不再自动加载模型。模型加载一次后，逐目录翻译，全部完成后卸载。
- **批量日中翻译-sakura-qwen3.command**: macOS Finder 双击启动脚本（降级方式），位于 `start-scripts/macos/`，固定使用 `TRANSLATOR_MODE=degraded`，先探测 Sakura Qwen3 GGUF（方式B），不可用时降级到 Ollama HTTP（方式A）。仅含 `SAKURA_GGUF_PATH`、`SAKURA_API_BASE`、`SAKURA_MODEL` 三个环境变量。
- **批量日中翻译-sakura-galtrans.command**: macOS Finder 双击启动脚本（方式C），位于 `start-scripts/macos/`，固定使用 `TRANSLATOR_MODE=galtransl`，直接使用 Galtransl GGUF 模型，不可用时报错不降级。仅含 `GALTRANS_GGUF_PATH` 一个环境变量。
- **批量日中翻译-sakura-galtrans-全量翻译.command**: macOS Finder 双击启动脚本（方式C 全量重译），位于 `start-scripts/macos/`，基于 `批量日中翻译-sakura-galtrans.command` 增加 `RETRANS=true` 和 `BENCHMARK=false`，固定全量重新翻译、不启用基准测试，仅需用户输入目录并确认开始。

## 翻译流水线阶段耗时（实测）

硬件: Apple M4 Pro / 64GB / macOS，Ollama sakura-14b-qwen2.5-v1.0 @ localhost:11434，use_gpu_limited。

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

基准：157页相同漫画素材（第13话），同一台机器 Apple M4 Pro / 64GB / macOS，use_gpu_limited（det/ocr/inpaint → MPS），仅翻译后端不同。

#### 157 页全量对比

| 阶段 | 方式A (Ollama HTTP) | 方式B (本地 GGUF) | 差值 | B vs A |
|------|---------------------|-------------------|------|--------|
| **总耗时** | **1061.5s** (17.7 min) | **988.8s** (16.5 min) | **-72.7s** | **快 6.8%** |
| **平均每页** | **6.8s** | **6.3s** | **-0.5s** | **快 7.4%** |
| Detection (文字检测) | 42.1s (4.0%) | 42.2s (4.3%) | +0.1s | 相同 |
| OCR (文字识别) | 150.9s (14.2%) | 156.2s (15.8%) | +5.3s | 慢 3.5% |
| **翻译 (Translation)** | **483.1s (45.5%)** | **407.0s (41.2%)** | **-76.1s** | **快 15.8%** |
| Inpainting (文字擦除) | 242.0s (22.8%) | 241.6s (24.4%) | -0.4s | 相同 |
| 模型加载+渲染+IO | 142.8s (13.5%) | 141.7s (14.3%) | -1.1s | 相同 |

#### 翻译阶段逐页分析

| 指标 | 方式A (Ollama) | 方式B (GGUF) | 差异 |
|------|---------------|-------------|------|
| 翻译总耗时 | 483.1s | 407.0s | B 快 76.1s |
| 平均每页翻译 | 3.2s | 2.7s | B 快 0.5s (15.6%) |
| 最快单页 | ~0.1s (无文字) | ~0.1s (无文字) | 相同 |
| 最慢单页 | ~13s (多文字页) | ~10s (多文字页) | B 快 ~23% |

**模式分析**：方式A 翻译耗时普遍为 2-4s/页，偶发 8-13s 抖动（网络波动+Ollama 内部排队）。方式B 稳定在 1.5-3s/页，最长 10s（多文字页），无明显随机抖动。方式B 消除了 HTTP 往返和 Ollama 内部序列化开销，每页节省约 0.5s。

#### 各阶段详析

**Detection / Inpainting / 渲染+IO**：两种方式完全一致（共用代码路径，测不出区别）。

**OCR**：方式B 比方式A 多 5.3s (3.5%)，属正常波动（OCR 结果受进程调度影响，每次运行略有差异）。

**翻译**：方式B **显著优于**方式A（快 15.8%），原因：
1. 消除 HTTP 往返延迟（每页约 0.3s）
2. 消除 Ollama 内部 JSON 序列化/反序列化（每页约 0.2s）
3. `llama-cpp-python` 直接调用 `create_chat_completion`，无中间层

#### 稳定性对比

| 指标 | 方式A | 方式B | 评价 |
|------|-------|-------|------|
| CV (变异系数) | **0.45** | **0.31** | B 更稳定 |
| 方差 σ | 3.0s | 2.0s | B 波动更小 |
| 异常慢页 (>8s) | 15 页 | 8 页 | B 大幅减少 |
| 判定 | 轻度波动 | 轻度波动 | B 边界更优 |

**根因**：方式A 的波动主要来自网络延迟和 Ollama HTTP 服务的偶发排队。方式B 全程本地推理，波动仅来自页内文字量差异（多文字页自然更慢），无外部不确定因素。

#### 翻译质量对比

| 原文 | 方式A | 方式B |
|------|-------|-------|
| いや…この場合は以下と表現すべきか？ | 不应该说『以下』吗？ | 应该用**以下犯上**来形容吧？ |

方式B 正确识别了日语惯用语「以下犯上」（匹夫之怒，以下犯上），方式A 将其误解为片假名「以下」。整体翻译质量两者接近，方式B 在惯用语识别上略优。

#### 综合结论

| 维度 | 胜出 | 说明 |
|------|------|------|
| **速度** | **方式B** | 翻译阶段快 15.8%，总耗时快 6.8%，每页省 0.5s |
| **稳定性** | **方式B** | CV 0.31 vs 0.45，异常慢页减半 |
| **质量** | **方式B** (略优) | 惯用语识别更准确 |
| **首次启动** | 方式A | GGUF 需加载 10s，Ollama 随系统启动 |
| **部署复杂度** | 方式A | 无需额外安装 llama-cpp-python |
| **独立性** | **方式B** | 不依赖 Ollama 服务，离线可用 |
| **多批次并行潜力** | **方式B** | llama-cpp-python 无 Ollama 单 GPU 串行限制 |

**推荐**：生产环境优先使用方式B（本地 GGUF），速度和稳定性均有可测量优势。方式A 作为后备方案保留。通过 `SAKURA_GGUF_PATH` 环境变量一键切换。

### 降级链 E2E 验证（2026-06-11）

使用30页测试集验证翻译器降级链自动选择逻辑。

| 模式 | 总耗时 | 平均/页 | 成功率 | 降级链 |
|------|--------|---------|--------|--------|
| 方式B (GGUF) | 223.7s (3.7 min) | 7.5s | 30/30 | GGUF 优先命中 |
| 方式A (Ollama) | 232.9s (3.9 min) | 7.8s | 30/30 | GGUF 缺失 → Ollama 降级 |

**降级链验证**：设置 `SAKURA_GGUF_PATH` 时自动选择方式B；取消设置时自动降级到方式A。两种方式均 100% 完成翻译。性能差异约 4%（9.2s），主要来自网络往返开销。

### 158页 E2E 实测对比（2026-06-12）

使用 158 页测试集（`test/e2e-materials/`），同一台机器 Apple M4 Pro / 64GB / macOS，use_gpu_limited，分别以方式A和方式B运行完整翻译流水线。

#### 总体对比

| 指标 | 方式B (GGUF) | 方式A (Ollama) | 差值 | B vs A |
|------|-------------|---------------|------|--------|
| **总耗时** | **973.9s** (16.2 min) | **965.4s** (16.1 min) | **+8.5s** | **慢 0.9%** |
| **平均每页** | **6.2s** | **6.1s** | **+0.1s** | **慢 1.6%** |
| 翻译成功率 | 158/158 (100%) | 158/158 (100%) | 相同 | 相同 |

#### 分析

本次 158 页测试中，方式A（Ollama）反而略快于方式B（GGUF），差异仅 8.5s（0.9%），在测量误差范围内。与之前 157 页（第13话）测试中方式B 快 6.8% 的结论不同，原因分析：

1. **素材差异**：本次 e2e-materials 的 158 张图片与第13话的 157 页漫画不同，图片特征（文字量、分辨率）影响各阶段耗时分布
2. **网络环境**：测试时 Ollama 服务（localhost）网络状况良好，HTTP 往返延迟极低
3. **GGUF 加载开销**：方式B 首次加载 8.4GB GGUF 模型到 MPS 约需 10s，计入总耗时
4. **差异极小**：8.5s 差异（0.9%）远小于正常波动范围，**两种方式在实际使用中速度基本持平**

#### 稳定性

两种方式均 158/158 全部翻译成功，无崩溃、无超时、无输出截断。降级链逻辑验证通过。

#### 综合结论（更新）

| 维度 | 胜出 | 说明 |
|------|------|------|
| **速度** | **持平** | 差异 <1%，在测量误差范围内 |
| **稳定性** | **持平** | 双方均 100% 成功率 |
| **质量** | **持平** | 共用相同模型和 Prompt 模板 |
| **首次启动** | 方式A | GGUF 需加载 10s，Ollama 随系统启动 |
| **部署复杂度** | 方式A | 无需额外安装 llama-cpp-python |
| **独立性** | **方式B** | 不依赖 Ollama 服务，离线可用 |

**推荐**：日常使用两种方式均可，速度差异可忽略。需要离线或 Ollama 服务不可用时使用方式B（GGUF），追求部署简便时使用方式A（Ollama）。通过 `SAKURA_GGUF_PATH` 环境变量一键切换。

## 项目架构

```
manga_translator/
├── batch.py                # 日中批量翻译入口（A+）：模型生命周期 + 目录遍历 + 交互式入口
├── batch_ko.py             # 韩中批量翻译入口：模型生命周期 + 目录遍历 + 交互式入口
├── batch_common.py         # 批量翻译公共模块：目录排序、图片扫描、进度管理
├── manga_translator.py     # 核心翻译管道（A）：逐页翻译 + 滑动窗口
├── sliding_window.py       # 滑动窗口翻译策略
├── mode/local.py           # 本地模式入口（B）：非递归扫描 + 进度跟踪 + 图片→翻译
├── translators/            # 翻译器实现
│   ├── common_gpt.py       # GPT 类翻译器基类
│   ├── custom_openai.py    # 自定义 OpenAI 兼容 API（Ollama 用此）
│   ├── chatgpt.py          # OpenAI ChatGPT 翻译器
│   ├── sakura.py           # Sakura API 翻译器（Ollama HTTP, 方式A）
│   ├── sakura_local.py     # Sakura 本地 GGUF 翻译器（llama-cpp-python + MPS, 方式B）
│   ├── galtransl_local.py  # Galtransl 本地 GGUF 翻译器（方式C）
│   ├── qwen3_kozh.py       # Qwen3 韩中翻译器（Ollama 原生 /api/chat）
│   └── sugoi.py            # Sugoi 本地翻译器（ctranslate2，不支持 MPS）
├── detection/              # 文字检测
├── ocr/                    # OCR 识别
├── inpainting/             # 文字擦除
└── rendering/              # 译文渲染

test/
├── unit/                   # 单元测试（218 tests, 全部 mock 外部依赖）
│   ├── test_batch.py       # 批量翻译编排层
│   ├── test_batch_ko.py    # 韩中批量翻译入口
│   ├── test_batch_progress.py  # 进度跟踪
│   ├── test_batch_sort.py  # 目录排序规则
│   ├── test_custom_openai.py   # GPT 基类翻译器
│   ├── test_empty_translation_progress.py  # 空翻译结果守卫
│   ├── test_galtransl_local.py    # Galtransl GGUF 翻译器
│   ├── test_local_norecurse.py    # 非递归图片扫描
│   ├── test_mode_local.py         # 核心翻译引擎层
│   ├── test_qwen3_kozh.py         # Qwen3 韩中翻译器
│   ├── test_sakura.py             # Sakura API 翻译器
│   ├── test_sakura_local.py       # Sakura GGUF 翻译器
│   ├── test_sliding_window.py     # 滑动窗口翻译策略
│   └── test_translator_fallback.py  # 翻译器降级链
```

**调用链路**：

```
start-scripts/macos/批量日中翻译.command  (macOS Finder 双击启动)
    │
    ▼
manga_translator/batch.py  (A+: 编排层)
    │  ┌─ 模型加载（一次性，整个翻译周期）
    │  ├─ 扫描目录 → sort_subdirs() 排序
    │  └─ 逐层翻译：
    │       ├─ translate_path(dir_a) ──→ mode/local.py (B)
    │       │     ├─ _get_image_files()  只扫描当前层级图片
    │       │     ├─ _load_progress()    跳过已翻译图片
    │       │     ├─ translate_file() ──→ manga_translator.py (A)
    │       │     └─ _save_progress()    每页记录进度
    │       ├─ translate_path(dir_a/01)
    │       ├─ translate_path(dir_a/02)
    │       └─ ...
    └─ 模型卸载
```

**三层职责划分**：
| 层 | 文件 | 职责 |
|----|------|------|
| A+ (编排层) | `batch.py` | 模型生命周期、目录排序与遍历、交互式入口 |
| B (翻译组层) | `mode/local.py` | 单目录图片扫描、进度跟踪、逐页翻译调度 |
| A (单页层) | `manga_translator.py` | 单页翻译流水线（detection → OCR → 翻译 → inpainting） |

## 操作指南

### 环境准备

```bash
# 方式A：Ollama HTTP（默认，需要远程 Ollama 服务）
export SAKURA_API_BASE='http://localhost:11434/v1'
export SAKURA_MODEL='sakura-14b-qwen2.5-v1.0'

# 方式B：本地 GGUF 直连 GPU（推荐，离线可用）
export SAKURA_GGUF_PATH='/path/to/sakura-14b-qwen2.5-v1.0-Q4_K_M.gguf'

# 通用配置
export USE_GPU_LIMITED='true'  # Detection/OCR/Inpainting → MPS, 翻译 → CPU/Ollama
```

### 使用方式一：Finder 双击启动（macOS 推荐）

提供 6 个脚本，按需选择：

| 脚本 | 翻译器 | 特点 |
|------|--------|------|
| `start-scripts/macos/批量日中翻译.command` | 交互选择 | 启动后选 Sakura Qwen2.5 (B→A) 或 Galtransl (C) |
| `start-scripts/macos/批量日中翻译-sakura-qwen3.command` | Sakura-14B-Qwen2.5 (方式B→A 降级) | GGUF 直连优先，Ollama 兜底 |
| `start-scripts/macos/批量日中翻译-sakura-galtrans.command` | Sakura-GalTransl-14B-v3.8 (方式C) | R18 友好，不可用时报错 |
| `start-scripts/macos/批量日中翻译-sakura-galtrans-全量翻译.command` | 方式C 全量重译 | RETRANS=true，全部重翻 |
| `start-scripts/macos/批量日中翻译-sakura-galtrans-续传翻译.command` | 方式C 续传 | RETRANS=false，仅翻新增 |
| `start-scripts/macos/批量韩中翻译.command` | Qwen3 14B 韩→中 | 需 Ollama + Qwen3 |

操作步骤：
1. 在 Finder 中找到对应 `.command` 文件
2. 双击启动 → 终端窗口自动打开（顶部 banner 显示当前翻译器模式）
3. 输入漫画目录路径（如 `test/materials/chapter-13`）
4. 确认是否重新翻译（输入 `y` 全量重新翻译，其他键续传）
5. 程序自动执行，完成后输出总结

**输出目录**：输入 `chapter-13` → 输出 `chapter-13 汉化`（位于输入目录的同级目录）

### 使用方式二：命令行直接调用

```bash
python -m manga_translator.batch
```

功能同方式一，交互式输入目录名和 retrans 确认。

### 翻译流程详解

```
输入: chapter-13/           ← 用户输入的漫画目录
      ├── 001.jpg           ← 当前目录的图片（优先翻译）
      ├── 002.jpg
      ├── 01/               ← 子目录（纯数字 → 按数值排序）
      │   ├── page01.png
      │   └── page02.png
      ├── 02a/              ← 子目录（数字+字母 → 数字→字母排序）
      │   └── 001.jpg
      └── readme.txt        ← 自动跳过非图片文件

执行顺序:
  1. 加载翻译模型（一次性，约 10s）
  2. 翻译 chapter-13/ 的 001.jpg, 002.jpg  → 跳过 01/, 02a/, readme.txt
  3. 翻译 chapter-13/01/ 的全部图片        → 按纯数字排序先于数字+字母
  4. 翻译 chapter-13/02a/ 的全部图片

输出: chapter-13 汉化/      ← 同级目录，"原名 汉化"
      ├── 001.jpg
      ├── 002.jpg
      ├── 01/
      │   ├── page01.png
      │   └── page02.png
      └── 02a/
          └── 001.jpg
```

### 子目录翻译顺序规则

| 优先级 | 模式 | 排序规则 | 示例 |
|--------|------|----------|------|
| 1 | 纯数字 | 数值从小到大 | `1`, `2`, `03`, `10` |
| 2 | 数字+字母 | 数字数值→字母字母序 | `01a`, `02a`, `02b`, `10c` |
| 3 | 字母+数字 | 字母字母序→数字数值 | `ch1`, `ch2`, `ep01`（纯字母=字母+0，排此类最前） |
| 4 | 其他 | 自然排序（排最后） | `_extra`, `.hidden` |

分隔符兼容：`01-a`、`01_a`、`01a` 均视为数字+字母模式。

### 中断续传

- 每目录下自动生成 `.translate_progress.json`（进度文件）
- 每翻译成功一张图片就立即写入进度
- 脚本重新执行时自动读取进度，跳过已翻译的图片
- 中断后重启 = 从中断点继续翻译，不重复工作

**重新翻译**：输入目录名后，确认提示时输入 `y` 即清空所有进度重新翻译。命令行等效：`--retrans` 参数。

### 单目录翻译（原有模式，保留兼容）

```bash
python -m manga_translator test/materials/chapter-13 \
    --translator sakura \
    --target-lang CHS \
    --use-gpu-limited \
    --retrans                     # 可选：重新翻译
```

此模式直接调用 `mode/local.py` 的 `translate_path`，仅翻译单个目录下的图片，不遍历子目录。进度文件仍然生效。

### 韩中翻译 (Korean-Chinese Translation)

#### 韩中翻译专用翻译器

- **Qwen3KoZhTranslator**: 韩中翻译器（`translators/qwen3_kozh.py`），基于 `CustomOpenAiTranslator`，通过 Ollama 调用 Qwen3 14B 模型。优化韩中漫画翻译 Prompt，禁用 `think` 模式（Ollama 原生参数，等效 Qwen3 的 `enable_thinking`）以提升效率。通过 `CUSTOM_OPENAI_API_BASE`、`CUSTOM_OPENAI_MODEL` 环境变量配置。
- **无降级链**: 韩中翻译不使用降级链，Ollama 不可达时直接报错退出。`attempts=1`。
- **think 模式**: Qwen3 模型的思考模式，在 Ollama 原生 `/api/chat` 端点中通过 `"think": false` 禁用以加速响应（等效 Qwen3 自身的 `enable_thinking` 参数）。

#### 韩中翻译领域术语

- **Webtoon (웹툰)**: 韩国网络漫画，垂直滚动格式，是韩中翻译的主要目标格式。
- **Manhwa (만화)**: 韩语中"漫画"的统称。
- **拟声词/拟态词 (의성어/의태어)**: 韩语中大量使用的拟声词和拟态词，翻译时保留原文或使用中文对应表达。
- **敬语/半语 (존댓말/반말)**: 韩语中的敬语体系，翻译时需根据语境转换为中文的礼貌程度。
- **Qwen3**: 阿里巴巴通义千问 Qwen3 系列模型，开源多语言 LLM，支持韩中翻译。14B 参数版使用 Q4_K_M 量化。

#### 韩中批量翻译入口

- **batch_ko.py**: 韩中批量翻译入口（`manga_translator/batch_ko.py`），与日中翻译共用 `batch_common.py` 的公共逻辑（目录排序、图片扫描、进度管理），配置 `source_lang='ko'`、`translator='qwen3_kozh'`。
- **批量韩中翻译.command**: macOS Finder 双击启动脚本，位于 `start-scripts/macos/`，设置韩中翻译环境变量（`CUSTOM_OPENAI_API_BASE`、`CUSTOM_OPENAI_MODEL`），调用 `batch_ko.py`。

#### 公共模块

- **batch_common.py**: 日中/韩中批量翻译的公共逻辑模块（`manga_translator/batch_common.py`），包含 `IMAGE_EXTS`、`sort_subdirs`、`_detect_device`、`_get_image_files`、`_load_progress`、`_save_progress`、`_clear_progress`、`_clear_all_progress`、`PROGRESS_FILE`。`batch.py`（日中）和 `batch_ko.py`（韩中）均从此模块导入。

### 环境变量速查表

| 变量 | 说明 | 必填 |
|------|------|------|
| `SAKURA_API_BASE` | Ollama API 地址（方式A） | 方式A 必填 |
| `SAKURA_MODEL` | Ollama 模型名 | 方式A 必填 |
| `SAKURA_VERSION` | Sakura 模型版本（`0.9` 或 `0.10`） | 可选 |
| `SAKURA_GGUF_PATH` | 本地 GGUF 文件路径（方式B） | 方式B 必填 |
| `GALTRANS_GGUF_PATH` | Galtransl GGUF 文件路径（方式C） | 方式C 必填 |
| `TRANSLATOR_MODE` | `degraded`(B→A) 或 `galtransl`(C) | 可选 |
| `RETRANS` | `true`=全量重翻, `false`=续传 | 可选 |
| `CUSTOM_OPENAI_API_BASE` | Qwen3 Ollama API 地址（韩中翻译） | 韩中 必填 |
| `CUSTOM_OPENAI_MODEL` | Qwen3 Ollama 模型名（韩中翻译） | 韩中 必填 |
| `CUSTOM_OPENAI_API_KEY` | API Key（韩中翻译，默认 `ollama`） | 韩中 必填 |
| `USE_GPU_LIMITED` | MPS 加速 Detection/OCR/Inpainting | 推荐 |

## 测试报告

### 测试总览（2026-07-05）

```bash
python -m pytest test/unit/ -v  # 218 tests, all pass
```

| 测试文件 | 用例数 | 说明 |
|----------|--------|------|
| `test/unit/test_batch_sort.py` | 18 | 目录排序规则（纯数字/数字+字母/字母+数字/纯字母/其他/分隔符/嵌套） |
| `test/unit/test_local_norecurse.py` | 12 | 非递归扫描（图片过滤/跳过子目录/跳过非图片/跳过进度文件/图片格式） |
| `test/unit/test_batch_progress.py` | 13 | 进度跟踪（保存/加载/清空/递归清空/幂等/排序存储/retrans 集成） |
| `test/unit/test_sakura_local.py` | 17 | Sakura 本地 GGUF 翻译器（单例/路由/Prompt/解析/参数） |
| `test/unit/test_galtransl_local.py` | 18 | Galtransl 本地 GGUF 翻译器 |
| `test/unit/test_sliding_window.py` | 30 | 滑动窗口翻译策略（分区/渲染/组装/解析/映射） |
| `test/unit/test_empty_translation_progress.py` | 16 | 空翻译结果跳过 progress 记录 |
| `test/unit/test_translator_fallback.py` | 12 | 翻译器降级链探测 |
| `test/unit/test_qwen3_kozh.py` | 14 | Qwen3 韩中翻译器（初始化/API 端点/参数构建） |
| `test/unit/test_batch_ko.py` | 18 | 韩中批量翻译入口（参数配置/翻译器实例化/Ollama 探测） |
| `test/unit/test_batch.py` | 10 | 批量翻译编排层（输出路径/边界/retrans/模式检测/设备检测） |
| `test/unit/test_mode_local.py` | 17 | 核心翻译引擎层（文本检测/进度守卫/翻译调度/强制清理） |
| `test/unit/test_sakura.py` | 12 | Sakura 翻译器（预处理/对齐检测/重复检测/翻译请求/风格切换） |
| `test/unit/test_custom_openai.py` | 11 | GPT 基类翻译器（抽取/提示组装/请求/重试/翻译流程） |
| **合计** | **218** | **全部通过，覆盖四种翻译方式全链路** |

> Iteration 15: 拆分 `test_batch_common.py` → 合并到对应目标文件后删除；新增 4 个测试文件；修复 3 个功能代码防御性 bug + 5 个已有测试 bug。

## 迭代历史

详细开发历史（Iteration 1-15 的完整 TDD 过程、架构决策、性能实测数据）见 [日中翻译-迭代报告](docs/日中翻译-迭代报告.md)。

## 基准测试操作指南

### 启用 Benchmark 模式

在批量翻译时添加 `--benchmark` 参数，或在交互模式中选择启用：

```bash
# 方式一：命令行参数
python -m manga_translator.batch --benchmark

# 方式二：交互模式中选择
# 启动后输入目录路径，然后选择是否启用 benchmark 模式
```

### 输出文件

基准测试完成后，在 `test/results/benchmark/{mode}/` 目录下生成以下文件：

| 文件 | 说明 |
|------|------|
| `YYYYMMDD-HHMMSS.md` | Markdown 专业分析报告（速度/质量/稳定性/归因分析/优化建议） |
| `YYYYMMDD-HHMMSS.json` | 原始逐页数据 + 统计数据（完整 JSON） |
| `YYYYMMDD-HHMMSS.csv` | 逐页耗时明细（Excel 友好，可导入分析工具） |

### 报告内容

报告包含以下章节：

1. **测试概况**：总页数、成功率、总耗时、吞吐量
2. **速度分析**：各阶段耗时分布（Avg/P50/P90/P95/P99/Std/CV）、Token 吞吐量
3. **质量分析**：翻译覆盖率、LLM-Judge 评分分布（需 Qwen3-14B 可用）
4. **稳定性分析**：错误率、重试次数、异常值检测（2σ 阈值）
5. **归因分析**：性能瓶颈根因定位、稳定性问题归因、质量问题归因
6. **优化建议**：基于数据的针对性优化方向
7. **逐页详情**：每页各阶段耗时表格

### LLM-as-Judge 质量评分

如需自动质量评分，确保 Qwen3-14B 模型在 Ollama 中可用：

```bash
# 检查 Qwen3 模型是否可用
curl http://localhost:11434/api/tags | grep qwen3

# 如不可用，拉取模型
ollama pull qwen3:14b-q4_k_m
```

Judge 评分在翻译完成后异步执行，不阻塞主流程。评分不可用时报告中的评分列留空，不影响其他指标。

### 对比测试流程（方式A vs 方式B）

```bash
# 1. 方式A (Ollama HTTP) 基准测试
unset SAKURA_GGUF_PATH
export SAKURA_API_BASE='http://localhost:11434/v1'
python -m manga_translator.batch --benchmark
# 输入目录路径，选择 benchmark 模式

# 2. 方式B (本地 GGUF) 基准测试
export SAKURA_GGUF_PATH='$HOME/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-Q4_K_M.gguf'
python -m manga_translator.batch --benchmark
# 输入相同目录路径，选择 benchmark 模式

# 3. 对比两份报告
# 报告位于 test/results/benchmark/modeA/ 和 test/results/benchmark/modeB/
```

### 最新基准测试结果 (2026-06-17/18, 158页漫画，第二次实测)

| 指标 | 方式A (Ollama HTTP) | 方式B (本地 GGUF) |
|------|---------------------|---------------------|
| 总耗时 | 16m 58s | 15m 6s |
| 吞吐量 | 9.31 页/分钟 | 10.46 页/分钟 |
| 翻译吞吐量 | 16.99 tokens/s | 21.62 tokens/s |
| 翻译占比 | 50.1% | 49.9% |
| 覆盖率 | 54.0% | 53.4% |

#### 两次实测对比

| 指标 | 方式A 第1次 | 方式A 第2次 | 方式B 第1次 | 方式B 第2次 |
|------|-------------|-------------|-------------|-------------|
| 总耗时 | 15m 59s | 16m 58s | 15m 36s | 15m 6s |
| 吞吐量 (p/min) | 9.89 | 9.31 | 10.13 | 10.46 |
| 翻译吞吐量 (t/s) | 18.69 | 16.99 | 21.69 | 21.62 |
| 覆盖率 | 54.0% | 54.0% | 53.4% | 53.4% |

**结论**：两次实测结果一致，方式B 翻译吞吐量稳定领先 27%+，覆盖率完全一致。方式B 在速度、延迟、稳定性上全面优于方式A。

详细对比见 [日中翻译-性能实测报告](docs/日中翻译-性能实测报告.md)

### 数据收集对性能的影响

- 逐阶段计时使用 `time.time()` 打点，每次调用 <1μs，总计 <10μs/页
- 数据存储为纯内存操作（追加到 Python list），无磁盘 IO
- 翻译完成后一次性写入磁盘（JSON + CSV + Markdown）
- **对主链路耗时影响 <0.01%，可忽略**