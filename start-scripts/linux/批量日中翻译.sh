#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 日中漫画批量翻译 — Linux 启动脚本 (交互式选择)
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."  # Go to project root

# ─── 翻译器配置 ───────────────────────────────────────────────────────────────
export SAKURA_GGUF_PATH="$HOME/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf"
export GALTRANS_GGUF_PATH="$HOME/.ollama/models/gguf/Sakura-Galtransl-14B-v3.8-Q4_K_M.gguf"
export SAKURA_API_BASE="${SAKURA_API_BASE:-http://localhost:11434/v1}"
export SAKURA_MODEL='sakura-14b-qwen2.5-v1.0'
# ─── 翻译器配置结束 ───────────────────────────────────────────────────────────

# 激活 conda 环境
source ~/.zshrc 2>/dev/null || source ~/.bashrc 2>/dev/null
conda activate ${CONDA_ENV:-manga-translator} 2>/dev/null

echo "============================================"
echo "  日中漫画批量翻译工具"
echo "============================================"
echo ""
echo "请选择翻译模式:"
echo "  a) 降级方式 (B→A fallback, 优先Sakura GGUF)"
echo "  b) 方式C (Galtransl GGUF, R18友好)"
echo ""
read -p "请输入 a 或 b (默认: a): " mode_choice
mode_choice=${mode_choice:-a}

case "$mode_choice" in
    b|B)
        export TRANSLATOR_MODE="galtransl"
        echo "已选择: 方式C (Galtransl GGUF)"
        ;;
    *)
        export TRANSLATOR_MODE="degraded"
        echo "已选择: 降级方式 (B→A fallback)"
        ;;
esac
echo ""

python -m manga_translator.batch

echo ""
echo "按回车键退出..."
read
