"""TDD tests for manga_translator.benchmark module."""

import pytest
import time
import json
from dataclasses import asdict

from manga_translator.benchmark import (
    StageTiming,
    PageMetrics,
    BenchmarkContext,
    benchmark_context,
    compute_statistics,
    compute_percentile,
    detect_outliers,
)


class TestStageTiming:
    """Test StageTiming dataclass."""

    def test_create_default(self):
        st = StageTiming()
        assert st.elapsed == 0.0
        assert st.start_ts == 0.0
        assert st.end_ts == 0.0

    def test_create_with_values(self):
        st = StageTiming(elapsed=1.5, start_ts=100.0, end_ts=101.5)
        assert st.elapsed == 1.5
        assert st.start_ts == 100.0
        assert st.end_ts == 101.5

    def test_serializable(self):
        st = StageTiming(elapsed=1.5, start_ts=100.0, end_ts=101.5)
        d = asdict(st)
        assert json.dumps(d)  # must not raise


class TestPageMetrics:
    """Test PageMetrics dataclass."""

    def test_create_default(self):
        pm = PageMetrics(page_index=0, image_name="001.jpg")
        assert pm.page_index == 0
        assert pm.image_name == "001.jpg"
        assert pm.detection.elapsed == 0.0
        assert pm.ocr.elapsed == 0.0
        assert pm.translation.elapsed == 0.0
        assert pm.inpainting.elapsed == 0.0
        assert pm.rendering.elapsed == 0.0
        assert pm.total_elapsed == 0.0
        assert pm.ocr_text_count == 0
        assert pm.translated_text_count == 0
        assert pm.prompt_tokens == 0
        assert pm.completion_tokens == 0
        assert pm.translation_ttfb == 0.0
        assert pm.error is None
        assert pm.retry_count == 0

    def test_total_auto_computed(self):
        pm = PageMetrics(page_index=0, image_name="001.jpg")
        pm.detection = StageTiming(elapsed=0.5)
        pm.ocr = StageTiming(elapsed=1.0)
        pm.translation = StageTiming(elapsed=3.0)
        pm.inpainting = StageTiming(elapsed=1.5)
        pm.rendering = StageTiming(elapsed=0.3)
        pm.compute_total()
        assert pm.total_elapsed == pytest.approx(6.3)

    def test_translation_coverage(self):
        pm = PageMetrics(page_index=0, image_name="001.jpg")
        pm.ocr_text_count = 10
        pm.translated_text_count = 8
        assert pm.translation_coverage == pytest.approx(0.8)

    def test_translation_coverage_zero_ocr(self):
        pm = PageMetrics(page_index=0, image_name="001.jpg")
        pm.ocr_text_count = 0
        pm.translated_text_count = 0
        assert pm.translation_coverage == 1.0  # no text = no coverage issue

    def test_serializable(self):
        pm = PageMetrics(page_index=0, image_name="001.jpg")
        pm.detection = StageTiming(elapsed=0.5)
        pm.ocr = StageTiming(elapsed=1.0)
        pm.translation = StageTiming(elapsed=3.0)
        pm.inpainting = StageTiming(elapsed=1.5)
        pm.rendering = StageTiming(elapsed=0.3)
        pm.compute_total()
        d = asdict(pm)
        assert json.dumps(d)  # must not raise


