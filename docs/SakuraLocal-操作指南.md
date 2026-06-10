# Sakura 本地 GGUF 翻译 (方式B) 操作指南

## 方式选择

| 方式 | 环境变量 | 说明 |
|------|---------|------|
| A (Ollama HTTP) | 不设置 `SAKURA_GGUF_PATH` | 默认，向后兼容，依赖 Ollama 服务 |
| B (本地 GGUF) | 设置 `SAKURA_GGUF_PATH` | GPU 直连，单例常驻显存，不依赖外部服务 |

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

## 可选配置

```bash
export SAKURA_GGUF_N_GPU_LAYERS=-1   # GPU 层数，-1=全部（默认）
export SAKURA_GGUF_N_CTX=4096        # 上下文长度（默认）
export SAKURA_VERSION=0.9            # Prompt 版本
```

## 性能对比 (157页实测)

| 阶段 | 方式A (Ollama) | 方式B (GGUF) | B 优势 |
|------|---------------|-------------|--------|
| 总耗时 | 1061.5s (17.7 min) | 988.8s (16.5 min) | 快 6.8% |
| 平均每页 | 6.8s | 6.3s | 快 7.4% |
| 翻译阶段 | 483.1s (45.5%) | 407.0s (41.2%) | **快 15.8%** |
| 平均翻译/页 | 3.2s | 2.7s | 每页省 0.5s |
| 稳定性 CV | 0.45 | 0.31 | 更稳定 |
| 异常慢页 (>8s) | 15 页 | 8 页 | 减半 |

**结论**: 方式B 在速度、稳定性、质量三个维度均优于方式A。推荐生产环境使用方式B。

## 测试

```bash
# 单元测试
python -m pytest test/unit/test_sakura_local.py -v

# A/B 对比 benchmark
python test/benchmark.py 30                    # 方式A
SAKURA_GGUF_PATH=... python test/benchmark_sakura_local.py 30  # 方式B
```

## 注意事项

- GGUF 模型文件约 8.5GB，首次加载 10 秒
- 模型加载后常驻显存（单例），进程退出时自动释放
- 本机统一内存 64GB，同时运行检测/OCR/擦除模型 + GGUF 翻译模型，绰绰有余
- 方式B 使用 `llama-cpp-python`，需已安装：`CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python`