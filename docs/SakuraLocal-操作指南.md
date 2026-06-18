# 日中漫画批量翻译 操作指南

## 翻译器降级链

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

## 环境变量配置

```bash
# 方式B (推荐): 本地 GGUF 直连 GPU
export SAKURA_GGUF_PATH="$HOME/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf"

# 方式A (降级): Ollama HTTP 远程服务
export SAKURA_API_BASE='http://192.168.1.15:11434/v1'
export SAKURA_MODEL='sakura-14b-qwen2.5-v1.0'
```

> `.command` 脚本已预设上述配置，双击即可启动。

## 方式B 使用

```bash
export SAKURA_GGUF_PATH=/Users/liujieliang/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf

# 翻译单页
python -m manga_translator --mode local -i input.jpg -o output.png \
  --translator sakura --use-gpu-limited

# 翻译目录（逐页）
python -m manga_translator --mode local -i chapter-13/ -o output/ \
  --translator sakura --use-gpu-limited
```

## 方式B 可选配置

```bash
export SAKURA_GGUF_N_GPU_LAYERS=-1   # GPU 层数，-1=全部（默认）
export SAKURA_GGUF_N_CTX=4096        # 上下文长度（默认）
export SAKURA_VERSION=0.9            # Prompt 版本
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

### 30页 E2E 对比（2026-06-11 实测）

| 模式 | 总耗时 | 平均/页 | 成功率 |
|------|--------|---------|--------|
| 方式B (GGUF) | 223.7s (3.7 min) | 7.5s | 30/30 |
| 方式A (Ollama) | 232.9s (3.9 min) | 7.8s | 30/30 |

**结论**: 方式B 在速度、稳定性、质量三个维度均优于方式A。推荐生产环境使用方式B。

## 测试

```bash
# 单元测试
python -m pytest test/unit/ -v

# 端到端测试
python test/e2e_gguf.py      # 方式B (GGUF) - 30页
python test/e2e_ollama.py    # 方式A (Ollama) - 30页
```

## 注意事项

- GGUF 模型文件约 8.5GB，首次加载 10 秒
- 模型加载后常驻显存（单例），进程退出时自动释放
- 本机统一内存 64GB，同时运行检测/OCR/擦除模型 + GGUF 翻译模型绰绰有余
- 方式B 使用 `llama-cpp-python`，需已安装：`CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python`