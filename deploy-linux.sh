#!/usr/bin/env bash
# ============================================================
#  NarratoAI - Linux 一键部署脚本
#  支持: Ubuntu/Debian, CentOS/RHEL/Fedora, macOS
#  用法: chmod +x deploy-linux.sh && ./deploy-linux.sh
# ============================================================

set -e

# -------------------- 颜色输出 --------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${BLUE}[信息]${NC} $*"; }
ok()    { echo -e "${GREEN}[成功]${NC} $*"; }
warn()  { echo -e "${YELLOW}[警告]${NC} $*"; }
err()   { echo -e "${RED}[错误]${NC} $*"; }
step()  { echo -e "\n${CYAN}===== $* =====${NC}"; }

# -------------------- 全局变量 --------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"
PYTHON_CMD=""
PIP_MIRROR="${PIP_MIRROR:-https://pypi.org/simple/}"
APP_PORT="${APP_PORT:-8501}"
APP_HOST="${APP_HOST:-0.0.0.0}"
INSTALL_MODE="${1:-full}"   # full | run | stop | status

# -------------------- 帮助信息 --------------------
show_help() {
    echo ""
    echo "NarratoAI - Linux 一键部署脚本"
    echo ""
    echo "用法: ./deploy-linux.sh [模式] [选项]"
    echo ""
    echo "模式:"
    echo "  full    完整安装（默认）: 系统依赖 + Python依赖 + 配置 + 启动"
    echo "  run     仅启动: 跳过安装步骤，直接启动应用"
    echo "  stop    停止应用: 停止后台运行的 NarratoAI 服务"
    echo "  status  查看状态: 查看应用运行状态"
    echo ""
    echo "环境变量:"
    echo "  APP_PORT=8501      应用端口（默认8501）"
    echo "  APP_HOST=0.0.0.0   监听地址（默认0.0.0.0）"
    echo "  PIP_MIRROR=URL     pip镜像源（默认官方源）"
    echo ""
    echo "示例:"
    echo "  ./deploy-linux.sh                        # 完整安装并启动"
    echo "  ./deploy-linux.sh run                    # 跳过安装，直接启动"
    echo "  ./deploy-linux.sh stop                   # 停止应用"
    echo "  ./deploy-linux.sh status                 # 查看运行状态"
    echo "  APP_PORT=8080 ./deploy-linux.sh          # 使用8080端口"
    echo "  PIP_MIRROR=https://mirrors.aliyun.com/pypi/simple/ ./deploy-linux.sh  # 使用阿里云镜像"
    echo ""
    exit 0
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_help
fi

# -------------------- 检测操作系统 --------------------
detect_os() {
    step "检测操作系统"
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="${ID}"
        OS_NAME="${PRETTY_NAME}"
    elif [ "$(uname)" = "Darwin" ]; then
        OS_ID="macos"
        OS_NAME="macOS $(sw_vers -productVersion 2>/dev/null || echo '')"
    else
        OS_ID="unknown"
        OS_NAME="$(uname -s)"
    fi
    info "操作系统: ${OS_NAME}"
}

# -------------------- 检测/安装 Python --------------------
find_python() {
    step "检测 Python"
    for cmd in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            local ver
            ver="$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")"
            local major minor
            major="$(echo "$ver" | cut -d. -f1)"
            minor="$(echo "$ver" | cut -d. -f2)"
            if [ "$major" = "3" ] && [ "$minor" -ge 10 ] && [ "$minor" -le 13 ]; then
                PYTHON_CMD="$cmd"
                ok "找到 Python: $($cmd --version) (路径: $(command -v $cmd))"
                return 0
            fi
        fi
    done

    warn "未找到 Python 3.10+，尝试自动安装..."
    install_python
}

