"""A Microserver working as bridge between Kafka and Godot Client"""
import json
import logging
import os
import socket
import sys

from contextlib import contextmanager
from logging.handlers import RotatingFileHandler

from confluent_kafka import Producer, Consumer, KafkaException, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

####################################################################################################
# Configuration & Logging
####################################################################################################

SETTINGS_FILE = "settings.json"

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
GENERAL_TOPIC = os.getenv("KAFKA_GENERAL_TOPIC", _SETTINGS.get("generalTopic", "serverGlobalTopic"))

# Get a log level from settings.json
DEBUG_MODE = _SETTINGS.get("log_level_debug", False) #Change to false in settings.json for .debug visible
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

class TCPSserver:
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
            with open(self.FILE_PORT_HANDLING, "w",encoding="utf-8") as f:
                f.write(str(self.port))
                # f.flush() # Not needed, file is closed after this block

            self.sock.listen()
            logger.info("Kafka service listening on %s:%s", self.HOST, self.port)

            # Accept a single connection (from Godot)
            self.conn, self.client_address = self.sock.accept()  # Blocks until connection (but has a timeout)
            logger.info("Client connected from %s", self.client_address)
            self._configure_socket(self.conn)
        except Exception:
            logger.exception("Failed to set up or accept TCP connection.")
            # self.cleanup()
            # raise # re-raise so the context manager won't proceed to __exit__
        
        return self # Return self so it can be used in the "with" block

        #     self.client_data = self.receive_message()
        #     self.conn.setblocking(False)
        #     self.conn.settimeout(0.1)
        # # except socket.timeout:
        # #     logger.warning(
        # #         "No connection received within 60 seconds. Exiting.")
        # #     sys.exit(1)  # Exit if no connection
        # except Exception:
        #     logger.exception("Unexpected error setting up TCP connection.")
        #     cleanup()
            
    def _configure_socket(self, sock):
        """
        Configures the socket with keep-alive options.
        Adjust if these options couse issues on some platforms
        """
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)  # Enable Keep-Alive
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)  # Wait 30 sec before checking
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)  # Send a keep-alive every 10 sec
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)  # Send 3 keep-alive probes before dropping

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

    def receive_message(self, bufsize: int = 1024, nonblocking: bool = True) -> str:
        """
        Non-blicking. Receive a message from Godot client via TCP. Returns the decoded string,
        or empty string if the connection is closed or an error occurs.
        """
        if nonblocking:
            self.conn.setblocking(False)
        # self.conn.settimeout(0.1)
        # # except socket.timeout:
        # #     logger.warning(
        # #         "No connection received within 60 seconds. Exiting.")
        # #     sys.exit(1)  # Exit if no connection
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
def kafka_resources(client_id: str):
    """
    A context manager that handles the creation of Kafka Admin Client, Producer,
    Consmer and a new topic for a specific client_id.
    """
    admin = None
    producer = None
    consumer = None
    topic = client_id # a topic name based on the username
    
    try:
        admin_conf = {
            'bootstrap.servers': BOOTSTRAP_SERVER
        }
        admin = AdminClient(admin_conf)
        
        producer_conf = {
            'bootstrap.servers': BOOTSTRAP_SERVER,
            'acks': 'all'
        }
        producer = Producer(producer_conf)
        
        consumer_conf = {
            'bootstrap.servers': BOOTSTRAP_SERVER,
            'group.id': client_id, # group.id is the same as client_id
            'auto.offset.reset': 'earliest'
        }
        consumer = Consumer(consumer_conf)
        
        # Creating a new topic. If it already exists we just log this info and continue.
        new_topic = NewTopic(topic)
        dict_future_topics = admin.create_topics([new_topic])
        try:
            dict_future_topics[topic].result()  # Wait for confirmation
            logger.info('Created Kafka topic "%s"', topic)
        except Exception as e:
            if "TopicAlreadyExistsException" in str(e):
                logger.info('Kafra topic "%s" already exists. Continuing.', topic)
            else:
                logger.exception('Failed to create topic %s.', topic)
                raise # re-raise to exit the context manager
        
        consumer.subscribe([topic])
        logger.info('Subscribed to Kafka topic "%s"', topic)
        
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
            logger.info('Closed Kafka consumer for topic "%s"', topic)
        
        if producer:
            producer.flush(3) # ensure all queued messages are delivered
            logger.info("Flushed Kafka producer.")
        
        # # OPTIONAL cleanup: delete the topic
        # if admin and topic:
        #     try:
        #         del_futures = admin.delete_topics([topic])
        #         del_futures[topic].result()
        #         logger.info("Deleted Kafka topic '%s'.", topic)
        #     except Exception:
        #         logger.exception("Failed to delete topic '%s'.", topic)

    def consume_message(self):
        """
        Consume one message (non-blocking)
        """
        # Poll with a short timeout
        msg = self.consumer.poll(0.1)
        if msg is None:
            return ""

        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                # Reached end of partition
                return ""
            logger.error("Error while consuming: %s", msg.error())
            return ""
        else:
            # We have a valid message
            msg_val = msg.value().decode("utf-8")
            logger.debug("Consumed message from %s: %s", msg.topic(),  msg_val)
            return msg_val

    def produce_message(self, message):
        """
        Send a message to Kafka using the topic initialized at constructor
        """
        try:
            # Asynchronous produce; if needed, handle delivery reports with callbacks
            # key is a name of topic, as Server then will send optional answer to this topic.
            self.producer.produce(self.PRODUCER_TOPIC,
                                  key=self.topic, value=message)
            # producer.poll(0)
            logger.debug("Produced message to %s: %s",
                         self.PRODUCER_TOPIC, message)
        except KafkaException:
            logger.exception("KafkaException while producing message")

    def cleanup(self):
        """Cleanup before closing Microserver"""
        self.consumer.close()
        self.producer.flush(3)
        dict_future_topics = self.admin.delete_topics([self.topic])
        try:
            dict_future_topics[self.topic].result()  # Wait for confirmation
            logger.info('Topic %s deleted successfully.', self.topic)
        except Exception:
            logger.exception('Failed to delete topic %s.', self.topic)





def cleanup(tcp=None, kafka=None):
    """Cleaning up before exit"""
    if kafka:
        kafka.cleanup()
    if tcp:
        tcp.conn.close()
    logger.info("CLEAN UP AND EXIT")
    sys.exit()





def main():
    """Main loop"""
    setup_logger()
    # Prepare connection
    k = None

    try:
        tcp = TCPMicroserver()
        logger.info("TCP connection created")
        client_data = tcp.client_data
        if client_data is None:
            cleanup(tcp)
            return
        
        k = KafkaHandler(client_data)
        if not k.initialized:
            logger.error("Kafka was not properly initialized.")
            cleanup(tcp, k)
            return
        
        logger.info("KAFKA connection created. Moving to main loop.")

        # Main loop
        while True:
            # Kafka -> Godot
            k_message = k.consume_message()
            if k_message:
                sent = tcp.send_message(k_message)
                if not sent:
                    # Ogarnąć co jeśli nie udało się wysłać.
                    logger.warning("Message %s has not been sent.", k_message)
            # Kafka <- Godot
            tcp_message = tcp.receive_message()
            if tcp_message:
                if tcp_message == "CLEANUP":
                    break
                k.produce_message(tcp_message)
    except KeyboardInterrupt:
        logger.info("Shutting down service.")
        cleanup(tcp, k)
    except Exception:
        logger.exception("An error occured, closing down.")
        cleanup(tcp, k)
    cleanup(tcp, k)


if __name__ == "__main__":
    main()
