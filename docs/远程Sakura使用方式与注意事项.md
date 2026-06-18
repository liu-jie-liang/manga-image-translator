# Sakura-14B-Qwen2.5 使用方式与注意事项

---

## 一、环境说明

| 项目 | 详情 |
|------|------|
| 服务器地址 | http://192.168.1.12:8080 |
| 模型文件 | sakura-14b-qwen2.5-v1.0-q4_k_m.gguf |
| 量化方式 | Q4_K_M（4bit量化） |
| GPU 显存 | 12GB（模型占用 ~11GB，剩余 ~1GB） |
| 并行数(np) | 1（严格串行） |
| 上下文长度 | 2048 tokens |
| KV Cache | f16 精度 |
| 启动脚本 | `01_2K_NP1.bat` |

---

## 二、API 调用方式

### 2.1 接口地址

```
POST http://192.168.1.12:8080/v1/chat/completions
```

### 2.2 推荐请求参数

```json
{
    "messages": [
        {
            "role": "system",
            "content": "你是一个专业的日译中翻译模型，请将输入的日文准确翻译成简体中文。只输出译文，不要添加任何解释。"
        },
        {
            "role": "user",
            "content": "<日文原文>"
        }
    ],
    "temperature": 0.1,
    "top_p": 0.3,
    "max_tokens": 512,
    "stream": false
}
```

### 2.3 Python 示例

```python
import requests

def translate(japanese_text: str, base_url: str = "http://192.168.1.12:8080") -> str:
    """调用 Sakura 模型翻译日文→中文"""
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "你是一个专业的日译中翻译模型，请将输入的日文准确翻译成简体中文。只输出译文，不要添加任何解释。"
            },
            {
                "role": "user",
                "content": japanese_text
            }
        ],
        "temperature": 0.1,
        "top_p": 0.3,
        "max_tokens": 512,
        "stream": False,
    }
    r = requests.post(f"{base_url}/v1/chat/completions", json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"].strip()

# 使用
result = translate("おはようございます、今日はいい天気ですね。")
print(result)  # → 早上好，今天天气不错呢。
```

### 2.4 其他有用接口

```bash
# 健康检查
GET http://192.168.1.12:8080/health

# 服务器指标（包含 KV Cache 占用率等）
GET http://192.168.1.12:8080/metrics

# 模型属性
GET http://192.168.1.12:8080/props
```

---

## 三、核心注意事项

### 3.1 必须加 system prompt

模型在无翻译指令时会进入"故事生成/续写"模式，产生无意义的重复输出（"…………"）。

**正确做法：** 始终带上 system prompt（见 2.2 节）。

### 3.2 严格串行调用

当前配置 `np=1`，仅支持 1 个并行请求。

**正确做法：**
```python
# 一条一条串行调用
for text in japanese_texts:
    result = translate(text)
    process(result)
```

**错误做法：**
```python
# 不要并发调用
import concurrent.futures
with concurrent.futures.ThreadPoolExecutor(max_workers=N) as executor:
    futures = [executor.submit(translate, text) for text in japanese_texts]
    # 并发请求会排队等待，第二个请求会报错或被延迟
```

### 3.3 控制输入长度

- 上下文限制为 **2048 tokens**（不含生成的 completion tokens）
- system prompt 约占 40~50 tokens
- 实际留给日文原文的 token 约 1900~2000 tokens
- 日文约 **1.5~2 字/token**，即单次最多翻译约 **1000~1400 字**日文
- 超出部分会被截断

### 3.4 不要调大 np 参数

- `np` 控制并行处理 slot 数，每增加 1 个 slot 多一份 KV cache（~336MB）
- 当前剩余显存仅 ~1GB，np=2 时 2 份 KV cache + 推理 buffer 可能超限
- **保持在 np=1**

### 3.5 不要随意扩大上下文

| 上下文 | KV Cache 占用 | 风险 |
|--------|-------------|------|
| 2048 (当前) | ~336MB | 安全 |
| 4096 | ~672MB | 低风险 |
| 8192 | ~1.3GB | **高风险** |

### 3.6 监控显存使用

定期检查 metrics 接口，关注 KV cache 占用率：

```python
import requests

metrics = requests.get("http://192.168.1.12:8080/metrics").text
for line in metrics.split("\n"):
    if "kv_cache_usage_ratio" in line:
        ratio = float(line.split()[-1])
        print(f"KV Cache 占用率: {ratio*100:.1f}%")
        if ratio > 0.8:
            print("[WARN] KV Cache 接近满载!")
```

### 3.7 清理旧 KV Cache

每个翻译请求完成后，llama.cpp server 会自动清理该 slot 的 KV cache，空出空间给下一个请求。无需手动处理。

但如果某些请求 token 数接近或超过 2048 限制，可能出现 token 驱逐导致翻译质量下降。

---

## 四、性能预期

| 场景 | 预期速度 | 典型耗时 |
|------|---------|---------|
| 短句（~20字日文） | 33~48 tok/s | 0.2~0.3s |
| 中句（~50字日文） | 54 tok/s | 0.4~0.5s |
| 长句（~90字日文） | 55 tok/s | 0.7~1.0s |
| 段落（~200字日文） | 56 tok/s | 1.5~2.0s |

---

## 五、扩展上下文长度

如果确实需要更长的上下文（如处理超长段落），有两种方案：

### 方案A：调大上下文（需谨慎）

编辑 `01_2K_NP1.bat`，修改：
```batch
set pctx=4096   REM 从 2048 改为 4096
```

然后重启服务。注意监控显存使用。

### 方案B：分段翻译（推荐）

将长文本按句号/换行切分，逐段送入翻译，最后拼接：

```python
def translate_long(text: str) -> str:
    """分段翻译长文本"""
    sentences = text.replace("。", "。\n").split("\n")
    results = []
    for sent in sentences:
        if sent.strip():
            results.append(translate(sent.strip()))
    return "".join(results)
```

---

## 六、故障排查

| 现象 | 可能原因 | 解决 |
|------|---------|------|
| 翻译输出"……"无限重复 | 缺少 system prompt | 添加翻译 system prompt |
| 返回空内容 | prompt 格式不对 | 使用 `/v1/chat/completions` 而非 `/v1/completions` |
| 请求超时 | max_tokens 过大 | 减小 max_tokens（建议 ≤512） |
| 返回错误 | 并发请求冲突 | 确保串行调用，一次只发一个请求 |
| 翻译截断 | 输入超出上下文 | 减小输入文本长度或分段翻译 |
| 服务无响应 | 进程崩溃 | 检查显存是否溢出，查看终端日志 |