@echo off
:: ═══════════════════════════════════════════════════════════════════════════════
:: 日中漫画批量翻译 — Sakura Galtransl (方式C, R18友好) — Windows
:: ═══════════════════════════════════════════════════════════════════════════════

cd /d "%~dp0\..\.."

set GALTRANS_GGUF_PATH=%USERPROFILE%\.ollama\models\gguf\Sakura-Galtransl-14B-v3.8-Q4_K_M.gguf
set TRANSLATOR_MODE=galtransl

:: 激活 conda 环境
if not defined CONDA_ENV set CONDA_ENV=TraeAI-2
call conda activate %CONDA_ENV% 2>nul

echo ============================================
echo   日中漫画批量翻译工具
echo   [Sakura Galtransl - 方式C: R18友好]
echo ============================================
echo.

python -m manga_translator.batch

echo.
pause
