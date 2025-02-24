"""A Microserver working as handler between Kafka and Godot Client"""
import json
import logging
import socket

from logging.handlers import RotatingFileHandler
from confluent_kafka import Producer, Consumer, KafkaException, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

DEBUG = False # Change to false in production
logger = logging.getLogger("mL microserver")

class KafkaHandler():
    """Kafka setup for morphoLogic Client"""
    BOOTSTRAP_SERVER = "localhost:9092" 
    PRODUCER_TOPIC = 'serverGlobalTopic'
    producer_config = {
        'bootstrap.servers': BOOTSTRAP_SERVER,

        # Fixed properties
        'acks': 'all'
    }
    consumer_config = {
        # User-specific properties that you must set
        'bootstrap.servers': BOOTSTRAP_SERVER,

        # Fixed properties
        'group.id':          '', # MUST BE updated
        'auto.offset.reset': 'earliest'
    }
    
    def __init__(self, client_info):
        client_data = json.loads(client_info)
        client_id = client_data.get("username", "")
        if client_id:
            # AdminClient
            self.admin = AdminClient({'bootstrap.servers': self.BOOTSTRAP_SERVER})
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
        else:
            self.initialized = False
        
    def _create_new_topic(self, topic_id):
        nt = NewTopic(topic_id)
        dict_future_topics = self.admin.create_topics([nt])
        try:
            dict_future_topics[topic_id].result() # Wait for confirmation
            logger.info('Topic %s created successfully.', topic_id)
        except Exception:
            logger.exception('Failed to create topic %s.', topic_id)
        
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
            # key is a name of topic, as Server then will send optional naswer to this topic.
            self.producer.produce (self.PRODUCER_TOPIC, key=self.topic, value=message)
            # producer.poll(0)
            logger.debug("Produced message to %s: %s", self.PRODUCER_TOPIC, message)
        except KafkaException:
            logger.exception("KafkaException while producing message")

    def cleanup(self):
        """Cleanup before closing Microserver"""
        self.consumer.close()
        self.producer.flush(3)
        dict_future_topics = self.admin.delete_topics([self.topic])
        try:
            dict_future_topics[self.topic].result() # Wait for confirmation
            logger.info('Topic %s deleted successfully.', self.topic)
        except Exception:
            logger.exception('Failed to delete topic %s.', self.topic)
        
class TCPMicroserver():
    """
    TCP connection for morphoLogic Client.
    It will hang on __init__ waiting for a connection from Godot.
    """
    HOST = "127.0.0.1"
    PORT = 6164
    conn = None
    client_data = None

    def __init__(self):
        """
        Start a TCP server that listens for connections from Godot
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((self.HOST, self.PORT))
        s.listen()
        logger.info("Kafka service listening on %s:%s", self.HOST, self.PORT)
        self.conn, addr = s.accept()
        logger.info("Connection from %s", addr)
        self.client_data = self.receive_message()
        self.conn.setblocking(False)
        self.conn.settimeout(0.1)
            
    def send_message(self, message):
        """Senf message to Godot via TCP"""
        try:
            coded = message.encode("utf-8")
            self.conn.sendall(coded)
        except OSError:
            return False
        except Exception:
            logger.exception("Error sending message via TCP.")

    def receive_message(self):
        """
        Reveive a message from Godot via TCP
        Godot will send "CLEANUP" before it closes itself to close the microserver too
        """
        try:
            data = self.conn.recv(1024)
            if not data:
                return 'CELANUP'
            message = data.decode("utf-8").strip()
            return message
        except OSError:
            return False

def cleanup(tcp, kafka = None):
    """Cleaning up before exit"""
    if kafka:
        kafka.cleanup()
    tcp.conn.close()
    logger.info("CLEAN UP AND EXIT")

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
                    logger.warning("Message %s has not been sent.", k_message) # Ogarnąć co jeśli nie udało się wysłać.
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