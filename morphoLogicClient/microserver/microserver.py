"""A Microserver working as handler between Kafka and Godot Client"""
import socket
from confluent_kafka import Producer, Consumer, KafkaException, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

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
    
    def __init__(self, client_id):
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
        
    def _create_new_topic(self, topic_id):
        nt = NewTopic(topic_id)
        dict_future_topics = self.admin.create_topics([nt])
        try:
            dict_future_topics[topic_id].result() # Wait for confirmation
            print(f'[KAFKA] Topic {topic_id} created successfully.')
        except Exception as e:
            print(f'[KAFKA] Failed to create topic {topic_id}: {e}')
        
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
            else:
                print(f"[KAFKA] Error while consuming: {msg.error()}")
                return ""
        else:
            # We have a valid message
            msg_val = msg.value().decode("utf-8")
            print(f"[KAFKA] Consumed message from {msg.topic()}: {msg_val}")
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
            print(f"[KAFKA] Produced message to {self.PRODUCER_TOPIC}: {message}")
        except KafkaException as e:
            print(f"[KAFKA] KafkaException while producing: {e}")

    def cleanup(self):
        """Cleanup before closing Microserver"""
        self.consumer.close()
        self.producer.flush(3)
        self.admin.delete_topics([self.topic])
        
class TCPMicroserver():
    """
    TCP connection for morphoLogic Client.
    It will hang on __init__ waiting for a connection from Godot.
    """
    HOST = "127.0.0.1"
    PORT = 6164
    conn = None
    username = None

    def __init__(self):
        """
        Start a TCP server that listens for connections from Godot
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((self.HOST, self.PORT))
        s.listen()
        print(f"[TCP] Kafka service listening on {self.HOST}:{self.PORT}")
        self.conn, addr = s.accept()
        print(f"[TCP] Connection from {addr}")
        self.username = self.receive_message()
        self.conn.setblocking(False)
        self.conn.settimeout(0.1)
            
    def send_message(self, message):
        """Senf message to Godot via TCP"""
        try:
            coded = message.encode("utf-8")
            self.conn.sendall(coded)
        except OSError:
            return False
        except Exception as e:
            print(f"[TCP] Error sending message via TCP: {e}")

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
    print("[mL MICROSERVER] CLEAN UP AND EXIT")

def main():
    """Main loop"""
    k = None
    try:
        tcp = TCPMicroserver()
        print("[mL MICROSERVER] TCP connection created")
        username = tcp.username
        if username is None:
            cleanup(tcp)
        k = KafkaHandler(username)
        print("[mL MICROSERVER] KAFKA connection created. Moving to main loop.")
        while True:
            # Kafka -> Godot
            k_message = k.consume_message()
            if k_message:
                sent = tcp.send_message(k_message)
                if not sent:
                    print(f"Message {k_message} has not been sent.") # Ogarnąć co jeśli nie udało się wysłać.
            # Kafka <- Godot
            tcp_message = tcp.receive_message()
            if tcp_message:
                if tcp_message == "CLEANUP":
                    break
                k.produce_message(tcp_message)
    except KeyboardInterrupt:
        print("[mL MICROSERVER] Shutting down service.")
        cleanup(tcp, k)
    except Exception as e:
        print(f"[mL MICROSERVER] An error occured, closing down: {e}")
        cleanup(tcp, k)
    cleanup(tcp, k)
        
if __name__ == "__main__":
    main()