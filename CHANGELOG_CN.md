# 更新日志 (中文)

### 2026-07-05

1. 单元测试全面重构：从 153 增至 218 个单测，覆盖方式A (Sakura Ollama)、方式B (Sakura GGUF)、方式C (Galtransl GGUF)、韩中 (Qwen3 Ollama) 全链路
2. 修复 `_has_text_content` 返回类型、`re.sub` None 崩溃、`kernel_size` 无默认值 3 个防御性 bug
3. Windows 支持增强：修复 SIGTERM/os.chmod/psutil 等 4 个 BLOCKING bug，.bat 加入 conda→venv→系统 Python 三级 fallback
4. 跨平台可移植性：消除 15+ 个文件中硬编码的个人 IP/路径/conda 环境名，全部改为环境变量读取
5. 开源发布打磨：四轮审查修复 20+ 项问题，git filter-branch 清除 676 张版权图片历史，依赖按场景分包
6. 启动脚本跨平台重组：18 个启动脚本按 `macos/`/`linux/`/`windows/` 组织

### 2026-06-25

1. 续传/Overwrite 优化：overwrite 强制 True，空翻译结果不污染 progress，方式B/C E2E 全链路 6/6 通过
2. 代码审查修复：`_should_record_progress` 从 `hasattr` 改为字典 `in` 检查，`translated_count` 统计修正

### 2026-06-19

1. 新增方式C翻译器：集成 Sakura-GalTransl-14B-v3.8 本地 GGUF 模型，专为视觉小说/Galgame 翻译优化
2. R18 翻译优化：Sakura Prompt 添加越狱提示，支持 R18 内容直接翻译，不再返回空白
3. 批量翻译入口新增交互式翻译模式选择：降级方式 (B→A) 或 方式C (Galtransl)

### 2026-06-18

1. 新增韩中翻译链路：Qwen3 14B 韩中翻译器 + batch_ko.py 批量编排 + 45 个韩中单测
2. 韩中翻译性能修复：从 OpenAI 兼容端点切换至 Ollama 原生 /api/chat，禁用 thinking 模式，2.1→8.8 页/分钟（提速 4.2 倍）

### 2026-06-11

1. 批量翻译 TDD 重构：抽取 batch.py 批量编排层，支持非递归扫描、目录排序、中断续传、模型单例复用

### 2026-06-10

1. GGUF 本地直连 GPU (方式B)：使用 llama-cpp-python 跳过 HTTP 层，翻译阶段快 15.8%，CV 从 0.45 降至 0.31
