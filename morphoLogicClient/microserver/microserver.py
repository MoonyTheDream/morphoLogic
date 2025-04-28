"""A Microserver working as bridge between Kafka and Godot Client"""

import asyncio
import json
import logging
import os
import socket
import sys

from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from time import gmtime, strftime
from confluent_kafka import Producer, Consumer, KafkaException

# ************************************************************************************************ #
#                                      CONFIGURATION & LOGGING                                     #
# ************************************************************************************************ #
RUN_BY_GODOT = True
MICROSERVER_VERSION = "0.2.0"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Settings ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
SETTINGS_FILE = (
    os.path.join("morphoLogicClient", "settings.json")
    if not RUN_BY_GODOT
    else "settings.json"
)


def load_settings(path=SETTINGS_FILE):
    """
    Loads global settings from JSON file.
    Raises FileNotFoundError if file is missing.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f'Settings file "{path}" not found.')

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_SETTINGS = load_settings()
# Allow environment variable overrides for Kafka bootstrap server and general topic
BOOTSTRAP_SERVER = os.getenv(
    "KAFKA_BOOTSTRAP_SERVER", _SETTINGS.get("kafka_server", "localhost:9092")
)
GENERAL_TOPIC = os.getenv(
    "KAFKA_GENERAL_TOPIC", _SETTINGS.get("generalTopic", "serverGeneralTopic")
)
CLIENT_HANDSHAKE_TOPIC = os.getenv(
    "KAFKA_HANDSHAKE_TOPIC", _SETTINGS.get("handshakeTopic", "clientHandshakeTopic")
)
SERVER_HANDSHAKE_TOPIC = os.getenv(
    "KAFKA_HANDSHAKE_TOPIC",
    _SETTINGS.get("serverHandshakeTopic", "serverHandshakeTopic"),
)

# Get a log level from settings.json
# Change to true in settings.json for .debug visible
DEBUG_MODE = _SETTINGS.get("log_level_debug", False)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Logger Setup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
logger = logging.getLogger("mL microserver")


def get_gmt_time():
    """Wrapper to get strigified GMT time"""
    return strftime("%Y-%m-%d %H:%M:%S", gmtime())


def setup_logger():
    """
    Prepares a rotating file logger and console logger
    """
    log_file = (
        os.path.join("morphoLogicClient", "microserver", "microserver.log")
        if not RUN_BY_GODOT
        else "microserver/microserver.log"
    )
    log_handler = RotatingFileHandler(
        log_file,
        maxBytes=4 * 1024 * 1024,
        backupCount=3,  # 4MB per file, keep 3 backups
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


# 88888888888 .d8888b.  8888888b.                888
#     888    d88P  Y88b 888   Y88b               888
#     888    888    888 888    888               888
#     888    888        888   d88P       .d8888b 888  8888b.  .d8888b  .d8888b
#     888    888        8888888P"       d88P"    888     "88b 88K      88K
#     888    888    888 888             888      888 .d888888 "Y8888b. "Y8888b.
#     888    Y88b  d88P 888             Y88b.    888 888  888      X88      X88
#     888     "Y8888P"  888              "Y8888P 888 "Y888888  88888P'  88888P'
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
        self.tcp_server = None
        self.sock = None
        self.client_address = None
        self.reader = None
        self.writer = None
        self.writer_reader_ready = asyncio.Event()

    async def __aenter__(self):
        """
        Create and bind the server socket, wait for one client connection (Godot), and store the
        dynamic port to handle it to Godot.
        """
        self.tcp_server = await asyncio.start_server(
            self.set_reader_and_writer,
            host=self.HOST,
            port=self.port,
            limit=1024,
            family=socket.AF_INET,
            keep_alive=True,
        )
        while not self.tcp_server.is_serving():
            asyncio.sleep(0.1)
        logger.info("TCP server started.")

        # Handling the port to Godot
        self.sock = self.tcp_server.sockets[0]
        self.port = self.sock.getsockname()[1]
        logger.info("Kafka service listening on %s:%s", self.HOST, self.port)

        # Godot will listen until it will receive PORT_FOR_GODOT message through pipe.
        # Then i stops listening to stdio and switch to tcp with given port.
        sys.stdout.write("PORT_FOR_GODOT " + str(self.port) + "\n")
        sys.stdout.flush()  # Force immediate send
        logger.debug("Sent port %d to Godot via pipe", self.port)

        self._configure_socket(self.sock)
        logger.debug("TCP server socket configured correctly.")

        await self.wait_for_reader_and_writer()

        return self  # Return self so it can be used in the "with" block

    def set_reader_and_writer(
        self, stream_reader: asyncio.StreamReader, stream_writer: asyncio.StreamWriter
    ):
        """
        Waits for a reader and writer to be available, then returns them as self objects.
        Also it's changes internal status self.writer_reader_ready
        """
        logger.info("Client connected.")
        self.reader = stream_reader
        self.writer = stream_writer
        self.writer_reader_ready.set()

    async def wait_for_reader_and_writer(
        self,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """
        Async method that waits until reader and writer are available
        (so until a connection is established)
        """
        await self.writer_reader_ready.wait()
        return self.reader, self.writer

    def _configure_socket(self, sock):
        """
        Configures the socket with keep-alive options.
        Adjust if these options couse issues on some platforms
        """
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)  # Enable Keep-Alive
        sock.setsockopt(
            socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30
        )  # Wait 30 sec before checking
        # Send a keep-alive every 10 sec
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        # Send 3 keep-alive probes before dropping
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)

    async def __aexit__(self, exc_type, exc_value, traceback):
        """
        Cleanup the connection and the socket.
        """
        if self.tcp_server and self.tcp_server.is_serving():
            try:
                self.tcp_server.close()
                self.tcp_server.close_clients()
                await self.tcp_server.wait_closed()
            except Exception:
                logger.exception("Error closing TCP connection.")
        logger.info("TCP connection closed.")

    async def send_message(self, data: str) -> bool:
        """
        Send and UTF-8 string to the Godot client.
        Returns True if successful.
        """
        if not self.sock or self.writer.is_closing():
            logger.error("No active TCP connection to send data.")
            return False
        try:
            self.writer.write(data.encode("utf-8"))
            await self.writer.drain()
            logger.debug('Sent via TCP: "%s"', data)
            return True
        except Exception:
            logger.exception("Error sending data via TCP.")
            return False

    def _add_metadata(self, data: dict):
        """
        Used when a microserver needs to send data directly to client.
        Wraps metadata data to the dictionary.
        """
        data.update(
            {
                "metadata": {
                    "source": "microserver",
                    # "to_user": username,
                    "server_version": MICROSERVER_VERSION,
                    "timestamp": get_gmt_time(),
                }
            }
        )
        return data

    async def send_system_message_to_client(self, message: str):
        """
        Used when a microserver has a system message to client like 'Connected to Server'
        """
        message = {
            "payload": {
                "type": "system_message",
                "content": message,
            },
        }
        wrapped_data = self._add_metadata(message)
        wrapped_data = json.dumps(wrapped_data)
        await self.send_message(wrapped_data)

    async def receive_message(self) -> str:
        """Async method to eceive a message from Godot client via TCP. Returns the decoded string,
        or None if the connection is closed or an error occurs.

        Returns:
            str:    The decoded string received from the client, or None if no data
                    is received or an error occurs.
        """
        try:
            msg = await self.reader.readline()
            return msg.decode("utf-8").strip()
        except Exception:
            logger.exception("Error receiving data via TCP.")
            return None


# ------------------------------------------------------------------------------------------------ #


# 888    d8P            .d888 888                             888             888
# 888   d8P            d88P"  888                             888             888
# 888  d8P             888    888                             888             888
# 888d88K      8888b.  888888 888  888  8888b.        .d8888b 888888 888  888 888888
# 8888888b        "88b 888    888 .88P     "88b      d88P"    888    `Y8bd8P' 888
# 888  Y88b   .d888888 888    888888K  .d888888      888      888      X88K   888
# 888   Y88b  888  888 888    888 "88b 888  888      Y88b.    Y88b.  .d8""8b. Y88b.
# 888    Y88b "Y888888 888    888  888 "Y888888       "Y8888P  "Y888 888  888  "Y888
@asynccontextmanager
async def kafka_resources(data_json: dict, tcp_server: TCPServer = None):
    """
    A context manager that handles the creation of Kafka Admin Client, Producer,
    Consmer and a new topic for a specific client_id.

    Args:
        data_json(dict): An initial message from the client with it's username.
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
            "bootstrap.servers": BOOTSTRAP_SERVER,
            "group.id": username + "ClientGroup",  # group.id is the same as client_id
            "auto.offset.reset": "earliest",
            "enable.partition.eof": False,  # we'll be hitting end of partition quite often
        }
        consumer = Consumer(consumer_conf)
        await _establish_kafka_connection(consumer, tcp_server)
        consumer.subscribe([CLIENT_HANDSHAKE_TOPIC])

        producer_conf = {"bootstrap.servers": BOOTSTRAP_SERVER, "acks": "all"}
        producer = Producer(producer_conf)

        yield {
            "producer": producer,
            "consumer": consumer,
        }
    except Exception:
        logger.exception("Error setting up Kafka resources.")
        await tcp_server.send_system_message_to_client("SERVER_CONNECTION_FAILURE")
        raise

    finally:
        # Cleanup: close consumer, flush producer
        if consumer:
            consumer.close()
            logger.info("Closed Kafka consumer.")

        if producer:
            producer.flush(3)  # ensure all queued messages are delivered
            logger.info("Flushed Kafka producer.")


