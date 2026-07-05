#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 日中漫画批量翻译 — Sakura Galtransl (方式C, R18友好) — Linux
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."  # Go to project root

export GALTRANS_GGUF_PATH="$HOME/.ollama/models/gguf/Sakura-Galtransl-14B-v3.8-Q4_K_M.gguf"
export TRANSLATOR_MODE="galtransl"

# 激活 conda 环境
source ~/.zshrc 2>/dev/null || source ~/.bashrc 2>/dev/null
conda activate ${CONDA_ENV:-TraeAI-2} 2>/dev/null

echo "============================================"
echo "  日中漫画批量翻译工具"
echo "  [Sakura Galtransl - 方式C: R18友好]"
echo "============================================"
echo ""

python -m manga_translator.batch

echo ""
echo "按回车键退出..."
read
