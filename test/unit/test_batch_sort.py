"""
TDD: Test directory sorting rules for batch translation.

规则:
1. 纯数字 → 按数值大小从小到大
2. 数字+字母（含 _ - 分隔符）→ 数字按数值从小到大，再字母按字母序从小到大
3. 字母+数字（含 _ - 分隔符）→ 字母按字母序从小到大，再数字按数值从小到大
4. 纯字母 → 等同于字母+数字0，归入字母+数字模式
5. 其他 → 自然排序，排最后
"""
from manga_translator.batch import sort_subdirs


# ─── 测试用例 ───

class TestSortSubdirs:
    """目录排序规则测试"""

    def test_pure_numbers(self):
        """纯数字目录 → 按数值大小"""
        dirs = ['10', '2', '1', '03', '100']
        result = sort_subdirs(dirs)
        assert result == ['1', '2', '03', '10', '100']

    def test_digits_then_letters(self):
        """数字+字母 → 先数字升序，再字母升序"""
        dirs = ['02b', '01a', '02a', '01b']
        result = sort_subdirs(dirs)
        assert result == ['01a', '01b', '02a', '02b']

    def test_digits_then_letters_with_separators(self):
        """数字_字母 / 数字-字母 → 归入数字+字母模式"""
        dirs = ['02_b', '01-a', '02_a', '01_b']
        result = sort_subdirs(dirs)
        assert result == ['01-a', '01_b', '02_a', '02_b']

    def test_letters_then_digits(self):
        """字母+数字 → 先字母升序，再数字升序"""
        dirs = ['ch5', 'ch1', 'ch10', 'ch2']
        result = sort_subdirs(dirs)
        assert result == ['ch1', 'ch2', 'ch5', 'ch10']

    def test_letters_then_digits_with_separators(self):
        """字母_数字 / 字母-数字 → 归入字母+数字模式"""
        dirs = ['ch_5', 'ch-1', 'ch_10', 'ch-2']
        result = sort_subdirs(dirs)
        assert result == ['ch-1', 'ch-2', 'ch_5', 'ch_10']

    def test_letters_only(self):
        """纯字母 → 等同于字母+数字0，按字母序"""
        dirs = ['bonus', 'alpha', 'zebra', 'a']
        result = sort_subdirs(dirs)
        assert result == ['a', 'alpha', 'bonus', 'zebra']

    def test_other_patterns(self):
        """其他模式 → 自然排序，排最后"""
        dirs = ['_extra', '!meta', '.hidden']
        result = sort_subdirs(dirs)
        # 自然排序
        assert result == ['!meta', '.hidden', '_extra']

    def test_mixed_all_patterns(self):
        """混合所有模式 → 纯数字 > 数字+字母 > 字母+数字(含纯字母) > 其他"""
        dirs = [
            'bonus',      # 纯字母 → 字母+数字模式
            '!meta',      # 其他
            '001',        # 纯数字
            '02a',        # 数字+字母
            'ch10',       # 字母+数字
            '10',         # 纯数字
            'extra',      # 纯字母
            '01_a',       # 数字+字母
            '_hidden',    # 其他
            'ch-2',       # 字母+数字
        ]
        result = sort_subdirs(dirs)
        expected = [
            '001', '10',                   # 纯数字
            '01_a', '02a',                 # 数字+字母
            'bonus', 'ch-2', 'ch10', 'extra',  # 字母+数字(含纯字母)
            '!meta', '_hidden',            # 其他
        ]
        assert result == expected

    def test_empty_list(self):
        """空列表"""
        assert sort_subdirs([]) == []

    def test_single_dir(self):
        """单个目录"""
        assert sort_subdirs(['test']) == ['test']

    def test_dir_with_only_digits_and_letters(self):
        """混合数字和字母但没有分隔符的情况，字母在前数字在后"""
        dirs = ['a1', 'a10', 'a2', 'b1', 'b10', 'b2']
        result = sort_subdirs(dirs)
        assert result == ['a1', 'a2', 'a10', 'b1', 'b2', 'b10']

    def test_dir_with_digits_only_leading_zeros(self):
        """纯数字带前导零 → 按数值排序，数值相同保留原顺序"""
        dirs = ['001', '0001', '01', '1']
        result = sort_subdirs(dirs)
        # 数值：1, 1, 1, 1 → 全部相同，稳定排序保持原顺序
        assert result == ['0001', '001', '01', '1']

    def test_dir_with_digits_only_leading_zeros_numeric(self):
        """纯数字带前导零 — 按数值排序"""
        # 按数值：0, 1, 1, 10, 100
        dirs = ['001', '000', '01', '10', '100']
        result = sort_subdirs(dirs)
        assert result == ['000', '001', '01', '10', '100']