install_python() {
    case "$OS_ID" in
        ubuntu|debian|pop|linuxmint)
            sudo apt-get update -qq
            sudo apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip 2>/dev/null || \
            sudo apt-get install -y python3 python3-venv python3-dev python3-pip
            if command -v python3.12 >/dev/null 2>&1; then
                PYTHON_CMD="python3.12"
            else
                PYTHON_CMD="python3"
            fi
            ;;
        centos|rhel|fedora|rocky|almalinux)
            if command -v dnf >/dev/null 2>&1; then
                sudo dnf install -y python3.12 python3.12-devel python3-pip 2>/dev/null || \
                sudo dnf install -y python3 python3-devel python3-pip
            else
                sudo yum install -y python3 python3-devel python3-pip
            fi
            if command -v python3.12 >/dev/null 2>&1; then
                PYTHON_CMD="python3.12"
            else
                PYTHON_CMD="python3"
            fi
            ;;
        macos)
            if command -v brew >/dev/null 2>&1; then
                brew install python@3.12
                PYTHON_CMD="python3.12"
            else
                err "请先安装 Homebrew (https://brew.sh) 或手动安装 Python 3.12"
                exit 1
            fi
            ;;
        *)
            err "无法自动安装 Python，请手动安装 Python 3.10+"
            err "下载地址: https://www.python.org/downloads/"
            exit 1
            ;;
    esac

    if ! command -v "$PYTHON_CMD" >/dev/null 2>&1; then
        err "Python 安装失败，请手动安装"
        exit 1
    fi
    ok "Python 安装完成: $($PYTHON_CMD --version)"
}

# -------------------- 安装系统依赖 --------------------
install_system_deps() {
    step "安装系统依赖"

    case "$OS_ID" in
        ubuntu|debian|pop|linuxmint)
            info "安装系统包 (apt)..."
            sudo apt-get update -qq
            sudo apt-get install -y \
                ffmpeg \
                imagemagick \
                git \
                git-lfs \
                curl \
                build-essential \
                libsndfile1 \
                2>/dev/null || warn "部分系统包安装失败，可能不影响使用"
            ;;
        centos|rhel|fedora|rocky|almalinux)
            info "安装系统包 (yum/dnf)..."
            if command -v dnf >/dev/null 2>&1; then
                sudo dnf install -y ffmpeg ImageMagick git git-lfs curl gcc gcc-c++ make libsndfile \
                    2>/dev/null || warn "部分系统包安装失败"
            else
                sudo yum install -y epel-release
                sudo yum install -y ffmpeg ImageMagick git git-lfs curl gcc gcc-c++ make libsndfile \
                    2>/dev/null || warn "部分系统包安装失败"
            fi
            ;;
        macos)
            info "安装系统包 (brew)..."
            if command -v brew >/dev/null 2>&1; then
                brew install ffmpeg imagemagick git git-lfs curl libsndfile 2>/dev/null || warn "部分 brew 包安装失败"
            else
                warn "未检测到 Homebrew，跳过系统包安装"
            fi
            ;;
        *)
            warn "未知操作系统，跳过系统依赖安装"
            warn "请确保已安装: FFmpeg, ImageMagick, git, git-lfs, curl"
            ;;
    esac

    # 初始化 git-lfs
    if command -v git-lfs >/dev/null 2>&1; then
        git lfs install 2>/dev/null || true
        ok "Git LFS 已初始化"
    fi

    # 验证 FFmpeg
    if command -v ffmpeg >/dev/null 2>&1; then
        ok "FFmpeg 已就绪: $(ffmpeg -version 2>&1 | head -1)"
    else
        warn "FFmpeg 未安装，视频处理功能将不可用"
        warn "安装方法: https://ffmpeg.org/download.html"
    fi

    # 修复 ImageMagick 策略（允许读写）
    if [ -f /etc/ImageMagick-6/policy.xml ]; then
        sudo sed -i 's/<policy domain="path" rights="none" pattern="@\*"/<policy domain="path" rights="read|write" pattern="@\*"/' /etc/ImageMagick-6/policy.xml 2>/dev/null || true
        ok "ImageMagick 策略已更新"
    fi
}

