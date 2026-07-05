#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 日中漫画批量翻译 — Sakura Qwen3 (降级方式 B→A)
# ═══════════════════════════════════════════════════════════════════════════════
#
# 翻译器: Sakura-14B-Qwen2.5 (方式B GGUF 优先, 方式A Ollama 降级)
# 模型:   sakura-14b-qwen2.5-v1.0
#
# 方式B: 本地 Sakura GGUF 直连 GPU
export SAKURA_GGUF_PATH="$HOME/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf"
# 方式A (降级): Ollama HTTP 远程服务
export SAKURA_API_BASE="${SAKURA_API_BASE:-http://localhost:11434/v1}"
export SAKURA_MODEL='sakura-14b-qwen2.5-v1.0'
# ─── 翻译器配置结束 ───────────────────────────────────────────────────────────

# 硬编码翻译模式: 降级方式 (B→A fallback)
export TRANSLATOR_MODE="degraded"

# 激活 conda 环境
source ~/.zshrc 2>/dev/null || source ~/.bashrc 2>/dev/null
conda activate ${CONDA_ENV:-TraeAI-2} 2>/dev/null

echo "============================================"
echo "  日中漫画批量翻译工具"
echo "  [Sakura Qwen3 - 降级模式: B→A Fallback]"
echo "============================================"
echo ""

python -m manga_translator.batch

echo ""
echo "按任意键关闭窗口..."
read -n 1