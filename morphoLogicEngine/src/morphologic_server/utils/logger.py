"""Configured logger for the server"""

import logging
import sys

from logging.handlers import RotatingFileHandler
from pathlib import Path
from morphologic_server import settings as _SETTINGS

formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s][%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


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
def setup_logger():
    """
    Prepares a rotating file logger and console logger
    """
    staged_logger = logging.getLogger("morphoLogic Server")

    debug_mode = _SETTINGS.get("log_level_debug", False)
    log_file = Path(__file__).resolve().parents[3] / "logs/server_logs.log"
    log_handler = RotatingFileHandler(
        log_file,
        maxBytes=4 * 1024 * 1024,
        backupCount=4,  # 4MB per file, keep 4 backups
    )
    log_handler.setFormatter(formatter)

    staged_logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    staged_logger.addHandler(log_handler)

    # OPTIONAL: Add a console handler for local debugging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    staged_logger.addHandler(console_handler)
    
    return staged_logger


logger = setup_logger()

def check_if_logging_to_console():
    """
    Checks if the logger is logging to the console.
    """
    if len(logger.handlers) > 1:
        return True
    return False
    
    
    
def remove_console_handler():
    """
    Removes the console handler from the logger
    """
    logger.removeHandler(logger.handlers[1])


def add_console_handler():
    """
    Adds the console handler to the logger
    """
    global logger
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    # return staged_logger