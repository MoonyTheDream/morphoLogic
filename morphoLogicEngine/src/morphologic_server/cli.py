import argparse
from morphologic_server.awakening import awake

def start_server(args):
    """
    Start the server
    """
    if args.log:
            print("Awakening of the World. The Scribes are here too.")
    else:
        print("Awakening of the World.")
    awake()

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
    if len(vars(args))>0:
        args.func(args)
    else:
        parser.print_help()
    
if __name__ == "__main__":
    main()