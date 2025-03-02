"""The main module starting the server and all needed services."""
# import logging
# from morpho_server.network.tcp_server import start_tcp_server
# from morpho_server.network.websocket import start_websocket_server
# from morpho_server.db.db_manager import initialize_db

# def setup_logging():
#     logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s]: %(message)s")

def awake():
    print("Testujemy sobie czy to w ogóle działa.")
    # setup_logging()
    # initialize_db()
    
    # # Start TCP and WebSocket servers
    # start_tcp_server()
    # start_websocket_server()

if __name__ == "__main__":
    awake()
