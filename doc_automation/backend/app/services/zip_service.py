"""
services/zip_service.py
────────────────────────
Creates a ZIP archive of all generated PDFs for a session.

Public API
──────────
    svc = ZipService()
    zip_path = svc.create_zip(pdf_paths, output_zip_path)
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from app.core.logging import get_logger

log = get_logger(__name__)


class ZipService:
    """Stateless ZIP creation service."""

    def create_zip(
        self,
        file_paths: list[str],
        output_path: Path,
    ) -> Path:
        """
        Bundle *file_paths* into a ZIP archive at *output_path*.

        Parameters
        ----------
        file_paths : list[str]
            Absolute paths to files to include.
        output_path : Path
            Where to write the ZIP file.

        Returns
        -------
        Path
            The path of the created ZIP file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(str(output_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for fpath in file_paths:
                p = Path(fpath)
                if p.exists() and p.is_file():
                    # Store with just the filename (no directory nesting)
                    zf.write(str(p), arcname=p.name)
                    log.debug("Added to ZIP: %s", p.name)
                else:
                    log.warning("Skipping missing file: %s", fpath)

        size_kb = output_path.stat().st_size // 1024
        log.info(
            "ZIP created: %s (%d files, %d KB)",
            output_path.name, len(file_paths), size_kb,
        )
        return output_path
