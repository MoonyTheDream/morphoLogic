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
# from confluent_kafka.admin import AdminClient, NewTopic

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
    "generalTopic", "serverGeneralTopic"))
CLIENT_HANDSHAKE_TOPIC = os.getenv("KAFKA_HANDSHAKE_TOPIC", _SETTINGS.get(
    "handshakeTopic", "clientHandshakeTopic"))
SERVER_HANDSHAKE_TOPIC = os.getenv("KAFKA_HANDSHAKE_TOPIC", _SETTINGS.get(
    "serverandshakeTopic", "serverHandshakeTopic"))


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

    # Showing .debug logs only when debug setting is true
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

        try:
            self.sock.bind((self.HOST, self.port))

            # Handling the port to Godot
            self.port = self.sock.getsockname()[1]

            # *********** NEED CHANGES *************
            # Głupia metoda, w przyszłości trzeba zrobić, żeby procesy między sobą to przekazały
            # Przy pomocy Standard Pipes
            with open(self.FILE_PORT_HANDLING, "w", encoding="utf-8") as f:
                f.write(str(self.port))
            # *********** NEED CHANGES *************

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
            self.cleanup()
            raise # re-raise so the context manager won't proceed to __exit__

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
        except Exception:
            logger.exception("Error sending data via TCP.")
            return False

    def _add_metadata(self, data: dict):
        """
        Used when a microserver needs to send data directly to client.
        Wraps metadata data to the dictionary.
        """
        data.update({
            "metadata": {
                    "source": "microserver",
                    # "to_user": username,
                    "server_version": MICROSERVER_VERSION,
                    "timestamp": get_gmt_time()
                    }
        })
        return data

    def send_direct_message_to_client(self, message: str, m_type: MessageType = MessageType.NORMAL):
        """
        Used when a microserver has a message that should be displayed directly in Godot (errors,
        connection confirmations etc.).

        ~~DEPRECATED!~~
        """
        if m_type.value != 1:
            message = self._colorize_message(message, m_type)
        message = {"direct_messages": [message]}
        wrapped_data = self._add_metadata(message)
        wrapped_data = json.dumps(wrapped_data)
        self.send_message(wrapped_data)

    def send_system_message_to_client(self, message: str):
        """
        Used when a microserver has a system message to client like 'Connected to Server'
        """
        message = {"system_message": message}
        wrapped_data = self._add_metadata(message)
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
        """Non-blocking by default. Receive a message from Godot client via TCP. Returns the decoded string,
        or empty string if the connection is closed or an error occurs.

        Args:
            bufsize (int, optional): Bufsize (in bytes). Defaults to 1024.
            nonblocking (bool, optional): Setting the socket to non-blocking. Defaults to True.

        Returns:
            str:    The decoded string received from the client, or an empty string if no data
                    is received or an error occurs.

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
            # The OSError occurs when there's no data received in the given period of time,
            # so in our case it's just fine, we can carry over
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


# def handle_kafka_handshake(consumer: Consumer, producer: Producer, tcp_server: TCPServer, username: str) -> str:
#     """
#     ~~DEPRECATED!~~
#     """
#     given_topic = None
#     attempt = 0
#     while attempt < 2:
#         if attempt > 0:
#             tcp_server.send_system_message_to_client(
#                 "SERVER_CONNECTION_RETRY", username)

#         try:
#             handshake_msg = consumer.consume(
#                 num_messages=1, timeout=5)  # timeout in s
#             if not handshake_msg:
#                 logger.warning(
#                     "No handshake message received from Kafka. Retrying.")
#                 attempt += 1
#                 continue
#             handshake_msg = handshake_msg[0]
#         # except Exception:
#         #     logger.exception("Error consuming handshake message from Kafka.")
#             if handshake_msg.error():
#                 logger.error("Error consuming message: %s",
#                              handshake_msg.error().str())
#                 attempt += 1
#                 continue

#             if handshake_msg:
#                 kafka_msg = handshake_msg.value().decode("utf-8")
#                 kafka_msg = json.loads(kafka_msg)
#                 if kafka_msg['metadata'].get("to_user", "") != username:
#                     continue

#                 if kafka_msg.get("system_message") == "TOPIC_CREATED_SEND_HANDSHAKE_THERE":
#                     given_topic = kafka_msg["client_topic_handoff"]
#                     _confirm_and_ack(given_topic, consumer,
#                                      producer, tcp_server, username)
#                     return given_topic

#             tcp_server.send_system_message_to_client(
#                 "SERVER_CONNECTION_FAILURE", username)
#             return None
#             # raise RuntimeError("Error consuming handshake message.")

#         except Exception:
#             tcp_server.send_system_message_to_client(
#                 "SERVER_CONNECTION_FAILURE", username)
#             logger.exception("Error consuming handshake message from Kafka.")
#             raise

#     return None


