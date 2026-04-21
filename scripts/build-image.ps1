param(
  [string]$ImageName = "aivideogpt:latest"
)

function Build-WithImage {
  param([string]$BaseImage)
  Write-Host "[INFO] Trying base image: $BaseImage"
  docker build --build-arg PYTHON_IMAGE=$BaseImage -t $ImageName .
  return $LASTEXITCODE -eq 0
}

if (Build-WithImage "python:3.12-slim") {
  Write-Host "[OK] Build succeeded with python:3.12-slim"
  exit 0
}

if (Build-WithImage "python:3.11-slim") {
  Write-Host "[OK] Build succeeded with python:3.11-slim"
  exit 0
}

Write-Host "[ERROR] Build failed with all fallback Python images"
exit 1
