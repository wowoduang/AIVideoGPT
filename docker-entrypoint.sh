#!/usr/bin/env bash
set -e

cd /NarratoAI || exit 1

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

install_runtime_dependencies() {
  log "检查并安装运行时依赖..."

  local requirements_file="requirements.txt"
  local installed_packages_file="storage/temp/.requirements_installed"

  mkdir -p storage/temp

  if [ -f "$requirements_file" ]; then
    if [ ! -f "$installed_packages_file" ] || [ "$requirements_file" -nt "$installed_packages_file" ]; then
      log "发现新的依赖需求，开始安装..."

      INSTALL_RESULT=0

      if command -v sudo >/dev/null 2>&1; then
        log "尝试使用sudo安装依赖..."
        sudo pip install --no-cache-dir -r "$requirements_file" 2>&1 | while read -r line; do
          log "pip: $line"
        done
        INSTALL_RESULT=${PIPESTATUS[0]}
      else
        INSTALL_RESULT=1
      fi

      if [ $INSTALL_RESULT -ne 0 ]; then
        log "尝试用户级安装依赖..."
        pip install --user --no-cache-dir -r "$requirements_file" 2>&1 | while read -r line; do
          log "pip: $line"
        done
        export PATH="$HOME/.local/bin:$PATH"
      fi

      log "确保腾讯云SDK已安装..."
      if ! pip list | grep -q "tencentcloud-sdk-python"; then
        log "安装腾讯云SDK..."
        pip install --user "tencentcloud-sdk-python>=3.0.1200"
      else
        log "腾讯云SDK已安装"
      fi

      touch "$installed_packages_file"
      log "依赖安装完成"
    else
      log "依赖已是最新版本，跳过安装"
    fi
  else
    log "未找到 requirements.txt 文件"
  fi
}

check_requirements() {
  log "检查应用环境..."

  if [ ! -f "config.toml" ]; then
    if [ -f "config.example.toml" ]; then
      log "复制示例配置文件..."
      cp config.example.toml config.toml
    else
      log "警告: 未找到配置文件"
    fi
  fi

  for dir in "storage/temp" "storage/tasks" "storage/json" "storage/narration_scripts" "storage/drama_analysis"; do
    if [ ! -d "$dir" ]; then
      log "创建目录: $dir"
      mkdir -p "$dir"
    fi
  done

  install_runtime_dependencies
  log "环境检查完成"
}

start_webui() {
  log "启动 NarratoAI WebUI..."

  if command -v netstat >/dev/null 2>&1; then
    if netstat -tuln | grep -q ":8866 "; then
      log "警告: 端口 8866 已被占用"
    fi
  fi

  exec streamlit run webui.py \
    --server.address=0.0.0.0 \
    --server.port=8866 \
    --server.enableCORS=true \
    --server.maxUploadSize=2048 \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false \
    --browser.serverAddress=0.0.0.0 \
    --logger.level=info
}

log "NarratoAI Docker 容器启动中..."

check_requirements

case "$1" in
  "webui"|"")
    start_webui
    ;;
  "bash"|"sh")
    log "启动交互式 shell..."
    exec /bin/bash
    ;;
  "health")
    log "执行健康检查..."
    if curl -f http://localhost:8866/_stcore/health >/dev/null 2>&1; then
      log "健康检查通过"
      exit 0
    else
      log "健康检查失败"
      exit 1
    fi
    ;;
  *)
    log "执行自定义命令: $*"
    exec "$@"
    ;;
esac
