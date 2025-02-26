import json
import logging
import os
import socket
import sys

from contextlib import contextmanager
from logging.handlers import RotatingFileHandler

from confluent_kafka import Producer, Consumer, KafkaException, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

###############################################################################
# Configuration & Logging
###############################################################################

SETTINGS_FILE = "settings.json"


def load_settings(path=SETTINGS_FILE):
    """
    Loads settings from a JSON file, raising FileNotFoundError if missing.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Settings file {path} not found.")
    
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_SETTINGS = load_settings()
# Allow environment variable overrides for Kafka if needed:
BOOTSTRAP_SERVER = os.environ.get("KAFKA_BOOTSTRAP_SERVER", _SETTINGS.get("kafka_server", "localhost:9092"))
GENERAL_TOPIC = os.environ.get("KAFKA_GENERAL_TOPIC", _SETTINGS.get("generalTopic", "serverGlobalTopic"))

# Determine log level from settings
DEBUG_MODE = _SETTINGS.get("log_level_debug", False)
logger = logging.getLogger("mL microserver")


def setup_logger():
    """
    Prepares a rotating file logger and (optionally) a console logger.
    """
    log_file = "microserver/microserver.log"
    log_handler = RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=3  # 5MB per file, up to 3 backups
    )
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s][%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log_handler.setFormatter(formatter)
    
    logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)
    logger.addHandler(log_handler)
    
    # Optional: Add a console handler for local debugging:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


###############################################################################
# TCP Server Context Manager
###############################################################################

class TCPServer:
    """
    Context manager that binds a TCP server to an dynamic port, waits
    for a single client connection, and exposes methods to send/receive data.
    """
    HOST = "127.0.0.1"
    FILE_PORT_HANDLING = "temp_port.txt"

    def __init__(self):
        """
        Initialize the socket; actual binding and acceptance
        happen upon entering the context.
        """
        self.sock = None
        self.conn = None
        self.client_address = None
        self.port = 0

    def __enter__(self):
        """
        Create and bind the server socket, wait for one client connection,
        and store the dynamic port for use by external processes.
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._configure_socket(self.sock)
        
        try:
            self.sock.bind((self.HOST, self.port))  # port=0 means ephemeral/dynamic
            self.port = self.sock.getsockname()[1]

            # Write the chosen port to a file so the client (Godot) can read it
            with open(self.FILE_PORT_HANDLING, "w", encoding="utf-8") as f:
                f.write(str(self.port))

            self.sock.listen()
            logger.info("TCP server listening on %s:%d", self.HOST, self.port)
            
            # Accept a single client connection
            self.conn, self.client_address = self.sock.accept()
            logger.info("Client connected from %s", self.client_address)
            self._configure_socket(self.conn)
        except Exception:
            logger.exception("Failed to set up or accept TCP connection.")
            self.cleanup()
            raise  # re-raise so the context manager won't proceed
        
        return self

    def _configure_socket(self, sock):
        """
        Configures the socket with keep-alive options. Adjust to your environment
        if these options cause issues on some platforms.
        """
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Clean up sockets on exit.
        """
        self.cleanup()

    def send_message(self, message: str) -> bool:
        """
        Send a UTF-8 string to the client. Returns True if successful.
        """
        if not self.conn:
            logger.warning("No active TCP connection to send data.")
            return False
        try:
            self.conn.sendall(message.encode("utf-8"))
            logger.info('Sent via TCP: "%s"', message)
            return True
        except Exception:
            logger.exception("Error sending data via TCP.")
            return False

    def receive_message(self, bufsize: int = 1024) -> str:
        """
        Blocking receive from the TCP client. Returns the decoded string,
        or empty string if the connection is closed or an error occurs.
        """
        if not self.conn:
            return ""
        try:
            data = self.conn.recv(bufsize)
            if not data:
                # No data means client closed or error
                # return ""
                self.cleanup()
            return data.decode("utf-8").strip()
        except Exception:
            logger.exception("Error receiving data via TCP.")
            return ""

    def cleanup(self):
        """
        Close the client connection and the server socket.
        """
        if self.conn:
            try:
                self.conn.close()
                logger.info("Closed client connection.")
            except Exception:
                logger.exception("Error closing client socket.")
        if self.sock:
            try:
                self.sock.close()
                logger.info("Closed server socket.")
            except Exception:
                logger.exception("Error closing server socket.")


###############################################################################
# Kafka Context Manager
###############################################################################

@contextmanager
def kafka_resources(client_id: str):
    """
    A context manager that handles the creation of Kafka AdminClient,
    Producer, Consumer, and a topic for a specific client_id.
    """
    admin = None
    producer = None
    consumer = None
    topic = client_id  # a topic name based on the username
    
    try:
        admin_conf = {
            "bootstrap.servers": BOOTSTRAP_SERVER
        }
        admin = AdminClient(admin_conf)

        producer_conf = {
            "bootstrap.servers": BOOTSTRAP_SERVER,
            "acks": "all"
        }
        producer = Producer(producer_conf)

        consumer_conf = {
            "bootstrap.servers": BOOTSTRAP_SERVER,
            "group.id": client_id,
            "auto.offset.reset": "earliest"
        }
        consumer = Consumer(consumer_conf)

        # Attempt to create a new topic. If it already exists, we handle that gracefully.
        new_topic = NewTopic(topic, num_partitions=1, replication_factor=1)
        futures = admin.create_topics([new_topic])
        try:
            futures[topic].result()
            logger.info("Created Kafka topic '%s'.", topic)
        except Exception as e:
            if "TopicAlreadyExistsException" in str(e):
                logger.info("Kafka topic '%s' already exists.", topic)
            else:
                logger.exception("Failed to create topic '%s'.", topic)
                raise

        consumer.subscribe([topic])
        logger.info("Kafka consumer subscribed to topic '%s'.", topic)

        yield {
            "admin": admin,
            "producer": producer,
            "consumer": consumer,
            "topic": topic
        }
    finally:
        # Cleanup: close consumer, flush producer, optionally delete topic
        if consumer:
            consumer.close()
            logger.info("Closed Kafka consumer for topic '%s'.", topic)

        if producer:
            producer.flush(3)  # ensure all queued messages are delivered
            logger.info("Flushed Kafka producer.")

        # if admin and topic:
        #     # If dynamic usage is truly desired, remove topic here:
        #     try:
        #         del_futures = admin.delete_topics([topic])
        #         del_futures[topic].result()
        #         logger.info("Deleted Kafka topic '%s'.", topic)
        #     except Exception:
        #         logger.exception("Failed to delete topic '%s'.", topic)


###############################################################################
# Main Microserver Loop
###############################################################################

def main():
    """
    Main function: sets up logging, starts the TCPServer and waits for a single
    client. Then reads initial JSON data to determine the Kafka client_id,
    creates dynamic Kafka resources, and enters a loop to shuttle messages
    between TCP and Kafka until "CLEANUP" or broken connections.
    """
    setup_logger()
    logger.info("Starting microserver...")

    try:
        with TCPServer() as tcp:
            logger.info("TCP server established on port %d.", tcp.port)

            # Expect the first message from client to be JSON with "username"
            client_info = tcp.receive_message()
            if not client_info:
                logger.error("No initial message received from TCP client. Shutting down.")
                return

            try:
                data_json = json.loads(client_info)
                client_id = data_json.get("username", "").strip()
            except (json.JSONDecodeError, AttributeError):
                logger.exception("Invalid JSON received from TCP client. Shutting down.")
                return

            if not client_id:
                logger.error("No valid 'username' in initial JSON. Shutting down.")
                return

            # Enter Kafka context
            with kafka_resources(client_id) as kafka_ctx:
                producer = kafka_ctx["producer"]
                consumer = kafka_ctx["consumer"]
                ephemeral_topic = kafka_ctx["topic"]

                logger.info("Kafka resources for client '%s' ready. Entering main loop.", client_id)

                # Main bridging loop
                while True:
                    # 1) Poll Kafka => TCP
                    msg = consumer.poll(timeout=0.1)
                    if msg and not msg.error():
                        kafka_msg = msg.value().decode("utf-8")
                        if kafka_msg:
                            sent_success = tcp.send_message(kafka_msg)
                            if not sent_success:
                                logger.warning("Failed to send message from Kafka to TCP.")

                    # 2) Poll TCP => Kafka
                    tcp_msg = tcp.receive_message()
                    if tcp_msg:
                        if tcp_msg == "CLEANUP":
                            logger.info("Received 'CLEANUP' from client. Shutting down loop.")
                            break
                        # Produce the message to the 'generalTopic', keyed by ephemeral_topic
                        try:
                            producer.produce(GENERAL_TOPIC, key=ephemeral_topic, value=tcp_msg)
                            # Process delivery reports
                            producer.poll(0)
                            logger.debug("Produced TCP->Kafka message to topic '%s': %s", GENERAL_TOPIC, tcp_msg)
                        except KafkaException:
                            logger.exception("KafkaException while producing message.")

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt detected. Shutting down gracefully.")
    except Exception:
        logger.exception("Unexpected error in microserver. Exiting.")
    finally:
        logger.info("Microserver has shut down.")


if __name__ == "__main__":
    main()
