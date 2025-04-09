"""
                                ⠀⣀⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣀⠀
                                ⢾⣿⣿⣿⣿⣶⣤⡀⠀⠀⠀⠀⠀⠀⠀⠀⠄⠀⣀⣴⣶⣿⣿⣿⣿⡇
                                ⠈⢿⣿⣿⣿⡛⠛⠈⠳⣄⠂⠀⠀⠀⠀⠀⣠⠞⠉⠛⢻⣿⣿⣿⡟⠀
                                ⠀⠸⣿⣿⣿⠥⠀⠀⠀⠈⢢⠀⠀⠀⠀⡜⠁⠀⠀⠀⢸⣿⣿⣿⠁⠀
                                ⠀⠀⣿⣿⣯⠭⠤⠀⠀⠀⠀⠃⣰⡄⠌⠀⠀⠀⠀⠨⢭⣿⣿⣿⠀⠀
                                ⠀⠀⠹⢿⣿⣈⣀⣀⠀⠀⠠⢴⣿⣿⡦⠀⠀⠀⣀⣈⣱⣿⠿⠃⠀⠀
                                ⠀⠀⠀⢠⣾⣿⡟⠁⠀⠀⠀⠀⣿⣏⠀⠀⠀⠀⠘⣻⣿⣶⠀⠀⠀⠀
                                ⠀⠀⠀⢸⣿⣿⢂⠀⠀⠀⠀⠘⢸⡇⠆⠀⠀⠀⢀⠰⣿⣿⠀⠀⠀⠀
                                ⠀⠀⠀⠈⣿⣷⣿⣆⡀⠀⠀⠁⠈⠀⠠⠀⠀⢀⣶⣿⣿⠏⠀⠀⠀⠀
                                ⠀⠀⠀⠀⠘⣿⣿⣿⣷⣴⡜⠀⠀⠀⠀⣦⣤⣾⣿⣿⡏⠀⠀⠀⠀⠀
                                ⠀⠀⠀⠀⢀⡿⠛⠿⠿⠛⠁⠀⠀⠀⠀⠘⠿⠿⠿⠿⢧⠀⠀⠀⠀⠀
                                ⠀⠀⠀⠀⣾⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣧⠀⠀⠀⠀
                                ⠀⠀⠀⠀⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠀⠀⠀⠀
"""
#                                         888               888                       d8b
#                                         888               888                       Y8P
#                                         888               888
# 88888b.d88b.   .d88b.  888d888 88888b.  88888b.   .d88b.  888      .d88b.   .d88b.  888  .d8888b
# 888 "888 "88b d88""88b 888P"   888 "88b 888 "88b d88""88b 888     d88""88b d88P"88b 888 d88P"
# 888  888  888 888  888 888     888  888 888  888 888  888 888     888  888 888  888 888 888
# 888  888  888 Y88..88P 888     888 d88P 888  888 Y88..88P 888     Y88..88P Y88b 888 888 Y88b.
# 888  888  888  "Y88P"  888     88888P"  888  888  "Y88P"  88888888 "Y88P"   "Y88888 888  "Y8888P
#                                888                                          "Y88P"
#                                888                                              888
#                                888                                         Y8b d88P

# ------------------------------------------------------------------------------------------------ #

from .utils.asyncio_helpers import TerminateTaskGroup, force_terminate_task_group
from .config import settings
from .utils.logger import logger, remove_console_handler, add_console_handler, check_if_logging_to_console

__all__ = [
    "logger",
    "settings",
    "TerminateTaskGroup",
    "force_terminate_task_group",
    "remove_console_handler",
    "add_console_handler",
    "check_if_logging_to_console"
]

# if __name__ == "__main__":
#     awake()