# def _confirm_and_ack(given_topic: str, consumer: Consumer, producer: Producer, tcp_server: TCPServer, username: str):
#     try:
#         # ZWALONE! DO POPRAWY!
#         value = json.dumps(
#             {
#                 "system_message": "HANDSHAKE_GLOBAL_TOPIC",
#                 "metadata": {
#                     "source": "client",
#                     "username": username
#                 }
#             }
#         )
#         producer.produce(given_topic, key=username, value=value)
#         consumer.subscribe([given_topic])
#         logger.info('Subscribed to Kafka topic "%s"', given_topic)

#         handshake_msg = consumer.consume(
#             num_messages=1, timeout=5)  # timeout in s
#         if not handshake_msg:
#             raise RuntimeError(
#                 "No handshake message received from Kafka after first handshake.")
#         handshake_msg = handshake_msg[0]
#         if handshake_msg.error():
#             logger.error("Error consuming message: %s",
#                          handshake_msg.error().str())

#         if handshake_msg:
#             kafka_msg = handshake_msg.value().decode("utf-8")
#             kafka_msg = json.loads(kafka_msg)

#             if kafka_msg.get("system_message") == "ACK":
#                 tcp_server.send_system_message_to_client(
#                     "SERVER_CONNECTION_SUCCESS", username)
#                 return

#             tcp_server.send_system_message_to_client(
#                 "SERVER_CONNECTION_FAILURE", username)
#             return None
#             # raise RuntimeError("Error consuming handshake message.")

#     except Exception:
#         tcp_server.send_system_message_to_client(
#             "SERVER_CONNECTION_FAILURE", username)
#         logger.exception("Error consuming handshake message from Kafka.")
#         raise


@contextmanager
def kafka_resources(data_json: dict, tcp_server: TCPServer = None):
    """
    A context manager that handles the creation of Kafka Admin Client, Producer,
    Consmer and a new topic for a specific client_id.

    Args:
        data_json (dict): An initial message from the client with it's username.
        tcp_server (TCPServer, optional): the TCPServer object. Defaults to None.

    Yields:
        Dictionary: Giving away producer, consumer and username, as follows:
            "producer": producer,
            "consumer": consumer,
            "username": username,
    """
    # admin = None
    producer = None
    consumer = None
    # a topic name based on the username
    username = data_json["metadata"]["username"].strip()

    try:
        consumer_conf = {
            'bootstrap.servers': BOOTSTRAP_SERVER,
            'group.id': username + "ClientGroup",  # group.id is the same as client_id
            'auto.offset.reset': 'earliest',
            "enable.partition.eof": False  # we'll be hitting end of partition quite often
        }
        consumer = Consumer(consumer_conf)
        _establish_kafka_connection(consumer, tcp_server)
        consumer.subscribe([CLIENT_HANDSHAKE_TOPIC])

        producer_conf = {
            'bootstrap.servers': BOOTSTRAP_SERVER,
            'acks': 'all'
        }
        producer = Producer(producer_conf)

        # # Handshake and request server for a topic name.
        # data_json = json.dumps(data_json)
        # try:
        #     producer.produce(
        #         HANDSHAKE_TOPIC, value=data_json)
        #     # Delivery reports if needed here
        #     logger.debug(
        #         "Produced TCP -> Kafka message to topic '%s': %s", HANDSHAKE_TOPIC, data_json)
        # except KafkaException:
        #     logger.exception(
        #         "KafkaException while producing message.")

        # # Reading topic from Kafka handshake message and subscribing to it
        # given_topic = handle_kafka_handshake(consumer, producer, tcp_server, username)
        # logger.debug("Given topic: %s", given_topic)
        # if not given_topic:
        #     raise RuntimeError("Error consuming handshake message.")

        # consumer.subscribe([given_topic])
        # logger.info('Subscribed to Kafka topic "%s"', given_topic)

        yield {
            # "admin": admin,
            "producer": producer,
            "consumer": consumer,
            # "username": username,
            # "topic": given_topic
        }
    # except RuntimeError:
    #     logger.exception("Error setting up Kafka resources.")
    #     tcp_server.send_system_message_to_client("SERVER_CONNECTION_FAILURE", username)
    #     raise
    except Exception:
        logger.exception("Error setting up Kafka resources.")
        tcp_server.send_system_message_to_client("SERVER_CONNECTION_FAILURE")
        raise

    finally:
        # Cleanup: close consumer, flush producer, optionally delete topic
        if consumer:
            consumer.close()
            logger.info('Closed Kafka consumer.')

        if producer:
            producer.flush(3)  # ensure all queued messages are delivered
            logger.info("Flushed Kafka producer.")

        tcp_server.send_system_message_to_client("SERVER_CONNECTION_CLOSED")


