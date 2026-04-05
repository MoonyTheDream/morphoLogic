"""Module responsible for the command line interface of the server."""

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Imports ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
import sys

import argparse
import asyncio
import debugpy

from ptpython.repl import embed

from morphologic_server import (
    TerminateTaskGroup,
    force_terminate_task_group
)
from morphologic_server.awakening import MorphoLogicHeart
from morphologic_server.config import ServerSettings
from morphologic_server.utils.async_cmd import AsyncCmd
from morphologic_server.utils.logger import (
    logger,
    remove_console_handler,
    add_console_handler,
    check_if_logging_to_console,
)

# ------------------------------------------------------------------------------------------------ #


async def run_python_shell(heart=None):
    """A coroutine to run the python shell."""
    from morphologic_server.db import models

    if heart is None:
        from morphologic_server.db.engine import create_sessionmaker
        from morphologic_server.db.memory import Memory
        from morphologic_server.config import ServerSettings

        settings = ServerSettings()
        sessionmaker = create_sessionmaker(settings.DB_ADDRESS)
        models.Base._sessionmaker = sessionmaker
        memory = Memory(sessionmaker)
    else:
        memory = heart.memory

    banner = "morphoLogic async shell Type `await ...` freely — Ctrl-D to exit."
    print(banner)

    context = {
        "asyncio": asyncio,
        "logger": logger,
        "heart": heart,
        "models": models,
        "memory": memory,
        "self": await memory.search("MoonyTheDream", models.Character),
    }
    await embed(globals=context, return_asyncio_coroutine=True, title=banner)


#  .d8888b.  888b     d888 8888888b.       888
# d88P  Y88b 8888b   d8888 888  "Y88b      888
# 888    888 88888b.d88888 888    888      888
# 888        888Y88888P888 888    888      888      .d88b.   .d88b.  88888b.
# 888        888 Y888P 888 888    888      888     d88""88b d88""88b 888 "88b
# 888    888 888  Y8P  888 888    888      888     888  888 888  888 888  888
# Y88b  d88P 888   "   888 888  .d88P      888     Y88..88P Y88..88P 888 d88P
#  "Y8888P"  888       888 8888888P"       88888888 "Y88P"   "Y88P"  88888P"
#                                                                    888
#                                                                    888
#                                                                    888
class MorphoLogicCmd(AsyncCmd):
    """
    Command-line interface for the morphoLogic server.
    It's using modified Cmd object from cmd package. Modifications makes the cmd_loop a coroutine
    function.
    """

    stop = None
    intro = """
Welcome. You are apparently one of the chosen ones as only few can enter this realm.
Say help or just raise your eyebrows — ? — to learn more.
"""
    prompt = "(morphoLogicServer) "

    def __init__(self, heart=None):
        super().__init__()
        self.heart = heart

    async def do_stop(self, _):
        """Stop the server."""
        print("Stars are fading — the Heaven's batteries are weakening.")
        await force_terminate_task_group()
        return True  # Exits the cmd loop

    def do_debug(self, _):
        """Listen on debugpy."""
        debugpy.listen(("localhost", 5678))
        debugpy.wait_for_client()   
        print("Debugger attached")

    async def do_shell(self, arg):
        """Drop into async-aware interactive shell."""

        log_to_console = check_if_logging_to_console()
        if log_to_console:
            print("Detaching logger while shell is active.")
            remove_console_handler()

        await run_python_shell(self.heart)

        # global logger
        if log_to_console:
            add_console_handler()
            print("Logging attached again.")

        if sys.stdin.closed:
            return True  # quit() in shell closed stdin — exit cmdloop

        self.do_help(arg)

    def do_detach(self, _):
        """Exiting Cmd Handler but letting server still run."""
        print(
            "Detaching from Cmd Handler. The Server will keep running.\nCtrl + C to stop the server."
        )
        return True

    def default(self, line):
        """Handle unknown commands."""
        print(f"Unknown command: {line}")

    async def do_exit(self, arg):
        """Alias for stopping the server."""
        return await self.do_stop(arg)


#          888                     888
#          888                     888
#          888                     888
# .d8888b  888888  8888b.  888d888 888888
# 88K      888        "88b 888P"   888
# "Y8888b. 888    .d888888 888     888
#      X88 Y88b.  888  888 888     Y88b.
#  88888P'  "Y888 "Y888888 888      "Y888
async def start_server(args):
    """
    Start the server asynchronously.
    """
    if args.log:
        print("Awakening of the World. The Scribes are here too.")
    else:
        print("Awakening of the World.")
        remove_console_handler()
    try:
        morpho_heart = MorphoLogicHeart(ServerSettings())
        async with asyncio.TaskGroup() as tg:
            # Both tasks run concurrently.
            tg.create_task(morpho_heart.awake(tg))
            tg.create_task(MorphoLogicCmd(heart=morpho_heart).cmdloop())
    except* TerminateTaskGroup:
        logger.info("Terminating tasks.")
    except* asyncio.exceptions.CancelledError:
        logger.warning("Keyboard Interrupt. Shutting down the server.")


#          888               888 888
#          888               888 888
#          888               888 888
# .d8888b  88888b.   .d88b.  888 888
# 88K      888 "88b d8P  Y8b 888 888
# "Y8888b. 888  888 88888888 888 888
#      X88 888  888 Y8b.     888 888
#  88888P' 888  888  "Y8888  888 888
async def just_shell(args):
    """
    Run just the python shell.
    """
    await run_python_shell()  # heart=None → creates its own Memory


async def run_seed(args):
    """Populate the database with test objects and areas."""
    from morphologic_server.scripts.seed import seed

    await seed()


# ------------------------------------------------------------------------------------------------ #


#  .d8888b.  888      8888888
# d88P  Y88b 888        888
# 888    888 888        888
# 888        888        888
# 888        888        888
# 888    888 888        888
# Y88b  d88P 888        888
#  "Y8888P"  88888888 8888888
def main():
    """
    Main function of CLI
    """
    parser = argparse.ArgumentParser(
        prog="morphologic",
        description="morhphoLogic Game Server CLI",
        usage="%(prog)s [options]",
    )
    subparsers = parser.add_subparsers()

    start = subparsers.add_parser(
        "start", help='Start the server ("%(prog)s start -h" for options)'
    )
    start.add_argument("-l", "--log", action="store_true", help="Enable logging")
    start.set_defaults(func=start_server)

    shell = subparsers.add_parser(
        "shell",
        help='Drop into async-aware interactive shell ("%(prog)s shell -h" for options)',
    )
    shell.set_defaults(func=just_shell)

    seed_cmd = subparsers.add_parser(
        "seed", help="Populate the database with test objects and areas"
    )
    seed_cmd.set_defaults(func=run_seed)

    args = parser.parse_args()

    # If no arguments provided, display help
    if hasattr(args, "func"):
        try:
            asyncio.run(args.func(args))
        except KeyboardInterrupt:
            pass
    else:
        parser.print_help()

    logger.info("Closed down the morphoLogic Server.")


if __name__ == "__main__":
    main()
