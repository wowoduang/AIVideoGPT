@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ============================================================
::  NarratoAI - Windows Docker 一键部署脚本
::  用法: 双击运行 或 在命令行执行 deploy-windows-docker.bat
:: ============================================================

title NarratoAI Docker 部署

:: -------------------- 颜色设置 --------------------
:: Windows 10+ 支持 ANSI 颜色
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "CYAN=[96m"
set "NC=[0m"

:: -------------------- 全局变量 --------------------
set "APP_PORT=8501"
set "SCRIPT_DIR=%~dp0"
:: 去掉末尾的反斜杠
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "INSTALL_MODE=%~1"
if "%INSTALL_MODE%"=="" set "INSTALL_MODE=full"

:: -------------------- 入口 --------------------
echo.
echo %CYAN%========================================%NC%
echo %CYAN%  NarratoAI - Windows Docker 一键部署   %NC%
echo %CYAN%========================================%NC%
echo.

if "%INSTALL_MODE%"=="-h" goto :show_help
if "%INSTALL_MODE%"=="--help" goto :show_help
if "%INSTALL_MODE%"=="/?" goto :show_help

if "%INSTALL_MODE%"=="stop" goto :stop_app
if "%INSTALL_MODE%"=="status" goto :show_status
if "%INSTALL_MODE%"=="logs" goto :show_logs
if "%INSTALL_MODE%"=="restart" goto :restart_app
if "%INSTALL_MODE%"=="rebuild" goto :rebuild_app

goto :main

:: -------------------- 帮助信息 --------------------
:show_help
echo.
echo NarratoAI - Windows Docker 一键部署脚本
echo.
echo 用法: deploy-windows-docker.bat [模式]
echo.
echo 模式:
echo   full      完整部署（默认）: 检查环境 + 构建镜像 + 启动服务
echo   stop      停止服务: 停止运行中的容器
echo   status    查看状态: 查看容器运行状态
echo   logs      查看日志: 查看应用日志
echo   restart   重启服务: 重启容器
echo   rebuild   重新构建: 强制重新构建镜像并启动
echo.
echo 示例:
echo   deploy-windows-docker.bat              # 完整部署
echo   deploy-windows-docker.bat stop         # 停止服务
echo   deploy-windows-docker.bat status       # 查看状态
echo   deploy-windows-docker.bat logs         # 查看日志
echo   deploy-windows-docker.bat restart      # 重启服务
echo   deploy-windows-docker.bat rebuild      # 重新构建
echo.
echo 前置要求:
echo   1. 安装 Docker Desktop: https://www.docker.com/products/docker-desktop
echo   2. 启用 WSL2 后端（推荐）
echo   3. 确保 Docker Desktop 已启动
echo.
goto :eof

:: -------------------- 检查 Docker --------------------
:check_docker
echo %GREEN%[信息]%NC% 检查 Docker 环境...

:: 检查 docker 命令
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[错误]%NC% 未检测到 Docker！
    echo.
    echo 请安装 Docker Desktop:
    echo   下载地址: https://www.docker.com/products/docker-desktop
    echo.
    echo 安装步骤:
    echo   1. 下载并安装 Docker Desktop
    echo   2. 启用 WSL2 后端（推荐，Settings -^> General -^> Use WSL 2）
    echo   3. 重启电脑
    echo   4. 启动 Docker Desktop 并等待其完全启动
    echo.
    pause
    exit /b 1
)

:: 检查 docker 是否运行中
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo %YELLOW%[警告]%NC% Docker Desktop 未运行，正在尝试启动...
    
    :: 尝试启动 Docker Desktop
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul
    if %errorlevel% neq 0 (
        start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" 2>nul
    )
    
    echo %GREEN%[信息]%NC% 等待 Docker Desktop 启动（最多等待 120 秒）...
    set "docker_wait=0"
    :docker_wait_loop
    if !docker_wait! geq 120 (
        echo %RED%[错误]%NC% Docker Desktop 启动超时！
        echo 请手动启动 Docker Desktop 后重新运行此脚本。
        pause
        exit /b 1
    )
    docker info >nul 2>&1
    if %errorlevel% neq 0 (
        timeout /t 5 /nobreak >nul
        set /a docker_wait+=5
        echo %GREEN%[信息]%NC% 已等待 !docker_wait! 秒...
        goto :docker_wait_loop
    )
)