def _establish_kafka_connection(
    consumer: Consumer, tcp_server: TCPServer, max_retries=3, wait_time=1
):
    """
    Verifies the connection to Kafka by requesting cluster metadata.
    Retries a few times before giving up.
    """
    for attempt in range(max_retries):
        try:
            cluster_metadata = consumer.list_topics(timeout=5)
            if cluster_metadata.brokers:
                logger.debug("Kafka connection verified.")
                return
        except KafkaException as e:
            if attempt < max_retries - 1:
                logger.warning("Kafka connection failed. Retrying.")
                tcp_server.send_direct_message_to_client(
                    "Kafka connection failed. Retrying.", MessageType.WARNING
                )
                sleep(wait_time)
            else:
                logger.error(
                    "Kafka connection failed after %d retries.", max_retries)
                tcp_server.send_direct_message_to_client(
                    f"Kafka connection failed after {max_retries} retries.", MessageType.ERROR
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
    produce_topic = GENERAL_TOPIC

    try:
        with TCPServer() as tcp:
            logger.info("TCP server established on port %d.", tcp.port)

            # Expect the first message from vlient to be JSON with "username"
            client_info = tcp.receive_message(nonblocking=False)
            if not client_info:
                logger.error(
                    "No initial message received from TCP client. Shutting down.")
                return

            client_id = None
            try:
                data_json = json.loads(client_info)
                if data_json["system_message"] == "REQUEST_SERVER_CONNECTION":
                    client_id = data_json["metadata"].get(
                        "username", None).strip()
            except json.JSONDecodeError:
                logger.exception(
                    "Invalid JSON received from TCP client. Shutting down.")
                return

            if not client_id:
                logger.error(
                    "No valid 'username' or 'system_message' field in initial JSON. Shutting down.")
                return

            # Enter Kafka context
            with kafka_resources(data_json, tcp) as kafka_context:
                producer: Producer = kafka_context["producer"]
                consumer: Consumer = kafka_context["consumer"]
                # topic = kafka_context["topic"]
                # username = kafka_context["username"]

                logger.info(
                    "Kafka resources for client '%s' set up. Entering main loop.", client_id
                )
                if DEBUG_MODE:
                    tcp.send_system_message_to_client("CONNECTED_TO_SERVER")
                    
                # The message needs to be sent to Kafka as it's an handshake message to server
                produce_msg_to_kafka(SERVER_HANDSHAKE_TOPIC, client_id, producer, client_info)
                producer.poll(0)


                # Main bridging loop
                while True:

                    # Kafka -> TCP -> Godot
                    try:
                        msg = consumer.consume(num_messages=1, timeout=0.1)
                        if msg:
                            msg = msg[0]

                    except Exception:
                        logger.exception("Error consuming message from Kafka.")
                    if msg and not msg.error():
                        kafka_msg = msg.value().decode("utf-8")
                        if kafka_msg:
                            sent = tcp.send_message(kafka_msg)
                            if not sent:
                                logger.warning(
                                    'Message from %s: "%s" not sent to Godot.', msg.topic(), kafka_msg)
                            else:
                                logger.debug(
                                    'Consumed message from %s: "%s"', msg.topic(), kafka_msg)
                    elif msg and msg.error():
                        logger.debug("Error consuming message: %s",
                                     msg.error().reason())

                    # Godot -> TCP -> Kafka
                    tcp_msg = tcp.receive_message()
                    if tcp_msg:

                        # Handling Godot requests to Microserver
                        system_message = json.loads(
                            tcp_msg).get("system_message", "")
                        match system_message:
                            case "CLEANUP":
                                logger.info(
                                    "Received CLEANUP message from Godot. Exiting.")
                                break
                            # case "REQUEST_SERVER_CONNECTION":

                            case "MICROSERVER_SUBSCRIBE":
                                subscribe_to = tcp_msg['microserver_subscribe_to']
                                consumer.subscribe([subscribe_to])
                                logger.debug(
                                    'Subscribed to:"%s"', subscribe_to)
                                continue
                            case "MICROSERVER_PRODUCE_TO":
                                produce_topic = tcp_msg['produce_topic']
                                logger.debug(
                                    'Changed topic to produce to, to: "%s"', produce_topic)
                                continue
                            case _:
                                pass

                        # Produce the message to the Kafka topic with username as a key
                        produce_msg_to_kafka(produce_topic, client_id, producer, tcp_msg)
                    producer.poll(0)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt detected. Shutting down gracefully.")
    except Exception:
        logger.exception("Unexpected error. Shutting down.")
    finally:
        logger.info("Exiting microserver.")

def produce_msg_to_kafka(produce_topic: str, client_id: str, producer: Producer, message: str):
    """
    Producing a given message to a given topic

    Args:
        produce_topic (str): a topic to where the message will be sent
        client_id (str): a username of a client
        producer (Producer): Producer object
        tcp_msg (str): a message to be sent to Kafka topic
    """
    try:
        producer.produce(produce_topic, key=client_id, value=message, on_delivery=_verify_delivery_kafka)
        # Delivery reports if needed here
        logger.debug("Produced TCP -> Kafka message to topic '%s': %s", produce_topic, message)
    except KafkaException:
        logger.exception("KafkaException while producing message.")


def _verify_delivery_kafka(err, _msg):
    """Trzeba tu zrobić handling niedostarczonej wiadomości i/lub kontroler ilości wysłanych w kliencie vs dostarczonych"""
    if err:
        logger.debug("Error after producing message: %s", err)
    # pass
    # logger.debug(str(err))
    # logger.debug(str(msg))


if __name__ == "__main__":
    main()
