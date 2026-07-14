"""
api/routes/download.py
──────────────────────
Serve generated Word documents and the ZIP archive for download.

GET /api/download/{session_id}/zip              – download full ZIP
GET /api/download/{session_id}/docx/{filename}  – download individual DOCX
GET /api/download/{session_id}/list             – list all output files
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logging import get_logger

router = APIRouter(prefix="/download", tags=["Download"])
log    = get_logger(__name__)


def _output_dir(session_id: str) -> Path:
    return settings.OUTPUT_DIR / session_id


@router.get("/{session_id}/zip")
async def download_zip(session_id: UUID):
    """Download the ZIP archive of all generated Word documents."""
    zip_path = _output_dir(str(session_id)) / "Generated_DOCXs.zip"
    if not zip_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ZIP not found. Processing may not be complete.",
        )
    log.info("Serving ZIP for session %s", session_id)
    return FileResponse(
        path         = str(zip_path),
        filename     = "Generated_DOCXs.zip",
        media_type   = "application/zip",
    )


@router.get("/{session_id}/docx/{filename}")
async def download_docx(session_id: UUID, filename: str):
    """Download a single generated Word document by filename."""
    # Safety: strip path traversal
    filename = Path(filename).name
    docx_path = _output_dir(str(session_id)) / filename
    if not docx_path.exists() or docx_path.suffix.lower() != ".docx":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DOCX '{filename}' not found.",
        )
    log.info("Serving DOCX %s for session %s", filename, session_id)
    return FileResponse(
        path       = str(docx_path),
        filename   = filename,
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/{session_id}/list")
async def list_outputs(session_id: UUID):
    """List all generated Word documents available for a session."""
    out_dir = _output_dir(str(session_id))
    if not out_dir.exists():
        raise HTTPException(status_code=404, detail="Session output not found.")
    docxs = [f.name for f in sorted(out_dir.glob("*.docx"))]
    return {
        "session_id": str(session_id),
        "files":      docxs,
        "count":      len(docxs),
        "zip_ready":  (out_dir / "Generated_DOCXs.zip").exists(),
    }