echo %GREEN%[成功]%NC% Docker 环境就绪

:: 检查 docker compose
docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    docker-compose version >nul 2>&1
    if %errorlevel% neq 0 (
        echo %RED%[错误]%NC% Docker Compose 不可用！
        echo 请确保安装了最新版 Docker Desktop（已内置 Docker Compose）
        pause
        exit /b 1
    )
)
echo %GREEN%[成功]%NC% Docker Compose 就绪
goto :eof

:: -------------------- 检查配置文件 --------------------
:check_config
echo %GREEN%[信息]%NC% 检查配置文件...

if not exist "%SCRIPT_DIR%\config.toml" (
    if exist "%SCRIPT_DIR%\config.example.toml" (
        echo %YELLOW%[警告]%NC% config.toml 不存在，从模板创建...
        copy "%SCRIPT_DIR%\config.example.toml" "%SCRIPT_DIR%\config.toml" >nul
        echo %GREEN%[成功]%NC% 已创建 config.toml
        echo %YELLOW%[提示]%NC% 请稍后编辑 config.toml 配置你的 API 密钥
    ) else (
        echo %RED%[错误]%NC% 未找到配置文件模板 config.example.toml
        pause
        exit /b 1
    )
) else (
    echo %GREEN%[成功]%NC% config.toml 已存在
)
goto :eof

:: -------------------- 创建目录 --------------------
:setup_directories
echo %GREEN%[信息]%NC% 创建存储目录...

if not exist "%SCRIPT_DIR%\storage\temp" mkdir "%SCRIPT_DIR%\storage\temp"
if not exist "%SCRIPT_DIR%\storage\tasks" mkdir "%SCRIPT_DIR%\storage\tasks"
if not exist "%SCRIPT_DIR%\storage\json" mkdir "%SCRIPT_DIR%\storage\json"
if not exist "%SCRIPT_DIR%\storage\narration_scripts" mkdir "%SCRIPT_DIR%\storage\narration_scripts"
if not exist "%SCRIPT_DIR%\storage\drama_analysis" mkdir "%SCRIPT_DIR%\storage\drama_analysis"
if not exist "%SCRIPT_DIR%\resource" mkdir "%SCRIPT_DIR%\resource"

echo %GREEN%[成功]%NC% 目录结构就绪
goto :eof

:: -------------------- 构建镜像 --------------------
:build_image
echo %GREEN%[信息]%NC% 构建 Docker 镜像（首次构建可能需要几分钟）...

cd /d "%SCRIPT_DIR%"
docker compose build
if %errorlevel% neq 0 (
    echo %RED%[错误]%NC% 镜像构建失败！
    echo 请检查网络连接或 Dockerfile 配置。
    pause
    exit /b 1
)
echo %GREEN%[成功]%NC% 镜像构建完成
goto :eof

:: -------------------- 启动服务 --------------------
:start_services
echo %GREEN%[信息]%NC% 启动 NarratoAI 服务...

cd /d "%SCRIPT_DIR%"
docker compose down >nul 2>&1
docker compose up -d
if %errorlevel% neq 0 (
    echo %RED%[错误]%NC% 服务启动失败！
    docker compose logs --tail=20
    pause
    exit /b 1
)
echo %GREEN%[成功]%NC% 容器已启动
goto :eof

:: -------------------- 等待服务就绪 --------------------
:wait_for_service
echo %GREEN%[信息]%NC% 等待服务就绪（最多等待 120 秒）...

set "wait_count=0"
:wait_loop
if !wait_count! geq 120 (
    echo %YELLOW%[警告]%NC% 服务启动超时，可能仍在初始化中。
    echo 请稍后访问 http://localhost:%APP_PORT% 或运行: deploy-windows-docker.bat status
    goto :eof
)

curl -sf http://localhost:%APP_PORT%/_stcore/health >nul 2>&1
if %errorlevel% equ 0 (
    echo %GREEN%[成功]%NC% 服务已就绪！
    goto :eof
)

:: 如果没有 curl，尝试 PowerShell
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:%APP_PORT%/_stcore/health' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if %errorlevel% equ 0 (
    echo %GREEN%[成功]%NC% 服务已就绪！
    goto :eof
)

