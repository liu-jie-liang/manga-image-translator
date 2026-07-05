#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 日中漫画批量翻译 — Sakura Galtransl 续传翻译 (方式C, R18友好)
# ═══════════════════════════════════════════════════════════════════════════════
#
# 翻译器: Sakura-GalTransl-14B-v3.8 (方式C GGUF 直连)
# 模型:   Sakura-Galtransl-14B-v3.8-Q4_K_M
# 注意:   - 续传模式：跳过已翻译的图片，只翻译新增图片
#         - 不启用基准测试模式
#         - 模型不可用时直接报错，不做降级
#
# 方式C: 本地 Galtransl GGUF 直连 GPU
export GALTRANS_GGUF_PATH="$HOME/.ollama/models/gguf/Sakura-Galtransl-14B-v3.8-Q4_K_M.gguf"
# ─── 翻译器配置结束 ───────────────────────────────────────────────────────────

# 硬编码翻译模式: 方式C (Galtransl GGUF)
export TRANSLATOR_MODE="galtransl"
# 续传模式: 跳过已翻译图片 + 不启用基准测试
export RETRANS=false
export BENCHMARK=false

# 激活 conda 环境
source ~/.zshrc 2>/dev/null || source ~/.bashrc 2>/dev/null
conda activate TraeAI-2 2>/dev/null

echo "============================================"
echo "  日中漫画批量翻译工具"
echo "  [Sakura Galtransl - 续传翻译]"
echo "============================================"
echo ""

python -m manga_translator.batch

echo ""
echo "按任意键关闭窗口..."
read -n 1