# -------------------- 创建虚拟环境 --------------------
setup_venv() {
    step "配置 Python 虚拟环境"

    if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/python" ]; then
        info "虚拟环境已存在: ${VENV_DIR}"
    else
        info "创建虚拟环境: ${VENV_DIR}"
        "$PYTHON_CMD" -m venv "$VENV_DIR" || {
            warn "venv 创建失败，尝试安装 python3-venv 后重试..."
            case "$OS_ID" in
                ubuntu|debian|pop|linuxmint)
                    local pyver
                    pyver="$("$PYTHON_CMD" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
                    sudo apt-get install -y "python${pyver}-venv" 2>/dev/null || true
                    ;;
            esac
            "$PYTHON_CMD" -m venv "$VENV_DIR"
        }
        ok "虚拟环境创建完成"
    fi

    source "$VENV_DIR/bin/activate"
    ok "虚拟环境已激活: $(python --version)"

    info "升级 pip..."
    pip install --upgrade pip setuptools wheel -q -i "$PIP_MIRROR" 2>/dev/null || pip install --upgrade pip setuptools wheel -q
}

# -------------------- 安装 Python 依赖 --------------------
install_python_deps() {
    step "安装 Python 依赖"

    source "$VENV_DIR/bin/activate"

    if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
        warn "requirements.txt 不存在，跳过依赖安装"
        return 0
    fi

    info "安装依赖 (requirements.txt)..."
    pip install -q -i "$PIP_MIRROR" -r "$SCRIPT_DIR/requirements.txt" \
        2>/dev/null || {
            warn "部分包通过镜像安装失败，尝试默认源..."
            pip install -q -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null || \
                warn "部分依赖安装失败，可能不影响核心功能"
        }

    ok "Python 依赖安装完成"
}

# -------------------- 创建目录结构 --------------------
setup_directories() {
    step "创建目录结构"

    local dirs=(
        "storage/temp"
        "storage/tasks"
        "storage/json"
        "storage/narration_scripts"
        "storage/drama_analysis"
    )

    for d in "${dirs[@]}"; do
        mkdir -p "$SCRIPT_DIR/$d"
    done

    ok "目录结构创建完成"
}

# -------------------- 初始化配置 --------------------
init_config() {
    step "检查配置文件"

    local config_file="$SCRIPT_DIR/config.toml"
    if [ -f "$config_file" ]; then
        ok "配置文件已存在: config.toml"
    else
        if [ -f "$SCRIPT_DIR/config.example.toml" ]; then
            cp "$SCRIPT_DIR/config.example.toml" "$config_file"
            ok "已从模板创建配置文件: config.toml"
            warn "请编辑 config.toml 配置你的 API 密钥"
        else
            err "未找到配置文件模板 config.example.toml"
            exit 1
        fi
    fi
}