timeout /t 5 /nobreak >nul
set /a wait_count+=5
echo %GREEN%[信息]%NC% 已等待 !wait_count! 秒...
goto :wait_loop

:: -------------------- 显示部署信息 --------------------
:show_deploy_info
echo.
echo %GREEN%============================================%NC%
echo %GREEN%    NarratoAI 部署完成！%NC%
echo %GREEN%============================================%NC%
echo.
echo   访问地址: http://localhost:%APP_PORT%
echo.
echo   常用命令:
echo     查看状态: deploy-windows-docker.bat status
echo     查看日志: deploy-windows-docker.bat logs
echo     重启服务: deploy-windows-docker.bat restart
echo     停止服务: deploy-windows-docker.bat stop
echo     重新构建: deploy-windows-docker.bat rebuild
echo.
echo   Docker 命令:
echo     查看日志: docker compose logs -f
echo     停止服务: docker compose down
echo     重启服务: docker compose restart
echo.
echo %YELLOW%  首次使用请在 Web 界面配置 AI API 密钥%NC%
echo.

:: 尝试自动打开浏览器
start "" "http://localhost:%APP_PORT%" 2>nul

goto :eof

:: -------------------- 停止应用 --------------------
:stop_app
echo %GREEN%[信息]%NC% 停止 NarratoAI 服务...
cd /d "%SCRIPT_DIR%"
docker compose down
if %errorlevel% equ 0 (
    echo %GREEN%[成功]%NC% 服务已停止
) else (
    echo %RED%[错误]%NC% 停止失败
)
goto :eof

:: -------------------- 查看状态 --------------------
:show_status
echo %GREEN%[信息]%NC% NarratoAI 服务状态:
echo.
cd /d "%SCRIPT_DIR%"
docker compose ps
echo.

:: 检查健康状态
docker inspect --format="{{.State.Health.Status}}" narratoai-webui 2>nul
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('docker inspect --format="{{.State.Health.Status}}" narratoai-webui 2^>nul') do (
        echo 健康状态: %%i
    )
)
echo.
echo 访问地址: http://localhost:%APP_PORT%
goto :eof

:: -------------------- 查看日志 --------------------
:show_logs
echo %GREEN%[信息]%NC% 显示 NarratoAI 日志（按 Ctrl+C 退出）:
echo.
cd /d "%SCRIPT_DIR%"
docker compose logs -f --tail=100
goto :eof

:: -------------------- 重启应用 --------------------
:restart_app
echo %GREEN%[信息]%NC% 重启 NarratoAI 服务...
cd /d "%SCRIPT_DIR%"
docker compose restart
if %errorlevel% equ 0 (
    echo %GREEN%[成功]%NC% 服务已重启
    echo 访问地址: http://localhost:%APP_PORT%
) else (
    echo %RED%[错误]%NC% 重启失败
)
goto :eof

:: -------------------- 重新构建 --------------------
:rebuild_app
echo %GREEN%[信息]%NC% 重新构建并部署 NarratoAI...
cd /d "%SCRIPT_DIR%"
call :check_docker
if %errorlevel% neq 0 goto :eof
call :check_config
call :setup_directories

echo %GREEN%[信息]%NC% 强制重新构建镜像...
docker compose build --no-cache
if %errorlevel% neq 0 (
    echo %RED%[错误]%NC% 镜像构建失败！
    pause
    exit /b 1
)
call :start_services
call :wait_for_service
call :show_deploy_info
goto :eof

:: ==================== 主流程 ====================
:main
echo %GREEN%[信息]%NC% 开始 NarratoAI Docker 部署...
echo.

:: 步骤 1: 检查 Docker
call :check_docker
if %errorlevel% neq 0 goto :eof

:: 步骤 2: 检查配置
call :check_config

:: 步骤 3: 创建目录
call :setup_directories

:: 步骤 4: 构建镜像
call :build_image
if %errorlevel% neq 0 goto :eof

:: 步骤 5: 启动服务
call :start_services
if %errorlevel% neq 0 goto :eof

:: 步骤 6: 等待就绪
call :wait_for_service

:: 步骤 7: 显示信息
call :show_deploy_info

echo.
pause
