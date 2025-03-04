"""A Microserver working as bridge between Kafka and Godot Client"""
import json
import logging
import os
import socket
import sys

from contextlib import contextmanager
from enum import Enum
from logging.handlers import RotatingFileHandler
from time import gmtime, strftime, sleep

from confluent_kafka import Producer, Consumer, KafkaException  # , KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

####################################################################################################
# Configuration & Logging
####################################################################################################

MICROSERVER_VERSION = "0.1.0"
SETTINGS_FILE = "settings.json"


def get_gmt_time():
    """Wrapper to get strigified GMT time"""
    return strftime("%Y-%m-%d %H:%M:%S", gmtime())


# Message type from microserver to clinet with enum
class MessageType(Enum):
    """
    Defines the possible types of messages from microserver to client
    """
    DEBUG = 0
    NORMAL = 1
    WARNING = 2
    ERROR = 3


def load_settings(path=SETTINGS_FILE):
    """
    Loads global settings from JSON file.
    Raises FileNotFoundError if file is missing.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Settings file {path} not found.")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_SETTINGS = load_settings()
# Allow environment variable overrides for Kafka bootstrap server and general topic
BOOTSTRAP_SERVER = os.getenv(
    "KAFKA_BOOTSTRAP_SERVER", _SETTINGS.get("kafka_server", "localhost:9092")
)
GENERAL_TOPIC = os.getenv("KAFKA_GENERAL_TOPIC", _SETTINGS.get(
    "generalTopic", "serverGlobalTopic"))
DELETE_TOPIC_AT_EXIT = os.getenv("DELETE_TOPIC_AT_EXIT", _SETTINGS.get(
    "deleteTopicAtExit", False))

# Get a log level from settings.json
# Change to false in settings.json for .debug visible
DEBUG_MODE = _SETTINGS.get("log_level_debug", False)
logger = logging.getLogger("mL microserver")


def setup_logger():
    """
    Prepares a rotating file logger and console logger
    """
    log_file = "microserver/microserver.log"
    log_handler = RotatingFileHandler(
        log_file, maxBytes=4*1024*1024, backupCount=3  # 4MB per file, keep 3 backups
    )
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s][%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log_handler.setFormatter(formatter)

    logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)
    logger.addHandler(log_handler)

    # OPTIONAL: Add a console handler for local debugging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


####################################################################################################
# TCP Server Context Manager
####################################################################################################

class TCPServer:
    """
    Context manager that binds a TCP server to a dynamic port, waits for a single clinet connection
    from Godot Client and exposes methods to send/receive data.
    """
    HOST = "127.0.0.1"
    FILE_PORT_HANDLING = "temp_port.txt"

    def __init__(self):
        """
        Initialize the socket. Actual binding and listening is done in __enter__ (that is upon
        entering the context with "with")
        """
        self.port = 0
        self.sock = None
        self.conn = None
        self.client_address = None

    def __enter__(self):
        """
        Create and bind the server socket, wait for one client connection (Godot), and store the
        dynamic port to handle it to Godot.
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._configure_socket(self.sock)
        # s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # s.settimeout(60)  # Exit if no connection within 1 min

        try:
            self.sock.bind((self.HOST, self.port))

            # Handling the port to Godot
            self.port = self.sock.getsockname()[1]
            with open(self.FILE_PORT_HANDLING, "w", encoding="utf-8") as f:
                f.write(str(self.port))
                # f.flush() # Not needed, file is closed after this block

            self.sock.listen()
            logger.info("Kafka service listening on %s:%s",
                        self.HOST, self.port)

            # Accept a single connection (from Godot)
            # Blocks until connection (but has a timeout)
            self.conn, self.client_address = self.sock.accept()
            logger.info("Client connected from %s", self.client_address)
            self._configure_socket(self.conn)
        except Exception:
            logger.exception("Failed to set up or accept TCP connection.")
            # self.cleanup()
            # raise # re-raise so the context manager won't proceed to __exit__

        return self  # Return self so it can be used in the "with" block

    def _configure_socket(self, sock):
        """
        Configures the socket with keep-alive options.
        Adjust if these options couse issues on some platforms
        """
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE,
                        1)  # Enable Keep-Alive
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE,
                        30)  # Wait 30 sec before checking
        # Send a keep-alive every 10 sec
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        # Send 3 keep-alive probes before dropping
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Cleanup the connection and the socket.
        """
        self.cleanup()

    def send_message(self, data: str) -> bool:
        """
        Send and UTF-8 string to the Godot client.
        Returns True if successful.
        """
        if not self.conn:
            logger.error("No active TCP connection to send data.")
            return False
        try:
            self.conn.sendall(data.encode("utf-8"))
            logger.info('Sent via TCP: "%s"', data)
            return True
        # except OSError:
        #     return True
        except Exception:
            logger.exception("Error sending data via TCP.")
            return False

    def add_auth(self, data: dict, username: str):
        """
        Used when a microserver needs to send data directly to client.
        Wraps auth data to the dictionary.
        """
        data.update({
            "auth": {
                    "source": "microserver",
                    "to_user": username,
                    "server_version": MICROSERVER_VERSION,
                    "timestamp": get_gmt_time()
                    }
        })
        return data

    def send_direct_message_to_client(self, message: str, username: str, m_type: MessageType = MessageType.NORMAL):
        """
        Used when a microserver has a message that should be displayed directly in Godot (errors,
        connection confirmations etc.).
        """
        if m_type.value != 1:
            message = self._colorize_message(message, m_type)
        message = {"direct_messages": [message]}
        wrapped_data = self.add_auth(message, username)
        wrapped_data = json.dumps(wrapped_data)
        self.send_message(wrapped_data)

    def send_system_message_to_client(self, message: str, username: str):
        """
        Used when a microserver has a system message to client like 'Connected to Server'
        """
        message = {"system_message": message}
        wrapped_data = self.add_auth(message, username)
        logger.debug(wrapped_data)
        wrapped_data = json.dumps(wrapped_data)
        self.send_message(wrapped_data)

    def _colorize_message(self, message: str, m_type: MessageType) -> str:
        color = "lime_green"  # fallback
        match m_type.value:
            case 0:
                color = "magenta"
            case 2:
                color = "gold"
            case 3:
                color = "tomato"
        return f"[color={color}]" + message + "[/color]"

    def receive_message(self, bufsize: int = 1024, nonblocking: bool = True) -> str:
        """
        Non-blicking. Receive a message from Godot client via TCP. Returns the decoded string,
        or empty string if the connection is closed or an error occurs.
        """
        if nonblocking:
            self.conn.setblocking(False)
        try:
            data = self.conn.recv(bufsize)
            if not data:
                # No data means client closed or error
                self.cleanup()
            return data.decode("utf-8").strip()
        except OSError:
            return ""
        except Exception:
            logger.exception("Error receiving data via TCP.")
            return ""
        finally:
            if nonblocking:
                self.conn.setblocking(True)

    def cleanup(self):
        """
        Close the client connection and the server socket
        """
        if self.conn:
            try:
                self.conn.shutdown(socket.SHUT_RDWR)
                self.conn.close()
                logger.info("TCP connection closed.")
            except Exception:
                logger.exception("Error closing TCP connection.")
        if self.sock:
            try:
                self.sock.close()
                logger.info("TCP server socket closed.")
            except Exception:
                logger.exception("Error closing TCP server socket.")

####################################################################################################
# Kafka Context Manager
####################################################################################################


@contextmanager
def kafka_resources(client_id: str, tcp_server: TCPServer = None):
    """
    A context manager that handles the creation of Kafka Admin Client, Producer,
    Consmer and a new topic for a specific client_id.
    """
    admin = None
    producer = None
    consumer = None
    topic = client_id  # a topic name based on the username

    try:
        admin_conf = {
            'bootstrap.servers': BOOTSTRAP_SERVER
        }
        admin = AdminClient(admin_conf)
        establish_kafka_connection(admin, tcp_server, client_id)

        producer_conf = {
            'bootstrap.servers': BOOTSTRAP_SERVER,
            'acks': 'all'
        }
        producer = Producer(producer_conf)

        consumer_conf = {
            'bootstrap.servers': BOOTSTRAP_SERVER,
            'group.id': client_id,  # group.id is the same as client_id
            'auto.offset.reset': 'earliest',
            "enable.partition.eof": False  # we'll be hitting end of partition quite often
        }
        consumer = Consumer(consumer_conf)

        # Creating a new topic. If it already exists we just log this info and continue.
        new_topic = NewTopic(topic)
        dict_future_topics = admin.create_topics([new_topic])
        try:
            dict_future_topics[topic].result()  # Wait for confirmation
            logger.info('Created Kafka topic "%s"', topic)
        except Exception as e:
            if "TOPIC_ALREADY_EXISTS" in str(e):
                logger.warning(
                    'Kafra topic "%s" already exists. Continuing.', topic)
            else:
                logger.exception('Failed to create topic %s.', topic)
                raise  # re-raise to exit the context manager

        consumer.subscribe([topic])
        logger.info('Subscribed to Kafka topic "%s"', topic)

        yield {
            "admin": admin,
            "producer": producer,
            "consumer": consumer,
            # "topic": topic
        }
    except Exception:
        logger.exception("Error setting up Kafka resources.")
        raise
    finally:
        # Cleanup: close consumer, flush producer, optionally delete topic
        if consumer:
            consumer.close()
            logger.info('Closed Kafka consumer for topic "%s"', topic)

        if producer:
            producer.flush(3)  # ensure all queued messages are delivered
            logger.info("Flushed Kafka producer.")

        # OPTIONAL cleanup: delete the topic
        if admin is not None and topic and DELETE_TOPIC_AT_EXIT:
            try:
                del_futures = admin.delete_topics([topic])
                del_futures[topic].result()
                logger.info("Deleted Kafka topic '%s'.", topic)
            except Exception:
                logger.exception("Failed to delete topic '%s'.", topic)


def establish_kafka_connection(
    admin: AdminClient, tcp_server: TCPServer, username, max_retries=3, wait_time=1
):
    """
    Verifies the connection to Kafka by requesting cluster metadata.
    Retries a few times before giving up.
    """
    for attemt in range(max_retries):
        try:
            cluster_metadata = admin.list_topics(timeout=5)
            if cluster_metadata.brokers:
                logger.debug("Kafka connection verified.")
                return
        except KafkaException as e:
            if attemt < max_retries - 1:
                logger.warning("Kafka connection failed. Retrying.")
                tcp_server.send_direct_message_to_client(
                    "Kafka connection failed. Retrying.", username, MessageType.WARNING
                )
                sleep(wait_time)
            else:
                logger.error(
                    "Kafka connection failed after %d retries.", max_retries)
                tcp_server.send_direct_message_to_client(
                    f"Kafka connection failed after {max_retries} retries.", username, MessageType.ERROR
                )
                raise RuntimeError(
                    "Kafka cluster is unreachable. Check if the broker is running.") from e


def main():
    """
    Main function: sets up logging, creates a TCP server and waits for a single client.
    Then reeads initial JSON data to determine the client_id and sets up Kafka 
    connection creating a new topic for the client if needed.
    Then enters a main loop to shuttle messages between TCP and Kafka until "CLEANUP"
    or broken connections.
    """
    setup_logger()
    logger.info("Starting microserver.")

    try:
        with TCPServer() as tcp:
            logger.info("TCP server established on port %d.", tcp.port)

            # Expect the first message from vlient to be JSON with "username"
            client_info = tcp.receive_message(nonblocking=False)
            if not client_info:
                logger.error(
                    "No initial message received from TCP client. Shutting down.")
                return

            try:
                data_json = json.loads(client_info)
                if data_json["client_input"] == "REQUEST_SERVER_CONNECTION":
                    client_id = data_json["auth"].get("username", "").strip()
                else:
                    client_id = ""
            except (json.JSONDecodeError, AttributeError):
                logger.exception(
                    "Invalid JSON received from TCP client. Shutting down.")
                return

            if not client_id:
                logger.error(
                    "No valid 'username' in initial JSON. Shutting down.")
                return

            # Enter Kafka context
            with kafka_resources(client_id, tcp) as kafka_context:
                producer: Producer = kafka_context["producer"]
                consumer: Consumer = kafka_context["consumer"]
                # topic = kafka_context["topic"]
                # logger.debug(str(kafka_resources))

                logger.info(
                    "Kafka resources for client '%s' set up. Entering main loop.", client_id
                )
                if DEBUG_MODE:
                    tcp.send_system_message_to_client(
                        "CONNECTED_TO_SERVER", client_id)

                # Main bridging loop
                while True:

                    # Kafka -> TCP -> Godot
                    try:
                        msg = consumer.consume(num_messages=1, timeout=0.1)[0]
                    except Exception:
                        logger.exception("Error consuming message from Kafka.")
                    if msg and not msg.error():
                        kafka_msg = msg.value().decode("utf-8")
                        if kafka_msg:
                            sent = tcp.send_message(kafka_msg)
                            if not sent:
                                logger.warning(
                                    "Message '%s' not sent to Godot.", kafka_msg)
                            else:
                                logger.debug(
                                    'Consumed message from Kafka: "%s"', kafka_msg)
                    elif msg and msg.error():
                        logger.debug("Error consuming message: %s",
                                     msg.error().reason())

                    # Godot -> TCP -> Kafka
                    tcp_msg = tcp.receive_message()
                    if tcp_msg:
                        if tcp_msg == "CLEANUP":
                            logger.info(
                                "Received CLEANUP message from Godot. Exiting.")
                            break
                        # Produce the message to the Kafka topic with username as a key
                        try:
                            producer.produce(
                                GENERAL_TOPIC, key=client_id, value=tcp_msg, on_delivery=_verify_delivery_kafka)
                            # Delivery reports if needed here
                            logger.debug(
                                "Produced TCP -> Kafka message to topic '%s': %s", GENERAL_TOPIC, tcp_msg)
                        except KafkaException:
                            logger.exception(
                                "KafkaException while producing message.")
                    producer.poll(0)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt detected. Shutting down gracefully.")
    except Exception:
        logger.exception("Unexpected error. Shutting down.")
    finally:
        logger.info("Exiting microserver.")


def _verify_delivery_kafka(err, _msg):
    """Trzeba tu zrobić handling niedostarczonej wiadomości i/lub kontroler ilości wysłanych w kliencie vs dostarczonych"""
    if err:
        logger.debug("Error after producing message: %s", err)
    # pass
    # logger.debug(str(err))
    # logger.debug(str(msg))


if __name__ == "__main__":
    main()
