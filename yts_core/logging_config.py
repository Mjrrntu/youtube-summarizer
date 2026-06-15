from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_path: str = "logs/pipeline.log") -> logging.Logger:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("youtube_summarizer")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)

        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(console)

    return logger
