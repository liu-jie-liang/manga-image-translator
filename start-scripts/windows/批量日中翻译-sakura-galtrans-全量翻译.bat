@echo off
:: ═══════════════════════════════════════════════════════════════════════════════
:: 日中漫画批量翻译 — Sakura Galtransl 全量翻译 (方式C, R18友好) — Windows
:: ═══════════════════════════════════════════════════════════════════════════════

cd /d "%~dp0\..\.."

set GALTRANS_GGUF_PATH=%USERPROFILE%\.ollama\models\gguf\Sakura-Galtransl-14B-v3.8-Q4_K_M.gguf
set TRANSLATOR_MODE=galtransl
set RETRANS=true
set BENCHMARK=false

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
echo   [Sakura Galtransl - 全量翻译]
echo ============================================
echo.

python -m manga_translator.batch

echo.
pause
