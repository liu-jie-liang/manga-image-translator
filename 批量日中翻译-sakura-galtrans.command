#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 日中漫画批量翻译 — Sakura Galtransl (方式C, R18友好)
# ═══════════════════════════════════════════════════════════════════════════════
#
# 翻译器: Sakura-GalTransl-14B-v3.8 (方式C GGUF 直连)
# 模型:   Sakura-Galtransl-14B-v3.8-Q4_K_M
# 注意:   模型不可用时直接报错，不做降级
#
# 方式C: 本地 Galtransl GGUF 直连 GPU
export GALTRANS_GGUF_PATH="$HOME/.ollama/models/gguf/Sakura-Galtransl-14B-v3.8-Q4_K_M.gguf"
# ─── 翻译器配置结束 ───────────────────────────────────────────────────────────

# 硬编码翻译模式: 方式C (Galtransl GGUF)
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
echo "按任意键关闭窗口..."
read -n 1