async def _establish_kafka_connection(
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
                await tcp_server.send_system_message_to_client(
                    "Kafka connection failed. Retrying."
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error("Kafka connection failed after %d retries.", max_retries)
                await tcp_server.send_system_message_to_client(
                    f"Kafka connection failed after {max_retries} retries."
                )
                raise RuntimeError(
                    "Kafka cluster is unreachable. Check if the broker is running."
                ) from e


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Task Group Terminator ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
class TerminateTaskGroup(Exception):
    """Exception raised to terminate a teask group."""


async def force_terminate_task_group():
    """Used to force termination of a task group."""
    raise TerminateTaskGroup()


# ------------------------------------------------------------------------------------------------ #


# 888b     d888        d8888 8888888 888b    888      888      .d88888b.   .d88888b.  8888888b.
# 8888b   d8888       d88888   888   8888b   888      888     d88P" "Y88b d88P" "Y88b 888   Y88b
# 88888b.d88888      d88P888   888   88888b  888      888     888     888 888     888 888    888
# 888Y88888P888     d88P 888   888   888Y88b 888      888     888     888 888     888 888   d88P
# 888 Y888P 888    d88P  888   888   888 Y88b888      888     888     888 888     888 8888888P"
# 888  Y8P  888   d88P   888   888   888  Y88888      888     888     888 888     888 888
# 888   "   888  d8888888888   888   888   Y8888      888     Y88b. .d88P Y88b. .d88P 888
# 888       888 d88P     888 8888888 888    Y888      88888888 "Y88888P"   "Y88888P"  888
async def main():
    """
    Main function: sets up logging, creates a TCP server and waits for a single client.
    Then reeads initial JSON data to determine the client_id and sets up Kafka
    connection creating a new topic for the client if needed.
    Then enters a main loop to shuttle messages between TCP and Kafka until "CLEANUP"
    or broken connections.
    """
    ### ~~~ Initial Setup ~~~ ###
    setup_logger()
    logger.info("Starting microserver.")
    produce_topic = GENERAL_TOPIC
    loop = asyncio.get_running_loop()
    loop.set_debug(DEBUG_MODE)

    if _SETTINGS.get("debugpy", False):
        import debugpy

        logger.info("Debugger listened at  5678 localhost")
        debugpy.listen(("localhost", 5678))
        debugpy.wait_for_client()
        print("Debugger attached")

    try:
        async with TCPServer() as tcp:
            logger.info("TCP server established on port %d.", tcp.port)

            # Expect the first message from client to be JSON with "username"
            client_info = await asyncio.wait_for(tcp.receive_message(), timeout=60)
            if not client_info:
                logger.error(
                    "No initial message received from TCP client. Shutting down."
                )
                return

            client_id = None
            try:
                data_json = json.loads(client_info)
                message_type = data_json["payload"]["type"]
                message_content = data_json["payload"]["content"]
                if message_type == "system_message":
                    if message_content == "REQUEST_SERVER_CONNECTION":
                        client_id = data_json["metadata"].get("username", None).strip()
            except json.JSONDecodeError:
                logger.exception(
                    "Invalid JSON received from TCP client. Shutting down."
                )
                return

            if not client_id:
                logger.error(
                    "No valid 'username' or 'system_message' field in initial JSON. Shutting down."
                )
                return

            # Enter Kafka context
            async with kafka_resources(data_json, tcp) as kafka_context:
                producer: Producer = kafka_context["producer"]
                consumer: Consumer = kafka_context["consumer"]

                logger.info(
                    "Kafka resources for client '%s' set up. Entering main loop.",
                    client_id,
                )
                if DEBUG_MODE:
                    await tcp.send_system_message_to_client("CONNECTED_TO_SERVER")

                # The message needs to be sent to Kafka as it's an handshake message to server
                produce_msg_to_kafka(
                    SERVER_HANDSHAKE_TOPIC, client_id, producer, data_json
                )
                producer.poll(0)

                try:
                    async with asyncio.TaskGroup() as tg:
                        # Kafka -> TCP -> Godot
                        tg.create_task(_kafka_to_tcp_handler(tcp, consumer))
                        # Godot -> TCP -> Kafka
                        tg.create_task(
                            _tcp_to_kafka_handler(
                                tcp, client_id, producer, consumer, produce_topic
                            )
                        )
                except* TerminateTaskGroup:
                    pass
    except Exception:
        logger.exception("Unexpected error. Shutting down.")
    finally:
        logger.info("Exiting microserver.")


async def _tcp_to_kafka_handler(
    tcp: TCPServer, client_id, producer, consumer, produce_topic
):
    """
    Async handler that reads tcp message asynchronously and then send it (not asyncronously)
    to the Kafka topic.
    """
    while True:
        tcp_msg = await tcp.receive_message()
        if tcp_msg:
            msg_list = tcp_msg.split("\n")

            # for msg in msg_list:
            # Handling Godot requests to Microserver
            for msg in msg_list:
                try:
                    msg: dict = json.loads(msg)
                except (json.JSONDecodeError, TypeError):
                    logger.exception("Error decoding JSON from TCP.")
                    continue

                logger.debug("Received TCP message: %s", msg)
                # system_message = msg.get("system_message", "")
                message_type = msg["payload"]["type"]
                message_content = msg["payload"]["content"]
                match message_type:

                    case "microserver_subscribe_to":
                        # subscribe_to = msg["microserver_subscribe_to"]
                        consumer.subscribe([message_content])
                        logger.debug('Subscribed to:"%s"', message_content)
                    # ---------------------------------------------------------------------------- #

                    case "produce_topic":
                        produce_topic = message_content
                        logger.debug(
                            'Changed topic to produce to, to: "%s"', produce_topic
                        )
                    # ---------------------------------------------------------------------------- #

                    case "system_message":

                        match message_content:

                            case "CLEANUP":
                                logger.info(
                                    "Received CLEANUP message from Godot. Exiting."
                                )
                                await force_terminate_task_group()

                            case _:
                                # Produce the message to the Kafka topic with username as a key
                                produce_msg_to_kafka(
                                    produce_topic, client_id, producer, msg
                                )
                                
                    case _:
                            # Produce the message to the Kafka topic with username as a key
                            produce_msg_to_kafka(
                                produce_topic, client_id, producer, msg
                            )

            producer.poll(0)


async def _kafka_to_tcp_handler(tcp: TCPServer, consumer):
    while True:
        try:
            # msg = consumer.consume(num_messages=1, timeout=0.1)
            msg = await asyncio.to_thread(
                lambda: consumer.consume(num_messages=1, timeout=1)
            )
            if msg:
                msg = msg[0] if isinstance(msg, list) else msg

        except Exception:
            logger.exception("Error consuming message from Kafka.")
            raise

        if msg and not msg.error():
            kafka_msg = msg.value().decode("utf-8")
            if kafka_msg:
                sent = await tcp.send_message(kafka_msg)
                if not sent:
                    logger.warning(
                        'Message from %s: "%s" not sent to Godot.',
                        msg.topic(),
                        kafka_msg,
                    )
                else:
                    logger.debug(
                        'Consumed message from %s: "%s"', msg.topic(), kafka_msg
                    )
        elif msg and msg.error():
            logger.debug("Error consuming message: %s", msg.error().str())


def produce_msg_to_kafka(
    produce_topic: str, client_id: str, producer: Producer, message: dict
):
    """
    Producing a given message to a given topic

    Args:
        produce_topic (str): a topic to where the message will be sent
        client_id (str): a username of a client
        producer (Producer): Producer object
        message (dict): a message to be sent to Kafka topic
    """
    try:
        message_to_send = json.dumps(message, ensure_ascii=False).encode("utf-8")

        producer.produce(
            produce_topic,
            key=client_id,
            value=message_to_send,
            on_delivery=_verify_delivery_kafka,
        )
        # Delivery reports if needed here
        logger.debug(
            "Produced TCP -> Kafka message to topic '%s': %s", produce_topic, message
        )
    except KafkaException:
        logger.exception("KafkaException while producing message.")


def _verify_delivery_kafka(err, _msg):
    """
    Trzeba tu zrobić handling niedostarczonej wiadomości i/lub kontroler ilości
    wysłanych w kliencie vs dostarczonych
    """
    if err:
        logger.debug("Error after producing message: %s", err)


# ------------------------------------------------------------------------------------------------ #

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Keyobard Interrupt. Exiting.")
    except asyncio.CancelledError:
        logger.warning("asyncio.CancelledError. Exiting.")
    finally:
        logger.info("Succesfully closed microserver.")
