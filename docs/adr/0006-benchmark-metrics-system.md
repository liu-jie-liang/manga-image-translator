# ADR-0006: 基准测试性能指标体系

## 状态

已实现 (Implemented)

**实现日期**: 2026-06-12  
**验证方式**: TDD（pytest 57 测试用例全部通过），端到端集成测试待执行

## 背景

日中漫画翻译的批量翻译流程需要量化评估翻译速度和翻译质量，以便：

1. 对比不同翻译后端（方式A Ollama vs 方式B GGUF）的客观性能差异
2. 识别翻译管线中的瓶颈阶段
3. 检测不稳定因素（网络波动、异常慢页、OOM）
4. 为优化决策提供数据支撑

当前缺乏系统化的性能测量框架，无法进行专业的端到端基准测试。

## 决策

### 1. 非侵入式数据收集

采用 `time.time()` 打点 + 内存存储的方式，零 IO 开销，不影响主链路性能：

- **逐阶段计时**：在 `manga_translator.py` 核心管线的每个阶段（detection、OCR、translation、inpainting、rendering）前后插入时间戳
- **Token 跟踪**：从翻译器（`sakura.py` / `sakura_local.py`）捕获 `usage` 信息，通过 `translators/__init__.py` 的 `_last_translation_usage` 全局变量传递
- **单例模式**：`BenchmarkContext` 使用单例模式，全局可访问，无需逐层传递 context 参数

### 2. 三维度指标体系

#### 速度指标 (Speed)

| 指标 | 计算方式 | 用途 |
|------|---------|------|
| 各阶段耗时 (Avg/P50/P90/P95/P99) | 百分位数 (线性插值) | 评估管线各阶段性能分布 |
| Token 吞吐量 (tokens/s) | `completion_tokens / 翻译总耗时` | 评估模型推理速度 |
| 页吞吐量 (pages/min) | `总页数 / 总耗时 * 60` | 评估整体处理能力 |
| 变异系数 (CV) | `Std / Avg` | 评估耗时波动性 |

#### 质量指标 (Quality)

| 指标 | 计算方式 | 用途 |
|------|---------|------|
| 翻译覆盖率 | `translated_text_count / ocr_text_count` | 评估翻译完整性 |
| LLM-Judge 评分 (1-5) | Qwen3-14B 自动评分 | 评估翻译准确性、地道性、术语一致性 |
| 可接受率 | `score ≥ 4 的页数 / 总评分页数` | 评估整体翻译质量 |

#### 稳定性指标 (Stability)

| 指标 | 计算方式 | 用途 |
|------|---------|------|
| 错误率 | `失败页数 / 总页数` | 评估系统可靠性 |
| 重试次数 | 累计重试计数 | 评估翻译器稳定性 |
| 异常值检测 | 2σ 阈值 | 识别异常慢的页面 |
| OOM 检测 | 布尔标志 | 检测内存不足事件 |

### 3. LLM-as-Judge 质量评分

使用 Qwen3-14B-Q4_K_M 通过 Ollama 进行自动化翻译质量评分：

- **评分维度**：准确性（无漏译/误译/增译）、地道性（符合中文表达习惯）、术语一致性
- **评分规则**：5分（几乎完美）、4分（可接受）、3分（需复审）、≤2分（严重问题）
- **推理参数**：temperature=0.0, top_p=1.0, repeat_penalty=1.1, seed=42（deterministic）
- **输出格式**：约束 JSON `{"score": 1-5, "accuracy_ok": true/false, "issues": "...", "revised": "..."}`
- **模块位置**：`manga_translator/quality_judge.py`

### 4. 报告输出

基准测试完成后生成三种格式报告：

| 格式 | 路径 | 内容 |
|------|------|------|
| Markdown (.md) | `test/results/benchmark/{mode}/YYYYMMDD-HHMMSS.md` | 专业分析报告（速度/质量/稳定性/归因/优化建议） |
| JSON (.json) | `test/results/benchmark/{mode}/YYYYMMDD-HHMMSS.json` | 原始逐页数据 + 统计数据 |
| CSV (.csv) | `test/results/benchmark/{mode}/YYYYMMDD-HHMMSS.csv` | 逐页耗时明细（Excel 友好） |

## 后果

### 正面影响

1. **可量化对比**：方式A vs 方式B 的性能差异现在有系统化的测量框架
2. **瓶颈识别**：逐阶段耗时分析可以精确定位优化方向
3. **质量监控**：LLM-Judge 自动评分提供可复现的质量评估
4. **零性能影响**：数据收集仅为内存操作，不在主链路中执行 IO

### 负面影响

1. **代码侵入**：在 `manga_translator.py` 核心管道中插入计时代码，增加了代码复杂度
2. **LLM-Judge 成本**：质量评分需要额外的 Ollama 推理调用，增加了后处理时间
3. **依赖 Ollama**：Judge 评分依赖 Ollama 服务可用，离线环境无法评分

### 缓解措施

- 计时代码仅 2-3 行/阶段，通过 `benchmark_context._active_page` 条件判断，非 benchmark 模式零开销
- Judge 评分在翻译完成后异步执行，不阻塞主流程
- Judge 不可用时评分字段留空，不影响其他指标的完整性

## 相关模块

- `manga_translator/benchmark.py`：数据模型 + 统计计算
- `manga_translator/quality_judge.py`：LLM-as-Judge 评分
- `manga_translator/report_generator.py`：报告生成
- `manga_translator/batch.py`：`--benchmark` 模式入口
- `manga_translator/manga_translator.py`：逐阶段计时注入
- `manga_translator/translators/sakura.py`：Ollama 翻译器 token 跟踪
- `manga_translator/translators/sakura_local.py`：GGUF 翻译器 token 跟踪
- `test/test_benchmark.py`：基准测试模块 TDD（28 用例）
- `test/test_quality_judge.py`：Judge 模块 TDD（18 用例）
- `test/test_report_generator.py`：报告生成器 TDD（11 用例）