"""基准测试数据收集模块 (Benchmark Data Collection)

纯数据模型 + 统计计算，不含任何 IO 操作。
主链路中只做 time.time() 打点，数据暂存内存，翻译完成后统一分析输出。

设计原则：
- 零 IO 开销：主链路中只做浮点减法，不写磁盘
- 单例模式：全局唯一 BenchmarkContext，避免多层传递
- 线程安全：asyncio 单线程模型下天然安全
"""

import time
import math
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class StageTiming:
    """单个管道阶段的计时数据。

    Attributes:
        elapsed: 阶段耗时 (秒)
        start_ts: 阶段开始时间戳 (time.time())
        end_ts: 阶段结束时间戳 (time.time())
    """
    elapsed: float = 0.0
    start_ts: float = 0.0
    end_ts: float = 0.0

    def to_dict(self) -> dict:
        return {
            'elapsed': self.elapsed,
            'start_ts': self.start_ts,
            'end_ts': self.end_ts,
        }


@dataclass
class PageMetrics:
    """单页翻译的完整度量数据。

    Pipeline stages: detection → ocr → translation → inpainting → rendering
    """

    # 标识
    page_index: int = 0
    image_name: str = ""

    # 管道阶段耗时
    detection: StageTiming = field(default_factory=StageTiming)
    ocr: StageTiming = field(default_factory=StageTiming)
    translation: StageTiming = field(default_factory=StageTiming)
    inpainting: StageTiming = field(default_factory=StageTiming)
    rendering: StageTiming = field(default_factory=StageTiming)

    # 总耗时（各阶段之和）
    total_elapsed: float = 0.0

    # 文本统计
    ocr_text_count: int = 0          # OCR 检测到的文本框数
    translated_text_count: int = 0   # 成功翻译的文本框数

    # Token 统计（翻译阶段）
    prompt_tokens: int = 0
    completion_tokens: int = 0
    translation_ttfb: float = 0.0    # Time To First Byte (首 token 延迟)

    # 稳定性
    error: Optional[str] = None      # 错误信息（None = 成功）
    retry_count: int = 0             # 重试次数

    @property
    def translation_coverage(self) -> float:
        """翻译覆盖率 = 已翻译文本框数 / OCR 检测文本框数。

        如果 OCR 未检测到文本，返回 1.0（无文本 = 无需翻译 = 无覆盖问题）。
        """
        if self.ocr_text_count == 0:
            return 1.0
        return self.translated_text_count / self.ocr_text_count

    @property
    def tokens_per_second(self) -> float:
        """翻译吞吐量 (tokens/sec)。

        计算公式: completion_tokens / translation.elapsed
        """
        if self.translation.elapsed <= 0:
            return 0.0
        return self.completion_tokens / self.translation.elapsed

    def compute_total(self):
        """自动计算总耗时 = 各阶段耗时之和。"""
        self.total_elapsed = (
            self.detection.elapsed +
            self.ocr.elapsed +
            self.translation.elapsed +
            self.inpainting.elapsed +
            self.rendering.elapsed
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 单例 BenchmarkContext
# ═══════════════════════════════════════════════════════════════════════════════

class BenchmarkContext:
    """全局基准测试上下文（单例模式）。

    在主链路中收集逐页度量数据，翻译完成后统一分析。

    用法:
        from manga_translator.benchmark import benchmark_context

        # 在 batch.py 中启用
        benchmark_context.reset()
        benchmark_context.mode = "ollama"  # or "gguf"
        benchmark_context.start_time = time.time()

        # 在核心管道中收集
        benchmark_context.start_page("001.jpg")
        benchmark_context.record_stage("detection", 0.5, 100.0, 100.5)
        benchmark_context.record_translation_usage(3.0, 0.5, 100, 50)
        benchmark_context.record_text_counts(10, 8)

        # 翻译完成后分析
        report = benchmark_context.generate_report()
    """

    _instance: Optional["BenchmarkContext"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.pages: List[PageMetrics] = []
        self.mode: str = ""            # "ollama" | "gguf"
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self._active_page: Optional[PageMetrics] = None
        self.oom_detected: bool = False
        self.oom_message: str = ""

    def reset(self):
        """重置所有数据，开始新的基准测试会话。"""
        self.pages = []
        self.mode = ""
        self.start_time = 0.0
        self.end_time = 0.0
        self._active_page = None
        self.oom_detected = False
        self.oom_message = ""

    # ─── 页面生命周期 ────────────────────────────────────────────────────────

    def start_page(self, image_name: str):
        """开始处理新页面，创建 PageMetrics 记录。

        Args:
            image_name: 图片文件名（用于标识）
        """
        pm = PageMetrics(
            page_index=len(self.pages),
            image_name=image_name,
        )
        self.pages.append(pm)
        self._active_page = pm

    def finish_page(self):
        """完成当前页面处理，计算总耗时。"""
        if self._active_page:
            self._active_page.compute_total()
            self._active_page = None

    # ─── 阶段计时 ────────────────────────────────────────────────────────────

    def record_stage(self, stage: str, elapsed: float,
                     start_ts: float = 0.0, end_ts: float = 0.0):
        """记录单个管道阶段的耗时。

        Args:
            stage: 阶段名称 ("detection", "ocr", "translation", "inpainting", "rendering")
            elapsed: 阶段耗时 (秒)
            start_ts: 阶段开始时间戳
            end_ts: 阶段结束时间戳
        """
        if self._active_page is None:
            raise ValueError("No active page. Call start_page() first.")
        timing = StageTiming(elapsed=elapsed, start_ts=start_ts, end_ts=end_ts)
        setattr(self._active_page, stage, timing)

    # ─── 翻译特殊指标 ────────────────────────────────────────────────────────

    def record_translation_usage(self, elapsed: float, ttfb: float = 0.0,
                                  prompt_tokens: int = 0, completion_tokens: int = 0):
        """记录翻译阶段的 token 使用量和首 token 延迟。

        Args:
            elapsed: 翻译总耗时 (秒)
            ttfb: 首 token 延迟 (秒)，Ollama 模式有意义
            prompt_tokens: 输入 token 数
            completion_tokens: 输出 token 数
        """
        if self._active_page is None:
            raise ValueError("No active page. Call start_page() first.")
        self._active_page.translation.elapsed = elapsed
        self._active_page.translation_ttfb = ttfb
        self._active_page.prompt_tokens = prompt_tokens
        self._active_page.completion_tokens = completion_tokens

    # ─── 文本统计 ────────────────────────────────────────────────────────────

    def record_text_counts(self, ocr_count: int, translated_count: int):
        """记录 OCR 检测和翻译成功的文本框数。

        Args:
            ocr_count: OCR 检测到的文本框总数
            translated_count: 成功翻译的文本框数
        """
        if self._active_page is None:
            raise ValueError("No active page. Call start_page() first.")
        self._active_page.ocr_text_count = ocr_count
        self._active_page.translated_text_count = translated_count

    # ─── 稳定性 ──────────────────────────────────────────────────────────────

    def record_error(self, error_message: str):
        """记录页面翻译错误。

        Args:
            error_message: 错误描述
        """
        if self._active_page is None:
            raise ValueError("No active page. Call start_page() first.")
        self._active_page.error = error_message

    def record_retry(self):
        """记录一次重试。"""
        if self._active_page is None:
            raise ValueError("No active page. Call start_page() first.")
        self._active_page.retry_count += 1

    def record_oom(self, message: str = ""):
        """记录 OOM 事件。"""
        self.oom_detected = True
        self.oom_message = message

    # ─── 批量操作 ────────────────────────────────────────────────────────────

    def add_llm_judge_score(self, page_index: int, score: int,
                            accuracy_ok: bool, issues: str = ""):
        """添加 LLM-as-Judge 评分到指定页面。

        Args:
            page_index: 页面索引 (0-based)
            score: 1-5 分
            accuracy_ok: 准确性是否通过
            issues: 问题描述
        """
        if 0 <= page_index < len(self.pages):
            # 使用 __dict__ 直接设置额外属性
            self.pages[page_index].__dict__['judge_score'] = score
            self.pages[page_index].__dict__['judge_accuracy_ok'] = accuracy_ok
            self.pages[page_index].__dict__['judge_issues'] = issues

    # ─── 统计导出 ────────────────────────────────────────────────────────────

    def stage_values(self, stage: str) -> List[float]:
        """提取所有页面的指定阶段耗时列表。

        Args:
            stage: 阶段名称

        Returns:
            耗时值列表 (秒)
        """
        return [getattr(p, stage).elapsed for p in self.pages]

    def total_values(self) -> List[float]:
        """提取所有页面的总耗时列表。"""
        return [p.total_elapsed for p in self.pages]

    def successful_pages(self) -> List[PageMetrics]:
        """返回成功翻译的页面（无错误）。"""
        return [p for p in self.pages if p.error is None]

    def failed_pages(self) -> List[PageMetrics]:
        """返回翻译失败的页面。"""
        return [p for p in self.pages if p.error is not None]

    def retried_pages(self) -> List[PageMetrics]:
        """返回发生重试的页面。"""
        return [p for p in self.pages if p.retry_count > 0]

    @property
    def total_wall_time(self) -> float:
        """端到端挂钟时间。"""
        if self.end_time > 0 and self.start_time > 0:
            return self.end_time - self.start_time
        return 0.0

    def to_dict(self) -> dict:
        """导出为可序列化的字典。"""
        return {
            'mode': self.mode,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_wall_time': self.total_wall_time,
            'oom_detected': self.oom_detected,
            'oom_message': self.oom_message,
            'page_count': len(self.pages),
            'success_count': len(self.successful_pages()),
            'failed_count': len(self.failed_pages()),
            'retried_count': len(self.retried_pages()),
            'pages': [asdict(p) for p in self.pages],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 模块级单例
# ═══════════════════════════════════════════════════════════════════════════════

benchmark_context = BenchmarkContext()


# ═══════════════════════════════════════════════════════════════════════════════
# 统计计算（纯函数，无副作用）
# ═══════════════════════════════════════════════════════════════════════════════

def compute_percentile(values: List[float], percentile: float) -> float:
    """计算百分位数（线性插值法）。

    Args:
        values: 数值列表
        percentile: 百分位 (0-100)

    Returns:
        百分位数值
    """
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]

    sorted_vals = sorted(values)
    k = (percentile / 100.0) * (len(sorted_vals) - 1)
    f = int(k)
    c = k - f
    if f + 1 < len(sorted_vals):
        return sorted_vals[f] + c * (sorted_vals[f + 1] - sorted_vals[f])
    return sorted_vals[f]


def compute_statistics(values: List[float]) -> dict:
    """计算数值列表的完整统计量。

    Args:
        values: 数值列表

    Returns:
        包含 count, sum, avg, min, max, std, cv, p50, p90, p95, p99 的字典
    """
    if not values:
        return {
            'count': 0, 'sum': 0.0, 'avg': 0.0, 'min': 0.0, 'max': 0.0,
            'std': 0.0, 'cv': 0.0,
            'p50': 0.0, 'p90': 0.0, 'p95': 0.0, 'p99': 0.0,
        }

    n = len(values)
    total = sum(values)
    avg = total / n
    min_v = min(values)
    max_v = max(values)

    if n > 1:
        variance = sum((x - avg) ** 2 for x in values) / (n - 1)
        std = math.sqrt(variance)
    else:
        std = 0.0

    cv = (std / avg) if avg > 0 else 0.0

    return {
        'count': n,
        'sum': round(total, 3),
        'avg': round(avg, 3),
        'min': round(min_v, 3),
        'max': round(max_v, 3),
        'std': round(std, 3),
        'cv': round(cv, 3),
        'p50': round(compute_percentile(values, 50), 3),
        'p90': round(compute_percentile(values, 90), 3),
        'p95': round(compute_percentile(values, 95), 3),
        'p99': round(compute_percentile(values, 99), 3),
    }


def detect_outliers(values: List[float], sigma: float = 2.0) -> List[Tuple[int, float]]:
    """检测超过 N 倍标准差的异常值。

    Args:
        values: 数值列表
        sigma: 标准差倍数阈值（默认 2σ）

    Returns:
        [(index, value), ...] 异常值列表
    """
    if len(values) < 3:
        return []

    n = len(values)
    avg = sum(values) / n
    variance = sum((x - avg) ** 2 for x in values) / (n - 1)
    std = math.sqrt(variance)

    if std == 0:
        return []

    threshold = avg + sigma * std
    outliers = []
    for i, v in enumerate(values):
        if v > threshold:
            outliers.append((i, v))
    return outliers


def compute_benchmark_statistics(pages: List[PageMetrics], session_elapsed: float) -> dict:
    """计算基准测试的完整统计数据。

    Args:
        pages: 所有页面的度量数据
        session_elapsed: 会话总耗时 (秒)

    Returns:
        包含速度、质量、稳定性三大维度的统计字典
    """
    if not pages:
        return {}

    # 辅助：提取成功页面的各阶段耗时
    successful = [p for p in pages if p.error is None]
    failed = [p for p in pages if p.error is not None]

    def _stage_stats(stage: str) -> dict:
        vals = [getattr(p, stage).elapsed for p in successful]
        return compute_statistics(vals)

    def _total_stats() -> dict:
        vals = [p.total_elapsed for p in successful]
        return compute_statistics(vals)

    # ─── 速度指标 ───
    speed = {
        'session_elapsed': round(session_elapsed, 3),
        'total_pages': len(pages),
        'successful_pages': len(successful),
        'failed_pages': len(failed),
        'pages_per_minute': round(len(pages) / (session_elapsed / 60), 2) if session_elapsed > 0 else 0,
        'avg_page_time': round(session_elapsed / len(pages), 3) if pages else 0,
        'stages': {
            'detection': _stage_stats('detection'),
            'ocr': _stage_stats('ocr'),
            'translation': _stage_stats('translation'),
            'inpainting': _stage_stats('inpainting'),
            'rendering': _stage_stats('rendering'),
        },
        'total': _total_stats(),
    }

    # Token 吞吐量
    total_prompt = sum(p.prompt_tokens for p in successful)
    total_completion = sum(p.completion_tokens for p in successful)
    total_translation_time = sum(p.translation.elapsed for p in successful)
    speed['token'] = {
        'total_prompt_tokens': total_prompt,
        'total_completion_tokens': total_completion,
        'total_tokens': total_prompt + total_completion,
        'tokens_per_second': round(total_completion / total_translation_time, 2) if total_translation_time > 0 else 0,
    }

    # ─── 质量指标 ───
    coverage_vals = [p.translation_coverage for p in successful]
    quality = {
        'translation_coverage': compute_statistics(coverage_vals),
        'avg_ocr_text_count': round(sum(p.ocr_text_count for p in successful) / len(successful), 1) if successful else 0,
        'avg_translated_text_count': round(sum(p.translated_text_count for p in successful) / len(successful), 1) if successful else 0,
    }

    # ─── 稳定性指标 ───
    error_rate = len(failed) / len(pages) if pages else 0
    retried = [p for p in pages if p.retry_count > 0]
    stability = {
        'error_rate': round(error_rate, 4),
        'failed_count': len(failed),
        'retried_pages': len(retried),
        'total_retries': sum(p.retry_count for p in pages),
    }

    # 异常值检测（各阶段+总耗时）
    outliers = {}
    for stage in ['detection', 'ocr', 'translation', 'inpainting', 'rendering']:
        vals = [getattr(p, stage).elapsed for p in successful]
        detected = detect_outliers(vals, sigma=2.0)
        if detected:
            outliers[stage] = [{'index': i, 'value': round(v, 3), 'page': successful[i].image_name} for i, v in detected]
    total_vals = [p.total_elapsed for p in successful]
    total_outliers = detect_outliers(total_vals, sigma=2.0)
    if total_outliers:
        outliers['total'] = [{'index': i, 'value': round(v, 3), 'page': successful[i].image_name} for i, v in total_outliers]
    stability['outliers'] = outliers

    return {
        'speed': speed,
        'quality': quality,
        'stability': stability,
    }