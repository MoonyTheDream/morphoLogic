"""Configured logger for the server"""

import logging
import sys

from logging.handlers import RotatingFileHandler
from pathlib import Path


# 888
# 888
# 888
# 888  .d88b.   .d88b.   .d88b.   .d88b.  888d888
# 888 d88""88b d88P"88b d88P"88b d8P  Y8b 888P"
# 888 888  888 888  888 888  888 88888888 888
# 888 Y88..88P Y88b 888 Y88b 888 Y8b.     888
# 888  "Y88P"   "Y88888  "Y88888  "Y8888  888
#                   888      888
#              Y8b d88P Y8b d88P
#               "Y88P"   "Y88P"

# ---------------------------------------------------------------------------
# Module-level logger and helper functions used by __init__.py and the rest
# of the codebase via:  from morphologic_server import logger, ...
# ---------------------------------------------------------------------------

formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s][%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("morphoLogic Server")

_log_dir = Path(__file__).resolve().parents[3] / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
_file_handler = RotatingFileHandler(
    _log_dir / "server_logs.log", maxBytes=4 * 1024 * 1024, backupCount=4
)
_file_handler.setFormatter(formatter)
logger.setLevel(logging.DEBUG)
logger.addHandler(_file_handler)

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(formatter)
logger.addHandler(_console_handler)


def check_if_logging_to_console() -> bool:
    """Return True if a stdout StreamHandler is attached to the module logger."""
    return any(
        isinstance(h, logging.StreamHandler)
        and getattr(h, "stream", None) is sys.stdout
        for h in logger.handlers
    )


def remove_console_handler() -> None:
    """Remove the stdout StreamHandler from the module logger."""
    for h in list(logger.handlers):
        if (
            isinstance(h, logging.StreamHandler)
            and getattr(h, "stream", None) is sys.stdout
        ):
            logger.removeHandler(h)
            break


def add_console_handler() -> None:
    """Add a stdout StreamHandler to the module logger."""
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(formatter)
    logger.addHandler(h)
