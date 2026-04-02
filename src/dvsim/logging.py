# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Logging config."""

import logging
import sys
from pathlib import Path
from typing import cast

__all__ = (
    "LOG_LEVELS",
    "configure_logging",
)


LOG_LEVELS = ["DEBUG", "VERBOSE", "INFO", "WARNING", "ERROR", "CRITICAL"]
DEFAULT_FORMAT = (
    "%(color)s[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d]%(end_color)s %(message)s"
)
_PLAIN_FORMAT = "[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s"
_DATE_FORMAT = "%y%m%d %H:%M:%S"

_VERBOSE_LOG_LEVEL = 15

# ANSI color codes keyed by level
_LEVEL_COLORS = {
    logging.DEBUG: "\033[36m",  # Cyan
    _VERBOSE_LOG_LEVEL: "\033[34m",  # Blue  (VERBOSE)
    logging.INFO: "\033[32m",  # Green
    logging.WARNING: "\033[33m",  # Yellow
    logging.ERROR: "\033[31m",  # Red
    logging.CRITICAL: "\033[31;1m",  # Bold red
}
_RESET = "\033[0m"


class _ColorFormatter(logging.Formatter):
    """Formatter that injects %(color)s / %(end_color)s into records."""

    def format(self, record: logging.LogRecord) -> str:
        record.color = _LEVEL_COLORS.get(record.levelno, "")
        record.end_color = _RESET if record.color else ""
        return super().format(record)


class DVSimLogger(logging.getLoggerClass()):
    """Logger class for DVSim."""

    # Log level for verbose logging between INFO (10) and DEBUG (20)
    CRITICAL = logging.CRITICAL
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    INFO = logging.INFO
    VERBOSE = _VERBOSE_LOG_LEVEL
    DEBUG = logging.DEBUG

    def __init__(self, name: str) -> None:
        """Initialise a logger."""
        super().__init__(name=name)

        logging.addLevelName(DVSimLogger.VERBOSE, "VERBOSE")

    def verbose(self, msg: object, *args: object) -> None:
        """Log a verbose msg."""
        self.log(self.VERBOSE, msg, *args)

    def set_logfile(
        self,
        path: Path,
        *,
        level: int | None = None,
        mode: str = "w",
    ) -> None:
        """Set a logfile to save the logs to."""
        fh = logging.FileHandler(filename=path, mode=mode)
        fh.setLevel(level if level is not None else self.DEBUG)
        fh.setFormatter(logging.Formatter(_PLAIN_FORMAT, datefmt=_DATE_FORMAT))
        self.addHandler(fh)

    def log_raw(self, contents: str) -> None:
        """Log raw string contents without any added log formatting."""
        for handler in self.handlers:
            handler.stream.write(contents)
            handler.flush()


def _build_logger() -> DVSimLogger:
    """Build a DVSim logger."""
    logging.setLoggerClass(DVSimLogger)

    logger = cast("DVSimLogger", logging.getLogger("dvsim"))

    # Attach a stderr handler with colour formatting (mirrors logzero default)
    if not logger.handlers:
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(_ColorFormatter(DEFAULT_FORMAT, datefmt=_DATE_FORMAT))
        logger.addHandler(sh)

    # Prevent log records bubbling up to the root logger
    logger.propagate = False

    # Log any unhandled exceptions
    _previous_excepthook = sys.excepthook

    def _handle_exception(exc_type, exc_value, exc_tb) -> None:
        logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        _previous_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = _handle_exception

    return logger


# Logger to import
log = _build_logger()


def configure_logging(*, verbose: bool, debug: bool, log_level: str | None, log_file: str) -> None:
    """Configure the Logger.

    Explicitly setting the log_level takes precedence. But if this is not set
    then the debug and verbose flags are checked in that order. The default
    logging level is INFO.
    """
    if log_level and log_level in LOG_LEVELS:
        new_log_level: int = getattr(log, log_level)
    elif debug:
        new_log_level = log.DEBUG
    elif verbose:
        new_log_level = log.VERBOSE
    else:
        new_log_level: int = log.INFO

    log.setLevel(new_log_level)

    # Push the same level down to the existing stream handler
    for handler in log.handlers:
        handler.setLevel(new_log_level)

    if log_file:
        log.set_logfile(
            path=Path(log_file),
            level=new_log_level,
        )
