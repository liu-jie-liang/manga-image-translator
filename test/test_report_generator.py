"""报告生成器 TDD 测试。"""

import os
import json
import tempfile
import pytest
from manga_translator.report_generator import (
    generate_benchmark_report,
    _format_seconds,
    _format_percentage,
    _format_stage_table,
)


SAMPLE_STATS = {
    'speed': {
        'session_elapsed': 360.5,
        'total_pages': 10,
        'successful_pages': 9,
        'failed_pages': 1,
        'pages_per_minute': 1.66,
        'avg_page_time': 36.05,
        'stages': {
            'detection': {'count': 9, 'avg': 2.1, 'min': 1.5, 'max': 3.0, 'std': 0.5, 'cv': 0.24, 'p50': 2.0, 'p90': 2.8, 'p95': 2.9, 'p99': 3.0},
            'ocr': {'count': 9, 'avg': 4.5, 'min': 3.0, 'max': 6.0, 'std': 1.0, 'cv': 0.22, 'p50': 4.3, 'p90': 5.8, 'p95': 5.9, 'p99': 6.0},
            'translation': {'count': 9, 'avg': 20.0, 'min': 15.0, 'max': 25.0, 'std': 3.5, 'cv': 0.18, 'p50': 19.5, 'p90': 24.0, 'p95': 24.5, 'p99': 25.0},
            'inpainting': {'count': 9, 'avg': 3.0, 'min': 2.0, 'max': 4.5, 'std': 0.8, 'cv': 0.27, 'p50': 2.8, 'p90': 4.2, 'p95': 4.4, 'p99': 4.5},
            'rendering': {'count': 9, 'avg': 1.5, 'min': 1.0, 'max': 2.0, 'std': 0.35, 'cv': 0.23, 'p50': 1.4, 'p90': 1.9, 'p95': 1.95, 'p99': 2.0},
        },
        'total': {'count': 9, 'avg': 31.1, 'min': 22.5, 'max': 38.0, 'std': 5.2, 'cv': 0.17, 'p50': 30.0, 'p90': 37.0, 'p95': 37.5, 'p99': 38.0},
        'token': {
            'total_prompt_tokens': 5000,
            'total_completion_tokens': 3000,
            'total_tokens': 8000,
            'tokens_per_second': 15.0,
        },
    },
    'quality': {
        'translation_coverage': {'count': 9, 'avg': 0.98, 'min': 0.9, 'max': 1.0, 'std': 0.03, 'cv': 0.03, 'p50': 1.0},
        'avg_ocr_text_count': 12.3,
        'avg_translated_text_count': 12.1,
    },
    'stability': {
        'error_rate': 0.1,
        'failed_count': 1,
        'retried_pages': 0,
        'total_retries': 0,
        'outliers': {'translation': [{'index': 5, 'value': 25.0, 'page': 'test_page.png'}]},
    },
    'judge': {
        'total_scored': 8,
        'acceptable_count': 7,
        'acceptable_rate': 0.875,
        'avg_score': 4.2,
        'score_distribution': {'5': 3, '4': 4, '3': 1, '2': 0, '1': 0},
    },
}


SAMPLE_PAGES = [
    {
        'page_index': 0,
        'image_name': 'page001.jpg',
        'detection': {'elapsed': 2.0, 'start_ts': 100.0, 'end_ts': 102.0},
        'ocr': {'elapsed': 4.0, 'start_ts': 102.0, 'end_ts': 106.0},
        'translation': {'elapsed': 18.0, 'start_ts': 106.0, 'end_ts': 124.0},
        'inpainting': {'elapsed': 3.0, 'start_ts': 124.0, 'end_ts': 127.0},
        'rendering': {'elapsed': 1.5, 'start_ts': 127.0, 'end_ts': 128.5},
        'total_elapsed': 28.5,
        'ocr_text_count': 10,
        'translated_text_count': 10,
        'prompt_tokens': 500,
        'completion_tokens': 300,
        'translation_ttfb': 0.5,
        'error': None,
        'retry_count': 0,
        'judge_score': 5,
        'judge_accuracy_ok': True,
        'judge_issues': '无明显问题',
    },
    {
        'page_index': 1,
        'image_name': 'page002.jpg',
        'detection': {'elapsed': 2.5, 'start_ts': 200.0, 'end_ts': 202.5},
        'ocr': {'elapsed': 5.0, 'start_ts': 202.5, 'end_ts': 207.5},
        'translation': {'elapsed': 22.0, 'start_ts': 207.5, 'end_ts': 229.5},
        'inpainting': {'elapsed': 3.5, 'start_ts': 229.5, 'end_ts': 233.0},
        'rendering': {'elapsed': 2.0, 'start_ts': 233.0, 'end_ts': 235.0},
        'total_elapsed': 35.0,
        'ocr_text_count': 15,
        'translated_text_count': 14,
        'prompt_tokens': 600,
        'completion_tokens': 350,
        'translation_ttfb': 0.6,
        'error': None,
        'retry_count': 0,
        'judge_score': 4,
        'judge_accuracy_ok': True,
        'judge_issues': '语序稍显生硬',
    },
]


