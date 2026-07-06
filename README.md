# 日中漫画批量翻译工具

> 一键批量翻译日韩漫画为中文，本地 GPU 运行，零网络依赖，R18 无审查。
> 基于 [zyddnys/manga-image-translator](https://github.com/zyddnys/manga-image-translator) 魔改，[GPL-3.0](LICENSE) 开源。

## 为什么选这个项目？

原项目是一个通用漫画翻译框架，功能强大但上手门槛高。本项目在它的基础上做了大量"开箱即用"的改造：

| 对比维度 | 原项目 | 本项目 |
|---------|--------|--------|
| **翻译方式** | 需搭 Ollama 服务，HTTP 转发损耗 | GGUF 直连 GPU，跳过网络层，速度 +15% |
| **批量处理** | 每次手动指定单目录 | 自动扫描全部子目录，排序、翻译、输出一气呵成 |
| **断点续传** | 不支持，中断后重来 | 自动记录进度，续传只翻新图，已有页面秒级跳过 |
| **R18 内容** | API 层可能被审查，返回空白 | 内置越狱 prompt，直接翻译不过滤 |
| **启动方式** | 命令行传参 | macOS/Linux/Windows 双击脚本一键启动 |
| **韩中翻译** | 不支持 | 内置 Qwen3 14B 韩→中专用流水线 |
| **模型自动检测** | 手动指定翻译器 | 自动检测 GGUF 是否存在 → Ollama 是否可用 → 降级链 |

**一句话**：如果你想把一堆日文/韩文漫画扔进文件夹、双击脚本、等结果——这就是你要的工具。

## 能做什么？我该选哪个模型？

根据你的内容类型选择：

| 我有什么 | 推荐模型 | 特点 | 速度 |
|---------|---------|------|------|
| 一般向日本漫画 | **Sakura Qwen2.5** | 日→中精度最高，GGUF 本地推理 | 约 8.7 秒/页 |
| R18 / 成人向日本漫画 | **Galtransl 14B** | 专为 Galgame 优化，无审查 | 约 8.8 秒/页 |
| 韩国漫画（webtoon） | **Qwen3 14B** | 韩→中翻译，Ollama 运行 | 约 6.8 秒/页 |

> **降级保障**：选择 Sakura Qwen2.5 时，如果 GGUF 模型未找到，会自动降级到本地 Ollama 服务——不会直接报错。

## 我需要什么设备？

| 你的选择 | 最低配置 | 推荐配置 | 需下载的模型（大小） |
|---------|---------|---------|---------------------|
| Sakura Qwen2.5 | 16GB 内存, 8GB 显存 | 32GB 内存, 16GB 统一内存 (M2 Pro+) | [sakura-14b-qwen2.5-v1.0-q4_k_m.gguf](https://huggingface.co/SakuraLLM/Sakura-14B-Qwen2.5-v1.0-GGUF) (~8.5GB) |
| Galtransl 14B | 16GB 内存, 8GB 显存 | 32GB 内存, 16GB 统一内存 | [Sakura-Galtransl-14B-v3.8.gguf](https://huggingface.co/SakuraLLM/Sakura-GalTransl-14B-v3.8) (~8.5GB) |
| Qwen3 14B (韩中) | 16GB 内存 | 32GB 内存 | `ollama pull qwen3:14b-q4_k_m` (~8.5GB) |

**操作系统**：macOS 14+ (Apple Silicon) / Ubuntu 22.04+ / Windows 10+ (NVIDIA GPU)  
**Python**：3.10+  
**磁盘**：模型 + 项目 + 依赖 ≈ 20GB

> GGUF 模型需要 GPU 加速（Apple Metal 或 NVIDIA CUDA）。纯 CPU 虽然能跑，但一页可能要几分钟。

## 安装

选择你的操作系统：

### macOS

```bash
# 1. 克隆
git clone https://github.com/liu-jie-liang/manga-image-translator.git
cd manga-image-translator

# 2. 虚拟环境
python -m venv venv && source venv/bin/activate

# 3. 核心依赖
pip install -r requirements.txt

# 4. GGUF 翻译支持 (Metal 加速)
CMAKE_ARGS="-DGGML_METAL=on" pip install -r requirements-gguf.txt

# 5. 下载模型 (选你需要的)
mkdir -p ~/.ollama/models/gguf

# Sakura Qwen2.5 (一般向):
curl -L -o ~/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf \
  "https://huggingface.co/SakuraLLM/Sakura-14B-Qwen2.5-v1.0-GGUF/resolve/main/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf"

# Galtransl (R18):
curl -L -o ~/.ollama/models/gguf/Sakura-Galtransl-14B-v3.8.gguf \
  "https://huggingface.co/SakuraLLM/Sakura-GalTransl-14B-v3.8/resolve/main/Sakura-Galtransl-14B-v3.8.gguf"

# 6. 验证
python -c "from manga_translator import MangaTranslator; print('安装成功')"
```

> 国内下载慢？把 `huggingface.co` 换成 `hf-mirror.com`。

### Linux

```bash
# 1-3 步同上（macOS）
git clone https://github.com/liu-jie-liang/manga-image-translator.git
cd manga-image-translator
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 4. GGUF (CUDA 加速)
CMAKE_ARGS="-DGGML_CUDA=on" pip install -r requirements-gguf.txt

# 5-6 步同上（macOS），下载模型后验证
```

### Windows

```cmd
:: 1. 克隆
git clone https://github.com/liu-jie-liang/manga-image-translator.git
cd manga-image-translator

:: 2. 虚拟环境
python -m venv venv
venv\Scripts\activate

:: 3. 核心依赖
pip install -r requirements.txt

:: 4. GGUF (CUDA 加速)
set CMAKE_ARGS=-DGGML_CUDA=on
pip install -r requirements-gguf.txt

:: 5. 下载模型
mkdir %USERPROFILE%\.ollama\models\gguf

:: Sakura Qwen2.5:
curl -L -o %USERPROFILE%\.ollama\models\gguf\sakura-14b-qwen2.5-v1.0-q4_k_m.gguf "https://huggingface.co/SakuraLLM/Sakura-14B-Qwen2.5-v1.0-GGUF/resolve/main/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf"

:: 6. 验证
python -c "from manga_translator import MangaTranslator; print('OK')"
```

### 额外：韩中翻译需要 Ollama

如果你需要翻译韩国漫画，额外安装 [Ollama](https://ollama.com) 并拉取模型：

```bash
ollama pull qwen3:14b-q4_k_m
```

## 开始使用

### 1. 放入漫画

把需要翻译的漫画文件夹放到项目根目录：

```
manga-image-translator/
├── [你的漫画文件夹1]/    ← 放图片在这里
├── [你的漫画文件夹2]/
├── start-scripts/       ← 启动脚本
└── ...
```

脚本运行后，翻译结果输出到 `<漫画文件夹名> 汉化/`（与源目录同级），进度文件 `.translate_progress.json` 保存在各源目录内。

### 2. 双击启动

| 你的系统 | 双击这里 | 
|---------|---------|
| macOS | `start-scripts/macos/批量日中翻译.command` |
| Linux | 终端运行 `bash start-scripts/linux/批量日中翻译.sh` |
| Windows | `start-scripts/windows/批量日中翻译.bat` |

首次使用选 `批量日中翻译`，运行时会提示你选择翻译模式（a=一般向, b=R18）。

### 3. 等待完成

脚本会自动：
1. 扫描所有子目录中的图片
2. 按文件名排序（数字→字母→其他）
3. 逐页检测→OCR→翻译→擦除→渲染
4. 翻译结果输出到 `<源目录名> 汉化/`，保留原始目录结构
5. 记录进度到各源目录下的 `.translate_progress.json`，下次续传跳过已完成页面

### 6 个脚本，按需选用

| 脚本 | 适用场景 |
|------|---------|
| `批量日中翻译` | **新手首选**，运行时选 a（一般向）或 b（R18） |
| `批量日中翻译-sakura-qwen3` | 一般向漫画，GGUF 不可用时自动降级 Ollama |
| `批量日中翻译-sakura-galtrans` | R18 / Galgame 内容，原生无审查 |
| `批量日中翻译-sakura-galtrans-全量翻译` | 已有翻译结果，想全部重翻 |
| `批量日中翻译-sakura-galtrans-续传翻译` | 文件夹中新增了漫画，只翻译新增的 |
| `批量韩中翻译` | 韩→中翻译，需先装 Ollama + Qwen3 |

## 能期待什么效果？

### 翻译质量

以下测试基于 12 页日本漫画，Apple Silicon MPS 环境：

| | Sakura Qwen2.5 | Galtransl 14B |
|------|---------------|----------------|
| 一般向漫画 | 术语准确，语气自然 | 同左，略偏口语化 |
| R18 内容 | 越狱后可翻译，偶有生硬 | 原生支持，流畅自然 |
| 速度 | 8.7 秒/页 | 8.8 秒/页 |
| 成功率 | 100% (12/12) | 100% (12/12) |

两种模型速度几乎一致，Galtransl 的 R18 翻译质量明显更好。

### 续传效率

| 场景 | 首次翻译 | 续传（新增1张） | 
|------|---------|---------------|
| 2 张图片 | 14-18 秒 | 2-3 秒 |

续传只翻译新增的图片，已有结果秒级跳过。你可以随时加新漫画进去、再次双击脚本——只翻新的。

## 环境变量参考

启动脚本已内置合理的默认值。如果你需要自定义：

```bash
# GGUF 模型路径（如果不在默认位置）
export SAKURA_GGUF_PATH="/your/path/to/sakura.gguf"
export GALTRANS_GGUF_PATH="/your/path/to/galtransl.gguf"

# 续传模式（跳过已翻译，仅翻译新图）
export RETRANS=false

# 全部重翻
export RETRANS=true
```

完整变量列表见下方表格。

<details>
<summary><b>全部环境变量</b></summary>

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SAKURA_GGUF_PATH` | Sakura GGUF 模型路径 | 无 |
| `GALTRANS_GGUF_PATH` | Galtransl GGUF 模型路径 | 无 |
| `SAKURA_API_BASE` | Ollama API 地址 | `http://localhost:11434/v1` |
| `SAKURA_MODEL` | Ollama 模型名 | `sakura-14b-qwen2.5-v1.0` |
| `TRANSLATOR_MODE` | `degraded`(B→A) 或 `galtransl`(C) | 自动检测 |
| `RETRANS` | `true`=全量重翻, `false`=续传 | 交互选择 |
| `BENCHMARK` | 输出 benchmark JSON | `false` |
| `CONDA_ENV` | conda 环境名 | `manga-translator` |
| `OLLAMA_HOST` | Ollama 主机地址 | `http://localhost:11434` |
| `CUSTOM_OPENAI_API_BASE` | Qwen3 Ollama API 地址（韩中） | `http://localhost:11434/v1` |
| `CUSTOM_OPENAI_MODEL` | Qwen3 Ollama 模型名（韩中） | `qwen3:14b-q4_k_m` |
| `CUSTOM_OPENAI_API_KEY` | API Key（韩中，默认 ollama） | `ollama` |

</details>

## 测试

```bash
# 单元测试（全部 mock 外部依赖，数量详见 CONTEXT.md）
python -m pytest test/unit/ -v

# E2E 测试（需要 GGUF 模型 + 测试素材）
python test/e2e_gguf_2img.py      # 方式B 场景化测试
python test/e2e_galtransl_2img.py # 方式C 场景化测试
```

## 文档

- [日中翻译 — 开发者技术指南](docs/日中翻译-开发者技术指南.md)
- [日中翻译 — 迭代报告](docs/日中翻译-迭代报告.md)
- [日中翻译 — 性能实测报告](docs/日中翻译-性能实测报告.md)
- [韩中翻译 — 开发者技术指南](docs/韩中翻译-开发者技术指南.md)
- [韩中翻译 — 迭代报告](docs/韩中翻译-迭代报告.md)
- [韩中翻译 — 性能实测报告](docs/韩中翻译-性能实测报告.md)

## 许可

基于 [zyddnys/manga-image-translator](https://github.com/zyddnys/manga-image-translator) 修改，[GPL-3.0](LICENSE)。
