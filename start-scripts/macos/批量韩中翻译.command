#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 韩中漫画批量翻译 — 双击启动脚本
# ═══════════════════════════════════════════════════════════════════════════════
#
# 使用前请确保已配置好 conda 环境 TraeAI-2
# 使用前请确保 Ollama 服务已启动且已拉取 qwen3:14b-q4_k_m 模型
#
# ─── 翻译器配置 ───────────────────────────────────────────────────────────────
# 翻译方式: Qwen3 14B via Ollama HTTP
#   - Ollama 服务地址: <OLLAMA_HOST>:11434
#   - 模型: qwen3:14b-q4_k_m
#   - 无降级链，Ollama 不可达时报错退出
# ──────────────────────────────────────────────────────────────────────────────

# Ollama 环境变量
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
echo "按任意键关闭窗口..."
read -n 1