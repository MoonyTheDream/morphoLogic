import argparse
from morphologic_server.awakening import awake

def main():
    parser = argparse.ArgumentParser(
        prog="morphologic", description="morhphoLogic Game Server CLI"
        )
    parser.add_argument("--start", action="store_true", help="Start the game server")
    parser.add_argument("-l", "--log", action="store_true", help="Enable logging")
    
    args = parser.parse_args()
    
    if args.start:
        if args.log:
            print("Awakening of the World. The Scribes are here too.")
        else:
            print("Awakening of the World.")
        awake()
    
if __name__ == "__main__":
    main()