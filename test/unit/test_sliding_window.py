"""滑动窗口模块单元测试"""

import pytest
from manga_translator.sliding_window import (
    partition_windows,
    render_pages_for_window,
    assemble_sliding_prompt,
    parse_sliding_response,
    build_id_to_page_map,
)


class TestWindowPartition:
    """窗口划分测试"""

    def test_normal_case(self):
        """正常10页5窗口"""
        windows = partition_windows(total_pages=10, window_size=5)
        assert windows == [(1, 5), (2, 6), (3, 7), (4, 8), (5, 9), (6, 10)]

    def test_exact_window(self):
        """页数正好等于窗口大小"""
        assert partition_windows(5, 5) == [(1, 5)]
        assert partition_windows(3, 3) == [(1, 3)]

    def test_less_than_window(self):
        """页数少于窗口大小"""
        assert partition_windows(3, 5) == [(1, 3)]
        assert partition_windows(1, 5) == [(1, 1)]

    def test_single_page(self):
        """单页"""
        assert partition_windows(1, 5) == [(1, 1)]

    def test_large_page_count(self):
        """大量页面"""
        windows = partition_windows(100, 5)
        assert len(windows) == 96
        assert windows[0] == (1, 5)
        assert windows[-1] == (96, 100)

    def test_window_size_one(self):
        """窗口大小为1（每页独立翻译）"""
        assert partition_windows(5, 1) == [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]

    def test_invalid_inputs(self):
        """非法输入"""
        with pytest.raises(ValueError):
            partition_windows(0, 5)
        with pytest.raises(ValueError):
            partition_windows(10, 0)
        with pytest.raises(ValueError):
            partition_windows(-1, 5)


class TestRenderPages:
    """渲染页映射测试"""

    def test_first_window(self):
        """首窗：渲染前半部分页"""
        assert render_pages_for_window((1, 5), 10, 5) == [1, 2, 3]

    def test_middle_windows(self):
        """中间窗：各渲染中间1页"""
        assert render_pages_for_window((2, 6), 10, 5) == [4]
        assert render_pages_for_window((3, 7), 10, 5) == [5]
        assert render_pages_for_window((4, 8), 10, 5) == [6]
        assert render_pages_for_window((5, 9), 10, 5) == [7]

    def test_last_window(self):
        """末窗：渲染后半部分页"""
        assert render_pages_for_window((6, 10), 10, 5) == [8, 9, 10]

    def test_single_window(self):
        """只有1个窗口时渲染全部页"""
        assert render_pages_for_window((1, 5), 5, 5) == [1, 2, 3, 4, 5]
        assert render_pages_for_window((1, 3), 3, 5) == [1, 2, 3]

    def test_two_pages_window_size_3(self):
        """2页漫画，窗口大小3"""
        assert render_pages_for_window((1, 2), 2, 3) == [1, 2]

    def test_overlap_page_count(self):
        """渲染页不应超过总页数"""
        # 第2窗重新渲染第4页，第4页只渲染1次
        rendered = set()
        windows = partition_windows(10, 5)
        for w in windows:
            pages = render_pages_for_window(w, 10, 5)
            for p in pages:
                assert p not in rendered, f"Page {p} rendered twice"
                rendered.add(p)
        assert rendered == set(range(1, 11))


class TestAssembleSlidingPrompt:
    """Prompt组装测试"""

    def test_basic_assembly(self):
        """基本组装"""
        pages = {
            1: ["こんにちは", "元気ですか"],
            2: ["はい"],
            3: ["またね"],
            4: [],
            5: ["ありがとう"],
        }
        prompt = assemble_sliding_prompt(pages, window=(1, 5))
        assert "|||" in prompt
        assert "<|1|>こんにちは" in prompt
        assert "<|2|>元気ですか" in prompt
        assert "<|3|>はい" in prompt
        assert "<|5|>ありがとう" in prompt
        # 第四页无文本，但分隔符应保留
        assert prompt.count("|||") >= 3

    def test_id_continuity(self):
        """全局ID应连续递增"""
        pages = {
            1: ["a"],
            2: ["b", "c"],
            3: ["d"],
        }
        prompt = assemble_sliding_prompt(pages, window=(1, 3))
        # 应该有 <|1|> <|2|> <|3|> <|4|>
        assert "<|1|>a" in prompt
        assert "<|2|>b" in prompt
        assert "<|3|>c" in prompt
        assert "<|4|>d" in prompt

    def test_partial_window(self):
        """窗口不是从第1页开始（中间窗）"""
        pages = {
            2: ["page2_text1", "page2_text2"],
            3: ["page3_text1"],
            4: ["page4_text1", "page4_text2", "page4_text3"],
            5: ["page5_text1"],
            6: ["page6_text1"],
        }
        prompt = assemble_sliding_prompt(pages, window=(2, 6))
        assert "<|1|>page2_text1" in prompt
        assert "<|2|>page2_text2" in prompt
        assert "<|3|>page3_text1" in prompt
        assert "|||" in prompt

    def test_single_page_window(self):
        """单页窗口"""
        pages = {1: ["hello", "world"]}
        prompt = assemble_sliding_prompt(pages, window=(1, 1))
        assert "|||" not in prompt  # 单页不需要分隔符
        assert "<|1|>hello" in prompt
        assert "<|2|>world" in prompt

    def test_empty_page_in_middle(self):
        """中间空页保留分隔符"""
        pages = {
            1: ["text1"],
            2: [],
            3: ["text3"],
        }
        prompt = assemble_sliding_prompt(pages, window=(1, 3))
        assert prompt.count("|||") == 2  # 页1-页2之间 和 页2-页3之间
        assert "<|1|>text1" in prompt
        assert "<|2|>text3" in prompt  # ID继续，text3是第2个非空文本


