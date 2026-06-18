#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 日中漫画批量翻译 — 双击启动脚本
# ═══════════════════════════════════════════════════════════════════════════════
#
# 使用前请确保已配置好 conda 环境 TraeAI-2
#
# ─── 翻译器配置 ───────────────────────────────────────────────────────────────
# 两种翻译方式，通过环境变量切换：
#
#   方式B (推荐离线/独立使用): 本地 GGUF 直连 GPU
#     - 需要设置 SAKURA_GGUF_PATH 指向 .gguf 模型文件
#     - 不依赖 Ollama 服务，离线可用
#     - 首次加载模型约 10s，之后翻译速度与方式A持平
#
#   方式A (推荐在线/简便使用): Ollama HTTP 远程服务
#     - 需要设置 SAKURA_API_BASE 指向 Ollama 服务地址
#     - 需要设置 SAKURA_MODEL 指定模型名称
#     - 无需额外安装 llama-cpp-python
#
#   降级链: 启动时自动检测 → 方式B优先 → 方式A降级 → 报错退出
#   (如果两种方式都配置了，优先使用方式B)
#
#   实测性能 (158页 E2E, M4 Pro 64GB, 2026-06-12):
#     方式B (GGUF):  16.2 min, 6.2s/页, 100% 成功率
#     方式A (Ollama): 16.1 min, 6.1s/页, 100% 成功率
#     两种方式速度差异 <1%，可忽略
# ──────────────────────────────────────────────────────────────────────────────
# 方式B (推荐): 本地 GGUF 直连 GPU
export SAKURA_GGUF_PATH="$HOME/.ollama/models/gguf/sakura-14b-qwen2.5-v1.0-q4_k_m.gguf"
# 方式A (降级): Ollama HTTP 远程服务
export SAKURA_API_BASE='http://192.168.1.15:11434/v1'
export SAKURA_MODEL='sakura-14b-qwen2.5-v1.0'
# ─── 翻译器配置结束 ───────────────────────────────────────────────────────────

# 激活 conda 环境
source ~/.zshrc 2>/dev/null || source ~/.bashrc 2>/dev/null
conda activate TraeAI-2 2>/dev/null

echo "启动日中漫画批量翻译..."
echo "翻译器降级链: 方式B(GGUF) → 方式A(Ollama) → 报错退出"
python -m manga_translator.batch

echo ""
echo "按任意键关闭窗口..."
read -n 1