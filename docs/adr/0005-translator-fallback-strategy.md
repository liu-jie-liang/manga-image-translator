# ADR-0005: 翻译器降级链策略

## 状态

已验证 (Verified)

**验证日期**: 2026-06-12  
**验证方式**: 158 页 E2E 实测（`test/e2e-materials/`），分别以方式B (GGUF) 和 方式A (Ollama) 运行完整翻译流水线。  
**验证结果**: 
- 方式B: 158/158 成功，973.9s (16.2 min)，平均 6.2s/页
- 方式A: 158/158 成功，965.4s (16.1 min)，平均 6.1s/页
- 降级链自动选择逻辑正确：设置 `SAKURA_GGUF_PATH` 时命中方式B，取消设置时降级到方式A
- 两种方式速度差异 <1%，在测量误差范围内

## 背景

日中漫画翻译主链路需要支持三种翻译模型调用方式：

1. **方式B (本地 GGUF 直连)**：`SakuraLocalTranslator`，通过 `llama-cpp-python` 直连 GPU(MPS) 运行本地 GGUF 量化模型。速度快、稳定性高、离线可用。
2. **方式A (Ollama HTTP)**：`SakuraTranslator`，通过 OpenAI 兼容 API 调用远程 Ollama 部署的 sakura-14b 模型。速度略慢于方式B，有网络波动风险。
3. **Sugoi (ctranslate2 本地)**：`SugoiTranslator`，基于 ctranslate2 运行 m2m100/jparacrawl 模型。**仅支持 JPN↔ENG 翻译，不支持 ja→zh-cn**，因此排除在日中漫画翻译降级链之外。

需要一种机制，在运行时自动选择最优翻译器，并在不可用时优雅降级。

## 决策

### 降级优先级

```
方式B (GGUF 本地) → 方式A (Ollama 远程) → 报错退出（无可用翻译器）
```

### 降级粒度：会话级

整个批次（batch session）使用同一个翻译器。启动时探测一次，选定后不再切换。

**理由**：
- 方式B 和方式A 共享相同的 Prompt 模板和输出解析逻辑，翻译质量一致
- 翻译器实例化（模型加载/HTTP 连接）有固定开销，频繁切换无意义
- 会话级选择避免了请求级失败时的复杂重试和状态管理

### 探测逻辑

#### 方式B 探测：文件存在性检查

```python
def _probe_gguf() -> bool:
    """GGUF 模型文件是否存在。"""
    path = os.environ.get('SAKURA_GGUF_PATH')
    return path is not None and os.path.isfile(path)
```

#### 方式A 探测：HTTP 可达性检查

```python
async def _probe_ollama() -> bool:
    """Ollama API 服务是否可达。"""
    base = os.environ.get('SAKURA_API_BASE', 'http://localhost:11434')
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{base}/api/tags', timeout=aiohttp.ClientTimeout(total=3)) as resp:
                return resp.status == 200
    except Exception:
        return False
```

### 降级选择入口

所有探测和选择逻辑集中在 `batch.py` 的 `_detect_translator_mode()` 函数中：

```python
async def _detect_translator_mode() -> str:
    """返回翻译器模式: 'gguf' | 'ollama' | None(报错)"""
    if _probe_gguf():
        return 'gguf'
    if await _probe_ollama():
        return 'ollama'
    return None  # 无可用翻译器，报错退出
```

## 后果

### 正面影响

1. **用户体验**：只需设置环境变量或双击 `.command`，程序自动选择最佳翻译器
2. **容错性**：方式B 模型文件被误删时自动降级到方式A
3. **可测试性**：探测逻辑独立为可 mock 的函数，支持单元测试
4. **最小代码修改**：不改变 `TRANSLATORS` 字典的现有分派逻辑，仅在 `batch.py` 层增加探测

### 负面影响

1. **启动延迟**：增加 Ollama HTTP 探测（最多 3 秒超时），首次启动慢 0-3 秒
2. **网络依赖**：方式B 文件存在时也需探测方式A（用于降级），但方式B 文件存在时直接跳过 HTTP 探测（短路求值），无额外开销

### 风险

1. Ollama 探测超时 3 秒可能不够（网络极差时），但 3 秒是合理的用户等待上限
2. 探测成功后翻译过程中 Ollama 可能崩溃，但这是请求级问题，不属于降级策略范畴

## 参考资料

- ADR-0004: 本地 GGUF 直连 GPU 翻译
- `batch.py` 的 `_load_models()` 和 `BATCH_PARAMS`
- `translators/__init__.py` 的 `TRANSLATORS` 字典和 `get_translator()`