@echo off
:: ═══════════════════════════════════════════════════════════════════════════════
:: 日中漫画批量翻译 — Sakura Qwen3 (降级方式 B-A) — Windows
:: ═══════════════════════════════════════════════════════════════════════════════

cd /d "%~dp0\..\.."

set SAKURA_GGUF_PATH=%USERPROFILE%\.ollama\models\gguf\sakura-14b-qwen2.5-v1.0-q4_k_m.gguf
if not defined SAKURA_API_BASE set SAKURA_API_BASE=http://localhost:11434/v1
set SAKURA_MODEL=sakura-14b-qwen2.5-v1.0
set TRANSLATOR_MODE=degraded

:: 激活 Python 环境（conda 优先，不存在则尝试 venv）
if not defined CONDA_ENV set CONDA_ENV=manga-translator
where conda >nul 2>nul
if %ERRORLEVEL% equ 0 (
    call conda activate %CONDA_ENV%
) else (
    if exist "venv\Scripts\activate.bat" (
        call venv\Scripts\activate.bat
        echo [INFO] 使用 venv 环境
    ) else (
        echo [WARN] 未检测到 conda 或 venv，使用系统 Python
    )
)

echo ============================================
echo   日中漫画批量翻译工具
echo   [Sakura Qwen3 - 降级模式: B-A Fallback]
echo ============================================
echo.

python -m manga_translator.batch

echo.
pause