class TestParseSlidingResponse:
    """响应解析测试"""

    def test_basic_parse(self):
        """基本解析"""
        response = "<|1|>Hello\n<|2|>How are you\n<|3|>Yes\n<|4|>Bye"
        translations = parse_sliding_response(response, expected_count=4)
        assert translations == ["Hello", "How are you", "Yes", "Bye"]

    def test_partial_response(self):
        """LLM返回不完整"""
        response = "<|1|>Hello\n<|2|>World"
        translations = parse_sliding_response(response, expected_count=5)
        assert translations[0] == "Hello"
        assert translations[1] == "World"
        assert translations[2] == ""  # 缺失
        assert translations[3] == ""
        assert translations[4] == ""

    def test_extra_response(self):
        """LLM返回超出预期数量"""
        response = "<|1|>A\n<|2|>B\n<|3|>C"
        translations = parse_sliding_response(response, expected_count=2)
        assert len(translations) == 2
        assert translations == ["A", "B"]

    def test_empty_response(self):
        """空响应"""
        translations = parse_sliding_response("", expected_count=3)
        assert translations == ["", "", ""]

    def test_none_response(self):
        """None响应"""
        translations = parse_sliding_response(None, expected_count=3)
        assert translations == ["", "", ""]

    def test_noisy_response(self):
        """带前导噪音的响应——LLM有时会在第一个标记前增加解释"""
        response = "Here is the translation:\n<|1|>Hello\n<|2|>World"
        translations = parse_sliding_response(response, expected_count=2)
        assert translations == ["Hello", "World"]

    def test_japanese_response(self):
        """日语翻译响应"""
        response = "<|1|>こんにちは\n<|2|>さようなら"
        translations = parse_sliding_response(response, expected_count=2)
        assert translations == ["こんにちは", "さようなら"]

    def test_skip_missing_ids(self):
        """跳过的ID"""
        response = "<|1|>A\n<|3|>C"
        translations = parse_sliding_response(response, expected_count=3)
        assert translations[0] == "A"
        assert translations[1] == ""
        assert translations[2] == "C"

    def test_multiline_translations(self):
        """多行翻译文本"""
        response = "<|1|>Line1\nLine2\n<|2|>Line3"
        translations = parse_sliding_response(response, expected_count=2)
        assert translations[0] == "Line1\nLine2"
        assert translations[1] == "Line3"


class TestBuildIdToPageMap:
    """ID到页面映射测试"""

    def test_basic_mapping(self):
        """基本映射"""
        page_text_counts = {1: 2, 2: 1, 3: 3}
        id_map = build_id_to_page_map(page_text_counts)
        # 页1: 2个文本 → IDs:0,1
        assert id_map[0] == (1, 0)
        assert id_map[1] == (1, 1)
        # 页2: 1个文本 → ID:2
        assert id_map[2] == (2, 0)
        # 页3: 3个文本 → IDs:3,4,5
        assert id_map[3] == (3, 0)
        assert id_map[4] == (3, 1)
        assert id_map[5] == (3, 2)

    def test_empty_page(self):
        """包含空页的映射"""
        page_text_counts = {1: 2, 2: 0, 3: 1}
        id_map = build_id_to_page_map(page_text_counts)
        assert id_map[0] == (1, 0)
        assert id_map[1] == (1, 1)
        # 页2无文本，不占ID
        assert id_map[2] == (3, 0)
        assert len(id_map) == 3  # 总共3个文本，3个全局ID

    def test_single_page(self):
        """单页映射"""
        id_map = build_id_to_page_map({1: 5})
        for i in range(5):
            assert id_map[i] == (1, i)