class TestFormatHelpers:
    """格式化辅助函数测试。"""

    def test_format_seconds(self):
        assert _format_seconds(0) == '0.00s'
        assert _format_seconds(1.5) == '1.50s'
        assert _format_seconds(65) == '1m 5s'
        assert _format_seconds(3661) == '1h 1m 1s'

    def test_format_percentage(self):
        assert _format_percentage(0.5) == '50.00%'
        assert _format_percentage(1.0) == '100.00%'
        assert _format_percentage(0.875) == '87.50%'

    def test_format_stage_table(self):
        """阶段表格应包含所有阶段及总计。"""
        table = _format_stage_table(SAMPLE_STATS['speed']['stages'])
        assert '检测 (Detection)' in table
        assert 'OCR识别' in table
        assert '翻译 (Translation)' in table
        assert '修复 (Inpainting)' in table
        assert '渲染 (Rendering)' in table
        assert '占总耗时' in table  # 占比列
        assert 'CV' in table  # 变异系数


class TestGenerateReport:
    """报告生成测试。"""

    def test_report_contains_sections(self):
        """报告应包含所有必需章节。"""
        report = generate_benchmark_report(
            mode_label='modeA',
            translator_mode='ollama',
            session_elapsed=360.5,
            stats=SAMPLE_STATS,
            pages=SAMPLE_PAGES,
        )
        assert '# 日中漫画翻译性能基准测试报告' in report
        assert '## 1. 测试概况' in report
        assert '## 2. 速度分析 (Speed)' in report
        assert '## 3. 质量分析 (Quality)' in report
        assert '## 4. 稳定性分析 (Stability)' in report
        assert '## 5. 归因分析' in report
        assert '## 6. 优化建议' in report

    def test_report_contains_stage_breakdown(self):
        """报告应包含各阶段耗时详情。"""
        report = generate_benchmark_report('modeA', 'ollama', 360.5, SAMPLE_STATS, SAMPLE_PAGES)
        assert '### 2.1 管线阶段耗时分布' in report
        assert 'Avg' in report
        assert 'P50' in report
        assert 'P90' in report
        assert 'P95' in report

    def test_report_contains_token_stats(self):
        """报告应包含 Token 吞吐量统计。"""
        report = generate_benchmark_report('modeA', 'ollama', 360.5, SAMPLE_STATS, SAMPLE_PAGES)
        assert '### 2.2 Token 吞吐量' in report
        assert '5000' in report or '3000' in report

    def test_report_contains_outlier_warnings(self):
        """报告应标注异常值。"""
        report = generate_benchmark_report('modeA', 'ollama', 360.5, SAMPLE_STATS, SAMPLE_PAGES)
        assert '异常值' in report or 'outlier' in report.lower()
        assert 'test_page.png' in report

    def test_report_contains_score_distribution(self):
        """报告应包含评分分布（如有 Judge 数据）。"""
        report = generate_benchmark_report('modeA', 'ollama', 360.5, SAMPLE_STATS, SAMPLE_PAGES)
        assert 'LLM-Judge 评分分布' in report
        assert '可接受率' in report

    def test_report_no_judge_section_when_empty(self):
        """无 Judge 数据时不应包含评分分布章节。"""
        stats_no_judge = {k: v for k, v in SAMPLE_STATS.items() if k != 'judge'}
        report = generate_benchmark_report('modeA', 'ollama', 360.5, stats_no_judge, SAMPLE_PAGES)
        assert 'LLM-Judge' not in report

    def test_report_json_serializable(self):
        """统计数据和报告应能 JSON 序列化。"""
        json.dumps(SAMPLE_STATS, ensure_ascii=False)
        report = generate_benchmark_report('modeA', 'ollama', 360.5, SAMPLE_STATS, SAMPLE_PAGES)
        assert len(report) > 500  # 报告应有足够长度

    def test_report_attribution_section(self):
        """归因分析应对慢/不稳定部分进行分析。"""
        report = generate_benchmark_report('modeA', 'ollama', 360.5, SAMPLE_STATS, SAMPLE_PAGES)
        assert '归因' in report
        # 翻译阶段占比最大，应有归因
        assert '翻译' in report