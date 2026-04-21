from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from app.utils import utils

router = APIRouter(prefix="/uploads", tags=["uploads"])


def _safe_name(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename or "file")
    return cleaned or "file"


def _upload_root(kind: str) -> Path:
    root = Path(utils.workspace_dir()) / "frontend_uploads" / kind
    root.mkdir(parents=True, exist_ok=True)
    return root


async def _save_upload(kind: str, file: UploadFile) -> dict:
    filename = _safe_name(file.filename or f"{kind}.bin")
    unique_filename = f"{uuid4().hex}_{filename}"
    target = _upload_root(kind) / unique_filename
    content = await file.read()
    target.write_bytes(content)
    return {
        "path": str(target),
        "filename": filename,
        "size": len(content),
        "kind": kind,
        "url": f"/uploads/{kind}/{unique_filename}",
    }


@router.post("/video")
async def upload_video(file: UploadFile = File(...)):
    if not str(file.content_type or "").startswith("video/"):
        raise HTTPException(status_code=400, detail="invalid_video_file")
    return await _save_upload("video", file)


@router.post("/subtitle")
async def upload_subtitle(file: UploadFile = File(...)):
    filename = str(file.filename or "").lower()
    if not filename.endswith((".srt", ".vtt", ".txt")):
        raise HTTPException(status_code=400, detail="invalid_subtitle_file")
    return await _save_upload("subtitle", file)


def _parse_srt_timestamp(value: str) -> str:
    return value.replace(",", ".").strip()


@router.get("/subtitle-content")
def subtitle_content(path: str = Query(...)):
    subtitle_path = Path(path)
    if not subtitle_path.exists() or not subtitle_path.is_file():
        raise HTTPException(status_code=404, detail="subtitle_not_found")

    text = subtitle_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []

    blocks = re.split(r"\n\s*\n+", text)
    lines = []
    for index, block in enumerate(blocks, start=1):
        raw_lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(raw_lines) < 2:
            continue
        time_line = raw_lines[1] if "-->" in raw_lines[1] else raw_lines[0]
        text_lines = raw_lines[2:] if "-->" in raw_lines[1] else raw_lines[1:]
        match = re.search(r"(\d+:\d+:\d+[,.]\d+)\s*-->\s*(\d+:\d+:\d+[,.]\d+)", time_line)
        start = _parse_srt_timestamp(match.group(1)) if match else f"{(index - 1) * 5}.0s"
        end = _parse_srt_timestamp(match.group(2)) if match else f"{index * 5}.0s"
        lines.append({
            "id": index,
            "start": start,
            "end": end,
            "text": " ".join(text_lines).strip() or f"字幕 {index}",
        })
    return lines
