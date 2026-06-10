"""
滑动窗口翻译策略模块 (Sliding Window Translation Module)

核心功能：
- partition_windows: 将 N 页漫画划分为滑动窗口
- render_pages_for_window: 确定每个窗口应渲染的页
- assemble_sliding_prompt: 组装滑动窗口翻译 prompt
- parse_sliding_response: 解析 LLM 响应中的翻译结果
- build_id_to_page_map: 构建全局 ID 到页码的映射

不依赖 manga_translator 其他模块，纯数据结构和算法。
"""

import re
from typing import Dict, List, Tuple


def partition_windows(total_pages: int, window_size: int) -> List[Tuple[int, int]]:
    """
    将 N 页漫画划分为滑动窗口。

    Args:
        total_pages: 总页数
        window_size: 滑动窗口大小（每窗口包含的页数）

    Returns:
        [(start_page, end_page), ...] 窗口列表，页码从1开始

    Raises:
        ValueError: total_pages <= 0 或 window_size <= 0

    Examples:
        >>> partition_windows(10, 5)
        [(1, 5), (2, 6), (3, 7), (4, 8), (5, 9), (6, 10)]
        >>> partition_windows(3, 5)
        [(1, 3)]
    """
    if total_pages <= 0:
        raise ValueError(f"total_pages must be positive, got {total_pages}")
    if window_size <= 0:
        raise ValueError(f"window_size must be positive, got {window_size}")

    if total_pages <= window_size:
        return [(1, total_pages)]

    windows = []
    for i in range(1, total_pages - window_size + 2):
        windows.append((i, i + window_size - 1))
    # 最后一窗确保覆盖到最后一页（防 off-by-one）
    if windows and windows[-1][1] < total_pages:
        windows.append((total_pages - window_size + 1, total_pages))

    return windows


def render_pages_for_window(
    window: Tuple[int, int],
    total_pages: int,
    window_size: int
) -> List[int]:
    """
    确定当前窗口应该渲染哪些页。

    规则：
    - 首窗（start=1）：渲染页1至 (window_size // 2) 页
    - 中间窗：只渲染窗口的中间页
    - 末窗（end=total_pages）：渲染末窗后半部分页
    - 如果只有1个窗口：渲染所有页

    Args:
        window: (start_page, end_page) 当前窗口
        total_pages: 总页数
        window_size: 窗口大小

    Returns:
        要渲染的页码列表

    Examples:
        >>> render_pages_for_window((1, 5), 10, 5)
        [1, 2, 3]
        >>> render_pages_for_window((2, 6), 10, 5)
        [4]
        >>> render_pages_for_window((6, 10), 10, 5)
        [8, 9, 10]
    """
    start, end = window
    middle = start + window_size // 2

    # 如果总页数 <= 窗口大小，只有1个窗口，渲染全部
    if total_pages <= window_size:
        return list(range(1, total_pages + 1))

    # 首窗：渲染 1 到 middle（中间页）
    if start == 1:
        return list(range(1, middle + 1))

    # 末窗：渲染 middle 到最后一页
    if end == total_pages:
        return list(range(middle, total_pages + 1))

    # 中间窗：只渲染中间页
    return [middle]


def assemble_sliding_prompt(
    pages_ocr: Dict[int, List[str]],
    window: Tuple[int, int]
) -> str:
    """
    将窗口内多页 OCR 文本组装成翻译 prompt。

    每页内的文本框按全局递增编号 <|N|>，
    页之间用 ||| 分隔。

    Args:
        pages_ocr: {页号: [文本框文本列表]}
        window: (start_page, end_page) 当前窗口

    Returns:
        格式化的 prompt 字符串

    Examples:
        >>> pages = {1: ["a", "b"], 2: ["c"], 3: ["d"]}
        >>> prompt = assemble_sliding_prompt(pages, (1, 3))
        >>> "<|1|>a\\n<|2|>b\\n|||\\n<|3|>c\\n|||\\n<|4|>d" in prompt
        True
    """
    start, end = window

    page_sections = []
    global_id = 1

    for page_num in range(start, end + 1):
        texts = pages_ocr.get(page_num, [])
        lines = []
        for text in texts:
            if text.strip():
                lines.append(f"<|{global_id}|>{text}")
                global_id += 1
        if lines:
            page_sections.append("\n".join(lines))
        else:
            # 空页仍然保留位置（占位分隔符）
            page_sections.append("")

    return "\n|||\n".join(page_sections)


def parse_sliding_response(
    response: str | None,
    expected_count: int
) -> List[str]:
    """
    从 LLM 响应中解析 <|N|> 标记的翻译结果。

    处理策略：
    - 提取所有 <|N|>... 片段
    - 缺失的 ID 填空字符串
    - 超出的 ID 截断

    Args:
        response: LLM 返回的翻译文本
        expected_count: 期望的翻译条数

    Returns:
        翻译结果列表，长度 == expected_count

    Examples:
        >>> parse_sliding_response("<|1|>Hello\\n<|2|>World", 3)
        ['Hello', 'World', '']
        >>> parse_sliding_response("<|1|>A\\n<|2|>B\\n<|3|>C", 2)
        ['A', 'B']
    """
    if not response:
        return [""] * expected_count

    # 策略：用 re.split 按 <|N|> 标记切分文本
    # parts[0] = 第一个标记前的噪音文本
    # parts[1] = <|1|> 后的内容（直到下一个标记）
    # parts[2] = <|2|> 后的内容，依此类推
    parts = re.split(r'<\|(\d+)\|>', response)
    # re.split with capturing group gives: [before, id1, after_id1, id2, after_id2, ...]
    # parts[0] = text before first <|N|>
    # parts[1] = first ID
    # parts[2] = text between first <|N|> and next marker
    # parts[3] = second ID
    # parts[4] = text between second <|N|> and next marker
    # ...

    id_to_translation: Dict[int, str] = {}
    # 从索引1开始，每次跳2个（ID -> 内容）
    for i in range(1, len(parts) - 1, 2):
        id_str = parts[i]
        text = parts[i + 1] if i + 1 < len(parts) else ""
        try:
            tid = int(id_str)
        except ValueError:
            continue
        if tid not in id_to_translation:
            cleaned = text.strip()
            id_to_translation[tid] = cleaned

    result = []
    for i in range(1, expected_count + 1):
        result.append(id_to_translation.get(i, ""))

    return result


def build_id_to_page_map(
    page_text_counts: Dict[int, int]
) -> Dict[int, Tuple[int, int]]:
    """
    构建全局 ID 到 (页码, 页内索引) 的映射。

    按页码排序，依次分配全局 ID。

    Args:
        page_text_counts: {页码: 该页文本框数量}

    Returns:
        {全局ID: (页码, 页内文本框索引)}

    Examples:
        >>> build_id_to_page_map({1: 2, 2: 1, 3: 3})
        {0: (1, 0), 1: (1, 1), 2: (2, 0), 3: (3, 0), 4: (3, 1), 5: (3, 2)}
    """
    id_map = {}
    global_id = 0
    for page_num in sorted(page_text_counts.keys()):
        count = page_text_counts[page_num]
        for local_idx in range(count):
            id_map[global_id] = (page_num, local_idx)
            global_id += 1
    return id_map