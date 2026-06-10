"""滑动窗口测试数据fixtures"""
from typing import Dict, List


def create_mock_ocr_pages(num_pages: int, texts_per_page: int = 3, prefix: str = "页") -> Dict[int, List[str]]:
    """
    生成模拟OCR结果：按页号组织的文本框文本列表。

    Args:
        num_pages: 页数
        texts_per_page: 每页文本框数
        prefix: 文本前缀

    Returns:
        {页号: [文本1, 文本2, ...]}
    """
    pages = {}
    for p in range(1, num_pages + 1):
        pages[p] = [f"{prefix}{p}文本{i+1}" for i in range(texts_per_page)]
    return pages


def create_mock_translations(text_count: int, prefix: str = "译") -> List[str]:
    """生成模拟翻译结果"""
    return [f"{prefix}{i+1}" for i in range(text_count)]


# 模拟漫画OCR数据（日语）
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