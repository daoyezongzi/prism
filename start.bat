@echo off
chcp 65001 >nul
title Prism 决策工作台 · 一键启动
cd /d "%~dp0"

echo ======================================================================
echo.
echo     ██████╗ ██████╗  ██╗███████╗███╗   ███╗
echo     ██╔══██╗██╔══██╗██║██╔════╝████╗ ████║
echo     ██████╔╝██████╔╝██║███████╗██╔████╔██║
echo     ██╔═══╝ ██╔══██╗██║╚════██║██║╚██╔╝██║
echo     ██║     ██║  ██║██║███████║██║ ╚═╝ ██║
echo     ╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚═╝
echo.
echo     Prism · 可解释个性化投资研究与决策支持工作台
echo ======================================================================
echo.

:: 1. 检查并激活虚拟环境 (若存在 .venv 或 venv)
if exist "%~dp0.venv\Scripts\activate.bat" (
    echo [环境] 正在激活虚拟环境: .venv
    call "%~dp0.venv\Scripts\activate.bat"
) else if exist "%~dp0venv\Scripts\activate.bat" (
    echo [环境] 正在激活虚拟环境: venv
    call "%~dp0venv\Scripts\activate.bat"
)

:: 2. 检查 Python 是否可用
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [错误] 未检测到 Python，请先安装 Python 3.11+ 并将其添加到 PATH 环境变量。
    echo.
    pause
    exit /b 1
)

:: 3. 检查核心依赖 (FastAPI & Uvicorn)
python -c "import fastapi, uvicorn" >nul 2>nul
if %errorlevel% neq 0 (
    echo [提示] 检测到缺失核心运行依赖，正在自动执行安装: pip install -e .
    python -m pip install -e .
    if %errorlevel% neq 0 (
        echo.
        echo [错误] 依赖安装失败，请检查网络连接或手动运行: pip install -e .
        echo.
        pause
        exit /b 1
    )
)

echo [就绪] 正在启动 Prism 决策工作台服务...
echo [地址] http://127.0.0.1:8000
echo [提示] 浏览器将自动打开，按 Ctrl+C 可终止服务。
echo ======================================================================
echo.

:: 4. 延迟 2 秒后自动打开系统默认浏览器
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8000"

:: 5. 启动 FastAPI / Uvicorn 服务 (支持热重载)
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload

pause
