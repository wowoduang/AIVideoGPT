#!/bin/bash

# NarratoAI Docker 一键部署脚本

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

docker_compose() {
    if command -v docker-compose &> /dev/null; then
        docker-compose "$@"
    else
        docker compose "$@"
    fi
}

# 显示帮助信息
show_help() {
    cat << EOF
NarratoAI Docker 一键部署脚本

使用方法:
    $0 [选项]

选项:
    -h, --help          显示此帮助信息
    -b, --build         强制重新构建镜像
    --no-cache          构建时不使用缓存

示例:
    $0                  # 标准部署
    $0 -b               # 重新构建并部署
    $0 --no-cache       # 无缓存构建

EOF
}

# 检查系统要求
check_requirements() {
    log_info "检查系统要求..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker 服务未运行，请启动 Docker"
        exit 1
    fi
}

# 检查配置文件
check_config() {
    if [ ! -f "config.toml" ]; then
        if [ -f "config.example.toml" ]; then
            log_warning "config.toml 不存在，复制示例配置文件"
            cp config.example.toml config.toml
            log_info "请编辑 config.toml 文件配置您的 API 密钥"
        else
            log_error "未找到配置文件模板"
            exit 1
        fi
    fi
}

setup_workspace() {
    local workspace_root="${WORKSPACE_ROOT:-../AIVideoGPT-workspace}"
    log_info "准备 Docker 工作区: ${workspace_root}"

    mkdir -p \
        "${workspace_root}/temp" \
        "${workspace_root}/cache" \
        "${workspace_root}/runtime" \
        "${workspace_root}/state" \
        "${workspace_root}/tasks" \
        "${workspace_root}/models" \
        "${workspace_root}/videos" \
        "${workspace_root}/subtitles" \
        "${workspace_root}/scripts" \
        "${workspace_root}/fonts" \
        "${workspace_root}/songs" \
        "${workspace_root}/analysis" \
        "${workspace_root}/analysis/json" \
        "${workspace_root}/analysis/narration_scripts" \
        "${workspace_root}/analysis/drama_analysis"
}

# 构建镜像
build_image() {
    log_info "构建 Docker 镜像..."

    local build_args=""
    if [ "$NO_CACHE" = "true" ]; then
        build_args="--no-cache"
    fi

    docker_compose build $build_args
}

# 启动服务
start_services() {
    log_info "启动 NarratoAI 服务..."

    docker_compose down 2>/dev/null || true
    docker_compose up -d
}

# 等待服务就绪
wait_for_service() {
    log_info "等待服务就绪..."

    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8866/_stcore/health &>/dev/null; then
            log_info "服务已就绪"
            return 0
        fi

        sleep 2
        ((attempt++))
    done

    log_warning "服务启动超时，请检查日志"
    return 1
}

# 显示部署信息
show_deployment_info() {
    echo
    log_info "NarratoAI 部署完成！"
    echo "访问地址: http://localhost:8866"
    echo "工作区目录: ${WORKSPACE_ROOT:-../AIVideoGPT-workspace}"
    echo
    echo "常用命令:"
    echo "  查看日志: docker compose logs -f"
    echo "  停止服务: docker compose down"
    echo "  重启服务: docker compose restart"
}

# 主函数
main() {
    FORCE_BUILD=false
    NO_CACHE=false

    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -b|--build)
                FORCE_BUILD=true
                shift
                ;;
            --no-cache)
                NO_CACHE=true
                shift
                ;;
            *)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # 执行部署流程
    log_info "开始 NarratoAI Docker 部署..."

    check_requirements
    check_config
    setup_workspace

    if [ "$FORCE_BUILD" = "true" ] || ! docker images | grep -q "narratoai"; then
        build_image
    fi

    start_services

    if wait_for_service; then
        show_deployment_info
    else
        log_error "部署失败，请检查日志"
        docker_compose logs --tail=20
        exit 1
    fi
}

# 执行主函数
main "$@"
