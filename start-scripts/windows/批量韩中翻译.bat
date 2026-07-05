@echo off
:: ═══════════════════════════════════════════════════════════════════════════════
:: 韩中漫画批量翻译 — Windows 启动脚本
:: ═══════════════════════════════════════════════════════════════════════════════

cd /d "%~dp0\..\.."

if not defined CUSTOM_OPENAI_API_BASE set CUSTOM_OPENAI_API_BASE=http://localhost:11434/v1
set CUSTOM_OPENAI_MODEL=qwen3:14b-q4_k_m
set CUSTOM_OPENAI_API_KEY=ollama

:: 激活 conda 环境
if not defined CONDA_ENV set CONDA_ENV=TraeAI-2
call conda activate %CONDA_ENV% 2>nul

echo 启动韩中漫画批量翻译...
echo 翻译器: Qwen3 14B (Ollama) — 韩文-简体中文
echo 无降级链，Ollama 不可达时报错退出
python -m manga_translator.batch_ko

echo.
pause
