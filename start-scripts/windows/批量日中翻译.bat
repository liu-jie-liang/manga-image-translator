@echo off
:: ═══════════════════════════════════════════════════════════════════════════════
:: 日中漫画批量翻译 — Windows 启动脚本 (交互式选择)
:: ═══════════════════════════════════════════════════════════════════════════════

cd /d "%~dp0\..\.."

:: ─── 翻译器配置 ───────────────────────────────────────────────────────────────
set SAKURA_GGUF_PATH=%USERPROFILE%\.ollama\models\gguf\sakura-14b-qwen2.5-v1.0-q4_k_m.gguf
set GALTRANS_GGUF_PATH=%USERPROFILE%\.ollama\models\gguf\Sakura-Galtransl-14B-v3.8-Q4_K_M.gguf
if not defined SAKURA_API_BASE set SAKURA_API_BASE=http://localhost:11434/v1
set SAKURA_MODEL=sakura-14b-qwen2.5-v1.0
:: ─── 翻译器配置结束 ───────────────────────────────────────────────────────────

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
echo ============================================
echo.
echo 请选择翻译模式:
echo   a) 降级方式 (B-A fallback, 优先Sakura GGUF)
echo   b) 方式C (Galtransl GGUF, R18友好)
echo.
choice /c ab /n /m "请输入 a 或 b (默认: a): "
if errorlevel 2 set TRANSLATOR_MODE=galtransl
if errorlevel 1 set TRANSLATOR_MODE=degraded
echo.

python -m manga_translator.batch

echo.
pause
