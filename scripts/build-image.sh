#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-aivideogpt:latest}"

build_with_image() {
  local base_image="$1"
  echo "[INFO] Trying base image: ${base_image}"
  docker build \
    --build-arg PYTHON_IMAGE="${base_image}" \
    -t "${IMAGE_NAME}" \
    .
}

if build_with_image "python:3.12-slim"; then
  echo "[OK] Build succeeded with python:3.12-slim"
  exit 0
fi

if build_with_image "python:3.11-slim"; then
  echo "[OK] Build succeeded with python:3.11-slim"
  exit 0
fi

echo "[ERROR] Build failed with all fallback Python images"
exit 1
