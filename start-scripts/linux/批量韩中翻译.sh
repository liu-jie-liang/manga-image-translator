#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 韩中漫画批量翻译 — Linux 启动脚本
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."  # Go to project root

export CUSTOM_OPENAI_API_BASE="${CUSTOM_OPENAI_API_BASE:-http://localhost:11434/v1}"
export CUSTOM_OPENAI_MODEL='qwen3:14b-q4_k_m'
export CUSTOM_OPENAI_API_KEY='ollama'

# 激活 conda 环境
source ~/.zshrc 2>/dev/null || source ~/.bashrc 2>/dev/null
conda activate ${CONDA_ENV:-TraeAI-2} 2>/dev/null

echo "启动韩中漫画批量翻译..."
echo "翻译器: Qwen3 14B (Ollama) — 韩文→简体中文"
echo "无降级链，Ollama 不可达时报错退出"
python -m manga_translator.batch_ko

echo ""
echo "按回车键退出..."
read
