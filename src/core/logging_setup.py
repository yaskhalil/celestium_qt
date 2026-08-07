import logging
import os
import sys
from logging.handlers import RotatingFileHandler
import structlog

DEFAULT_LOG_FILE = "data/logs/celestium.log"


def setup_logging(level: str | None = None, log_file: str = DEFAULT_LOG_FILE) -> None:
    """
    Central structlog configuration for CelestiumQT.

    - Level from LOG_LEVEL env var (default INFO).
    - Rotating JSON file (5MB x 3 backups) for aggregation, colored
      human-readable console output for local debugging.
    - Call once at process entry (main.py, scripts, TUI).
    """
    level_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    log_level = getattr(logging, level_name, logging.INFO)

    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
            ],
            foreign_pre_chain=shared_processors,
        )
    )

    file_handler = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=3)
    file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            foreign_pre_chain=shared_processors,
        )
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [console_handler, file_handler]
