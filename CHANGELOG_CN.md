# 更新日志 (中文)

### 2026-07-05

1. 单元测试全面重构：拆分 `test_batch_common.py`（与 4 个文件重复），新建 `test_batch.py`、`test_mode_local.py`、`test_sakura.py`、`test_custom_openai.py` 四个测试文件，覆盖全四种翻译方式
2. 修复 `_has_text_content` 返回类型不一致问题（`bool()` 包装），确保始终返回 True/False
3. 修复 `custom_openai.py` 中 `re.sub(None)` 崩溃问题（`extract_capture_groups` 返回 None 时加空字符串防护）
4. 修复 `manga_translator.py` 中 `kernel_size` 无默认值问题（`int(params.get('kernel_size', 3))`）
5. 修复 `test_galtransl_local.py` 中 3 个 `asyncio.get_event_loop()` 异步事件循环问题（改为 `@pytest.mark.asyncio` + `await`）
6. 修复 `test_custom_openai.py` 中 `RateLimitError` 构造参数格式和 `test_empty_queries` 未 mock API 调用问题
7. 修复 `test_batch_progress.py` 中 `TestClearAllProgress` 类注入到 `TestGetUncompletedFiles` 中间的结构 bug
8. 修复 `test_mode_local.py` 中 `MangaTranslatorLocal` 缺少 `kernel_size` 参数问题（6 处）
9. 218 个单元测试全部通过，覆盖方式A (Sakura Ollama)、方式B (Sakura GGUF)、方式C (Galtransl GGUF)、韩中 (Qwen3 Ollama)

### 2026-06-19

1. 新增方式C翻译器：集成 Sakura-GalTransl-14B-v3.8 本地 GGUF 模型，专为视觉小说/Galgame 翻译优化
2. 优化 Sakura 翻译器 Prompt，添加越狱提示以支持 R18 内容直接翻译，不再返回空白
3. 批量翻译入口（`start-scripts/macos/*.command`）新增交互式翻译模式选择：降级方式 (B→A) 或 方式C (Galtransl)
4. 方式C 不可用时不会降级到其他方式，直接报错提示用户
5. 新增 `test/e2e_galtransl.py` 端到端测试脚本
6. 新增 `test/unit/test_galtransl_local.py` 单元测试

### 2023-11-11

1. 添加了新的OCR模型`48px`

### 2023-05-08

1. 添加了[4x-UltraSharp](https://mega.nz/folder/qZRBmaIY#nIG8KyWFcGNTuMX_XNbJ_g)超分辨率

### 2023-04-30

1. 无数bug修复和重构
2. 添加了[CRAFT](https://github.com/clovaai/CRAFT-pytorch)文本检测器，使用`--detector craft`启用

### 2022-06-15

1. 增加了来自[dmMaze](https://github.com/dmMaze)的LaMa MPE图像修补模型

### 2022-04-23

版本更新为beta-0.3

1. 增加了来自[dmMaze](https://github.com/dmMaze)的英语文本渲染器
2. 增加了基于CTC的OCR模型，识别速度大幅提升
3. 新OCR模型增加韩语识别支持

### 2022-03-19

1. 增加了来自[pokedexter](https://github.com/pokedexter)的新文本渲染器
2. 增加了来自[rspreet92](https://github.com/rspreet92)的人工翻译页面

### 2022-01-24

1. 增加了来自[dmMaze](https://github.com/dmMaze)的文本检测模型

### 2021-08-21

1. 文本区域合并算法更新，先已经实现几乎完美文本行合并
2. 增加演示模式百度翻译支持
3. 增加演示模式谷歌翻译支持
4. 各类 bug 修复

### 2021-07-29

1. 网页版增加翻译器、分辨率和目标语言选项
2. 文本颜色提取小腹提升

### 2021-07-26

程序所有组件都大幅升级，本程序现已进入 beta 版本！ \
注意：该版本所有英文检测只会输出大写字母。\
你需要 Python>=3.8 版本才能运行

1. 检测模型升级
2. OCR 模型升级，文本颜色抽取质量大幅提升
3. 图像修补模型升级
4. 文本渲染升级，渲染更快，并支持更高质量的文本和文本阴影渲染
5. 文字掩膜补全算法小幅提升
6. 各类 BUG 修复
7. 默认检测分辨率为 1536

### 2021-07-09

1. 修复不使用 inpainting 时图片错误

### 2021-06-18

1. 增加手动翻译选项
2. 支持倾斜文本的识别和渲染

### 2021-06-13

1. 文字掩膜补全算法更新为基于 CRF 算法，补全质量大幅提升

### 2021-06-10

1. 完善文本渲染

### 2021-06-09

1. 使用基于区域的文本方向检测，文本方向检测效果大幅提升
2. 增加 web 服务功能

### 2021-05-20

1. 检测模型更新为基于 ResNet34 的 DBNet
2. OCR 模型更新增加更多英语预料训练
3. 图像修补模型升级到基于[AOT](https://arxiv.org/abs/2104.01431)的模型，占用更少显存
4. 图像修补默认分辨率增加到 2048
5. 支持多行英语单词合并

### 2021-05-11

1. 增加并默认使用有道翻译

### 2021-05-06

1. 检测模型更新为基于 ResNet101 的 DBNet
2. OCR 模型更新更深
3. 默认检测分辨率增加到 2048

注意这个版本除了英文检测稍微好一些，其他方面都不如之前版本

### 2021-03-04

1. 添加图片修补模型

### 2021-02-17

1. 初步版本发布