class TestBenchmarkContext:
    """Test BenchmarkContext singleton."""

    def test_singleton(self):
        ctx1 = BenchmarkContext()
        ctx2 = BenchmarkContext()
        assert ctx1 is ctx2

    def test_reset(self):
        ctx = BenchmarkContext()
        ctx.start_page("001.jpg")
        ctx.reset()
        assert len(ctx.pages) == 0
        assert ctx.mode == ""
        assert ctx.start_time == 0.0

    def test_start_page(self):
        ctx = BenchmarkContext()
        ctx.reset()
        ctx.start_page("001.jpg")
        assert len(ctx.pages) == 1
        assert ctx.pages[0].image_name == "001.jpg"
        assert ctx.pages[0].page_index == 0

    def test_start_page_increments_index(self):
        ctx = BenchmarkContext()
        ctx.reset()
        ctx.start_page("a.jpg")
        ctx.start_page("b.jpg")
        assert len(ctx.pages) == 2
        assert ctx.pages[0].page_index == 0
        assert ctx.pages[1].page_index == 1

    def test_record_stage_timing(self):
        ctx = BenchmarkContext()
        ctx.reset()
        ctx.start_page("001.jpg")
        ctx.record_stage("detection", 0.5, 100.0, 100.5)
        ctx.record_stage("ocr", 1.0, 100.5, 101.5)
        assert ctx.pages[0].detection.elapsed == 0.5
        assert ctx.pages[0].ocr.elapsed == 1.0

    def test_record_stage_no_page_raises(self):
        ctx = BenchmarkContext()
        ctx.reset()
        with pytest.raises(ValueError, match="No active page"):
            ctx.record_stage("detection", 0.5)

    def test_record_translation_usage(self):
        ctx = BenchmarkContext()
        ctx.reset()
        ctx.start_page("001.jpg")
        ctx.record_translation_usage(
            elapsed=3.0, ttfb=0.5,
            prompt_tokens=100, completion_tokens=50
        )
        assert ctx.pages[0].translation.elapsed == 3.0
        assert ctx.pages[0].translation_ttfb == 0.5
        assert ctx.pages[0].prompt_tokens == 100
        assert ctx.pages[0].completion_tokens == 50

    def test_record_text_counts(self):
        ctx = BenchmarkContext()
        ctx.reset()
        ctx.start_page("001.jpg")
        ctx.record_text_counts(ocr_count=10, translated_count=8)
        assert ctx.pages[0].ocr_text_count == 10
        assert ctx.pages[0].translated_text_count == 8

    def test_record_error(self):
        ctx = BenchmarkContext()
        ctx.reset()
        ctx.start_page("001.jpg")
        ctx.record_error("OCR timeout")
        assert ctx.pages[0].error == "OCR timeout"
        assert ctx.pages[0].retry_count == 0

    def test_record_retry(self):
        ctx = BenchmarkContext()
        ctx.reset()
        ctx.start_page("001.jpg")
        ctx.record_retry()
        ctx.record_retry()
        assert ctx.pages[0].retry_count == 2

    def test_module_level_benchmark_context(self):
        assert benchmark_context is BenchmarkContext()


class TestComputeStatistics:
    """Test statistics computation functions."""

    def test_compute_percentile(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert compute_percentile(values, 50) == 3.0
        # P90 of 5 values via linear interpolation: k=3.6, 4 + 0.6*(5-4) = 4.6
        assert compute_percentile(values, 90) == 4.6
        assert compute_percentile(values, 0) == 1.0
        assert compute_percentile(values, 100) == 5.0

    def test_compute_percentile_single(self):
        assert compute_percentile([42.0], 50) == 42.0

    def test_compute_percentile_empty(self):
        assert compute_percentile([], 50) == 0.0

    def test_detect_outliers(self):
        values = [1.0, 2.0, 3.0, 4.0, 200.0]
        # avg=42, std≈87.7, 2σ threshold=42+175.4=217.4, 200 not > 217.4
        # Use sigma=1.5: threshold=42+131.6=173.6, 200 > 173.6 ✓
        outliers = detect_outliers(values, sigma=1.5)
        assert len(outliers) == 1
        assert outliers[0][0] == 4  # index
        assert outliers[0][1] == 200.0  # value

    def test_detect_outliers_none(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        outliers = detect_outliers(values, sigma=2.0)
        assert len(outliers) == 0

    def test_detect_outliers_small_sample(self):
        # With < 3 values, std is unreliable, return empty
        outliers = detect_outliers([1.0, 2.0], sigma=2.0)
        assert len(outliers) == 0

    def test_compute_statistics_basic(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        stats = compute_statistics(values)
        assert stats['count'] == 5
        assert stats['sum'] == 15.0
        assert stats['avg'] == 3.0
        assert stats['min'] == 1.0
        assert stats['max'] == 5.0
        assert stats['p50'] == 3.0
        assert stats['p90'] == 4.6  # linear interpolation
        assert stats['p95'] == 4.8  # linear interpolation
        assert stats['p99'] == 4.96  # linear interpolation
        assert 'std' in stats
        assert 'cv' in stats

    def test_compute_statistics_single(self):
        stats = compute_statistics([42.0])
        assert stats['count'] == 1
        assert stats['avg'] == 42.0
        assert stats['min'] == 42.0
        assert stats['max'] == 42.0
        assert stats['std'] == 0.0
        assert stats['cv'] == 0.0

    def test_compute_statistics_empty(self):
        stats = compute_statistics([])
        assert stats['count'] == 0
        assert stats['sum'] == 0.0
        assert stats['avg'] == 0.0