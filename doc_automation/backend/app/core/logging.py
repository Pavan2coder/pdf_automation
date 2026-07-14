"""
core/logging.py
───────────────
Configures a structured, coloured logger used across the application.
Import `get_logger` in any module to get a named logger.
"""

from __future__ import annotations

import logging
import sys

try:
    import colorlog  # type: ignore

    _HAVE_COLOR = True
except ImportError:
    _HAVE_COLOR = False

from app.core.config import settings

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE   = "%H:%M:%S"


def _configure_root() -> None:
    root = logging.getLogger()
    if root.handlers:          # already configured (e.g. uvicorn reload)
        return

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root.setLevel(level)

    if _HAVE_COLOR:
        handler: logging.Handler = colorlog.StreamHandler(sys.stdout)
        handler.setFormatter(
            colorlog.ColoredFormatter(
                "%(log_color)s" + _FORMAT,
                datefmt=_DATE,
                log_colors={
                    "DEBUG":    "cyan",
                    "INFO":     "green",
                    "WARNING":  "yellow",
                    "ERROR":    "red",
                    "CRITICAL": "bold_red",
                },
            )
        )
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE))

    root.addHandler(handler)


_configure_root()


def get_logger(name: str) -> logging.Logger:
    """Return a named child logger."""
    return logging.getLogger(name)
