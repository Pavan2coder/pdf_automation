"""
api/routes/process.py
─────────────────────
Orchestrates the full pipeline for a session:

  1. Discover uploaded files in session directory
  2. Extract raw text from each source document
  3. Send combined text to AI → structured ProjectData JSON
  4. Edit Plan + Incubation PDF templates (PyMuPDF)
  5. Write output PDFs + ZIP archive

POST /api/process           – trigger pipeline (async background task)
GET  /api/process/{id}/status – poll progress
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import (
    ProcessRequest,
    ProcessResponse,
    ProcessingStatus,
    StatusResponse,
)
from app.services.extraction_service import ExtractionService
from app.services.ai_service import AIService
from app.services.docx_editor import DocxEditor
from app.services.zip_service import ZipService

router = APIRouter(prefix="/process", tags=["Process"])
log    = get_logger(__name__)

# ── In-memory session state (replace with Redis for multi-worker deployments) ──
_sessions: dict[str, dict] = {}


# ──────────────────────────────────────────────────────────────────────────────
# Background pipeline
# ──────────────────────────────────────────────────────────────────────────────

async def _run_pipeline(session_id: str) -> None:
    """Full processing pipeline executed in background."""
    state = _sessions[session_id]
    sid   = session_id

    try:
        session_dir  = settings.UPLOAD_DIR  / sid
        sources_dir  = session_dir / "sources"
        template_dir = session_dir / "templates"
        output_dir   = settings.OUTPUT_DIR / sid
        output_dir.mkdir(parents=True, exist_ok=True)

        plan_template = template_dir / "plan_template.docx"
        inc_template  = template_dir / "incubation_template.docx"

        # ── Step 1: Extract text from all source documents ────────────────────
        _update(sid, ProcessingStatus.EXTRACTING, 10, "Extracting text from documents…")
        extractor = ExtractionService()
        source_files = list(sources_dir.glob("*")) if sources_dir.exists() else []
        raw_texts: dict[str, str] = {}

        for fpath in source_files:
            try:
                text = extractor.extract(fpath)
                raw_texts[fpath.name] = text
                log.info("[%s] Extracted %d chars from %s", sid, len(text), fpath.name)
            except Exception as exc:
                log.warning("[%s] Extraction failed for %s: %s", sid, fpath.name, exc)

        if not raw_texts:
            raise ValueError("No text could be extracted from the uploaded source files.")

        # ── Step 2: Group files by project & call AI ──────────────────────────
        _update(sid, ProcessingStatus.AI_PROCESSING, 30, "AI extracting project information…")

        ai = AIService()
        projects_data = await ai.extract_projects(raw_texts)

        if not projects_data:
            raise ValueError("AI returned no project data.")

        state["projects"] = [p.project_name or f"Project_{i+1}"
                             for i, p in enumerate(projects_data)]
        log.info("[%s] Detected %d projects: %s", sid, len(projects_data), state["projects"])

        # ── Step 3: Edit Word templates for each project ───────────────────────
        _update(sid, ProcessingStatus.EDITING, 55, "Editing Word templates…")

        editor       = DocxEditor()
        output_files: list[str] = []
        n = len(projects_data)

        for idx, project in enumerate(projects_data):
            pname   = project.project_name or f"Project_{idx+1}"
            safe    = "".join(c if c.isalnum() or c in "-_" else "_" for c in pname)
            prog    = 55 + int(35 * (idx + 0.5) / n)

            _update(sid, ProcessingStatus.EDITING, prog, f"Editing Word Docs for {pname}…")

            # Plan Word Doc
            plan_out = output_dir / f"{safe}_Plan.docx"
            editor.edit_template(plan_template, plan_out, project, template_type="plan")
            output_files.append(str(plan_out))
            log.info("[%s] Generated %s", sid, plan_out.name)

            # Incubation Word Doc
            inc_out = output_dir / f"{safe}_Incubation.docx"
            editor.edit_template(inc_template, inc_out, project, template_type="incubation")
            output_files.append(str(inc_out))
            log.info("[%s] Generated %s", sid, inc_out.name)

        state["output_files"] = output_files

        # ── Step 4: Bundle into ZIP ────────────────────────────────────────────
        _update(sid, ProcessingStatus.EDITING, 92, "Creating ZIP archive…")
        zip_svc  = ZipService()
        zip_path = zip_svc.create_zip(output_files, output_dir / "Generated_DOCXs.zip")
        state["zip_path"] = str(zip_path)

        _update(sid, ProcessingStatus.DONE, 100, "All Word documents generated successfully.")

    except Exception as exc:
        log.exception("[%s] Pipeline failed: %s", session_id, exc)
        state["status"]  = ProcessingStatus.FAILED
        state["error"]   = str(exc)
        state["progress"]= 0


def _update(sid: str, status: ProcessingStatus, progress: int, msg: str) -> None:
    _sessions[sid]["status"]   = status
    _sessions[sid]["progress"] = progress
    _sessions[sid]["message"]  = msg
    log.info("[%s] %d%% – %s", sid, progress, msg)


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post("", response_model=ProcessResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_processing(
    body: ProcessRequest,
    bg: BackgroundTasks,
):
    """
    Trigger the full extraction → AI → PDF edit pipeline for a session.
    Returns immediately with 202; poll `/process/{session_id}/status` for progress.
    """
    sid = str(body.session_id)

    if not (settings.UPLOAD_DIR / sid).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{sid}' not found. Upload files first.",
        )

    _sessions[sid] = {
        "status":       ProcessingStatus.PENDING,
        "progress":     0,
        "message":      "Queued",
        "projects":     [],
        "output_files": [],
        "zip_path":     None,
        "error":        None,
    }

    bg.add_task(_run_pipeline, sid)

    return ProcessResponse(
        session_id   = body.session_id,
        status       = ProcessingStatus.PENDING,
        projects     = [],
        output_files = [],
        message      = "Processing started. Poll /process/{id}/status for updates.",
    )


@router.get("/{session_id}/status", response_model=StatusResponse)
async def get_status(session_id: UUID):
    """Poll processing progress for a session."""
    sid = str(session_id)
    if sid not in _sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{sid}' not found or not yet started.",
        )
    s = _sessions[sid]
    return StatusResponse(
        session_id = session_id,
        status     = s["status"],
        progress   = s["progress"],
        message    = s.get("message", ""),
        error      = s.get("error"),
    )


@router.get("/{session_id}/result", response_model=ProcessResponse)
async def get_result(session_id: UUID):
    """Retrieve final result once status == done."""
    sid = str(session_id)
    if sid not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    s = _sessions[sid]
    if s["status"] not in (ProcessingStatus.DONE, ProcessingStatus.FAILED):
        raise HTTPException(status_code=409, detail="Processing not yet complete.")
    return ProcessResponse(
        session_id   = session_id,
        status       = s["status"],
        projects     = s.get("projects", []),
        output_files = s.get("output_files", []),
        zip_path     = s.get("zip_path"),
        message      = s.get("message", ""),
    )
