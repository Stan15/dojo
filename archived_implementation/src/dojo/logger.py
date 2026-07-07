from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from . import db

_loggers: dict[tuple[str, str], logging.Logger] = {}


def get_logger(db_path: str | Path | None = None, name: str = "dojo") -> logging.Logger:
    # Resolve the database path to determine log directory
    if db_path is None:
        resolved_db_path = db.DEFAULT_DB_PATH
    else:
        resolved_db_path = Path(db_path)

    log_dir = resolved_db_path.parent
    log_file = log_dir / "dojo.log"

    # We cache loggers by absolute log file path & logger name
    key = (str(log_file.resolve()), name)
    if key in _loggers:
        return _loggers[key]

    # Create directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)

    # Use a unique internal logger name to prevent standard logging collisions
    logger = logging.getLogger(f"{name}:{key[0]}")
    logger.setLevel(logging.DEBUG)

    # Avoid adding multiple handlers if the logger already has them
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
