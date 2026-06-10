# ADR-0004: 本地 GGUF 直连 GPU 翻译后端

**状态**: 已采纳  
**日期**: 2026-06-10  
**决策者**: AI 辅助  

## 背景

当前 Sakura 翻译通过 Ollama HTTP API（方式A）完成。实测 157 页翻译中，翻译耗时占 46%（483s），每页 3.2s，瓶颈在于：
1. 网络往返延迟（HTTP 请求/响应）
2. Ollama Server 单 GPU 串行化处理

存在本地 GGUF 量化模型文件 `sakura-14b-qwen2.5-v1.0-q4_k_m.gguf`，可以通过 `llama-cpp-python` 直连 GPU 推理，消除 HTTP 开销。

## 决策

新增 **方式B：本地 GGUF 直连 GPU 翻译后端**，通过 `translators/sakura_local.py` 实现。

### 技术选型

| 方面 | 选择 | 原因 |
|------|------|------|
| 推理后端 | `llama-cpp-python` | 原生 Metal(MPS) 支持，Python 绑定完善，Qwen2.5 架构兼容 |
| 设备 | Metal(MPS) `n_gpu_layers=-1` | 全层加载到 Apple Silicon GPU |
| 生命周期 | 单例 + atexit 兜底 | 模型常驻显存，进程退出自动释放 |
| Prompt | 复用 `sakura.py` 的 Sakura v0.9 格式 | 保证方式A/B行为一致，便于对比 |

### 运行时选择

`SAKURA_GGUF_PATH` 环境变量控制：

| `SAKURA_GGUF_PATH` | 行为 |
|---|---|
| 未设置 | 方式A（Ollama HTTP），向后兼容 |
| 指向有效 `.gguf` | 方式B（本地 GGUF 直连 GPU） |

### 翻译策略

1. **单实例逐页推理**：一个 Llama 实例处理一页的所有文本（合并为一次 `create_chat_completion`）
2. **不做多实例并发**：单 GPU 多实例争抢不会产生真正加速，反而增加管理复杂度

### 批量策略

- 本地 GGUF 支持单次推理处理一页所有文本（与 Ollama HTTP 格式一致）
- 不尝试多页合并为一次推理（batch 效果已证明不可靠，覆盖率降低）

## 后果

### 正面
- **消除 HTTP 往返延迟**：本地推理无需网络往返
- **消除 Ollama 串行化瓶颈**：直接控制 Llama 实例运行推理
- **更大的模型上下文窗口控制**：可以根据需要调整 `n_ctx`
- **保持向后兼容**：`SAKURA_GGUF_PATH` 为空时绝不加载 llama-cpp-python

### 负面
- **模型常驻显存**：约 8.5GB GGUF 文件加载后占用约 10GB 统一内存
- **加载耗时**：首次加载 GGUF 到 GPU 需 ~5-10s（一次性成本）
- **新增依赖**：`llama-cpp-python` 需要带 Metal 编译标志安装

### 风险
- llama-cpp-python 的 Metal 支持可能在某些 macOS 版本不稳定
- GGUF 模型加载到 MPS 后的输出质量需要与 Ollama 版本对比验证

## 输出质量对比

两种方式运行**完全相同的模型文件**（同一 GGUF 文件），Prompt 格式完全一致，因此输出质量理论上相同。如果实测出现差异，将记录为 llama-cpp-python 的 tokenize/sampling 实现差异。

## 参考文献

- ADR-0003: CPU/GPU 设备使用分析
- CONTEXT.md: 翻译器章节