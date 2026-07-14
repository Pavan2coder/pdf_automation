"""
models/schemas.py
─────────────────
All Pydantic request / response models shared across the API layer.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────────────

class FileRole(str, Enum):
    """Role of each uploaded file in the processing pipeline."""
    SOURCE   = "source"       # abstract, report, PPT, proposal …
    PLAN     = "plan"         # Plan PDF template
    INCUBATION = "incubation" # Incubation PDF template


class ProcessingStatus(str, Enum):
    PENDING    = "pending"
    UPLOADING  = "uploading"
    EXTRACTING = "extracting"
    AI_PROCESSING = "ai_processing"
    EDITING    = "editing"
    DONE       = "done"
    FAILED     = "failed"


# ──────────────────────────────────────────────────────────────────────────────
# File metadata
# ──────────────────────────────────────────────────────────────────────────────

class UploadedFile(BaseModel):
    id:          UUID   = Field(default_factory=uuid4)
    filename:    str
    role:        FileRole
    size_bytes:  int
    saved_path:  str                   # relative path under uploads/
    project_name: Optional[str] = None # linked project (auto-detected)


# ──────────────────────────────────────────────────────────────────────────────
# Project data – AI-extracted structured content
# ──────────────────────────────────────────────────────────────────────────────

class TeamMember(BaseModel):
    name:        str
    roll_number: Optional[str] = None
    phone:       Optional[str] = None
    email:       Optional[str] = None


class ProjectData(BaseModel):
    """
    Structured project information extracted by the AI service.
    Every field is Optional so partial extraction never raises.
    """
    project_name:       Optional[str] = None
    project_title:      Optional[str] = None
    theme:              Optional[str] = None
    problem_statement:  Optional[str] = None
    idea_description:   Optional[str] = None
    objectives:         Optional[str] = None
    purpose:            Optional[str] = None
    motivation:         Optional[str] = None
    methodology:        Optional[str] = None
    technology_stack:   Optional[str] = None
    components:         Optional[str] = None
    working_principle:  Optional[str] = None
    architecture:       Optional[str] = None
    features:           Optional[str] = None
    uniqueness:         Optional[str] = None
    advantages:         Optional[str] = None
    applications:       Optional[str] = None
    customer_segment:   Optional[str] = None
    customer_survey:    Optional[str] = None
    market_analysis:    Optional[str] = None
    competitor_analysis:Optional[str] = None
    business_model:     Optional[str] = None
    revenue_streams:    Optional[str] = None
    cost_estimation:    Optional[str] = None
    prototype_details:  Optional[str] = None
    implementation_plan:Optional[str] = None
    roadmap:            Optional[str] = None
    future_scope:       Optional[str] = None
    expected_outcomes:  Optional[str] = None
    conclusion:         Optional[str] = None
    team_members:       list[TeamMember] = Field(default_factory=list)
    guide_name:         Optional[str] = None
    guide_designation:  Optional[str] = None
    guide_department:   Optional[str] = None
    institution:        Optional[str] = None
    references:         Optional[str] = None
    # catch-all for any extra fields the AI detects
    extra_fields:       dict[str, Any] = Field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# Session (one batch of uploads = one session)
# ──────────────────────────────────────────────────────────────────────────────

class Session(BaseModel):
    id:             UUID              = Field(default_factory=uuid4)
    status:         ProcessingStatus  = ProcessingStatus.PENDING
    uploaded_files: list[UploadedFile]= Field(default_factory=list)
    projects:       list[str]         = Field(default_factory=list)  # project names
    output_files:   list[str]         = Field(default_factory=list)  # generated PDF paths
    zip_path:       Optional[str]     = None
    error:          Optional[str]     = None
    progress:       int               = 0   # 0-100


# ──────────────────────────────────────────────────────────────────────────────
# API request / response shapes
# ──────────────────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    session_id:     UUID
    uploaded_files: list[UploadedFile]
    message:        str


class ProcessRequest(BaseModel):
    session_id: UUID
    ai_provider: Optional[str] = None    # override settings default


class ProcessResponse(BaseModel):
    session_id:   UUID
    status:       ProcessingStatus
    projects:     list[str]
    output_files: list[str]
    zip_path:     Optional[str] = None
    message:      str


class StatusResponse(BaseModel):
    session_id: UUID
    status:     ProcessingStatus
    progress:   int
    message:    str
    error:      Optional[str] = None


class ErrorResponse(BaseModel):
    detail:     str
    session_id: Optional[UUID] = None
