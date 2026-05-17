"""
Centralized logging configuration for Ashen World.

Usage:
    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    
    logger.info("Day advanced to %d", day)
    logger.warning("Low population: %d villagers", count)
    logger.error("Failed to save: %s", exc)
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

import config

# Module-level flag to prevent duplicate setup
_initialized = False


def setup_logging() -> None:
    """
    Configure root logger with console and file handlers.
    Call once at app startup.
    """
    global _initialized
    if _initialized:
        return
    
    # Parse log level from config
    level_name = config.LOG_LEVEL.upper()
    level = getattr(logging, level_name, logging.INFO)
    
    # Create formatters
    console_fmt = logging.Formatter(
        "[%(levelname).1s] %(message)s"
    )
    file_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Reconfigure stdout to UTF-8 with replacement so emoji log messages
    # (🌻, ⚔, ☠, …) don't blow up the Windows cp1252 console with
    # UnicodeEncodeError tracebacks. The sim writes plenty of emoji.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Console handler (INFO+ only, brief format)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_fmt)
    
    # File handler (all levels, detailed format, rotating)
    file_handler = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(file_fmt)
    
    # Configure root logger
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console_handler)
    root.addHandler(file_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    _initialized = True
    logging.getLogger(__name__).debug("Logging initialized (level=%s)", level_name)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for the given module name.
    Ensures logging is initialized on first call.
    
    Args:
        name: Usually __name__ from the calling module
        
    Returns:
        Configured logger instance
    """
    setup_logging()
    return logging.getLogger(name)


# Convenience loggers for common categories
def get_simulation_logger() -> logging.Logger:
    """Logger for simulation events (day advance, births, deaths)."""
    return get_logger("ashen.simulation")



# Removed unused loggers: election, quest, event, db (use get_logger() directly if needed)