# -------------------- 生成 systemd 服务文件 --------------------
generate_systemd() {
    step "生成 systemd 服务文件（可选）"

    local service_file="$SCRIPT_DIR/narratoai.service"
    local current_user
    current_user="$(whoami)"

    cat > "$service_file" << EOF
[Unit]
Description=NarratoAI - AI Video Narration Tool
After=network.target

[Service]
Type=simple
User=${current_user}
WorkingDirectory=${SCRIPT_DIR}
Environment=PATH=${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=${SCRIPT_DIR}
ExecStart=${VENV_DIR}/bin/streamlit run webui.py \\
    --server.address=${APP_HOST} \\
    --server.port=${APP_PORT} \\
    --server.enableCORS=true \\
    --server.maxUploadSize=2048 \\
    --server.enableXsrfProtection=false \\
    --browser.gatherUsageStats=false \\
    --logger.level=info
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    ok "systemd 服务文件已生成: narratoai.service"
    info "安装为系统服务（后台自启动）:"
    info "  sudo cp narratoai.service /etc/systemd/system/"
    info "  sudo systemctl daemon-reload"
    info "  sudo systemctl enable --now narratoai"
}

# -------------------- 停止应用 --------------------
stop_app() {
    step "停止 NarratoAI"

    # 检查 systemd 服务
    if systemctl is-active --quiet narratoai 2>/dev/null; then
        sudo systemctl stop narratoai
        ok "systemd 服务已停止"
        return
    fi

    # 检查 PID 文件
    local pid_file="$SCRIPT_DIR/.narratoai.pid"
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            rm -f "$pid_file"
            ok "应用已停止 (PID: $pid)"
            return
        else
            rm -f "$pid_file"
        fi
    fi

    # 尝试通过进程名查找
    local pids
    pids=$(pgrep -f "streamlit run webui.py" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill 2>/dev/null || true
        ok "应用已停止"
    else
        info "未检测到运行中的 NarratoAI 进程"
    fi
}

# -------------------- 查看状态 --------------------
show_status() {
    step "NarratoAI 状态"

    # 检查 systemd 服务
    if systemctl is-active --quiet narratoai 2>/dev/null; then
        ok "systemd 服务运行中"
        systemctl status narratoai --no-pager 2>/dev/null || true
        return
    fi

    # 检查 PID 文件
    local pid_file="$SCRIPT_DIR/.narratoai.pid"
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            ok "应用运行中 (PID: $pid)"
            info "访问地址: http://127.0.0.1:${APP_PORT}"
            return
        else
            rm -f "$pid_file"
        fi
    fi

    # 尝试通过进程名查找
    local pids
    pids=$(pgrep -f "streamlit run webui.py" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        ok "应用运行中 (PID: $pids)"
        info "访问地址: http://127.0.0.1:${APP_PORT}"
    else
        warn "NarratoAI 未运行"
    fi
}

# -------------------- 启动应用 --------------------
start_app() {
    step "启动 NarratoAI"

    source "$VENV_DIR/bin/activate"
    cd "$SCRIPT_DIR"

    export PYTHONPATH="$SCRIPT_DIR"

    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}   NarratoAI 启动中...${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    info "监听地址: ${APP_HOST}:${APP_PORT}"
    info "本地访问: http://127.0.0.1:${APP_PORT}"
    if [ "$APP_HOST" = "0.0.0.0" ]; then
        local ip
        ip="$(hostname -I 2>/dev/null | awk '{print $1}')" || ip=""
        if [ -n "$ip" ]; then
            info "局域网访问: http://${ip}:${APP_PORT}"
        fi
    fi
    echo ""
    info "按 Ctrl+C 停止服务"
    echo ""

    streamlit run webui.py \
        --server.address="$APP_HOST" \
        --server.port="$APP_PORT" \
        --server.enableCORS=true \
        --server.maxUploadSize=2048 \
        --server.enableXsrfProtection=false \
        --browser.gatherUsageStats=false \
        --logger.level=info
}

# ==================== 主流程 ====================
main() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     NarratoAI - Linux 一键部署脚本         ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════╝${NC}"
    echo ""

    case "$INSTALL_MODE" in
        run)
            if [ ! -d "$VENV_DIR" ]; then
                err "虚拟环境不存在，请先运行 ./deploy-linux.sh 完成安装"
                exit 1
            fi
            start_app
            return
            ;;
        stop)
            stop_app
            return
            ;;
        status)
            show_status
            return
            ;;
    esac

    detect_os
    find_python
    install_system_deps
    setup_venv
    install_python_deps
    setup_directories
    init_config
    generate_systemd

    step "部署完成"
    echo ""
    ok "所有步骤完成！"
    echo ""
    echo -e "${CYAN}快速启动:${NC}"
    echo "  ./deploy-linux.sh run"
    echo ""
    echo -e "${CYAN}使用 systemd 管理（后台运行 + 开机自启）:${NC}"
    echo "  sudo cp narratoai.service /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable --now narratoai"
    echo "  sudo systemctl status narratoai"
    echo ""
    echo -e "${CYAN}其他命令:${NC}"
    echo "  ./deploy-linux.sh stop       # 停止应用"
    echo "  ./deploy-linux.sh status     # 查看状态"
    echo "  ./deploy-linux.sh run        # 前台启动"
    echo ""
    echo -e "${YELLOW}首次使用请编辑 config.toml 配置 AI API 密钥${NC}"
    echo ""

    # 询问是否立即启动
    read -r -p "是否立即启动应用？[Y/n] " answer
    case "$answer" in
        [nN]|[nN][oO])
            info "跳过启动。稍后可运行: ./deploy-linux.sh run"
            ;;
        *)
            start_app
            ;;
    esac
}

main "$@"
