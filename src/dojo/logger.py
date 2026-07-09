"""Rotating file logging into the dojo data directory (`dojo.log`). Loggers
are cached per (directory, name); nothing ever logs to stdout — the CLI owns
the terminal."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_DOJO_DIR = Path.home() / ".local" / "share" / "dojo"
_loggers: dict[tuple[str, str], logging.Logger] = {}


def get_logger(dojo_dir: str | Path | None = None, name: str = "dojo") -> logging.Logger:
    """Gets or creates a rotating file logger scoped to the Dojo directory."""
    if dojo_dir is None:
        resolved_dojo_dir = DEFAULT_DOJO_DIR
    else:
        path = Path(dojo_dir)
        # Handle db_path fallback: if path points to a file, use its parent
        if path.suffix:
            resolved_dojo_dir = path.parent
        else:
            resolved_dojo_dir = path

    log_file = resolved_dojo_dir / "dojo.log"
    key = (str(log_file.resolve()), name)
    if key in _loggers:
        return _loggers[key]

    resolved_dojo_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"{name}:{key[0]}")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _loggers[key] = logger
    return logger
