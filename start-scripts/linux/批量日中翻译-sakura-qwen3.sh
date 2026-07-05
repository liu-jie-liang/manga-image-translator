#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 日中漫画批量翻译 — Sakura Qwen3 (降级方式 B→A) — Linux
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."  # Go to project root

export SAKURA_GGUF_PATH="$HOME/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf"
export SAKURA_API_BASE="${SAKURA_API_BASE:-http://localhost:11434/v1}"
export SAKURA_MODEL='sakura-14b-qwen2.5-v1.0'
export TRANSLATOR_MODE="degraded"

# 激活 conda 环境
source ~/.zshrc 2>/dev/null || source ~/.bashrc 2>/dev/null
conda activate ${CONDA_ENV:-manga-translator} 2>/dev/null

echo "============================================"
echo "  日中漫画批量翻译工具"
echo "  [Sakura Qwen3 - 降级模式: B→A Fallback]"
echo "============================================"
echo ""

python -m manga_translator.batch

echo ""
echo "按回车键退出..."
read
