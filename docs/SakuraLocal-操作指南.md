# 日中漫画批量翻译 操作指南

## 快速启动

根据你的操作系统，在 `start-scripts/` 目录下找到对应的启动脚本：

| 平台 | 目录 | 文件格式 | 启动方式 |
|------|------|---------|---------|
| macOS | `start-scripts/macos/` | `.command` | Finder 双击 |
| Linux | `start-scripts/linux/` | `.sh` | 终端运行 `bash xxx.sh` |
| Windows | `start-scripts/windows/` | `.bat` | 双击运行（自动检测 conda，不存在则使用 venv） |

共提供 6 个功能变体：

| 脚本 | 翻译器 | 模式 | 说明 |
|------|--------|------|------|
| `批量日中翻译` | 交互选择 | a/b 选择 | **推荐首次使用**，运行时选择降级或 Galtransl |
| `批量日中翻译-sakura-qwen3` | Sakura Qwen2.5 | degraded | B→A 降级，优先 GGUF |
| `批量日中翻译-sakura-galtrans` | Galtransl 14B | galtransl | 方式C，R18 友好 |
| `批量日中翻译-sakura-galtrans-全量翻译` | Galtransl 14B | galtransl + RETRANS=true | 全部重新翻译 |
| `批量日中翻译-sakura-galtrans-续传翻译` | Galtransl 14B | galtransl + RETRANS=false | 仅翻译新增图片 |
| `批量韩中翻译` | Qwen3 14B | Ollama HTTP | 韩文→简体中文 |

## 翻译器选择

启动时双击 `start-scripts/macos/` 目录下对应的 `.command` 脚本（macOS），或 `start-scripts/linux/*.sh`（Linux），或 `start-scripts/windows/*.bat`（Windows），会提示选择翻译模式：

```
请选择翻译模式:
  a) 降级方式 (B→A fallback, 优先Sakura GGUF)
  b) 方式C (Galtransl GGUF, R18友好)
```

## 翻译器降级链 (选项a)

启动时自动按优先级选择翻译器：

```
方式B (本地 GGUF) → 方式A (Ollama HTTP) → 报错退出
```

| 优先级 | 方式 | 触发条件 | 说明 |
|--------|------|---------|------|
| 1 (默认) | 方式B (GGUF) | `SAKURA_GGUF_PATH` 指向有效 .gguf 文件 | GPU 直连，单例常驻显存 |
| 2 (降级) | 方式A (Ollama) | GGUF 不可用 + Ollama `/api/tags` 可达 | HTTP API 远程调用 |
| - | 报错退出 | 两者都不可用 | 提示用户设置环境变量 |

探测时机：批处理启动时（`batch_translate` 入口），选定后整个批次使用同一翻译器。

## 方式C (选项b) - Galtransl GGUF

基于 Sakura-GalTransl-14B-v3.8，专为视觉小说/Galgame 翻译优化，对 R18 内容翻译支持更好。

- **不可用则不降级**，直接报错退出
- 使用 GalTransl v3 视觉小说翻译模型 prompt 模板
- 推理参数：temperature=0.3, top_p=0.8

## 环境变量配置

```bash
# 方式B: 本地 Sakura GGUF 直连 GPU
export SAKURA_GGUF_PATH="$HOME/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf"

# 方式C: 本地 Galtransl GGUF 直连 GPU
export GALTRANS_GGUF_PATH="$HOME/.ollama/models/gguf/Sakura-Galtransl-14B-v3.8-Q4_K_M.gguf"

# 方式A (降级): Ollama HTTP 远程服务
export SAKURA_API_BASE='http://localhost:11434/v1'
export SAKURA_MODEL='sakura-14b-qwen2.5-v1.0'
```

> `.command`/`.sh`/`.bat` 脚本已预设上述配置，双击即可启动。

## 方式B 使用

```bash
export SAKURA_GGUF_PATH="$HOME/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf"

# 翻译单页
python -m manga_translator --mode local -i input.jpg -o output.png \
  --translator sakura --use-gpu-limited

# 翻译目录（逐页）
python -m manga_translator --mode local -i chapter-13/ -o output/ \
  --translator sakura --use-gpu-limited
```

## 方式C 使用

```bash
export GALTRANS_GGUF_PATH="$HOME/.ollama/models/gguf/Sakura-Galtransl-14B-v3.8-Q4_K_M.gguf"
export TRANSLATOR_MODE=galtransl

# 翻译目录
python -m manga_translator.batch
```

## 方式C 可选配置

```bash
export GALTRANS_GGUF_N_GPU_LAYERS=-1   # GPU 层数，-1=全部（默认）
export GALTRANS_GGUF_N_CTX=4096        # 上下文长度（默认）
```

## 性能对比

### 157页全量对比（第13话，2026-06-10 实测）

| 阶段 | 方式A (Ollama) | 方式B (GGUF) | B 优势 |
|------|---------------|-------------|--------|
| 总耗时 | 1061.5s (17.7 min) | 988.8s (16.5 min) | 快 6.8% |
| 平均每页 | 6.8s | 6.3s | 快 7.4% |
| 翻译阶段 | 483.1s (45.5%) | 407.0s (41.2%) | **快 15.8%** |
| 平均翻译/页 | 3.2s | 2.7s | 每页省 0.5s |
| 稳定性 CV | 0.45 | 0.31 | 更稳定 |
| 异常慢页 (>8s) | 15 页 | 8 页 | 减半 |

### 12页 E2E 对比（2026-06-19 实测）

| 模式 | 总耗时 | 平均/页 | 成功率 |
|------|--------|---------|--------|
| 方式B (Sakura GGUF) | 104.2s | 8.7s | 12/12 |
| 方式C (Galtransl GGUF) | 105.2s | 8.8s | 12/12 |

**结论**: 方式B 和方式C 速度差异 <1%，方式C 对 R18 内容翻译支持更好。

## Overwrite 与续传行为

**overwrite 始终为 True**：无论 `retrans=True` 还是 `retrans=False`，目标目录的图片都会被覆盖。不存在"跳过已存在文件"的情况。

**续传逻辑**：
- `retrans=False`：跳过 progress 文件中已记录的图片，只翻译新图片
- `retrans=True`：无视 progress 记录，所有图片全部重翻

**关键变化**：
- **目标文件存在性不再参与判断**——即使目标文件已存在，只要 progress 没有记录，就会重新翻译
- **翻译结果全部为空时不记录 progress**——如果 OCR 检测到原文但模型返回空结果（如 R18 内容被审查），progress 不会被写入，下次续传时该图片仍会被处理

## 测试

```bash
# 单元测试
python -m pytest test/unit/ -v

# 端到端测试（首次/续传/重翻 3 场景）
SAKURA_GGUF_PATH=... python test/e2e_gguf_2img.py         # 方式B
TRANSLATOR_MODE=galtransl GALTRANS_GGUF_PATH=... python test/e2e_galtransl_2img.py  # 方式C

# 旧版端到端测试（单次翻译）
python test/e2e_gguf.py         # 方式B (GGUF)
python test/e2e_ollama.py       # 方式A (Ollama)
python test/e2e_galtransl.py    # 方式C (Galtransl) - 直接模型测试
```

## 注意事项

- GGUF 模型文件约 8.5GB，首次加载 10 秒
- 模型加载后常驻显存（单例），进程退出时自动释放
- 本机统一内存 64GB，同时运行检测/OCR/擦除模型 + GGUF 翻译模型绰绰有余
- 方式B/C 使用 `llama-cpp-python`，需已安装：`CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python`
- 方式C 使用 GalTransl v3 prompt 模板，与方式B 的轻小说风格不同