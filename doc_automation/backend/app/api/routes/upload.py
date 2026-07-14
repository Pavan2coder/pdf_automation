"""
api/routes/upload.py
────────────────────
Handles multipart file uploads.

POST /api/upload
  – Accepts N source documents + 1 Plan template + 1 Incubation template
  – Validates file types and sizes
  – Saves files into uploads/<session_id>/
  – Returns session_id + metadata for every accepted file
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import (
    FileRole,
    UploadedFile,
    UploadResponse,
)

router = APIRouter(prefix="/upload", tags=["Upload"])
log    = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _validate_extension(filename: str) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{ext}' not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}",
        )


async def _save_file(upload: UploadFile, dest: Path) -> int:
    """Stream-save upload to *dest* and return bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with dest.open("wb") as fh:
        while chunk := await upload.read(1024 * 256):   # 256 KB chunks
            total += len(chunk)
            if total > settings.max_upload_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File '{upload.filename}' exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit.",
                )
            fh.write(chunk)
    return total


# ──────────────────────────────────────────────────────────────────────────────
# Endpoint
# ──────────────────────────────────────────────────────────────────────────────

@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_files(
    source_files:      list[UploadFile] = File(...,  description="Source documents (reports, PPTs, abstracts …)"),
    plan_template:     UploadFile        = File(...,  description="Plan Word template (.docx)"),
    incubation_template: UploadFile      = File(...,  description="Incubation Word template (.docx)"),
):
    """
    Upload all project source documents together with the two Word templates.

    - **source_files**: one or more files per project (PDF / DOCX / PPTX)
    - **plan_template**: the Plan Word template (must be DOCX)
    - **incubation_template**: the Incubation Word template (must be DOCX)
    """
    session_id  = uuid.uuid4()
    session_dir = settings.UPLOAD_DIR / str(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    accepted: list[UploadedFile] = []

    # ── Save source documents ─────────────────────────────────────────────────
    if len(source_files) > settings.MAX_FILES_PER_BATCH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many source files. Max {settings.MAX_FILES_PER_BATCH} allowed.",
        )

    for upload in source_files:
        _validate_extension(upload.filename)
        dest       = session_dir / "sources" / upload.filename
        size_bytes = await _save_file(upload, dest)
        accepted.append(
            UploadedFile(
                filename   = upload.filename,
                role       = FileRole.SOURCE,
                size_bytes = size_bytes,
                saved_path = str(dest.relative_to(settings.UPLOAD_DIR)),
            )
        )
        log.info("Saved source: %s (%d bytes)", upload.filename, size_bytes)

    # ── Save Plan template ────────────────────────────────────────────────────
    _validate_extension(plan_template.filename)
    plan_dest  = session_dir / "templates" / "plan_template.docx"
    plan_bytes = await _save_file(plan_template, plan_dest)
    accepted.append(
        UploadedFile(
            filename   = plan_template.filename,
            role       = FileRole.PLAN,
            size_bytes = plan_bytes,
            saved_path = str(plan_dest.relative_to(settings.UPLOAD_DIR)),
        )
    )
    log.info("Saved plan template: %s", plan_template.filename)

    # ── Save Incubation template ──────────────────────────────────────────────
    _validate_extension(incubation_template.filename)
    inc_dest  = session_dir / "templates" / "incubation_template.docx"
    inc_bytes = await _save_file(incubation_template, inc_dest)
    accepted.append(
        UploadedFile(
            filename   = incubation_template.filename,
            role       = FileRole.INCUBATION,
            size_bytes = inc_bytes,
            saved_path = str(inc_dest.relative_to(settings.UPLOAD_DIR)),
        )
    )
    log.info("Saved incubation template: %s", incubation_template.filename)

    return UploadResponse(
        session_id     = session_id,
        uploaded_files = accepted,
        message        = f"Uploaded {len(accepted)} files. Session: {session_id}",
    )
