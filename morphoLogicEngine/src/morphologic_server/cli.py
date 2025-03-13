import argparse
import asyncio
import cmd
import debugpy
import sys

from .awakening import awake, stop_event as _stop_event, logger
from .utils.async_cmd import AsyncCmd


class MorphoLogicCmd(AsyncCmd):
    """Command-line interface for the morphoLogic server."""
    stop = None
    intro = """
Welcome. You are apparently one of the chosen ones as only few can enter this realm.
Say help or just raise your eyebrows - ? - to learn more.
"""
    prompt = "(morphoLogicServer) "
    
    def do_stop(self, _):
        """Stop the server."""
        print("Stars are fading... All the Heaven's batteries are turning off.")
        _stop_event.set()
        return True # Exits the cmd loop
    
    def do_debug(self, _):
        """Listen on debugpy."""
        debugpy.listen(('localhost', 5678))
        debugpy.wait_for_client()
        print("Debugger attached")
    
    def default(self, line):
        """Handle unknown commands."""
        print(f"Unknown command: {line}")
        
    def do_exit(self, arg):
        """Alias for stopping the server."""
        return self.do_stop(arg)
    
    # def custom_loop(self, intro=None):
    #     if _stop_event.is_set():
    #         self.stop = True
    #     super().cmdloop(intro)
    
    
    # def do_help(self, arg):
    #     """Show help information."""
    #     super().do_help(arg)

async def run_cmdloop():
    """Run the command loop asynchronously without blocking the server."""
    await asyncio.to_thread(MorphoLogicCmd().cmdloop)
    
# async def handle_commands_while_server_running():
#     """
#     Asynchronous command loop.
#     """
#     while not _stop_event.is_set():
#         cmd = await asyncio.to_thread(input, ">> ") # Non-blocking input
#         cmd = cmd.strip().lower()
        
#         match cmd:
#             case "stop":
#                 print("Stars are fading... All the Heaven's batteries are turning off.")
#                 _stop_event.set()
#             case "":
#                 continue
#             case _:
#                 print(f"Unknown command: {cmd}")
        

async def start_server(args):
    """
    Start the server asynchronously.
    """
    if args.log:
            print("Awakening of the World. The Scribes are here too.")
    else:
        print("Awakening of the World.")
    task_awake = asyncio.create_task(awake())
    task_cmd = asyncio.create_task(MorphoLogicCmd().cmdloop())
    try:
        await asyncio.gather(
            task_awake,
            task_cmd    
        )
    except KeyboardInterrupt: #, asyncio.CancelledError):
        logger.warning("Stars where switched off! Someone decided to just put them down.\n")
        task_awake.cancel()
        task_cmd.cancel()
    # finally:
    #     sys.exit(1)


def main():
    """
    Main function of CLI
    """
    parser = argparse.ArgumentParser(
        prog="morphologic", description="morhphoLogic Game Server CLI",
        usage="%(prog)s [options]"
        )
    subparsers = parser.add_subparsers()
    
    start = subparsers.add_parser("start", help='Start the server ("%(prog)s start -h" for options)')
    start.add_argument("-l", "--log", action="store_true", help="Enable logging")
    start.set_defaults(func=start_server)
    
    args = parser.parse_args()
    
    # If no arguments provided, display help
    if hasattr(args, 'func'):
        # try:
        asyncio.run(args.func(args))
        # except KeyboardInterrupt:
        #     print("Server shutdown requested by KeyboardInterrupt.\n")
    else:
        parser.print_help()
    
if __name__ == "__main__":
    main()