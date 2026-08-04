import logging
import os
from logging.handlers import RotatingFileHandler
import structlog

DEFAULT_LOG_FILE = "data/logs/celestium.log"


def setup_logging(level: str | None = None, log_file: str = DEFAULT_LOG_FILE) -> None:
    """
    Central structlog configuration for CelestiumQT.

    - Level from LOG_LEVEL env var (default INFO).
    - Structured JSON logs to a rotating file (5MB x 3 backups) AND console.
    - Call once at process entry (main.py, scripts, TUI).
    """
    level_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    log_level = getattr(logging, level_name, logging.INFO)

    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)

    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=[
            RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=3),
            logging.StreamHandler(),
        ],
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
