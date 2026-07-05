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

## 系统要求

### 硬件

| 要求 | 最低 | 推荐 |
|------|------|------|
| **操作系统** | macOS 14+ / Linux / Windows 10+ | macOS 15+ (Apple Silicon) / Ubuntu 22.04+ / Windows 11 |
| **Python** | 3.10 | 3.11+ |
| **内存** | 16 GB | 32 GB+ |
| **显存 / 统一内存** | 8 GB | 16 GB+ (14B 模型需 ~10 GB) |
| **磁盘空间** | 20 GB | 30 GB+ (含模型) |
| **GPU** | Apple Silicon (M1+) / NVIDIA GTX 1060+ | Apple M2 Pro+ / NVIDIA RTX 3060+ |

> **说明**：
> - **方式B/C (GGUF)** 需要 GPU 加速（Metal / CUDA），纯 CPU 可用但极慢
> - **方式A (Ollama)** 可跑在仅 CPU 环境（韩中翻译同样可用）
> - Windows 仅支持 NVIDIA GPU（llama-cpp-python 的 CUDA 后端）

### 模型文件

本项目不内置模型。你需要从 HuggingFace 下载 GGUF 量化模型：

| 方式 | 模型 | HuggingFace 仓库 | 文件 | 大小 |
|------|------|-----------------|------|------|
| B | Sakura-14B-Qwen2.5 | [SakuraLLM/Sakura-14B-Qwen2.5-v1.0-GGUF](https://huggingface.co/SakuraLLM/Sakura-14B-Qwen2.5-v1.0-GGUF) | `sakura-14b-qwen2.5-v1.0-q4_k_m.gguf` | ~8.5 GB |
| C | Sakura-GalTransl-14B-v3.8 | [SakuraLLM/Sakura-GalTransl-14B-v3.8](https://huggingface.co/SakuraLLM/Sakura-GalTransl-14B-v3.8) | `Sakura-Galtransl-14B-v3.8.gguf` | ~8.5 GB |
| 韩中 | Qwen3 14B (Ollama) | 通过 `ollama pull qwen3:14b-q4_k_m` 自动获取 | — | ~8.5 GB |

> **网络问题？** 国内用户可使用镜像：`https://hf-mirror.com/SakuraLLM/...`

## 安装与配置

### 1. 克隆仓库

```bash
git clone https://github.com/liu-jie-liang/manga-image-translator.git
cd manga-image-translator
```

### 2. 创建虚拟环境

<details open>
<summary><b>macOS / Linux</b></summary>

```bash
python -m venv venv
source venv/bin/activate
```

</details>

<details>
<summary><b>Windows</b></summary>

```cmd
python -m venv venv
venv\Scripts\activate
```

</details>

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 安装 GGUF 翻译支持（如需方式B/C）

根据 GPU 选择编译参数：

<details open>
<summary><b>macOS (Apple Silicon / Metal)</b></summary>

```bash
CMAKE_ARGS="-DGGML_METAL=on" pip install -r requirements-gguf.txt
```

</details>

<details>
<summary><b>Linux / Windows (NVIDIA / CUDA)</b></summary>

```bash
# Linux
CMAKE_ARGS="-DGGML_CUDA=on" pip install -r requirements-gguf.txt

# Windows CMD
set CMAKE_ARGS=-DGGML_CUDA=on
pip install -r requirements-gguf.txt
```

</details>

<details>
<summary><b>仅 CPU</b>（不推荐，速度极慢）</summary>

```bash
pip install -r requirements-gguf.txt
```

</details>

### 5. 下载模型文件

下载你需要的 GGUF 模型放到 `~/.ollama/models/gguf/` 目录：

<details open>
<summary><b>macOS / Linux</b></summary>

```bash
mkdir -p ~/.ollama/models/gguf

# 方式B — Sakura Qwen2.5
curl -L -o ~/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf \
  "https://huggingface.co/SakuraLLM/Sakura-14B-Qwen2.5-v1.0-GGUF/resolve/main/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf"

# 方式C — Galtransl
curl -L -o ~/.ollama/models/gguf/Sakura-Galtransl-14B-v3.8.gguf \
  "https://huggingface.co/SakuraLLM/Sakura-GalTransl-14B-v3.8/resolve/main/Sakura-Galtransl-14B-v3.8.gguf"
```

</details>

<details>
<summary><b>Windows</b></summary>

```cmd
mkdir %USERPROFILE%\.ollama\models\gguf

:: 方式B — Sakura Qwen2.5
curl -L -o %USERPROFILE%\.ollama\models\gguf\sakura-14b-qwen2.5-v1.0-q4_k_m.gguf "https://huggingface.co/SakuraLLM/Sakura-14B-Qwen2.5-v1.0-GGUF/resolve/main/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf"

:: 方式C — Galtransl
curl -L -o %USERPROFILE%\.ollama\models\gguf\Sakura-Galtransl-14B-v3.8.gguf "https://huggingface.co/SakuraLLM/Sakura-GalTransl-14B-v3.8/resolve/main/Sakura-Galtransl-14B-v3.8.gguf"
```

</details>

> 国内用户可将 `huggingface.co` 替换为 `hf-mirror.com` 加速下载。

### 6. 安装 Ollama（如需方式A 降级或韩中翻译）

方式B/C 不需要 Ollama。只有以下场景需要：

- 方式B 的 GGUF 不可用时需要降级到 Ollama HTTP API
- 韩中翻译（`批量韩中翻译`）依赖 Ollama 运行 Qwen3

从 [ollama.com](https://ollama.com) 下载安装后：

```bash
ollama pull sakura-14b-qwen2.5-v1.0   # 方式A 降级模型
ollama pull qwen3:14b-q4_k_m           # 韩中翻译模型
```

### 7. 验证安装

```bash
python -c "from manga_translator import MangaTranslator; print('OK')"
```

## 快速开始

### 图形化启动（推荐）

将漫画图片放入项目根目录，双击对应平台的启动脚本即可：

| 平台 | 启动目录 | 文件格式 |
|------|---------|---------|
| macOS | `start-scripts/macos/` | `.command` |
| Linux | `start-scripts/linux/` | `.sh` |
| Windows | `start-scripts/windows/` | `.bat` |

首次使用推荐 **`批量日中翻译`**（交互式选择翻译模式）。

### 命令行

<details>
<summary><b>macOS / Linux (bash/zsh)</b></summary>

```bash
# 方式B — Sakura GGUF 直连
export SAKURA_GGUF_PATH="$HOME/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf"
python -m manga_translator.batch

# 方式C — Galtransl GGUF 直连 (R18友好)
export GALTRANS_GGUF_PATH="$HOME/.ollama/models/gguf/Sakura-Galtransl-14B-v3.8.gguf"
export TRANSLATOR_MODE=galtransl
python -m manga_translator.batch

# 续传模式（跳过已翻译）
export RETRANS=false
python -m manga_translator.batch
```

</details>

<details>
<summary><b>Windows (CMD)</b></summary>

```cmd
:: 方式B — Sakura GGUF 直连
set SAKURA_GGUF_PATH=%USERPROFILE%\.ollama\models\gguf\sakura-14b-qwen2.5-v1.0-q4_k_m.gguf
python -m manga_translator.batch

:: 方式C — Galtransl GGUF 直连 (R18友好)
set GALTRANS_GGUF_PATH=%USERPROFILE%\.ollama\models\gguf\Sakura-Galtransl-14B-v3.8.gguf
set TRANSLATOR_MODE=galtransl
python -m manga_translator.batch

:: 续传模式（跳过已翻译）
set RETRANS=false
python -m manga_translator.batch
```

</details>

## 使用指南

### 启动脚本

6 个预配置脚本，满足不同场景：

| 脚本 | 翻译器 | 特点 |
|--------|--------|------|
| `批量日中翻译` | 交互选择 a/b | 运行时选择降级或 Galtransl |
| `批量日中翻译-sakura-qwen3` | Sakura Qwen2.5 | B→A 降级，优先 GGUF |
| `批量日中翻译-sakura-galtrans` | Galtransl 14B | 方式C，R18 友好 |
| `批量日中翻译-sakura-galtrans-全量翻译` | Galtransl 14B | 全部重新翻译 |
| `批量日中翻译-sakura-galtrans-续传翻译` | Galtransl 14B | 仅翻译新增图片 |
| `批量韩中翻译` | Qwen3 14B | 韩文→简体中文 |

### 工作目录

启动脚本会在项目根目录寻找以下文件夹进行翻译：

```
项目根目录/
├── 漫画文件夹1/   ← 脚本会扫描并翻译所有子目录中的图片
├── 漫画文件夹2/
├── result/       ← 翻译结果输出（自动创建）
└── progress/     ← 翻译进度记录（自动创建，用于续传）
```

## 翻译器架构

```
选项a: 方式B (GGUF) → 降级 → 方式A (Ollama) → 报错
选项b: 方式C (Galtransl GGUF) → 不可用直接报错（不降级）
```

| 方式 | 模型 | 适用场景 | R18 | 降级策略 |
|------|------|---------|-----|---------|
| B | Sakura-14B-Qwen2.5 | 一般漫画 | 越狱后可用 | → 方式A |
| C | Sakura-GalTransl-14B-v3.8 | Galgame/R18漫画 | 原生支持 | 不降级 |
| A (降级) | Ollama HTTP API | 备选方案 | 同方式B | 报错退出 |

## 续传逻辑

- `overwrite` 始终为 True — 目标图片总会被覆盖
- `retrans=False`（续传）— 跳过 progress 文件中已记录的图片
- `retrans=True`（重翻）— 无视 progress，全部重翻
- 全空翻译结果不记录 progress — 下次续传仍会重试

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

## 环境变量参考

### 设置方式

| Shell | 语法 |
|-------|------|
| bash/zsh | `export VAR=VALUE` |
| CMD | `set VAR=VALUE` |
| PowerShell | `$env:VAR = "VALUE"` |

### 翻译器配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SAKURA_GGUF_PATH` | 方式B GGUF 模型路径 | 无 |
| `GALTRANS_GGUF_PATH` | 方式C GGUF 模型路径 | 无 |
| `TRANSLATOR_MODE` | `degraded`(B→A) 或 `galtransl`(C) | 自动检测 |
| `SAKURA_MODEL` | 方式A Ollama 模型名 | `sakura-14b-qwen2.5-v1.0` |
| `SAKURA_VERSION` | Sakura prompt 版本 | `0.9` |

### API 和服务地址

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SAKURA_API_BASE` | 方式A Sakura Ollama 地址 | `http://localhost:11434/v1` |
| `CUSTOM_OPENAI_API_BASE` | 韩中翻译 Ollama 地址 | `http://localhost:11434/v1` |
| `OLLAMA_HOST` | Ollama 服务根地址 | `http://localhost:11434` |
| `SAKURA_API_KEY` | Ollama API Key | `ollama` |

### 续传与行为

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `RETRANS` | `true`=全量重翻, `false`=续传 | 交互式选择 |
| `BENCHMARK` | 是否输出 benchmark JSON | `false` |

### GPU 与性能

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `GALTRANS_GGUF_N_GPU_LAYERS` | 方式C GPU 层数 | `-1`（全部） |
| `GALTRANS_GGUF_N_CTX` | 方式C 上下文长度 | `4096` |
| `USE_GPU_LIMITED` | 限制 GPU 使用（仅 det/ocr） | `false` |

### 运行环境

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CONDA_ENV` | conda 环境名 | `manga-translator` |

## 测试

```bash
# 单元测试
python -m pytest test/unit/ -v

# 端到端测试 (需先设置 GGUF 模型路径)
python test/e2e_gguf_2img.py         # 方式B
python test/e2e_galtransl_2img.py    # 方式C
```

## 文档

- [日中翻译 — 操作指南](docs/SakuraLocal-操作指南.md)
- [日中翻译 — 迭代报告](docs/日中翻译-迭代报告.md)
- [日中翻译 — 性能实测报告](docs/日中翻译-性能实测报告.md)

## 许可

本项目基于 [zyddnys/manga-image-translator](https://github.com/zyddnys/manga-image-translator) 修改，遵循 [GPL-3.0](LICENSE) 协议开源。
