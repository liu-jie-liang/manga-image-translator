"""滑动窗口集成测试

测试完整滑动窗口翻译流水线，使用 Mock 翻译服务。
"""

import sys
import os

# Add project root to path for test fixture imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from manga_translator.sliding_window import (
    partition_windows,
    render_pages_for_window,
    assemble_sliding_prompt,
    parse_sliding_response,
)

# Inline fixtures (avoid cross-package import issues)
from typing import Dict, List

def create_mock_ocr_pages(num_pages: int, texts_per_page: int = 3, prefix: str = "页") -> Dict[int, List[str]]:
    pages = {}
    for p in range(1, num_pages + 1):
        pages[p] = [f"{prefix}{p}文本{i+1}" for i in range(texts_per_page)]
    return pages

MANGA_OCR_5_PAGES: Dict[int, List[str]] = {
    1: ["僕はアイネと共に一度、宿の方に戻った",
        "改めて直面するのは部屋の問題"],
    2: ["部屋のベッドが一つでは、さすがに狭すぎるだろう",
        "アイネは何も言わずに"],
    3: ["仕方ない、私は床で寝るよ",
        "えっ、でも"],
    4: ["遠慮しないで、君はベッドを使って",
        "そんなわけには"],
    5: ["じゃあ一緒に寝る？",
        "なっ！"],
}


# 模拟翻译调度函数：返回模拟翻译结果
async def mock_translate(prompt: str) -> str:
    """
    模拟翻译：从 prompt 中提取 <|N|> 标记，
    返回模拟翻译结果（编号不变）。
    """
    import re
    markers = re.findall(r'<\|(\d+)\|>([^\n]*)', prompt)
    lines = []
    for n, text in markers:
        lines.append(f"<|{n}|>[译]{text}")
    return "\n".join(lines)


class TestSlidingWindowIntegration:
    """集成测试：完整滑动窗口翻译流水线"""

    @pytest.mark.asyncio
    async def test_full_pipeline_5_pages(self):
        """5页漫画完整滑动窗口翻译"""
        pages_ocr = MANGA_OCR_5_PAGES.copy()  # 5页日语漫画OCR数据
        window_size = 5
        total_pages = 5

        windows = partition_windows(total_pages, window_size)
        assert windows == [(1, 5)], "5页漫画应该只有1个窗口"

        for window in windows:
            # 1. 组装 prompt
            prompt = assemble_sliding_prompt(pages_ocr, window)

            # 2. 模拟翻译
            response = await mock_translate(prompt)

            # 3. 解析响应
            expected_count = sum(
                len(texts) for p, texts in pages_ocr.items()
                if window[0] <= p <= window[1] and texts
            )
            translations = parse_sliding_response(response, expected_count)

            # 4. 映射回页面
            render_pages = render_pages_for_window(window, total_pages, window_size)
            assert len(render_pages) == total_pages  # 5页漫画渲染所有页

            # 验证翻译结果不为空
            assert len(translations) == expected_count
            for t in translations:
                assert t, "翻译结果不应为空"
                assert "[译]" in t, "模拟翻译应包含[译]标记"

    def test_window_coverage_no_overlap(self):
        """所有页面恰好被渲染一次，无重复无遗漏"""
        total_pages = 10
        window_size = 5
        windows = partition_windows(total_pages, window_size)

        rendered = set()
        for window in windows:
            pages = render_pages_for_window(window, total_pages, window_size)
            for p in pages:
                assert p not in rendered, f"第{p}页被重复渲染"
                rendered.add(p)

        assert rendered == set(range(1, total_pages + 1)), \
            f"缺失页面: {set(range(1,total_pages+1)) - rendered}"

    def test_prompt_contains_context(self):
        """Prompt 包含前后文页面信息"""
        pages = create_mock_ocr_pages(5, texts_per_page=2)
        prompt = assemble_sliding_prompt(pages, (1, 5))

        # 验证页分隔符
        assert prompt.count("|||") == 4  # 5页 → 4个分隔符

        # 验证每页文本都在 prompt 中
        for texts in pages.values():
            for text in texts:
                assert text in prompt

    def test_parse_back_to_page(self):
        """验证翻译结果可以正确映射回页面"""
        pages = {
            1: ["textA", "textB"],
            2: ["textC"],
            3: [],
            4: ["textD", "textE"]
        }
        # 全局ID: textA=1, textB=2, textC=3, textD=4, textE=5

        # 模拟翻译返回
        response = "<|1|>译A\n<|2|>译B\n<|3|>译C\n<|4|>译D\n<|5|>译E"
        translations = parse_sliding_response(response, expected_count=5)

        assert translations == ["译A", "译B", "译C", "译D", "译E"]

        # 验证：pages = {1:2个文字, 2:1个, 3:0个, 4:2个}
        assert pages == {1: ["textA", "textB"], 2: ["textC"], 3: [], 4: ["textD", "textE"]}

        # 映射：全局ID0→页1text0, ID1→页1text1, ID2→页2text0, ID3→页4text0, ID4→页4text1
        page1_trans = [translations[0], translations[1]]
        page2_trans = [translations[2]]
        page4_trans = [translations[3], translations[4]]

        assert page1_trans == ["译A", "译B"]
        assert page2_trans == ["译C"]
        assert page4_trans == ["译D", "译E"]


class TestSlidingWindowEdgeCases:
    """边界情况集成测试"""

    def test_single_page(self):
        """单页漫画：只有1个窗口"""
        windows = partition_windows(1, 5)
        assert len(windows) == 1
        assert windows[0] == (1, 1)

        pages = render_pages_for_window((1, 1), 1, 5)
        assert pages == [1]

        prompt = assemble_sliding_prompt({1: ["hello"]}, (1, 1))
        assert "hello" in prompt
        assert "|||" not in prompt  # 单页无分隔符

    def test_many_empty_pages(self):
        """多页空文本"""
        pages = {1: [], 2: ["only_text"], 3: [], 4: [], 5: []}
        prompt = assemble_sliding_prompt(pages, (1, 5))
        assert "only_text" in prompt
        assert "<|1|>only_text" in prompt  # 第一个非空文本

    def test_large_manga(self):
        """67页漫画（接近你的测试材料）"""
        pages = create_mock_ocr_pages(67, texts_per_page=5, prefix="生肉")
        windows = partition_windows(67, 5)

        assert len(windows) == 63  # 67 - 5 + 1 = 63
        assert windows[0] == (1, 5)
        assert windows[-1] == (63, 67)

        # 验证渲染覆盖
        rendered = set()
        for w in windows:
            for p in render_pages_for_window(w, 67, 5):
                rendered.add(p)
        assert rendered == set(range(1, 68))

        # 模拟翻译一个窗口
        prompt = assemble_sliding_prompt(pages, (1, 5))
        assert prompt.count("|||") == 4
        # 5页 × 5文本 = 25个全局ID
        assert prompt.count("<|") == 25