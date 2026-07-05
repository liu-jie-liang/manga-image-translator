# 日中漫画批量翻译工具

> 基于 [zyddnys/manga-image-translator](https://github.com/zyddnys/manga-image-translator) 魔改，专注日文漫画→中文的本地 GPU 批量翻译。
> 本项目遵循 [GPL-3.0](LICENSE) 协议开源。

## 核心功能

- **本地 GPU 直连翻译**：无需 Ollama 服务，`llama-cpp-python` 直接加载 GGUF 模型到 GPU，翻译速度提升 15%+
- **两种翻译模型可选**：
  - 方式B — Sakura-14B-Qwen2.5，适合一般漫画
  - 方式C — Sakura-GalTransl-14B-v3.8，R18 内容友好，专为 Galgame 优化
- **智能续传**：基于 progress 记录跳过已翻译图片，断点续传不重复劳动
- **R18 越狱**：Sakura 模型内置 jailbreak prompt，拒绝审查，直接翻译
- **Apple Silicon 优化**：Metal/MPS 后端，64GB 统一内存可同时运行检测/OCR/擦除/翻译全部模型

## 快速开始

### 环境要求

- macOS (Apple Silicon) 或 Linux + NVIDIA GPU
- Python 3.10+
- 约 10GB 磁盘空间（GGUF 模型文件）

### 安装

```bash
git clone https://github.com/liu-jie-liang/manga-image-translator.git
cd manga-image-translator

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# Metal 版 llama-cpp（Apple Silicon）
CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python

# 安装其他依赖
pip install -r requirements.txt
```

### 启动

双击对应平台的启动脚本：

| 平台 | 启动目录 | 双击即可运行 |
|------|---------|-------------|
| macOS | `start-scripts/macos/` | `.command` 文件 |
| Linux | `start-scripts/linux/` | `.sh` 文件 |
| Windows | `start-scripts/windows/` | `.bat` 文件 |

首次使用推荐 `批量日中翻译.command`（交互式选择翻译模式）。

或命令行：

```bash
# 方式B — Sakura GGUF 直连
export SAKURA_GGUF_PATH="$HOME/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf"
python -m manga_translator.batch

# 方式C — Galtransl GGUF 直连 (R18友好)
export GALTRANS_GGUF_PATH="$HOME/.ollama/models/gguf/Sakura-Galtransl-14B-v3.8-Q4_K_M.gguf"
export TRANSLATOR_MODE=galtransl
python -m manga_translator.batch

# 续传模式（跳过已翻译）
export RETRANS=false
python -m manga_translator.batch
```

## 性能数据

### 方式B vs 方式C（12页日文漫画，Apple Silicon MPS）

| 指标 | 方式B (Sakura) | 方式C (Galtransl) |
|------|---------------|-------------------|
| 总耗时 | 104.2s | 105.2s |
| 平均每页 | 8.7s | 8.8s |
| 成功率 | 12/12 | 12/12 |
| 翻译吞吐量 | 21.65 tok/s | 21.49 tok/s |

两种方式速度差异 <1%，方式C 对 R18 内容翻译质量更好。

### 续传效率（Iteration 10 实测）

| 场景 | 方式B | 方式C |
|------|-------|-------|
| 首次翻译（2张） | 14.8s | 17.7s |
| 续传（+1张新图） | 2.6s | 3.3s |
| 全量重翻（3张） | 20.2s | 20.7s |

续传只翻译新增图片，已有图片秒级跳过。

## 翻译器架构

```
选项a: 方式B (GGUF) → 降级 → 方式A (Ollama) → 报错
选项b: 方式C (Galtransl GGUF) → 不可用直接报错（不降级）
```

| 方式 | 模型 | 适用场景 | R18 | 降级 |
|------|------|---------|-----|------|
| B | Sakura-14B-Qwen2.5 | 一般漫画 | 越狱后可用 | → 方式A |
| C | Sakura-GalTransl-14B-v3.8 | Galgame/R18漫画 | 原生支持 | 不降级 |
| A (降级) | Ollama HTTP API | 备选方案 | 同方式B | 报错 |

## Overwrite 与续传逻辑

- `overwrite` 始终为 True — 目标图片总会被覆盖
- `retrans=False`（续传）— 跳过 progress 文件中已记录的图片
- `retrans=True`（重翻）— 无视 progress，全部重翻
- 全空翻译结果不记录 progress — 下次续传仍会重试

## 测试

```bash
# 单元测试 (16/16 PASS)
python -m pytest test/unit/ -v

# 场景化端到端测试
SAKURA_GGUF_PATH=... python test/e2e_gguf_2img.py         # 方式B
TRANSLATOR_MODE=galtransl GALTRANS_GGUF_PATH=... python test/e2e_galtransl_2img.py  # 方式C
```

## 环境变量

### 翻译器配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SAKURA_GGUF_PATH` | 方式B 模型路径 | 无（需手动设置） |
| `GALTRANS_GGUF_PATH` | 方式C 模型路径 | 无（需手动设置） |
| `TRANSLATOR_MODE` | 翻译模式选择 | 自动检测 |
| `SAKURA_MODEL` | 方式A Ollama 模型名 | `sakura-14b-qwen2.5-v1.0` |
| `SAKURA_VERSION` | Sakura prompt 版本 | `0.9` |

### API 和服务地址

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SAKURA_API_BASE` | 方式A Sakura Ollama 地址 | `http://localhost:11434/v1` |
| `CUSTOM_OPENAI_API_BASE` | 韩中翻译 Ollama 地址 | `http://localhost:11434/v1` |
| `OLLAMA_HOST` | Ollama 服务根地址（仅 host:port） | `http://localhost:11434` |
| `SAKURA_API_KEY` | Ollama API Key（通常不需要） | `ollama` |

### 续传与行为

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `RETRANS` | `true`=全量重翻, `false`=续传 | 交互式选择 |
| `BENCHMARK` | 是否输出 benchmark JSON 报告 | `false` |

### GPU 与性能

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `GALTRANS_GGUF_N_GPU_LAYERS` | 方式C GPU 层数 | `-1`（全部） |
| `GALTRANS_GGUF_N_CTX` | 方式C 上下文长度 | `4096` |
| `USE_GPU_LIMITED` | 限制 GPU 使用（仅 det/ocr） | `false` |

### 运行环境

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CONDA_ENV` | conda 环境名（启动脚本使用） | `TraeAI-2` |

> 示例：`SAKURA_GGUF_PATH="$HOME/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf"`

## 文档

- [日中翻译 — 操作指南](docs/SakuraLocal-操作指南.md)
- [日中翻译 — 迭代报告](docs/日中翻译-迭代报告.md)
- [日中翻译 — 性能实测报告](docs/日中翻译-性能实测报告.md)

## 许可

本项目基于 [zyddnys/manga-image-translator](https://github.com/zyddnys/manga-image-translator) 修改，遵循 [GPL-3.0](LICENSE) 协议开源。
