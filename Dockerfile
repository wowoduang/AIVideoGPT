# 多阶段构建 - 构建阶段
FROM python:3.12-slim-bookworm AS builder

# 设置构建参数
ARG DEBIAN_FRONTEND=noninteractive

# 设置工作目录
WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    git-lfs \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 升级 pip 并创建虚拟环境
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m venv /opt/venv

# 激活虚拟环境
ENV PATH="/opt/venv/bin:$PATH"

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .

# 先装项目依赖，再显式安装 PyTorch CPU 版，确保 funasr 可导入
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir --default-timeout=120 \
    -i https://pypi.org/simple \
    -r requirements.txt && \
    python -m pip install --no-cache-dir --default-timeout=120 \
    --index-url https://download.pytorch.org/whl/cpu \
    torch torchaudio && \
    python -m pip check

# 运行阶段
FROM python:3.12-slim-bookworm

# 设置运行参数
ARG DEBIAN_FRONTEND=noninteractive

# 设置工作目录
WORKDIR /NarratoAI

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 设置环境变量
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/NarratoAI" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    APP_PORT=8866 \
    NARRATO_WORKSPACE_ROOT=/NarratoAI-workspace

# 一次性安装所有依赖、创建用户、配置系统，减少层级
RUN apt-get update && apt-get install -y --no-install-recommends \
    imagemagick \
    ffmpeg \
    wget \
    curl \
    git-lfs \
    ca-certificates \
    dos2unix \
    && sed -i 's/<policy domain="path" rights="none" pattern="@\*"/<policy domain="path" rights="read|write" pattern="@\*"/' /etc/ImageMagick-6/policy.xml || true \
    && git lfs install \
    && rm -rf /var/lib/apt/lists/*

# 复制入口脚本并修复换行符问题
COPY docker-entrypoint.sh /usr/local/bin/
RUN dos2unix /usr/local/bin/docker-entrypoint.sh && chmod +x /usr/local/bin/docker-entrypoint.sh

# 复制其余的应用代码
COPY . .

# 创建目录、复制配置、设置权限
RUN mkdir -p \
    /NarratoAI-workspace/temp \
    /NarratoAI-workspace/cache \
    /NarratoAI-workspace/runtime \
    /NarratoAI-workspace/state \
    /NarratoAI-workspace/tasks \
    /NarratoAI-workspace/models \
    /NarratoAI-workspace/videos \
    /NarratoAI-workspace/subtitles \
    /NarratoAI-workspace/scripts \
    /NarratoAI-workspace/fonts \
    /NarratoAI-workspace/songs \
    /NarratoAI-workspace/analysis \
    /NarratoAI-workspace/analysis/json \
    /NarratoAI-workspace/analysis/narration_scripts \
    /NarratoAI-workspace/analysis/drama_analysis && \
    if [ ! -f config.toml ]; then cp config.example.toml config.toml; fi && \
    chmod -R 755 /NarratoAI /NarratoAI-workspace

# 暴露端口
EXPOSE 8866

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8866/_stcore/health || exit 1

# 设置入口点
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["webui"]
