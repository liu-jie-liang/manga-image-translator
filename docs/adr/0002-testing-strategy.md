# ADR-0002: 自动化测试规范

## 状态

已提案 (Proposed)

## 背景

当前项目测试覆盖极低：
- [test_translation.py](file:///Users/liujieliang/Downloads/GitHub/manga-image-translator/test/test_translation.py) — 仅4个pytest用例，且依赖真实API Key
- [test_translation_manual.py](file:///Users/liujieliang/Downloads/GitHub/manga-image-translator/test/test_translation_manual.py) — 手动测试脚本，非自动化
- [test_textline_merge.py](file:///Users/liujieliang/Downloads/GitHub/manga-image-translator/test/test_textline_merge.py) — 有测试但只有1个
- [test_render.py](file:///Users/liujieliang/Downloads/GitHub/manga-image-translator/test/test_render.py) — 渲染测试

缺乏对核心翻译管道、滑动窗口逻辑的单元测试。

## 决策

建立分层测试体系，采用 pytest + pytest-asyncio 框架。

### 测试层级

```
test/
├── unit/                    # 单元测试（无外部依赖）
│   ├── test_sliding_window.py     # 滑动窗口核心逻辑
│   ├── test_prompt_assembly.py    # Prompt 组装
│   ├── test_response_parse.py     # 响应解析
│   └── test_window_calc.py        # 窗口计算逻辑
├── integration/             # 集成测试（Mock API）
│   ├── test_sliding_window_integration.py
│   └── conftest.py                # Mock fixtures
└── fixtures/                # 测试数据
    └── ocr_fixtures.py           # Mock OCR 结果
```

### 单元测试规范

#### 1. 滑动窗口模块 (`test/unit/test_sliding_window.py`)

测试 `manga_translator/sliding_window.py` 的核心函数：

```python
# 窗口划分
def test_window_partition():
    """测试将N页划分为滑动窗口"""
    windows = partition_windows(total_pages=10, window_size=5)
    assert windows == [(1,5), (2,6), (3,7), (4,8), (5,9), (6,10)]

def test_window_partition_edge_cases():
    """边界情况：少于窗口大小的页数"""
    assert partition_windows(3, 5) == [(1,3)]    # 3页<5，单窗
    assert partition_windows(5, 5) == [(1,5)]    # 刚好5页
    assert partition_windows(1, 5) == [(1,1)]    # 只有1页

# 渲染页映射
def test_render_pages():
    """测试每个窗口应该渲染哪些页"""
    assert render_pages_for_window((1,5), 10, 5) == [1,2,3]   # 首窗
    assert render_pages_for_window((2,6), 10, 5) == [4]       # 中间窗
    assert render_pages_for_window((3,7), 10, 5) == [5]       # 中间窗
    assert render_pages_for_window((6,10), 10, 5) == [8,9,10] # 末窗

# Prompt 组装
def test_assemble_sliding_prompt():
    """将多页OCR结果组装成滑动窗口prompt"""
    pages = {
        1: ["こんにちは", "元気ですか"],
        2: ["はい"],
        3: ["またね"],
        4: [],
        5: ["ありがとう"]
    }
    prompt = assemble_sliding_prompt(pages, window=(1,5))
    assert "|||" in prompt
    assert "<|1|>こんにちは" in prompt
    assert "<|2|>元気ですか" in prompt
    assert "<|3|>はい" in prompt
    # 第四页无文本，分隔符保留
    assert prompt.count("|||") >= 3  # 至少3个分隔符（页之间）

# 响应解析
def test_parse_sliding_response():
    """从LLM响应中提取每个<|N|>标记的翻译"""
    response = "<|1|>Hello\n<|2|>How are you\n<|3|>Yes\n<|4|>Bye\n<|5|>Thanks"
    translations = parse_sliding_response(response, expected_count=5)
    assert translations == ["Hello", "How are you", "Yes", "Bye", "Thanks"]

def test_parse_sliding_response_partial():
    """处理LLM返回不完整的情况"""
    response = "<|1|>Hello\n<|2|>How are you"  # 只返回前2个
    translations = parse_sliding_response(response, expected_count=5)
    assert translations[0] == "Hello"
    assert translations[1] == "How are you"
    assert translations[2] == ""  # 缺失的填空
```

#### 2. Prompt 组装 (`test/unit/test_prompt_assembly.py`)

```python
def test_global_id_assignment():
    """测试跨页的全局ID分配"""
    pages_ocr = {
        1: ["a", "b", "c"],
        2: ["d"],
        3: ["e", "f"]
    }
    id_map, prompt = assign_global_ids(pages_ocr)
    # 页1: IDs 0-2, 页2: ID 3, 页3: IDs 4-5
    assert id_map[1] == (0, 3)
    assert id_map[2] == (3, 1)
    assert id_map[3] == (4, 2)

def test_page_mapping():
    """测试从全局ID反向映射回页号和文本框索引"""
    id_to_page = build_id_to_page_map({1:3, 2:1, 3:2})  # 页1有3个框，页2有1个，页3有2个
    assert id_to_page[0] == (1, 0)
    assert id_to_page[2] == (1, 2)
    assert id_to_page[3] == (2, 0)
    assert id_to_page[4] == (3, 0)
    assert id_to_page[5] == (3, 1)
```

#### 3. 响应解析 (`test/unit/test_response_parse.py`)

```python
def test_robust_parse_with_noise():
    """测试带噪音标记的解析"""
    response = "some noise <|1|>Hello\nmore noise<|2|>World\nend"
    translations = parse_sliding_response(response, expected_count=2)
    assert translations == ["Hello", "World"]

def test_parse_with_missing_ids():
    """跳过的ID"""
    response = "<|1|>A\n<|3|>C"  # ID 2 缺失
    translations = parse_sliding_response(response, expected_count=3)
    assert translations[0] == "A"
    assert translations[1] == ""  # ID 2 使用原文或空
    assert translations[2] == "C"

def test_parse_empty_response():
    assert parse_sliding_response("", expected_count=3) == ["", "", ""]
```

### 集成测试规范

使用 `unittest.mock` patch 掉翻译 API 调用，测试完整滑动窗口流水线：

```python
@pytest.mark.asyncio
async def test_sliding_window_integration():
    """集成测试：10页漫画完整滑动窗口翻译"""
    pages_ocr = create_mock_ocr_pages(10, texts_per_page=3)
    
    with patch('manga_translator.sliding_window.dispatch_translation') as mock_dispatch:
        # Mock 翻译服务返回
        mock_dispatch.return_value = create_mock_translations()
        
        results = await translate_with_sliding_window(
            pages_ocr, window_size=5,
            translator_chain=TranslatorChain('custom_openai:CHS')
        )
        
        # 验证所有页都有翻译
        assert len(results) == 10
        
        # 验证窗口调用次数
        assert mock_dispatch.call_count == 6  # 10页→6窗

@pytest.mark.asyncio  
async def test_sliding_window_with_sakura():
    """集成测试：使用sakura模型的滑动窗口翻译"""
    # 使用真实ollama API（需要ollama运行中）
    pages_ocr = create_mock_ocr_pages(5, texts_per_page=2)
    
    # 不Mock，真实调用（需要环境变量配置）
    config = SlidingWindowConfig(
        window_size=5,
        model='sakura-14b-qwen2.5-v1.0:latest'
    )
    results = await translate_with_sliding_window(pages_ocr, config)
    assert len(results) == 5
```

### 测试数据规范

`test/fixtures/ocr_fixtures.py`：
```python
def create_mock_ocr_pages(num_pages, texts_per_page=3):
    """生成模拟OCR结果"""
    pages = {}
    for p in range(1, num_pages+1):
        pages[p] = [f"第{p}页文本{i+1}" for i in range(texts_per_page)]
    return pages

def create_mock_translations():
    """生成模拟翻译结果"""
    ...
```

### 运行命令

```bash
# 单元测试（无外部依赖，快速）
pytest test/unit/ -v

# 集成测试（需要ollama运行）
pytest test/integration/ -v --run-slow

# 所有测试
pytest test/ -v

# 带覆盖率
pytest test/unit/ --cov=manga_translator/sliding_window --cov-report=html
```

### 必须测试的边界情况

| 场景 | 输入 | 预期 |
|------|------|------|
| 空OCR结果 | 某些页无文本 | 跳过或生成空翻译 |
| 单页漫画 | total_pages=1 | 窗口 = [(1,1)], 直接翻译 |
| 窗口大小>总页数 | window=10, pages=3 | 单窗覆盖全部 |
| LLM返回不完整 | 返回tokens少于输入 | 缺失项用原文填充 |
| LLM返回超量 | 返回tokens多于输入 | 截断多余项 |
| 特殊字符 | 文本含`\|\|\|` | 转义处理 |
| 并发请求 | 多语言链 | 串行窗口保证顺序 |

## 影响

### 不测试的内容
- OCR 模型推理（属于上游依赖）
- PyTorch 模型加载（框架层面）
- 渲染输出图片的像素级对比

### 测试覆盖率目标
- 滑动窗口核心逻辑 ≥ 90%
- Prompt 组装/解析 ≥ 95%
- 集成测试覆盖主要翻译流程

## 参考资料

- 现有测试：[test_translation.py](file:///Users/liujieliang/Downloads/GitHub/manga-image-translator/test/test_translation.py)
- pytest-asyncio: https://pytest-asyncio.readthedocs.io/