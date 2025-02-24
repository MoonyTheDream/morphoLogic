"""A Microserver working as bridge between Kafka and Godot Client"""
import json
import logging
import os
import socket
import sys

from logging.handlers import RotatingFileHandler
from confluent_kafka import Producer, Consumer, KafkaException, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

SETTINGS_FILE = "settings.json"

def load_settings():
    """Load global settings from JSON file"""
    if not os.path.exists(SETTINGS_FILE):
        raise FileNotFoundError(f"Settings file {SETTINGS_FILE} not found.")
    
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)

_SETTINGS = load_settings()

DEBUG = _SETTINGS.get("log_level_debug", False) #Change to false in settings.json for .debug visible
logger = logging.getLogger("mL microserver")


class KafkaHandler():
    """Kafka setup for morphoLogic Client"""
    BOOTSTRAP_SERVER = _SETTINGS.get("kafka_server")
    PRODUCER_TOPIC = _SETTINGS.get('generalTopic')
    producer_config = {
        'bootstrap.servers': BOOTSTRAP_SERVER,

        # Fixed properties
        'acks': 'all'
    }
    consumer_config = {
        # User-specific properties that you must set
        'bootstrap.servers': BOOTSTRAP_SERVER,

        # Fixed properties
        'group.id':          '',  # MUST BE updated
        'auto.offset.reset': 'earliest'
    }

    def __init__(self, client_info):
        # user information wrapped to json by the Godot with answer for Username
        client_data = json.loads(client_info)
        client_id = client_data.get("username", "")
        
        if client_id:
            try:
                # AdminClient
                self.admin = AdminClient(
                    {'bootstrap.servers': self.BOOTSTRAP_SERVER})
                
                # Producer
                self.producer = Producer(self.producer_config)
                
                # Consumer
                self.consumer_config["group.id"] = client_id
                self.consumer = Consumer(self.consumer_config)
                
                # Create new topic for this client
                self.topic = self._create_new_topic(client_id)
                
                # Subscribe to the topic
                self.consumer.subscribe([self.topic])
                
                self.initialized = True
            except Exception:
                logger.exception("Failed to initialize Kafka connection.")
                cleanup()
        else:
            logger.warning("Failed to initialize Kafka connection.")
            cleanup()


    def _create_new_topic(self, topic_id):
        nt = NewTopic(topic_id)
        dict_future_topics = self.admin.create_topics([nt])
        try:
            dict_future_topics[topic_id].result()  # Wait for confirmation
            logger.info('Topic %s created successfully.', topic_id)
        except Exception:
            logger.exception('Failed to create topic %s.', topic_id)
            cleanup(kafka=self)
        return topic_id

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


class TCPMicroserver():
    """
    TCP connection for morphoLogic Client.
    It will hang on __init__ waiting for a connection from Godot.
    """
    HOST = "127.0.0.1"
    FILE_PORT_HANDLING = "temp_port.txt"
    port = 0
    conn = None
    client_data = None

    def __init__(self):
        """
        Start a TCP server that listens for connections from Godot
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # s.settimeout(60)  # Exit if no connection within 1 min
        
        # Enable TCP Keep-Alive
        s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)  # Enable Keep-Alive
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)  # Wait 30 sec before checking
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)  # Send a keep-alive every 10 sec
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)  # Send 3 keep-alive probes before dropping

        try:
            s.bind((self.HOST, self.port))

            # Handling the port to Godot
            self.port = s.getsockname()[1]
            with open(self.FILE_PORT_HANDLING, "w") as f:
                f.write(str(self.port))
                f.flush()

            s.listen()
            logger.info("Kafka service listening on %s:%s",
                        self.HOST, self.port)

            self.conn, addr = s.accept()  # Blocks until connection (but has a timeout)
            logger.info("Connection from %s", addr)
            
            self.conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            self.conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            self.conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)

            self.client_data = self.receive_message()
            self.conn.setblocking(False)
            self.conn.settimeout(0.1)
        # except socket.timeout:
        #     logger.warning(
        #         "No connection received within 60 seconds. Exiting.")
        #     sys.exit(1)  # Exit if no connection
        except Exception:
            logger.exception("Unexpected error setting up TCP connection.")
            cleanup()

    def send_message(self, message) -> bool:
        """Senf message to Godot via TCP"""
        try:
            coded = message.encode("utf-8")
            self.conn.sendall(coded)
            logger.info(
                'Message has been sent via TCP. The message: "%s"', message)
            return True
        except OSError:
            return True
        except Exception:
            logger.exception("Error sending message via TCP.")
            return False

    def receive_message(self):
        """
        Reveive a message from Godot via TCP
        Godot will send "CLEANUP" before it closes itself to close the microserver too
        """
        try:
            data = self.conn.recv(1024)
            if not data:
                cleanup(self)
            message = data.decode("utf-8").strip()
            return message
        except OSError:
            return False


def cleanup(tcp=None, kafka=None):
    """Cleaning up before exit"""
    if kafka:
        kafka.cleanup()
    if tcp:
        tcp.conn.close()
    logger.info("CLEAN UP AND EXIT")
    sys.exit()


def setup_logger():
    """Preparing logger for microserver"""
    log_file = "microserver/microserver.log"
    log_handler = RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=3  # 5MB per file, keep 3 backups
    )
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s][%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log_handler.setFormatter(formatter)
    logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)
    logger.addHandler(log_handler)


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
