# ADR-0003: CPU/GPU 设备使用分析与优化

## 状态

已提案 (Proposed)

## 设备分配现状

代码入口：[manga_translator.py#L290](../../manga_translator/manga_translator.py#L290)

```python
device = 'mps' if torch.backends.mps.is_available() else 'cuda'
self.device = device if params.get('use_gpu', False) else 'cpu'
```

### 各阶段设备分配

| 流水线阶段 | 默认设备 | `--use-gpu` | `--use-gpu-limited` | 所在代码行 |
|-----------|---------|-------------|---------------------|-----------|
| Detection | CPU | MPS/GPU | MPS/GPU | L693 |
| OCR | CPU | MPS/GPU | MPS/GPU | L753 |
| Textline Merge | N/A (算法) | N/A | N/A | - |
| Translation (API) | N/A (网络) | N/A | N/A | L1055 |
| Translation (本地) | CPU | MPS/GPU | **CPU** (强制) | L1055, L2341 |
| Inpainting | CPU | MPS/GPU | MPS/GPU | L1362 |
| Upscaling | CPU | MPS/GPU | MPS/GPU | L684 |
| Colorization | CPU | MPS/GPU | MPS/GPU | L440 |

### 硬件现状

| 指标 | 值 |
|------|-----|
| CPU | Apple M4 Pro (14核) |
| GPU | 集成 GPU (统一内存架构) |
| RAM | 64 GB (CPU/GPU 共享) |
| Ollama 模型 | 9 GB (Q4_K_M), num_gpu=999 |

## 决策

### 推荐配置：启用 `--use-gpu`（不使用 `--use-gpu-limited`）

理由：
1. **M4 Pro 64GB 统一内存**：足够同时加载 detection (~500MB) + OCR (~300MB) + inpainting (~500MB) + Ollama 模型 (~9GB)，总计约 10.5GB，剩余约 53.5GB
2. **Apple MPS 性能**：Metal Performance Shaders 在 M4 Pro 上的矩阵运算速度远高于 CPU
3. **Ollama 翻译不受影响**：Ollama API 翻译走网络，设备参数不影响翻译阶段

### 不稳定的根因分析

MPS (Metal Performance Shaders) 在 PyTorch 上存在已知稳定性问题：

| 问题 | 描述 | 影响阶段 |
|------|------|---------|
| MPS 内存碎片 | 多次模型加载/卸载后 MPS 内存无法完全释放 | Detection |
| float64 不支持 | MPS 不完全支持 float64 运算 | OCR |
| 并发限制 | MPS 不支持多流并发 | 全局 |
| MPS fallback | 不支持的 op 会 fallback 到 CPU，但 torch 可能不警告 | 随机阶段 |

### 稳定性优化策略

1. **不启用 `--use-gpu-limited`**：避免翻译本地模型被强制切到 CPU 造成速度抖动
2. **加 MPS 内存清理**：每页翻译后调用 `torch.mps.empty_cache()` + `gc.collect()`
3. **OCR 强制 float32**：检查 OCR 模型输入 dtype
4. **Detection 单例复用**：避免重复加载/卸载检测模型
5. **可选 CPU fallback**：当 MPS OOM 时自动回退到 CPU

### 当前项目的 MPS 清理代码

[local.py#L55-L71](../../manga_translator/mode/local.py#L55-L71) 已有 `force_cleanup()`，但只处理 CUDA：

```python
def force_cleanup():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
```

**需要补充 MPS 清理**：
```python
def force_cleanup():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()  # ← 新增
```

## 影响

- `--use-gpu` 启用后，Detection 速度预期提升 3-5x
- OCR 速度预期提升 2-3x
- Inpainting 速度预期提升 3-5x
- MPS 稳定性通过清理策略改善

## 参考资料

- 设备检测代码：[manga_translator.py#L288-L300](../../manga_translator/manga_translator.py#L288-L300)
- 现有清理代码：[local.py#L55-L71](../../manga_translator/mode/local.py#L55-L71)