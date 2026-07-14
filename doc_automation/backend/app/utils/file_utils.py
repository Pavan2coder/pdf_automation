"""
utils/file_utils.py
────────────────────
Shared file-handling utilities used across services.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from app.core.logging import get_logger

log = get_logger(__name__)


def safe_filename(name: str) -> str:
    """
    Convert an arbitrary string into a filesystem-safe filename.
    Replaces non-alphanumeric characters (except - _) with underscores.
    """
    safe = re.sub(r"[^\w\-]", "_", name.strip())
    safe = re.sub(r"_+", "_", safe)
    return safe.strip("_") or "project"


def ensure_dir(path: Path) -> Path:
    """Create directory and all parents; return the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_session(session_dir: Path) -> None:
    """Remove a session upload directory (called after TTL expires)."""
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)
        log.info("Cleaned up session dir: %s", session_dir)


def human_size(size_bytes: int) -> str:
    """Return a human-readable file size string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes //= 1024
    return f"{size_bytes:.1f} TB"
