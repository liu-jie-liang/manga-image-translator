"""基准测试报告生成器

生成 Markdown 格式的专业分析报告，包含速度/质量/稳定性三大维度的详细分析。

输出格式：
- Markdown 报告: test/results/benchmark/{mode}/YYYYMMDD-HHMMSS.md
- JSON 原始数据: test/results/benchmark/{mode}/YYYYMMDD-HHMMSS.json
- JSON 统计数据: test/results/benchmark/{mode}/YYYYMMDD-HHMMSS-stats.json
- Per-Page CSV: test/results/benchmark/{mode}/YYYYMMDD-HHMMSS.csv
"""

import os
import json
import csv
from datetime import datetime
from typing import List, Optional, Dict, Any


# ═══════════════════════════════════════════════════════════════════════════════
# 格式化辅助
# ═══════════════════════════════════════════════════════════════════════════════

def _format_seconds(seconds: float) -> str:
    """格式化秒数为可读字符串。"""
    if seconds < 60:
        return f'{seconds:.2f}s'
    elif seconds < 3600:
        m = int(seconds // 60)
        s = seconds % 60
        return f'{m}m {s:.0f}s'
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f'{h}h {m}m {s:.0f}s'


def _format_percentage(value: float) -> str:
    """格式化百分比。"""
    return f'{value * 100:.2f}%'


def _format_stage_table(stages: dict) -> str:
    """生成阶段耗时表格。

    Args:
        stages: 各阶段统计数据字典

    Returns:
        Markdown 格式表格
    """
    stage_names = {
        'detection': '检测 (Detection)',
        'ocr': 'OCR识别',
        'translation': '翻译 (Translation)',
        'inpainting': '修复 (Inpainting)',
        'rendering': '渲染 (Rendering)',
    }

    # 计算总平均耗时
    total_avg = sum(
        s['avg'] for s in stages.values()
        if isinstance(s, dict) and 'avg' in s
    )

    lines = [
        '| 阶段 | Avg | P50 | P90 | P95 | P99 | Std | CV | 占总耗时 |',
        '|------|-----|-----|-----|-----|-----|-----|-----|----------|',
    ]

    for key, name in stage_names.items():
        if key not in stages:
            continue
        s = stages[key]
        if not isinstance(s, dict) or 'avg' not in s:
            continue
        pct = (s['avg'] / total_avg * 100) if total_avg > 0 else 0
        lines.append(
            f'| {name} | {s["avg"]:.2f}s | {s.get("p50", 0):.2f}s | '
            f'{s.get("p90", 0):.2f}s | {s.get("p95", 0):.2f}s | '
            f'{s.get("p99", 0):.2f}s | {s["std"]:.2f}s | '
            f'{s.get("cv", 0):.2f} | {pct:.1f}% |'
        )

    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 归因分析
# ═══════════════════════════════════════════════════════════════════════════════

def _attribution_analysis(stats: dict) -> str:
    """对性能瓶颈进行归因分析。

    Args:
        stats: 统计数据

    Returns:
        归因分析文本
    """
    speed = stats.get('speed', {})
    stages = speed.get('stages', {})
    stability = stats.get('stability', {})
    quality = stats.get('quality', {})

    lines = []
    lines.append('### 5.1 速度瓶颈归因')
    lines.append('')

    # 计算各阶段占比
    total_avg = sum(
        s['avg'] for s in stages.values()
        if isinstance(s, dict) and 'avg' in s
    )

    if total_avg > 0:
        stage_contributions = [
            (name, s['avg'], s['avg'] / total_avg * 100)
            for name, s in stages.items()
            if isinstance(s, dict) and 'avg' in s
        ]
        stage_contributions.sort(key=lambda x: x[1], reverse=True)

        lines.append('**各阶段耗时占比（从高到低）：**')
        lines.append('')
        for name, avg, pct in stage_contributions:
            stage_labels = {
                'detection': '检测', 'ocr': 'OCR', 'translation': '翻译',
                'inpainting': '修复', 'rendering': '渲染',
            }
            label = stage_labels.get(name, name)
            lines.append(f'- **{label}**：{avg:.2f}s（{pct:.1f}%）')

        # 找出最大瓶颈
        top_bottleneck = stage_contributions[0]
        lines.append('')
        if top_bottleneck[0] == 'translation':
            lines.append(
                '**归因结论**：翻译阶段是主要性能瓶颈，占总耗时 **{:.1f}%**。'
                '优化方向：\n'
                '- 提高模型推理速度（使用更小量化或硬件加速）\n'
                '- 减少每页翻译文本量（合并相邻文本框）\n'
                '- 增加并发翻译能力（调整 batch_size）'
                .format(top_bottleneck[2])
            )
        elif top_bottleneck[0] in ('detection', 'ocr'):
            lines.append(
                '**归因结论**：{} 阶段是主要性能瓶颈，占总耗时 **{:.1f}%**。'
                '优化方向：\n'
                '- 检查模型是否使用了 GPU 加速\n'
                '- 考虑使用更轻量的检测/OCR 模型\n'
                '- 减少输入图像分辨率'
                .format(
                    {'detection': '文字检测', 'ocr': 'OCR识别'}.get(top_bottleneck[0], top_bottleneck[0]),
                    top_bottleneck[2],
                )
            )

    # 稳定性归因
    lines.append('')
    lines.append('### 5.2 稳定性归因')
    lines.append('')

    error_rate = stability.get('error_rate', 0)
    failed_count = stability.get('failed_count', 0)
    retried_pages = stability.get('retried_pages', 0)
    outliers = stability.get('outliers', {})

    if failed_count > 0:
        lines.append(f'- **失败页面**：{failed_count} 页（错误率 {error_rate * 100:.1f}%）')
        lines.append('  - 可能原因：网络超时（Ollama HTTP）、模型显存不足、图片格式异常')
        lines.append('  - 建议：检查 `--attempts` 重试次数配置，确认 Ollama 服务稳定性')
    else:
        lines.append('- **失败页面**：0 页，稳定性良好')

    if retried_pages > 0:
        lines.append(f'- **重试页面**：{retried_pages} 页')
        lines.append('  - 建议：分析重试页面特征，判断是否为偶发问题')

    if outliers:
        lines.append('')
        lines.append('**异常值分析（2σ 阈值）：**')
        for stage, items in outliers.items():
            stage_labels = {
                'detection': '检测', 'ocr': 'OCR', 'translation': '翻译',
                'inpainting': '修复', 'rendering': '渲染', 'total': '总耗时',
            }
            label = stage_labels.get(stage, stage)
            page_names = ', '.join(item['page'] for item in items[:3])
            if len(items) > 3:
                page_names += f' 等 {len(items)} 页'
            lines.append(f'- **{label}**异常：{page_names}')
            lines.append('  - 可能原因：特定图片复杂度高、文本框数多、网络波动')

    # 质量归因
    lines.append('')
    lines.append('### 5.3 质量归因')
    lines.append('')

    coverage = quality.get('translation_coverage', {})
    if isinstance(coverage, dict) and coverage.get('avg', 1.0) < 0.95:
        lines.append(
            f'- **翻译覆盖率**：{coverage["avg"] * 100:.1f}%（低于 95%）'
        )
        lines.append('  - 可能原因：部分文本框 OCR 识别失败或翻译器返回空结果')
        lines.append('  - 建议：检查 OCR 置信度阈值，调整翻译器超时设置')

    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 优化建议
# ═══════════════════════════════════════════════════════════════════════════════

def _optimization_suggestions(stats: dict) -> str:
    """生成优化建议。

    Args:
        stats: 统计数据

    Returns:
        优化建议 Markdown 文本
    """
    speed = stats.get('speed', {})
    stages = speed.get('stages', {})
    stability = stats.get('stability', {})
    quality = stats.get('quality', {})

    suggestions = []

    # 速度建议
    translation = stages.get('translation', {})
    if isinstance(translation, dict) and translation.get('avg', 0) > 15:
        suggestions.append(
            '1. **翻译速度优化**：翻译阶段平均耗时较长（{:.1f}s），建议：\n'
            '   - 考虑使用更低量化（如 Q4_K_M → Q3_K_M）提升推理速度\n'
            '   - 检查 GPU 是否被充分利用（nvidia-smi / mps 监控）\n'
            '   - 评估 batch_size 参数是否合适'
            .format(translation['avg'])
        )

    detection = stages.get('detection', {})
    if isinstance(detection, dict) and detection.get('cv', 0) > 0.5:
        suggestions.append(
            '2. **检测阶段稳定性**：CV（变异系数）较高（{:.2f}），表示不同页面耗时差异大，'
            '建议检查图片尺寸是否差异过大'
            .format(detection['cv'])
        )

    # 稳定性建议
    if stability.get('error_rate', 0) > 0.05:
        suggestions.append(
            '3. **稳定性改进**：错误率 {:.1f}%，建议增加重试次数或调查失败原因'
            .format(stability['error_rate'] * 100)
        )

    # 质量建议
    coverage = quality.get('translation_coverage', {})
    if isinstance(coverage, dict) and coverage.get('avg', 1.0) < 0.95:
        suggestions.append(
            '4. **翻译质量**：覆盖率 {:.1f}%，建议检查 OCR 和翻译结果'
            .format(coverage['avg'] * 100)
        )

    if not suggestions:
        suggestions.append('当前翻译性能良好，暂无优化建议。')

    return '\n\n'.join(suggestions)


# ═══════════════════════════════════════════════════════════════════════════════
# 报告生成
# ═══════════════════════════════════════════════════════════════════════════════

def generate_benchmark_report(
    mode_label: str,
    translator_mode: str,
    session_elapsed: float,
    stats: dict,
    pages: List[dict],
    oom_detected: bool = False,
    oom_message: str = '',
) -> str:
    """生成 Markdown 格式的基准测试报告。

    Args:
        mode_label: 模式标签 (modeA/modeB)
        translator_mode: 翻译器模式 (ollama/gguf)
        session_elapsed: 会话总耗时 (秒)
        stats: 统计数据 (来自 compute_benchmark_statistics)
        pages: 逐页数据
        oom_detected: 是否检测到 OOM
        oom_message: OOM 信息

    Returns:
        Markdown 格式报告文本
    """
    speed = stats.get('speed', {})
    quality = stats.get('quality', {})
    stability = stats.get('stability', {})
    judge = stats.get('judge', {})

    mode_display = {
        'modeA': '方式A (Ollama HTTP)',
        'modeB': '方式B (本地 GGUF)',
    }.get(mode_label, mode_label)

    lines = [
        f'# 日中漫画翻译性能基准测试报告',
        '',
        f'**模式**：{mode_display}',
        f'**生成时间**：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        '',
        '---',
        '',
        '## 1. 测试概况',
        '',
        f'| 指标 | 数值 |',
        f'|------|------|',
        f'| 总页数 | {speed.get("total_pages", 0)} |',
        f'| 成功页数 | {speed.get("successful_pages", 0)} |',
        f'| 失败页数 | {speed.get("failed_pages", 0)} |',
        f'| 总耗时 | {_format_seconds(session_elapsed)} |',
        f'| 平均每页耗时 | {_format_seconds(speed.get("avg_page_time", 0))} |',
        f'| 吞吐量 | {speed.get("pages_per_minute", 0):.2f} 页/分钟 |',
    ]

    if oom_detected:
        lines.append(f'| ⚠️ OOM | {oom_message} |')

    lines.extend([
        '',
        '---',
        '',
        '## 2. 速度分析 (Speed)',
        '',
        '### 2.1 管线阶段耗时分布',
        '',
        '下表展示各管线阶段的耗时统计（仅统计成功页面）：',
        '',
        _format_stage_table(speed.get('stages', {})),
        '',
        '**说明**：',
        '- **Avg**：算术平均耗时',
        '- **P50/P90/P95/P99**：百分位数，反映耗时分布',
        '- **Std**：标准差，反映耗时波动',
        '- **CV**：变异系数（Std/Avg），>0.3 表示波动较大',
        '- **占总耗时**：该阶段平均耗时占总平均耗时的百分比',
    ])

    # Token 吞吐量
    token = speed.get('token', {})
    if token:
        lines.extend([
            '',
            '### 2.2 Token 吞吐量',
            '',
            f'| 指标 | 数值 |',
            f'|------|------|',
            f'| 总 Prompt Tokens | {token.get("total_prompt_tokens", 0)} |',
            f'| 总 Completion Tokens | {token.get("total_completion_tokens", 0)} |',
            f'| 总 Tokens | {token.get("total_tokens", 0)} |',
            f'| 翻译吞吐量 | {token.get("tokens_per_second", 0):.2f} tokens/s |',
        ])

    # 质量分析
    lines.extend([
        '',
        '---',
        '',
        '## 3. 质量分析 (Quality)',
        '',
    ])

    coverage = quality.get('translation_coverage', {})
    if isinstance(coverage, dict):
        lines.extend([
            '### 3.1 翻译覆盖率',
            '',
            f'| 指标 | 数值 |',
            f'|------|------|',
            f'| 平均覆盖率 | {_format_percentage(coverage.get("avg", 0))} |',
            f'| 最低覆盖率 | {_format_percentage(coverage.get("min", 0))} |',
            f'| 覆盖率 P50 | {_format_percentage(coverage.get("p50", 0))} |',
        ])

    lines.extend([
        '',
        '### 3.2 文本统计',
        '',
        f'| 指标 | 数值 |',
        f'|------|------|',
        f'| 平均 OCR 文本框数 | {quality.get("avg_ocr_text_count", 0):.1f} |',
        f'| 平均翻译文本框数 | {quality.get("avg_translated_text_count", 0):.1f} |',
    ])

    # LLM-Judge 评分
    if judge:
        lines.extend([
            '',
            '### 3.3 LLM-Judge 评分分布',
            '',
            f'| 指标 | 数值 |',
            f'|------|------|',
            f'| 已评分页数 | {judge.get("total_scored", 0)} |',
            f'| 可接受页数 (≥4分) | {judge.get("acceptable_count", 0)} |',
            f'| 可接受率 | {_format_percentage(judge.get("acceptable_rate", 0))} |',
            f'| 平均分 | {judge.get("avg_score", 0):.1f} |',
        ])

        dist = judge.get('score_distribution', {})
        if dist:
            lines.extend([
                '',
                '| 评分 | 页数 | 占比 |',
                '|------|------|------|',
            ])
            total = judge.get('total_scored', 1)
            for score in ['5', '4', '3', '2', '1']:
                count = dist.get(score, 0)
                pct = count / total * 100 if total > 0 else 0
                bar = '█' * int(pct / 5)
                lines.append(f'| {score} 分 | {count} | {bar} {pct:.1f}% |')

    # 稳定性分析
    lines.extend([
        '',
        '---',
        '',
        '## 4. 稳定性分析 (Stability)',
        '',
        f'| 指标 | 数值 |',
        f'|------|------|',
        f'| 错误率 | {_format_percentage(stability.get("error_rate", 0))} |',
        f'| 失败页数 | {stability.get("failed_count", 0)} |',
        f'| 重试页数 | {stability.get("retried_pages", 0)} |',
        f'| 总重试次数 | {stability.get("total_retries", 0)} |',
    ])

    outliers = stability.get('outliers', {})
    if outliers:
        lines.extend([
            '',
            '### 4.1 异常值检测（2σ 阈值）',
            '',
        ])
        for stage, items in outliers.items():
            stage_labels = {
                'detection': '检测', 'ocr': 'OCR', 'translation': '翻译',
                'inpainting': '修复', 'rendering': '渲染', 'total': '总耗时',
            }
            label = stage_labels.get(stage, stage)
            page_list = ', '.join(
                f'`{item["page"]}`({item["value"]:.2f}s)' for item in items[:5]
            )
            if len(items) > 5:
                page_list += f' 等 {len(items)} 页'
            lines.append(f'- **{label}**：{page_list}')

    # 归因分析
    lines.extend([
        '',
        '---',
        '',
        '## 5. 归因分析',
        '',
        _attribution_analysis(stats),
    ])

    # 优化建议
    lines.extend([
        '',
        '---',
        '',
        '## 6. 优化建议',
        '',
        _optimization_suggestions(stats),
    ])

    # 逐页详情
    if pages:
        lines.extend([
            '',
            '---',
            '',
            '## 7. 逐页详情',
            '',
            '| # | 图片 | 检测 | OCR | 翻译 | 修复 | 渲染 | 总耗时 | 状态 | 评分 |',
            '|---|------|------|-----|------|------|------|--------|------|------|',
        ])
        for p in pages:
            det = p.get('detection', {}).get('elapsed', 0)
            ocr = p.get('ocr', {}).get('elapsed', 0)
            trans = p.get('translation', {}).get('elapsed', 0)
            inp = p.get('inpainting', {}).get('elapsed', 0)
            rend = p.get('rendering', {}).get('elapsed', 0)
            total = p.get('total_elapsed', 0)
            status = '❌' if p.get('error') else '✅'
            score = p.get('judge_score', '-')
            lines.append(
                f'| {p["page_index"]} | {p["image_name"][:20]} | {det:.1f}s | {ocr:.1f}s | '
                f'{trans:.1f}s | {inp:.1f}s | {rend:.1f}s | {total:.1f}s | {status} | {score} |'
            )

    lines.extend([
        '',
        '---',
        '',
        f'*报告由 benchmark 模块自动生成*',
    ])

    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 文件导出
# ═══════════════════════════════════════════════════════════════════════════════

def save_report(
    report_md: str,
    mode_label: str,
    timestamp: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> str:
    """保存 Markdown 报告到文件。

    Args:
        report_md: Markdown 报告文本
        mode_label: 模式标签 (modeA/modeB)
        timestamp: 时间戳（可选，默认当前时间）
        output_dir: 输出目录（可选，默认 test/results/benchmark/{mode}）

    Returns:
        报告文件路径
    """
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')

    if output_dir is None:
        output_dir = os.path.join('test', 'results', 'benchmark', mode_label)

    os.makedirs(output_dir, exist_ok=True)

    report_path = os.path.join(output_dir, f'{timestamp}.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_md)

    return report_path


def save_per_page_csv(
    pages: List[dict],
    mode_label: str,
    timestamp: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> str:
    """保存逐页数据为 CSV 文件。

    Args:
        pages: 逐页数据
        mode_label: 模式标签
        timestamp: 时间戳
        output_dir: 输出目录

    Returns:
        CSV 文件路径
    """
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')

    if output_dir is None:
        output_dir = os.path.join('test', 'results', 'benchmark', mode_label)

    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, f'{timestamp}.csv')

    fieldnames = [
        'page_index', 'image_name',
        'detection_elapsed', 'ocr_elapsed', 'translation_elapsed',
        'inpainting_elapsed', 'rendering_elapsed', 'total_elapsed',
        'ocr_text_count', 'translated_text_count',
        'prompt_tokens', 'completion_tokens',
        'error', 'retry_count', 'judge_score',
    ]

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for p in pages:
            row = {
                'page_index': p.get('page_index', 0),
                'image_name': p.get('image_name', ''),
                'detection_elapsed': p.get('detection', {}).get('elapsed', 0),
                'ocr_elapsed': p.get('ocr', {}).get('elapsed', 0),
                'translation_elapsed': p.get('translation', {}).get('elapsed', 0),
                'inpainting_elapsed': p.get('inpainting', {}).get('elapsed', 0),
                'rendering_elapsed': p.get('rendering', {}).get('elapsed', 0),
                'total_elapsed': p.get('total_elapsed', 0),
                'ocr_text_count': p.get('ocr_text_count', 0),
                'translated_text_count': p.get('translated_text_count', 0),
                'prompt_tokens': p.get('prompt_tokens', 0),
                'completion_tokens': p.get('completion_tokens', 0),
                'error': p.get('error', ''),
                'retry_count': p.get('retry_count', 0),
                'judge_score': p.get('judge_score', ''),
            }
            writer.writerow(row)

    return csv_path